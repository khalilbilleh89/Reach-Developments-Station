"""Constrained configurable fields: definitions, options and values.

The MVP requires extension fields without a database redesign. This is that,
and deliberately no more than that.

A custom field **adds** a fact the product did not anticipate. It can never
**redefine** one it did: identity, hierarchy, the four status dimensions, the
release gates and anything monetary are core columns, and ``field_key`` is
checked against a reserved list so a field named ``commercial_status`` cannot
exist. Validation is bounds, length, pattern and option membership — there is no
expression language, because a configuration screen that can execute something
is a programming environment with no code review.

Values live in three tables, one per entity, each with a real foreign key. A
single polymorphic ``entity_type``/``entity_id`` table would have neither
referential integrity nor a way to stop one project's identifier being read
through another's path.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import ColumnElement, Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.access.models import SYSTEM_ROLES
from app.modules.audit.service import record_event
from app.modules.inventory.models import (
    CUSTOM_FIELD_TYPE_BOOLEAN,
    CUSTOM_FIELD_TYPE_DATE,
    CUSTOM_FIELD_TYPE_DECIMAL,
    CUSTOM_FIELD_TYPE_INTEGER,
    CUSTOM_FIELD_TYPE_OPTION,
    CUSTOM_FIELD_TYPE_TEXT,
    ENTITY_CUSTOM_FIELD,
    ENTITY_CUSTOM_VALUE,
    SCOPE_COUNTRY,
    SCOPE_GLOBAL,
    SCOPE_PROJECT,
    SCOPE_UNIT_TYPE,
    CustomFieldDefinition,
    CustomFieldOption,
    LandParcelCustomFieldValue,
    ProjectCustomFieldValue,
    Unit,
    UnitCustomFieldValue,
)
from app.modules.projects.models import LandParcel, Project

#: Names a custom field may never take, per entity. A custom
#: ``commercial_status`` or ``contract_price`` would look like core truth in
#: every export and report while obeying none of the rules that protect it.
_RESERVED_KEYS: dict[str, frozenset[str]] = {
    "project": frozenset(
        {
            "id",
            "code",
            "name",
            "status",
            "country_pack_id",
            "base_currency_id",
            "reporting_currency_id",
            "project_manager_user_id",
            "created_at",
            "updated_at",
        }
    ),
    "land_parcel": frozenset(
        {
            "id",
            "project_id",
            "plot_number",
            "land_area",
            "purchase_price",
            "acquisition_fees",
            "ownership_share_fraction",
            "is_active",
        }
    ),
    "unit": frozenset(
        {
            "id",
            "project_id",
            "floor_id",
            "phase_id",
            "building_id",
            "unit_number",
            "unit_reference",
            "asset_class",
            "unit_type_code",
            "commercial_status",
            "legal_status",
            "collection_status",
            "delivery_status",
            "drawings_approved",
            "legal_sale_eligible",
            "pricing_approved",
            "release_date",
            "release_batch",
            "block_reason",
            "is_active",
        }
    ),
}

#: Words that never belong to inventory at all. Blocked on every entity so a
#: field cannot pre-empt a domain a later PR will build properly.
_RESERVED_EVERYWHERE = frozenset(
    {
        "price",
        "unit_price",
        "contract_price",
        "list_price",
        "discount",
        "amount_paid",
        "balance",
        "installment",
        "receipt",
        "commission",
        "profit",
        "margin",
        "cost",
    }
)

#: Stands in for a sensitive field's name in a completeness list. It says
#: something is outstanding without saying what, which is the whole point of
#: marking a field sensitive in the first place.
_WITHHELD_LABEL = "A field restricted to other roles"

_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

#: The fixed role catalogue. A visibility rule naming a role that does not exist
#: silently hides the field from everyone.
_VALID_ROLE_KEYS = frozenset(key for key, _ in SYSTEM_ROLES)

_DEFINITION_FIELDS = (
    "id",
    "entity_type",
    "field_key",
    "display_label",
    "description",
    "data_type",
    "unit_of_measure",
    "help_text",
    "required",
    "required_for_release",
    "minimum_value",
    "maximum_value",
    "regex_pattern",
    "is_unique",
    "scope_type",
    "country_pack_id",
    "project_id",
    "unit_type_code",
    "visible_role_keys",
    "editable_role_keys",
    "sensitive",
    "approval_required",
    "filterable",
    "groupable",
    "dashboard_visible",
    "export_visible",
    "valid_from",
    "valid_to",
    "is_active",
    "version",
)

#: Which value table belongs to which entity. Three tables, three foreign keys.
_VALUE_MODELS = {
    "project": (ProjectCustomFieldValue, "project_id"),
    "land_parcel": (LandParcelCustomFieldValue, "parcel_id"),
    "unit": (UnitCustomFieldValue, "unit_id"),
}

#: The fields an update may change. Entity, key, data type and scope are absent:
#: changing any of them would reinterpret every value already recorded.
_DEFINITION_UPDATABLE = (
    "display_label",
    "description",
    "unit_of_measure",
    "help_text",
    "required",
    "required_for_release",
    "minimum_value",
    "maximum_value",
    "regex_pattern",
    "visible_role_keys",
    "editable_role_keys",
    "sensitive",
    "approval_required",
    "filterable",
    "groupable",
    "dashboard_visible",
    "export_visible",
    "valid_from",
    "valid_to",
    "is_active",
)


# --------------------------------------------------------------------------- #
# Definitions
# --------------------------------------------------------------------------- #


def _normalize_key(field_key: str, *, entity_type: str) -> str:
    key = field_key.strip().lower()
    if not _KEY_PATTERN.match(key):
        raise ValidationError(
            "A field key starts with a letter and contains only lowercase letters, "
            "digits and underscores."
        )
    if key in _RESERVED_KEYS.get(entity_type, frozenset()) or key in _RESERVED_EVERYWHERE:
        raise ValidationError(f"'{key}' is a core field name. A custom field cannot redefine one.")
    return key


def _validate_role_keys(keys: list[str] | None, *, label: str) -> list[str] | None:
    if keys is None:
        return None
    unknown = sorted(set(keys) - _VALID_ROLE_KEYS)
    if unknown:
        raise ValidationError(f"{label} names roles that do not exist: {', '.join(unknown)}.")
    return sorted(set(keys))


def _validate_scope_columns(
    *,
    scope_type: str,
    country_pack_id: object,
    project_id: object,
    unit_type_code: object,
) -> None:
    """A scope has to name what it is scoped to, and nothing else.

    The database enforces this too. It is checked here so the answer is a 422
    naming the missing column rather than a 500 from a CHECK constraint, and so
    a definition that could never apply to anything is refused at the door
    instead of sitting in the table looking configured.
    """
    required, forbidden = {
        SCOPE_GLOBAL: ((), ("country_pack_id", "project_id", "unit_type_code")),
        SCOPE_COUNTRY: (("country_pack_id",), ("project_id", "unit_type_code")),
        SCOPE_PROJECT: (("project_id",), ("country_pack_id", "unit_type_code")),
        SCOPE_UNIT_TYPE: (("project_id", "unit_type_code"), ("country_pack_id",)),
    }[scope_type]
    supplied = {
        "country_pack_id": country_pack_id,
        "project_id": project_id,
        "unit_type_code": unit_type_code,
    }
    missing = [name for name in required if supplied[name] is None]
    if missing:
        raise ValidationError(
            f"A {scope_type} field needs {' and '.join(missing)}. "
            "Without it the field would never apply to anything."
        )
    extra = [name for name in forbidden if supplied[name] is not None]
    if extra:
        raise ValidationError(
            f"A {scope_type} field does not take {' or '.join(extra)}. "
            "A scope that names two things is a scope nobody can predict."
        )


def business_today() -> date:
    """The date applicability is judged against.

    One function so a definition's window is read the same way everywhere — the
    API, completeness and the CSV importer — rather than three call sites each
    reaching for ``date.today()`` and one of them eventually not.
    """
    return date.today()


def _within_validity(as_of: date) -> ColumnElement[bool]:
    """The SQL form of "this definition is in force on ``as_of``"."""
    return (
        CustomFieldDefinition.valid_from.is_(None) | (CustomFieldDefinition.valid_from <= as_of)
    ) & (CustomFieldDefinition.valid_to.is_(None) | (CustomFieldDefinition.valid_to >= as_of))


def _applicable_scope_clause(
    *,
    entity_type: str,
    project: Project | None,
    unit_type_code: str | None,
    as_of: date,
) -> Select[tuple[CustomFieldDefinition]]:
    """Definitions that apply to one entity, by scope.

    Global applies everywhere; country applies within its pack; project within
    its project; unit-type within one unit type of one project. There is no
    inheritance and no override precedence, on purpose — a key resolving to two
    competing definitions is rejected at creation instead.
    """
    clauses = [CustomFieldDefinition.scope_type == SCOPE_GLOBAL]
    if project is not None:
        clauses.append(
            (CustomFieldDefinition.scope_type == SCOPE_COUNTRY)
            & (CustomFieldDefinition.country_pack_id == project.country_pack_id)
        )
        clauses.append(
            (CustomFieldDefinition.scope_type == SCOPE_PROJECT)
            & (CustomFieldDefinition.project_id == project.id)
        )
        if unit_type_code is not None:
            clauses.append(
                (CustomFieldDefinition.scope_type == SCOPE_UNIT_TYPE)
                & (CustomFieldDefinition.project_id == project.id)
                & (CustomFieldDefinition.unit_type_code == unit_type_code)
            )
    applies = clauses[0]
    for clause in clauses[1:]:
        applies = applies | clause
    # Effective dates are not decoration. A field dated to start next quarter
    # must not appear, become editable, or block a release today; an expired one
    # must stop doing all three.
    return select(CustomFieldDefinition).where(
        CustomFieldDefinition.entity_type == entity_type,
        CustomFieldDefinition.is_active.is_(True),
        _within_validity(as_of),
        applies,
    )


def _conflicting_definition(
    session: Session,
    *,
    entity_type: str,
    field_key: str,
    scope_type: str,
    country_pack_id: uuid.UUID | None,
    project_id: uuid.UUID | None,
    unit_type_code: str | None,
    exclude_id: uuid.UUID | None = None,
) -> CustomFieldDefinition | None:
    """An existing definition that could apply to the same entity as a new one.

    Two definitions of one key that can both reach the same record make the key
    ambiguous, and an ambiguous key has no correct answer. Rather than inventing
    a precedence rule nobody would remember, the second definition is refused.
    """
    candidates = list(
        session.scalars(
            select(CustomFieldDefinition).where(
                CustomFieldDefinition.entity_type == entity_type,
                CustomFieldDefinition.field_key == field_key,
                CustomFieldDefinition.is_active.is_(True),
            )
        )
    )
    for other in candidates:
        if exclude_id is not None and other.id == exclude_id:
            continue
        if _scopes_overlap(
            session,
            first=(scope_type, country_pack_id, project_id, unit_type_code),
            second=(
                other.scope_type,
                other.country_pack_id,
                other.project_id,
                other.unit_type_code,
            ),
        ):
            return other
    return None


def _country_pack_of(session: Session, project_id: uuid.UUID | None) -> uuid.UUID | None:
    if project_id is None:
        return None
    project = session.get(Project, project_id)
    return project.country_pack_id if project is not None else None


def _scopes_overlap(
    session: Session,
    *,
    first: tuple[str, uuid.UUID | None, uuid.UUID | None, str | None],
    second: tuple[str, uuid.UUID | None, uuid.UUID | None, str | None],
) -> bool:
    """Whether two scopes can both reach at least one entity."""
    scope_a, country_a, project_a, type_a = first
    scope_b, country_b, project_b, type_b = second
    if SCOPE_GLOBAL in (scope_a, scope_b):
        return True

    def pack(scope: str, country: uuid.UUID | None, project: uuid.UUID | None) -> uuid.UUID | None:
        return country if scope == SCOPE_COUNTRY else _country_pack_of(session, project)

    pack_a = pack(scope_a, country_a, project_a)
    pack_b = pack(scope_b, country_b, project_b)
    if SCOPE_COUNTRY in (scope_a, scope_b):
        return pack_a == pack_b
    if project_a != project_b:
        return False
    if SCOPE_PROJECT in (scope_a, scope_b):
        return True
    return type_a == type_b


def list_definitions(
    session: Session,
    *,
    entity_type: str | None = None,
    project_id: uuid.UUID | None = None,
    include_inactive: bool = True,
) -> list[CustomFieldDefinition]:
    statement = select(CustomFieldDefinition)
    if entity_type is not None:
        statement = statement.where(CustomFieldDefinition.entity_type == entity_type)
    if project_id is not None:
        # "Belongs to this project, or to nobody" was too wide: a country-scoped
        # field carries no project id, so a Jordan project was listing the UAE
        # pack's fields as if they were its own configuration.
        project = session.get(Project, project_id)
        statement = statement.where(
            (CustomFieldDefinition.project_id == project_id)
            | (CustomFieldDefinition.scope_type == SCOPE_GLOBAL)
            | (
                (CustomFieldDefinition.scope_type == SCOPE_COUNTRY)
                & (
                    CustomFieldDefinition.country_pack_id
                    == (project.country_pack_id if project is not None else None)
                )
            )
        )
    if not include_inactive:
        statement = statement.where(CustomFieldDefinition.is_active.is_(True))
    return list(
        session.scalars(
            statement.order_by(CustomFieldDefinition.entity_type, CustomFieldDefinition.field_key)
        )
    )


def get_definition(session: Session, definition_id: uuid.UUID) -> CustomFieldDefinition:
    definition = session.get(CustomFieldDefinition, definition_id)
    if definition is None:
        raise NotFoundError("Field definition not found.")
    return definition


def options_of(session: Session, definition_id: uuid.UUID) -> list[CustomFieldOption]:
    return list(
        session.scalars(
            select(CustomFieldOption)
            .where(CustomFieldOption.definition_id == definition_id)
            .order_by(CustomFieldOption.sort_order, CustomFieldOption.code)
        )
    )


def _write_options(
    session: Session, *, definition: CustomFieldDefinition, options: list[dict[str, Any]]
) -> None:
    if definition.data_type != CUSTOM_FIELD_TYPE_OPTION:
        if options:
            raise ValidationError("Only an option field carries options.")
        return
    existing = {option.code: option for option in options_of(session, definition.id)}
    for entry in options:
        code = str(entry["code"]).strip()
        option = existing.pop(code, None)
        if option is None:
            session.add(
                CustomFieldOption(
                    definition_id=definition.id,
                    code=code,
                    label=str(entry["label"]).strip(),
                    sort_order=int(entry.get("sort_order") or 0),
                    is_active=bool(entry.get("is_active", True)),
                )
            )
        else:
            option.label = str(entry["label"]).strip()
            option.sort_order = int(entry.get("sort_order") or 0)
            option.is_active = bool(entry.get("is_active", True))
    # Options not named again are retired, never deleted: rows already carrying
    # them stay readable.
    for orphan in existing.values():
        orphan.is_active = False


def create_definition(
    session: Session,
    *,
    actor: ActorContext,
    entity_type: str,
    field_key: str,
    data_type: str,
    scope_type: str,
    options: list[dict[str, Any]] | None = None,
    **fields: object,
) -> CustomFieldDefinition:
    key = _normalize_key(field_key, entity_type=entity_type)
    if scope_type == SCOPE_UNIT_TYPE and entity_type != "unit":
        raise ValidationError("Unit-type scope applies to units only.")

    country_pack_id = fields.get("country_pack_id")
    project_id = fields.get("project_id")
    unit_type_code = fields.get("unit_type_code")
    _validate_scope_columns(
        scope_type=scope_type,
        country_pack_id=country_pack_id,
        project_id=project_id,
        unit_type_code=unit_type_code,
    )
    conflict = _conflicting_definition(
        session,
        entity_type=entity_type,
        field_key=key,
        scope_type=scope_type,
        country_pack_id=country_pack_id,
        project_id=project_id,
        unit_type_code=unit_type_code,
    )
    if conflict is not None:
        raise ConflictError(
            f"'{key}' is already defined at {conflict.scope_type} scope for this entity. "
            "Two definitions that reach the same record would make the field ambiguous."
        )

    if fields.get("sensitive") and not fields.get("visible_role_keys"):
        raise ValidationError("A sensitive field needs an explicit list of roles that may see it.")
    if data_type != CUSTOM_FIELD_TYPE_OPTION and options:
        raise ValidationError("Only an option field carries options.")
    if data_type == CUSTOM_FIELD_TYPE_OPTION and not options:
        raise ValidationError("An option field needs at least one option.")
    if fields.get("regex_pattern"):
        _compile_pattern(str(fields["regex_pattern"]))
    _require_coherent_definition(
        minimum_value=fields.get("minimum_value"),
        maximum_value=fields.get("maximum_value"),
        valid_from=fields.get("valid_from"),
        valid_to=fields.get("valid_to"),
    )

    definition = CustomFieldDefinition(
        entity_type=entity_type,
        field_key=key,
        data_type=data_type,
        scope_type=scope_type,
        display_label=str(fields["display_label"]).strip(),
        description=fields.get("description"),
        unit_of_measure=fields.get("unit_of_measure"),
        help_text=fields.get("help_text"),
        required=bool(fields.get("required")),
        required_for_release=bool(fields.get("required_for_release")),
        minimum_value=fields.get("minimum_value"),
        maximum_value=fields.get("maximum_value"),
        regex_pattern=fields.get("regex_pattern"),
        is_unique=bool(fields.get("is_unique")),
        country_pack_id=country_pack_id,
        project_id=project_id,
        unit_type_code=unit_type_code,
        visible_role_keys=_validate_role_keys(fields.get("visible_role_keys"), label="Visibility"),
        editable_role_keys=_validate_role_keys(
            fields.get("editable_role_keys"), label="Editability"
        ),
        sensitive=bool(fields.get("sensitive")),
        approval_required=bool(fields.get("approval_required")),
        filterable=bool(fields.get("filterable")),
        groupable=bool(fields.get("groupable")),
        dashboard_visible=bool(fields.get("dashboard_visible")),
        export_visible=bool(fields.get("export_visible", True)),
        valid_from=fields.get("valid_from"),
        valid_to=fields.get("valid_to"),
        created_by_user_id=actor.user_id,
    )
    session.add(definition)
    _flush(session)
    _write_options(session, definition=definition, options=options or [])
    _flush(session)
    record_event(
        session,
        action="custom_field.created",
        entity_type=ENTITY_CUSTOM_FIELD,
        entity_id=definition.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(definition),
    )
    session.commit()
    session.refresh(definition)
    return definition


def _require_coherent_definition(
    *,
    minimum_value: object,
    maximum_value: object,
    valid_from: object,
    valid_to: object,
) -> None:
    """Check the definition the row will actually hold, not the request's half of it.

    PostgreSQL refuses both of these, but a CHECK violation surfaces as a 500
    naming a constraint. A person mistyping a range deserves a sentence telling
    them which way round it goes.
    """
    if minimum_value is not None and maximum_value is not None and maximum_value < minimum_value:
        raise ValidationError("The maximum cannot be lower than the minimum.")
    if valid_from is not None and valid_to is not None and valid_to < valid_from:
        raise ValidationError("The end of a field's validity cannot be before its start.")


def update_definition(
    session: Session,
    *,
    definition: CustomFieldDefinition,
    actor: ActorContext,
    options: list[dict[str, Any]] | None = None,
    change_reason: str | None = None,
    **changes: object,
) -> CustomFieldDefinition:
    """Change what a definition says about itself, never what it is.

    Entity, key, data type and scope are not accepted. Tightening bounds is
    accepted even when values exist: the existing rows keep their values, and
    the next write of one has to satisfy the new rule.
    """
    from app.core.patching import resolve_updates

    updates = resolve_updates(
        changes,
        fields=_DEFINITION_UPDATABLE,
        clearable=frozenset(
            {
                "description",
                "unit_of_measure",
                "help_text",
                "minimum_value",
                "maximum_value",
                "regex_pattern",
                "visible_role_keys",
                "editable_role_keys",
                "valid_from",
                "valid_to",
            }
        ),
    )
    if "visible_role_keys" in updates:
        updates["visible_role_keys"] = _validate_role_keys(
            updates["visible_role_keys"], label="Visibility"
        )
    if "editable_role_keys" in updates:
        updates["editable_role_keys"] = _validate_role_keys(
            updates["editable_role_keys"], label="Editability"
        )
    if updates.get("regex_pattern"):
        _compile_pattern(str(updates["regex_pattern"]))

    resulting_sensitive = updates.get("sensitive", definition.sensitive)
    resulting_visible = updates.get("visible_role_keys", definition.visible_role_keys)
    if resulting_sensitive and not resulting_visible:
        raise ValidationError("A sensitive field needs an explicit list of roles that may see it.")
    _require_coherent_definition(
        minimum_value=updates.get("minimum_value", definition.minimum_value),
        maximum_value=updates.get("maximum_value", definition.maximum_value),
        valid_from=updates.get("valid_from", definition.valid_from),
        valid_to=updates.get("valid_to", definition.valid_to),
    )

    before = _snapshot(definition)
    for field, value in updates.items():
        setattr(definition, field, value)
    if options is not None:
        _write_options(session, definition=definition, options=options)
    definition.version += 1
    definition.change_reason = change_reason
    definition.updated_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="custom_field.updated",
        entity_type=ENTITY_CUSTOM_FIELD,
        entity_id=definition.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=change_reason,
        before=before,
        after=_snapshot(definition),
    )
    session.commit()
    session.refresh(definition)
    return definition


def _snapshot(definition: CustomFieldDefinition) -> dict[str, Any]:
    return {field: getattr(definition, field) for field in _DEFINITION_FIELDS}


def _flush(session: Session) -> None:
    try:
        session.flush()
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        session.rollback()
        if constraint == "uq_custom_field_definitions_scope":
            raise ConflictError("That field is already defined at this scope.") from exc
        if constraint and constraint.endswith("_unique_value"):
            raise ConflictError("That value is already used by another record.") from exc
        raise


def _compile_pattern(pattern: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise ValidationError(f"That is not a valid pattern: {exc}.") from exc


# --------------------------------------------------------------------------- #
# Field security
# --------------------------------------------------------------------------- #


def can_view(definition: CustomFieldDefinition, actor: ActorContext) -> bool:
    """Whether this caller may receive this field's value at all.

    A restricted value is absent from the response body, not hidden by the
    interface: a field the caller may not see never leaves the server.
    """
    if actor.is_system_admin:
        return True
    if not definition.visible_role_keys:
        return True
    return bool(actor.role_keys.intersection(definition.visible_role_keys))


#: Who maintains an entity's configurable values when the definition does not
#: say. These mirror who maintains the entity itself, so an unconfigured field
#: behaves like the record it hangs off rather than like everything-goes.
DEFAULT_EDITOR_ROLES: dict[str, frozenset[str]] = {
    "project": frozenset({"system_admin", "project_manager"}),
    "land_parcel": frozenset({"system_admin", "project_manager"}),
    "unit": frozenset({"system_admin", "project_manager", "design_engineering"}),
}


def editor_roles(definition: CustomFieldDefinition) -> frozenset[str]:
    """The roles that may write this field, configured or defaulted.

    ``editable_role_keys`` is published in the definition's own contract, so it
    has to be the answer when it is set — a field configured as editable by
    Sales Operations that Sales Operations cannot edit is a lie in the metadata.
    Naming a role here grants that role this one field, never the unit's
    physical facts, which keep their own gate.
    """
    if definition.editable_role_keys:
        return frozenset(definition.editable_role_keys) | {"system_admin"}
    return DEFAULT_EDITOR_ROLES.get(definition.entity_type, frozenset({"system_admin"}))


def can_edit(definition: CustomFieldDefinition, actor: ActorContext) -> bool:
    """Whether this caller may change this field's value."""
    if actor.is_system_admin:
        return True
    if definition.approval_required:
        # Deliberately a control shortcut, not an approval workflow: until a real
        # one is justified, a field marked as needing approval is simply reserved
        # to the two roles that would have given it.
        return "project_manager" in actor.role_keys
    if not can_view(definition, actor):
        return False
    return bool(actor.role_keys.intersection(editor_roles(definition)))


# --------------------------------------------------------------------------- #
# Values
# --------------------------------------------------------------------------- #


def _coerce(definition: CustomFieldDefinition, value: object, session: Session) -> object:
    """Turn a submitted value into the stored JSON form, or refuse it.

    Decimals are stored and returned as strings. Routed through a JSON number
    they would become binary floats, and a measurement nobody can reproduce is
    worse than no measurement.
    """
    data_type = definition.data_type
    if data_type == CUSTOM_FIELD_TYPE_BOOLEAN:
        if isinstance(value, bool):
            return value
        raise ValidationError(f"{definition.display_label} expects true or false.")

    if data_type == CUSTOM_FIELD_TYPE_INTEGER:
        if isinstance(value, bool) or not isinstance(value, int | str):
            raise ValidationError(f"{definition.display_label} expects a whole number.")
        try:
            number = int(str(value).strip())
        except ValueError as exc:
            raise ValidationError(f"{definition.display_label} expects a whole number.") from exc
        _check_bounds(definition, Decimal(number))
        return number

    if data_type == CUSTOM_FIELD_TYPE_DECIMAL:
        if isinstance(value, bool) or not isinstance(value, int | float | str | Decimal):
            raise ValidationError(f"{definition.display_label} expects a number.")
        try:
            number = Decimal(str(value).strip())
        except InvalidOperation as exc:
            raise ValidationError(f"{definition.display_label} expects a number.") from exc
        if not number.is_finite():
            raise ValidationError(f"{definition.display_label} expects a number.")
        _check_bounds(definition, number)
        return str(number)

    if data_type == CUSTOM_FIELD_TYPE_DATE:
        if isinstance(value, date):
            return value.isoformat()
        try:
            return date.fromisoformat(str(value).strip()).isoformat()
        except ValueError as exc:
            raise ValidationError(
                f"{definition.display_label} expects a date as YYYY-MM-DD."
            ) from exc

    if data_type == CUSTOM_FIELD_TYPE_OPTION:
        code = str(value).strip()
        option = session.scalars(
            select(CustomFieldOption).where(
                CustomFieldOption.definition_id == definition.id,
                CustomFieldOption.code == code,
            )
        ).first()
        if option is None:
            raise ValidationError(f"'{code}' is not an option of {definition.display_label}.")
        if not option.is_active:
            raise ValidationError(f"'{code}' is no longer an active option.")
        return code

    text = str(value)
    if len(text) > 2000:
        raise ValidationError(f"{definition.display_label} is limited to 2000 characters.")
    if definition.regex_pattern and not _compile_pattern(definition.regex_pattern).match(text):
        raise ValidationError(f"{definition.display_label} does not match its required format.")
    if definition.minimum_value is not None and len(text) < int(definition.minimum_value):
        raise ValidationError(
            f"{definition.display_label} needs at least {int(definition.minimum_value)} characters."
        )
    if definition.maximum_value is not None and len(text) > int(definition.maximum_value):
        raise ValidationError(
            f"{definition.display_label} is limited to {int(definition.maximum_value)} characters."
        )
    return text


def _check_bounds(definition: CustomFieldDefinition, number: Decimal) -> None:
    if definition.minimum_value is not None and number < definition.minimum_value:
        raise ValidationError(
            f"{definition.display_label} cannot be below {definition.minimum_value}."
        )
    if definition.maximum_value is not None and number > definition.maximum_value:
        raise ValidationError(
            f"{definition.display_label} cannot be above {definition.maximum_value}."
        )


def _canonical(definition: CustomFieldDefinition, stored: object) -> str | None:
    """The comparable text form used to enforce uniqueness in the database."""
    if not definition.is_unique or stored is None:
        return None
    if definition.data_type == CUSTOM_FIELD_TYPE_DECIMAL:
        return format(Decimal(str(stored)).normalize(), "f")
    if definition.data_type == CUSTOM_FIELD_TYPE_TEXT:
        return " ".join(str(stored).split()).casefold()[:200]
    return str(stored)[:200]


def definitions_for(
    session: Session,
    *,
    entity_type: str,
    project: Project | None,
    unit_type_code: str | None = None,
    as_of: date | None = None,
) -> list[CustomFieldDefinition]:
    """Every definition in force today that applies to one entity."""
    statement = _applicable_scope_clause(
        entity_type=entity_type,
        project=project,
        unit_type_code=unit_type_code,
        as_of=as_of or business_today(),
    )
    return list(session.scalars(statement.order_by(CustomFieldDefinition.field_key)))


def unit_definitions_of_project(
    session: Session, *, project: Project, as_of: date | None = None
) -> list[CustomFieldDefinition]:
    """Every unit field of this project, whatever unit type it is scoped to.

    ``definitions_for`` answers for one entity, so it needs that entity's unit
    type and excludes every other. A CSV header is read once, before any row has
    a type, so it needs the project-wide set — and then each row checks the
    field against the type that row actually produces.
    """
    moment = as_of or business_today()
    return list(
        session.scalars(
            select(CustomFieldDefinition)
            .where(
                CustomFieldDefinition.entity_type == "unit",
                CustomFieldDefinition.is_active.is_(True),
                _within_validity(moment),
                (CustomFieldDefinition.scope_type == SCOPE_GLOBAL)
                | (
                    (CustomFieldDefinition.scope_type == SCOPE_COUNTRY)
                    & (CustomFieldDefinition.country_pack_id == project.country_pack_id)
                )
                | (
                    CustomFieldDefinition.scope_type.in_((SCOPE_PROJECT, SCOPE_UNIT_TYPE))
                    & (CustomFieldDefinition.project_id == project.id)
                ),
            )
            .order_by(CustomFieldDefinition.field_key)
        )
    )


def _entity_context(
    session: Session, *, entity_type: str, entity: object
) -> tuple[Project | None, str | None]:
    if entity_type == "project":
        return entity, None
    if entity_type == "land_parcel":
        return session.get(Project, entity.project_id), None
    return session.get(Project, entity.project_id), entity.unit_type_code


def read_values(
    session: Session, *, entity_type: str, entity: object, actor: ActorContext
) -> list[dict[str, Any]]:
    """Every applicable field and this entity's value, filtered by visibility."""
    project, unit_type_code = _entity_context(session, entity_type=entity_type, entity=entity)
    definitions = definitions_for(
        session, entity_type=entity_type, project=project, unit_type_code=unit_type_code
    )
    model, column = _VALUE_MODELS[entity_type]
    stored = {
        row.definition_id: row
        for row in session.scalars(select(model).where(getattr(model, column) == entity.id))
    }
    result: list[dict[str, Any]] = []
    for definition in definitions:
        if not can_view(definition, actor):
            continue
        row = stored.get(definition.id)
        result.append(
            {
                "definition_id": definition.id,
                "field_key": definition.field_key,
                "display_label": definition.display_label,
                "data_type": definition.data_type,
                "unit_of_measure": definition.unit_of_measure,
                "help_text": definition.help_text,
                "required": definition.required,
                "required_for_release": definition.required_for_release,
                "is_editable": can_edit(definition, actor),
                "options": [
                    option for option in options_of(session, definition.id) if option.is_active
                ],
                "value": row.value_json if row is not None else None,
            }
        )
    return result


def write_values(
    session: Session,
    *,
    entity_type: str,
    entity: object,
    actor: ActorContext,
    values: dict[str, object],
    change_reason: str | None = None,
) -> None:
    """Write a set of custom values in one transaction.

    Security is evaluated per definition, not once for the request: a caller may
    legitimately be allowed one field of a body and refused another, and the
    refusal must not quietly drop the field.

    Does not commit — the caller owns the transaction boundary, so the values and
    their audit entries land together with whatever else the request changed.
    """
    project, unit_type_code = _entity_context(session, entity_type=entity_type, entity=entity)
    definitions = {
        definition.field_key: definition
        for definition in definitions_for(
            session, entity_type=entity_type, project=project, unit_type_code=unit_type_code
        )
    }
    model, column = _VALUE_MODELS[entity_type]

    for field_key, raw in values.items():
        definition = definitions.get(field_key)
        if definition is None:
            raise ValidationError(f"'{field_key}' is not a field of this record.")
        if not can_view(definition, actor):
            # Same answer as for a field that does not exist: telling the caller
            # a hidden field is there is itself the leak.
            raise ValidationError(f"'{field_key}' is not a field of this record.")
        if not can_edit(definition, actor):
            raise PermissionDeniedError(f"You may not change {definition.display_label}.")
        if definition.approval_required and not (change_reason or "").strip():
            raise ValidationError(f"{definition.display_label} needs a reason for the change.")

        row = session.scalars(
            select(model).where(
                model.definition_id == definition.id, getattr(model, column) == entity.id
            )
        ).first()
        before = {"value": row.value_json} if row is not None else {"value": None}

        if raw is None:
            if definition.required:
                raise ValidationError(f"{definition.display_label} is required.")
            stored: Any = None
        else:
            stored = _coerce(definition, raw, session)

        if row is None:
            row = model(
                definition_id=definition.id,
                value_json=stored,
                unique_value=_canonical(definition, stored),
                updated_by_user_id=actor.user_id,
                **{column: entity.id},
            )
            session.add(row)
        else:
            row.value_json = stored
            row.unique_value = _canonical(definition, stored)
            row.updated_by_user_id = actor.user_id
        _flush(session)
        record_event(
            session,
            action="custom_field_value.updated",
            entity_type=ENTITY_CUSTOM_VALUE,
            entity_id=row.id,
            correlation_id=actor.correlation_id,
            actor_user_id=actor.user_id,
            reason=change_reason,
            before=before,
            after={"value": stored, "field_key": definition.field_key},
        )


def check_value(
    session: Session,
    *,
    definition: CustomFieldDefinition,
    value: object,
    actor: ActorContext,
    change_reason: str | None = None,
) -> None:
    """Say whether a proposed value would be accepted, writing nothing.

    Exactly the rules ``write_values`` applies, run without a row, a flush or a
    transaction, so the CSV importer can promise during validation what apply
    will actually do. The alternative — the importer restating type coercion,
    option lookup, bounds and regex — is two copies of the rule and one of them
    drifting.
    """
    if not can_view(definition, actor):
        raise ValidationError(f"'{definition.field_key}' is not a field of this record.")
    if not can_edit(definition, actor):
        raise PermissionDeniedError(f"You may not change {definition.display_label}.")
    if definition.approval_required and not (change_reason or "").strip():
        raise ValidationError(f"{definition.display_label} needs a reason for the change.")
    if value is None:
        if definition.required:
            raise ValidationError(f"{definition.display_label} is required.")
        return
    _coerce(definition, value, session)


def missing_required_custom_fields(
    session: Session, *, unit: Unit, actor: ActorContext | None = None
) -> list[tuple[str, bool]]:
    """Release-required custom fields, and whether this unit has filled each in.

    A field the caller may not see still counts — completeness has to read the
    same for everyone, or two people looking at one unit disagree about whether
    it is ready. Only its name is withheld, because a label like "Owner
    litigation note" is exactly the thing the sensitivity flag exists to hide.
    """
    project = session.get(Project, unit.project_id)
    definitions = [
        definition
        for definition in definitions_for(
            session, entity_type="unit", project=project, unit_type_code=unit.unit_type_code
        )
        if definition.required_for_release
    ]
    if not definitions:
        return []
    filled = {
        row.definition_id
        for row in session.scalars(
            select(UnitCustomFieldValue).where(
                UnitCustomFieldValue.unit_id == unit.id,
                UnitCustomFieldValue.value_json.is_not(None),
            )
        )
    }
    return [
        (
            definition.display_label
            if actor is None or can_view(definition, actor)
            else _WITHHELD_LABEL,
            definition.id in filled,
        )
        for definition in definitions
    ]


def parcel_of(session: Session, *, project_id: uuid.UUID, parcel_id: uuid.UUID) -> LandParcel:
    parcel = session.scalars(
        select(LandParcel).where(LandParcel.id == parcel_id, LandParcel.project_id == project_id)
    ).first()
    if parcel is None:
        raise NotFoundError("Land parcel not found.")
    return parcel
