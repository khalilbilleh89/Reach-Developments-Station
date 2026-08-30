"""Pricing domain logic and transaction boundaries.

Everything that decides *whether* something may happen lives here; everything
that decides *what a number is* lives in :mod:`calculator`, which has no session
and cannot read a row. The split is the point: a price has to be reproducible
from its inputs, and a calculation that can also query is a calculation whose
answer depends on when it ran.

Three shapes recur.

**Prepare, submit, approve, activate.** A configuration and a price version
follow the same lifecycle, and in both cases the person who submits may not be
the person who approves. Nothing here is a workflow engine — it is a status
column, a handful of guards and one comparison of user identifiers.

**Lock, re-read, decide.** Anything whose invariant spans rows takes the project
row, or the unit row, or both in that order, and re-reads before deciding. The
partial unique indexes behind "one active configuration" and "one active price"
are the backstop, not the mechanism.

**Freeze, then compare.** A draft price records what the calculation saw. Before
it may be submitted, approved or activated, that record is compared against what
is true now. Physical data that moved underneath a price is the one thing an
approval must never wave through.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.patching import resolve_updates
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.inventory import custom_fields as inventory_fields
from app.modules.inventory import models as inventory_models
from app.modules.inventory import service as inventory
from app.modules.inventory.models import (
    AREA_ROLE_INTERNAL,
    CATEGORY_ACCESSIBILITY,
    CATEGORY_FLOOR_BAND,
    CATEGORY_GARDEN_CLASS,
    CATEGORY_ORIENTATION,
    CATEGORY_SUB_ASSET_SUBTYPE,
    CATEGORY_UNIT_TYPE,
    CATEGORY_VIEW_CLASS,
    AreaType,
    Building,
    CustomFieldDefinition,
    CustomFieldOption,
    Floor,
    InventorySubAsset,
    Phase,
    Unit,
    UnitAreaSchedule,
    UnitAreaValue,
    UnitCustomFieldValue,
)
from app.modules.pricing import calculator
from app.modules.pricing.calculator import (
    AreaInput,
    EscalationInput,
    PremiumInput,
    PricingInput,
    UpgradeInput,
    money,
)
from app.modules.pricing.models import (
    ADJUSTMENT_PERCENTAGE,
    AREA_METHOD_FACTOR,
    AREA_METHOD_FIXED_RATE,
    AREA_METHOD_INTERNAL_BASE,
    BASIS_INTERNAL,
    COMPONENT_BASE_ATTACHED,
    COMPONENT_BASE_INTERNAL,
    COMPONENT_ESCALATION,
    COMPONENT_FEATURE_PREMIUM,
    COMPONENT_PAID_UPGRADE,
    COMPONENT_PREMIUM_CAP,
    COMPONENT_SCOPE_ADJUSTMENT,
    COMPONENT_SUB_ASSET_PREMIUM,
    ENTITY_AREA_RULE,
    ENTITY_BENCHMARK,
    ENTITY_CONFIGURATION,
    ENTITY_ESCALATION_ACTIVATION,
    ENTITY_ESCALATION_RULE,
    ENTITY_PREMIUM_RULE,
    ENTITY_PRICE_VERSION,
    ESCALATION_SCOPE_PHASE,
    ESCALATION_SCOPE_PROJECT,
    ESCALATION_SCOPE_UNIT_TYPE,
    ESCALATION_TRIGGER_INPUTS,
    FLAG_ABOVE,
    FLAG_BELOW,
    FLAG_NONE,
    FLAG_WITHIN,
    PREMIUM_ASSET_SOURCES,
    PREMIUM_FLAG_SOURCES,
    PREMIUM_METHOD_PER_AREA,
    PREMIUM_METHOD_PER_ASSET,
    STATUS_ACTIVE,
    STATUS_APPROVED,
    STATUS_DRAFT,
    STATUS_SUBMITTED,
    STATUS_SUPERSEDED,
    TRIGGER_DATE,
    TRIGGER_SALES_PERCENTAGE,
    MarketBenchmark,
    PricingAreaRule,
    PricingConfiguration,
    PricingEscalationActivation,
    PricingEscalationRule,
    PricingPremiumRule,
    UnitPriceComponent,
    UnitPriceVersion,
)
from app.modules.pricing.permissions import require_different_checker
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.settings import service as settings_service
from app.modules.settings.models import Currency, TaxRule

#: Re-exported so a route can build a paid-upgrade line without importing the
#: calculator: the API's contract is with this module, not with the arithmetic
#: behind it.
__all__ = ["UpgradeInput"]

#: The reference catalogue behind each code-matching premium source. It is the
#: same catalogue inventory validates the unit's own columns against, so a rule
#: and the units it hopes to match are checked against one list rather than two.
PREMIUM_REFERENCE_CATEGORIES = {
    "unit_type": CATEGORY_UNIT_TYPE,
    "view_class": CATEGORY_VIEW_CLASS,
    "floor_band": CATEGORY_FLOOR_BAND,
    "orientation": CATEGORY_ORIENTATION,
    "accessibility": CATEGORY_ACCESSIBILITY,
    "garden_class": CATEGORY_GARDEN_CLASS,
}

ZERO = Decimal("0")
ONE = Decimal("1")

#: The largest number of units one bulk request may act on. Generous for a real
#: development — the reference project is 247 units — and there only to refuse a
#: request nobody meant to send.
MAX_BULK_UNITS = 5000

#: Unique constraint names mapped to the conflict a client should see. The
#: service checks first so the message is useful; this catches the race where
#: two requests both pass that check and the database decides between them.
_CONFLICTS = {
    "uq_pricing_configurations_active": (
        "This project already has an active pricing configuration."
    ),
    "uq_pricing_configurations_project_id_version_number": (
        "That pricing configuration version already exists."
    ),
    "uq_unit_price_versions_active": "This unit already has an active price.",
    "uq_unit_price_versions_unit_id_version_number": (
        "That price version number already exists for this unit."
    ),
    "uq_market_benchmarks_scope": "An active benchmark already covers that scope.",
    "uq_pricing_escalation_activations_rule": "That escalation is already active.",
    "uq_pricing_premium_rules_pricing_configuration_id_code": (
        "A premium rule with that code already exists in this configuration."
    ),
    "uq_pricing_escalation_rules_pricing_configuration_id_code": (
        "An escalation rule with that code already exists in this configuration."
    ),
    "uq_pricing_area_rules_pricing_configuration_id_area_type_id": (
        "That area type is already priced by this configuration."
    ),
}

_CONFIG_FIELDS = (
    "id",
    "project_id",
    "version_number",
    "name",
    "status",
    "pricing_currency_id",
    "base_internal_rate",
    "premium_stacking_default",
    "maximum_premium_fraction",
    "offer_valid_days",
    "price_lock_days",
    "reservation_expiry_days",
    "default_payment_plan_adjustment_fraction",
    "tax_treatment_code",
    "valid_from",
    "valid_to",
)
_CONFIG_UPDATABLE = (
    "name",
    "pricing_currency_id",
    "base_internal_rate",
    "premium_stacking_default",
    "maximum_premium_fraction",
    "offer_valid_days",
    "price_lock_days",
    "reservation_expiry_days",
    "default_payment_plan_adjustment_fraction",
    "tax_treatment_code",
    "valid_from",
    "valid_to",
)
_CONFIG_CLEARABLE = frozenset(
    {
        "maximum_premium_fraction",
        "offer_valid_days",
        "price_lock_days",
        "reservation_expiry_days",
        "default_payment_plan_adjustment_fraction",
        "valid_to",
    }
)

_AREA_RULE_FIELDS = (
    "id",
    "pricing_configuration_id",
    "area_type_id",
    "pricing_method",
    "rate_per_area",
    "internal_rate_factor",
    "sort_order",
    "is_active",
)
_AREA_RULE_UPDATABLE = (
    "pricing_method",
    "rate_per_area",
    "internal_rate_factor",
    "sort_order",
    "is_active",
)
_AREA_RULE_CLEARABLE = frozenset({"rate_per_area", "internal_rate_factor"})

_PREMIUM_FIELDS = (
    "id",
    "pricing_configuration_id",
    "code",
    "label",
    "source_kind",
    "match_code",
    "custom_field_definition_id",
    "custom_option_code",
    "method",
    "percentage_fraction",
    "amount",
    "eligible_base",
    "stacking_method",
    "sequence",
    "is_active",
)
_PREMIUM_UPDATABLE = (
    "label",
    "match_code",
    "custom_option_code",
    "method",
    "percentage_fraction",
    "amount",
    "eligible_base",
    "stacking_method",
    "sequence",
    "is_active",
)
_PREMIUM_CLEARABLE = frozenset(
    {"match_code", "custom_option_code", "percentage_fraction", "amount", "stacking_method"}
)

_ESCALATION_FIELDS = (
    "id",
    "pricing_configuration_id",
    "code",
    "label",
    "trigger_type",
    "scope_type",
    "phase_id",
    "unit_type_code",
    "threshold_date",
    "threshold_fraction",
    "milestone_reference",
    "market_index_reference",
    "adjustment_method",
    "adjustment_percentage_fraction",
    "adjustment_amount",
    "cumulative",
    "sequence",
    "is_active",
)
_ESCALATION_UPDATABLE = (
    "label",
    "threshold_date",
    "threshold_fraction",
    "milestone_reference",
    "market_index_reference",
    "adjustment_method",
    "adjustment_percentage_fraction",
    "adjustment_amount",
    "cumulative",
    "sequence",
    "is_active",
)
_ESCALATION_CLEARABLE = frozenset(
    {
        "threshold_date",
        "threshold_fraction",
        "milestone_reference",
        "market_index_reference",
        "adjustment_percentage_fraction",
        "adjustment_amount",
    }
)

_BENCHMARK_FIELDS = (
    "id",
    "project_id",
    "phase_id",
    "unit_type_code",
    "area_basis",
    "benchmark_price_per_area",
    "currency_id",
    "comparison_date",
    "source_name",
    "source_reference",
    "tolerance_fraction",
    "notes",
    "is_active",
)
_BENCHMARK_UPDATABLE = (
    "benchmark_price_per_area",
    "comparison_date",
    "source_name",
    "source_reference",
    "tolerance_fraction",
    "notes",
    "is_active",
)
_BENCHMARK_CLEARABLE = frozenset({"source_reference", "notes"})

_VERSION_FIELDS = (
    "id",
    "project_id",
    "unit_id",
    "version_number",
    "status",
    "pricing_configuration_id",
    "unit_area_schedule_id",
    "currency_id",
    "valid_from",
    "valid_to",
    "base_area_value",
    "scope_adjustment_total",
    "premium_total",
    "premium_cap_adjustment",
    "escalation_total",
    "paid_upgrade_total",
    "reference_price_ex_tax",
    "market_flag",
    "market_deviation_fraction",
)


def _flush(session: Session) -> None:
    """Flush, turning a known uniqueness race into the message it deserves."""
    try:
        session.flush()
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        detail = _CONFLICTS.get(constraint or "")
        if detail is None:
            raise
        session.rollback()
        raise ConflictError(detail) from exc


def _snapshot(instance: object, fields: tuple[str, ...]) -> dict[str, Any]:
    return {name: getattr(instance, name) for name in fields}


def _require_reason(reason: str | None, *, detail: str) -> str:
    text = (reason or "").strip()
    if not text:
        raise ValidationError(detail)
    return text


# --------------------------------------------------------------------------- #
# Pricing configuration
# --------------------------------------------------------------------------- #


def list_configurations(session: Session, *, project_id: uuid.UUID) -> list[PricingConfiguration]:
    return list(
        session.scalars(
            select(PricingConfiguration)
            .where(PricingConfiguration.project_id == project_id)
            .order_by(PricingConfiguration.version_number.desc())
        )
    )


def get_configuration(
    session: Session, *, project_id: uuid.UUID, configuration_id: uuid.UUID
) -> PricingConfiguration:
    """Load a configuration by its project *and* its own identifier.

    Never by primary key with the project checked afterwards: that is the shape
    that lets one project's identifier be substituted into another's path.
    """
    configuration = session.scalars(
        select(PricingConfiguration).where(
            PricingConfiguration.id == configuration_id,
            PricingConfiguration.project_id == project_id,
        )
    ).first()
    if configuration is None:
        raise NotFoundError("Pricing configuration not found.")
    return configuration


def active_configuration(session: Session, *, project_id: uuid.UUID) -> PricingConfiguration | None:
    return session.scalars(
        select(PricingConfiguration).where(
            PricingConfiguration.project_id == project_id,
            PricingConfiguration.status == STATUS_ACTIVE,
        )
    ).first()


def _require_active_currency(session: Session, currency_id: uuid.UUID) -> Currency:
    currency = session.scalars(select(Currency).where(Currency.id == currency_id)).first()
    if currency is None:
        raise ValidationError("That currency is not configured.")
    if not currency.is_active:
        raise ValidationError("That currency is not active.")
    return currency


def _require_configuration_validity(
    configuration: PricingConfiguration, *, effective_from: date
) -> None:
    """A price may only be effective on a day its policy was in force.

    A configuration states the window it governs. Pricing a unit effective
    before that window means the number was produced by a policy nobody had
    adopted yet; pricing it after means a policy already withdrawn. Neither is
    a price anyone could defend, so neither is stored.
    """
    if effective_from < configuration.valid_from:
        raise ConflictError(
            f"This pricing configuration takes effect on "
            f"{configuration.valid_from.isoformat()}. A price cannot be effective before it."
        )
    if configuration.valid_to is not None and effective_from > configuration.valid_to:
        raise ConflictError(
            f"This pricing configuration ended on {configuration.valid_to.isoformat()}. "
            "A price cannot be effective after it."
        )


def _require_draft(configuration: PricingConfiguration) -> None:
    if configuration.status != STATUS_DRAFT:
        raise ConflictError(
            "Only a draft pricing configuration can be changed. "
            "Create a new version to change an approved policy."
        )


def create_configuration(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    **fields: object,
) -> PricingConfiguration:
    """Open a new draft pricing policy for a project.

    The project row is locked before the next version number is read: two
    requests arriving together must produce version 3 and version 4, not two
    rows both claiming to be version 3 and one of them losing at the index.
    """
    project = lock_project(session, project.id)
    _require_active_currency(session, fields["pricing_currency_id"])
    highest = session.scalar(
        select(func.max(PricingConfiguration.version_number)).where(
            PricingConfiguration.project_id == project.id
        )
    )
    configuration = PricingConfiguration(
        project_id=project.id,
        version_number=(highest or 0) + 1,
        status=STATUS_DRAFT,
        created_by_user_id=actor.user_id,
        **fields,
    )
    session.add(configuration)
    _flush(session)
    record_event(
        session,
        action="pricing_configuration.created",
        entity_type=ENTITY_CONFIGURATION,
        entity_id=configuration.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(configuration, _CONFIG_FIELDS),
    )
    session.commit()
    session.refresh(configuration)
    return configuration


def update_configuration(
    session: Session,
    *,
    project: Project,
    configuration: PricingConfiguration,
    actor: ActorContext,
    **changes: object,
) -> PricingConfiguration:
    updates = resolve_updates(changes, fields=_CONFIG_UPDATABLE, clearable=_CONFIG_CLEARABLE)
    lock_project(session, project.id)
    session.refresh(configuration)
    _require_draft(configuration)
    if "pricing_currency_id" in updates:
        _require_active_currency(session, updates["pricing_currency_id"])  # type: ignore[arg-type]

    before = _snapshot(configuration, _CONFIG_FIELDS)
    for name, value in updates.items():
        setattr(configuration, name, value)
    if configuration.valid_to is not None and configuration.valid_to < configuration.valid_from:
        raise ValidationError("valid_to cannot be before valid_from.")
    _flush(session)
    record_event(
        session,
        action="pricing_configuration.updated",
        entity_type=ENTITY_CONFIGURATION,
        entity_id=configuration.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(configuration, _CONFIG_FIELDS),
    )
    session.commit()
    session.refresh(configuration)
    return configuration


def submit_configuration(
    session: Session,
    *,
    project: Project,
    configuration: PricingConfiguration,
    actor: ActorContext,
    change_reason: str | None = None,
) -> PricingConfiguration:
    """Put a draft policy forward for approval.

    A configuration with no priced internal area would generate a price of zero
    for every unit, so the check that there is one belongs here rather than in
    the approver's head.
    """
    lock_project(session, project.id)
    session.refresh(configuration)
    _require_draft(configuration)
    _require_internal_base_rule(session, project=project, configuration=configuration)

    before = _snapshot(configuration, _CONFIG_FIELDS)
    configuration.status = STATUS_SUBMITTED
    configuration.submitted_at = func.now()
    configuration.submitted_by_user_id = actor.user_id
    if change_reason:
        configuration.change_reason = change_reason.strip()
    _flush(session)
    record_event(
        session,
        action="pricing_configuration.submitted",
        entity_type=ENTITY_CONFIGURATION,
        entity_id=configuration.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=change_reason,
        before=before,
        after=_snapshot(configuration, _CONFIG_FIELDS),
    )
    session.commit()
    session.refresh(configuration)
    return configuration


def _require_internal_base_rule(
    session: Session, *, project: Project, configuration: PricingConfiguration
) -> None:
    """Exactly one active internal-base rule, and it is the internal area.

    Checked again at submission rather than trusted from creation time, because
    a rule can be deactivated or the project's area types reconfigured after the
    rule was written. Submission is the last moment before an approver is asked
    to sanction a policy, so it is the moment the policy has to still be one.

    The internal area is also refused an attached-area method: pricing it as an
    add-on would leave the configuration with a ``base_internal_rate`` that no
    area is quoted against.
    """
    rules = list_area_rules(session, configuration_id=configuration.id)
    active = [rule for rule in rules if rule.is_active]
    bases = [rule for rule in active if rule.pricing_method == AREA_METHOD_INTERNAL_BASE]
    if not bases:
        raise ValidationError(
            "This configuration prices no internal area. Add an area rule using the "
            "internal base rate before submitting it."
        )
    if len(bases) > 1:  # pragma: no cover - the partial unique index refuses this first
        raise ConflictError("This configuration prices two area types at the internal base rate.")
    internal = inventory.internal_area_type(session, project_id=project.id)
    if internal is None:
        raise ValidationError(
            "This project has no active internal area type to price at the internal base rate."
        )
    if bases[0].area_type_id != internal.id:
        raise ValidationError(
            f"The internal base rate is applied to an area that is not this project's "
            f"internal area ('{internal.code}'). Correct the area rule before submitting."
        )
    misplaced = [
        rule
        for rule in active
        if rule.area_type_id == internal.id and rule.pricing_method != AREA_METHOD_INTERNAL_BASE
    ]
    if misplaced:  # pragma: no cover - one rule per area type, and it is the base above
        raise ValidationError(
            f"'{internal.code}' is this project's internal area and must be priced at the "
            "internal base rate."
        )


def return_configuration(
    session: Session,
    *,
    project: Project,
    configuration: PricingConfiguration,
    actor: ActorContext,
    reason: str,
) -> PricingConfiguration:
    """Send a submitted policy back to its author, with the reason recorded."""
    detail = _require_reason(reason, detail="A reason is required to return a configuration.")
    lock_project(session, project.id)
    session.refresh(configuration)
    if configuration.status != STATUS_SUBMITTED:
        raise ConflictError("Only a submitted pricing configuration can be returned.")

    before = _snapshot(configuration, _CONFIG_FIELDS)
    configuration.status = STATUS_DRAFT
    configuration.submitted_at = None
    configuration.submitted_by_user_id = None
    configuration.change_reason = detail
    _flush(session)
    record_event(
        session,
        action="pricing_configuration.returned",
        entity_type=ENTITY_CONFIGURATION,
        entity_id=configuration.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=detail,
        before=before,
        after=_snapshot(configuration, _CONFIG_FIELDS),
    )
    session.commit()
    session.refresh(configuration)
    return configuration


def approve_configuration(
    session: Session,
    *,
    project: Project,
    configuration: PricingConfiguration,
    actor: ActorContext,
    reason: str,
) -> PricingConfiguration:
    """Sanction a submitted policy. Approved is not yet live."""
    detail = _require_reason(reason, detail="A reason is required to approve a configuration.")
    lock_project(session, project.id)
    session.refresh(configuration)
    if configuration.status != STATUS_SUBMITTED:
        raise ConflictError("Only a submitted pricing configuration can be approved.")
    require_different_checker(actor, maker_user_id=configuration.submitted_by_user_id)

    before = _snapshot(configuration, _CONFIG_FIELDS)
    configuration.status = STATUS_APPROVED
    configuration.approved_at = func.now()
    configuration.approved_by_user_id = actor.user_id
    configuration.change_reason = detail
    _flush(session)
    record_event(
        session,
        action="pricing_configuration.approved",
        entity_type=ENTITY_CONFIGURATION,
        entity_id=configuration.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=detail,
        before=before,
        after=_snapshot(configuration, _CONFIG_FIELDS),
    )
    session.commit()
    session.refresh(configuration)
    return configuration


def activate_configuration(
    session: Session,
    *,
    project: Project,
    configuration: PricingConfiguration,
    actor: ActorContext,
) -> PricingConfiguration:
    """Make an approved policy the one the project prices from.

    Under the project lock, and re-read after taking it: the previous active
    configuration is superseded and the new one activated in one transaction, so
    there is no instant in which a project has two live pricing policies or
    none.
    """
    project = lock_project(session, project.id)
    session.refresh(configuration)
    if configuration.status != STATUS_APPROVED:
        raise ConflictError("Only an approved pricing configuration can be activated.")
    # A future-dated policy stays approved until somebody activates it on a day
    # it actually governs. No scheduler: nothing in this module runs unless a
    # person asks it to, and a policy that switched itself on overnight is the
    # silent repricing the whole design refuses.
    _require_configuration_validity(configuration, effective_from=inventory_fields.business_today())

    current = active_configuration(session, project_id=project.id)
    before = _snapshot(configuration, _CONFIG_FIELDS)
    if current is not None:
        superseded_before = _snapshot(current, _CONFIG_FIELDS)
        current.status = STATUS_SUPERSEDED
        current.superseded_at = func.now()
        if current.valid_to is None:
            current.valid_to = configuration.valid_from
        session.flush()
        record_event(
            session,
            action="pricing_configuration.superseded",
            entity_type=ENTITY_CONFIGURATION,
            entity_id=current.id,
            correlation_id=actor.correlation_id,
            actor_user_id=actor.user_id,
            before=superseded_before,
            after=_snapshot(current, _CONFIG_FIELDS),
        )
    configuration.status = STATUS_ACTIVE
    configuration.activated_at = func.now()
    configuration.activated_by_user_id = actor.user_id
    _flush(session)
    record_event(
        session,
        action="pricing_configuration.activated",
        entity_type=ENTITY_CONFIGURATION,
        entity_id=configuration.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(configuration, _CONFIG_FIELDS),
    )
    session.commit()
    session.refresh(configuration)
    return configuration


# --------------------------------------------------------------------------- #
# Area rules
# --------------------------------------------------------------------------- #


def list_area_rules(session: Session, *, configuration_id: uuid.UUID) -> list[PricingAreaRule]:
    return list(
        session.scalars(
            select(PricingAreaRule)
            .where(PricingAreaRule.pricing_configuration_id == configuration_id)
            .order_by(PricingAreaRule.sort_order, PricingAreaRule.id)
        )
    )


def _validate_area_rule(
    *, pricing_method: str, rate_per_area: Decimal | None, internal_rate_factor: Decimal | None
) -> None:
    """Each method carries exactly the number it reads, and no other.

    The database says the same thing, but a CHECK violation reaches a client as
    a 500 with nothing useful in it.
    """
    if pricing_method == AREA_METHOD_FIXED_RATE and rate_per_area is None:
        raise ValidationError("A fixed rate per area needs rate_per_area.")
    if pricing_method == AREA_METHOD_FACTOR and internal_rate_factor is None:
        raise ValidationError("A factor of the internal rate needs internal_rate_factor.")
    if pricing_method != AREA_METHOD_FIXED_RATE and rate_per_area is not None:
        raise ValidationError("rate_per_area applies only to fixed_rate_per_area.")
    if pricing_method != AREA_METHOD_FACTOR and internal_rate_factor is not None:
        raise ValidationError("internal_rate_factor applies only to factor_of_internal_rate.")


def _require_one_internal_base(
    session: Session, *, configuration_id: uuid.UUID, area_rule_id: uuid.UUID | None
) -> None:
    """Only one area type may be the base the internal rate is quoted against."""
    statement = select(PricingAreaRule).where(
        PricingAreaRule.pricing_configuration_id == configuration_id,
        PricingAreaRule.pricing_method == AREA_METHOD_INTERNAL_BASE,
        PricingAreaRule.is_active.is_(True),
    )
    if area_rule_id is not None:
        statement = statement.where(PricingAreaRule.id != area_rule_id)
    if session.scalars(statement).first() is not None:
        raise ConflictError(
            "This configuration already prices an area type at the internal base rate."
        )


def _require_internal_area_role(session: Session, *, project: Project, area_type: AreaType) -> None:
    """``internal_base`` must name the area that actually *is* internal.

    Nothing else in the system asks whether the "internal base" is internal, and
    everything downstream assumes it: ``base_internal_rate`` is applied to it,
    ``internal_area_snapshot`` is its measurement, ``price_per_internal_area``
    divides by it, and a benchmark quoted on an internal basis is compared
    against it. Point that at a balcony and every one of those numbers is
    quietly about balconies while still being labelled internal.
    """
    if area_type.area_role != AREA_ROLE_INTERNAL:
        raise ValidationError(
            f"'{area_type.code}' is a {area_type.area_role} area. Only the project's "
            "internal area can be priced at the internal base rate."
        )


def _require_matching_unit_of_measure(
    session: Session, *, project: Project, area_type: AreaType
) -> None:
    """A factor of the internal rate has to be a factor of *this* rate.

    ``factor_of_internal_rate`` multiplies a rate quoted per unit of internal
    area. Applying a JOD-per-square-metre rate to an area measured in square
    feet needs a conversion, and there is deliberately no conversion anywhere in
    this system — so the two measurements have to already agree.

    ``fixed_rate_per_area`` is exempt on purpose: its rate is stated against that
    area's own unit, so nothing is being carried across from anywhere else.
    """
    internal = inventory.internal_area_type(session, project_id=project.id)
    if internal is None:
        raise ValidationError(
            "This project has no active internal area type, so there is no internal "
            "rate to take a factor of."
        )
    if area_type.unit_of_measure != internal.unit_of_measure:
        raise ValidationError(
            f"'{area_type.code}' is measured in {area_type.unit_of_measure} and the "
            f"internal rate is quoted per {internal.unit_of_measure}. There is no "
            "conversion here — price this area with its own rate instead."
        )


def create_area_rule(
    session: Session,
    *,
    project: Project,
    configuration: PricingConfiguration,
    actor: ActorContext,
    area_type_id: uuid.UUID,
    pricing_method: str,
    rate_per_area: Decimal | None = None,
    internal_rate_factor: Decimal | None = None,
    sort_order: int = 0,
) -> PricingAreaRule:
    lock_project(session, project.id)
    session.refresh(configuration)
    _require_draft(configuration)
    _validate_area_rule(
        pricing_method=pricing_method,
        rate_per_area=rate_per_area,
        internal_rate_factor=internal_rate_factor,
    )
    area_type = inventory.get_area_type(session, project_id=project.id, area_type_id=area_type_id)
    if pricing_method == AREA_METHOD_INTERNAL_BASE:
        _require_internal_area_role(session, project=project, area_type=area_type)
        _require_one_internal_base(session, configuration_id=configuration.id, area_rule_id=None)
    if pricing_method == AREA_METHOD_FACTOR:
        _require_matching_unit_of_measure(session, project=project, area_type=area_type)

    rule = PricingAreaRule(
        project_id=project.id,
        pricing_configuration_id=configuration.id,
        area_type_id=area_type.id,
        pricing_method=pricing_method,
        rate_per_area=rate_per_area,
        internal_rate_factor=internal_rate_factor,
        sort_order=sort_order,
        created_by_user_id=actor.user_id,
    )
    session.add(rule)
    _flush(session)
    record_event(
        session,
        action="pricing_area_rule.created",
        entity_type=ENTITY_AREA_RULE,
        entity_id=rule.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(rule, _AREA_RULE_FIELDS),
    )
    session.commit()
    session.refresh(rule)
    return rule


def get_area_rule(
    session: Session, *, project_id: uuid.UUID, rule_id: uuid.UUID
) -> PricingAreaRule:
    rule = session.scalars(
        select(PricingAreaRule).where(
            PricingAreaRule.id == rule_id, PricingAreaRule.project_id == project_id
        )
    ).first()
    if rule is None:
        raise NotFoundError("Pricing area rule not found.")
    return rule


def update_area_rule(
    session: Session,
    *,
    project: Project,
    rule: PricingAreaRule,
    actor: ActorContext,
    **changes: object,
) -> PricingAreaRule:
    updates = resolve_updates(changes, fields=_AREA_RULE_UPDATABLE, clearable=_AREA_RULE_CLEARABLE)
    lock_project(session, project.id)
    session.refresh(rule)
    configuration = get_configuration(
        session, project_id=project.id, configuration_id=rule.pricing_configuration_id
    )
    _require_draft(configuration)

    before = _snapshot(rule, _AREA_RULE_FIELDS)
    for name, value in updates.items():
        setattr(rule, name, value)
    _validate_area_rule(
        pricing_method=rule.pricing_method,
        rate_per_area=rule.rate_per_area,
        internal_rate_factor=rule.internal_rate_factor,
    )
    area_type = inventory.get_area_type(
        session, project_id=project.id, area_type_id=rule.area_type_id
    )
    if rule.pricing_method == AREA_METHOD_INTERNAL_BASE and rule.is_active:
        _require_internal_area_role(session, project=project, area_type=area_type)
        _require_one_internal_base(session, configuration_id=configuration.id, area_rule_id=rule.id)
    if rule.pricing_method == AREA_METHOD_FACTOR:
        _require_matching_unit_of_measure(session, project=project, area_type=area_type)
    _flush(session)
    record_event(
        session,
        action="pricing_area_rule.updated",
        entity_type=ENTITY_AREA_RULE,
        entity_id=rule.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(rule, _AREA_RULE_FIELDS),
    )
    session.commit()
    session.refresh(rule)
    return rule


# --------------------------------------------------------------------------- #
# Premium rules
# --------------------------------------------------------------------------- #


def list_premium_rules(
    session: Session, *, configuration_id: uuid.UUID
) -> list[PricingPremiumRule]:
    return list(
        session.scalars(
            select(PricingPremiumRule)
            .where(PricingPremiumRule.pricing_configuration_id == configuration_id)
            .order_by(PricingPremiumRule.sequence, PricingPremiumRule.code)
        )
    )


def _validate_premium_rule(
    session: Session,
    *,
    project: Project,
    source_kind: str,
    match_code: str | None,
    method: str,
    percentage_fraction: Decimal | None,
    amount: Decimal | None,
    custom_field_definition_id: uuid.UUID | None,
    custom_option_code: str | None = None,
) -> None:
    """Refuse a rule that could never match, or that names a number it will not read.

    Every check here is about the rule making sense against the fixed source
    list — not about evaluating anything. A rule naming a view class the project
    has never configured is a rule that will silently price nothing, which is
    worse than being told now.
    """
    if method == "percentage" and percentage_fraction is None:
        raise ValidationError("A percentage premium needs percentage_fraction.")
    if method != "percentage" and amount is None:
        raise ValidationError(f"A {method} premium needs an amount.")
    if method == "percentage" and amount is not None:
        raise ValidationError("amount applies only to a non-percentage premium.")
    if method != "percentage" and percentage_fraction is not None:
        raise ValidationError("percentage_fraction applies only to a percentage premium.")

    if method == PREMIUM_METHOD_PER_AREA and source_kind != "area_type":
        raise ValidationError("A per-area premium must read an area type.")
    if method == PREMIUM_METHOD_PER_ASSET and source_kind not in PREMIUM_ASSET_SOURCES:
        raise ValidationError("A per-asset premium must read parking or storage.")

    if source_kind == "custom_field":
        if custom_field_definition_id is None:
            raise ValidationError("A custom-field premium must name the field it reads.")
        _require_custom_field_source(
            session,
            project=project,
            definition_id=custom_field_definition_id,
            option_code=custom_option_code,
        )
        return
    if source_kind in PREMIUM_FLAG_SOURCES:
        if match_code is not None:
            raise ValidationError(f"A {source_kind} premium takes no match code.")
        return
    if source_kind in PREMIUM_ASSET_SOURCES:
        # Optional here: no subtype means "any parking bay". A subtype that was
        # supplied still has to be one the catalogue knows, or the rule counts
        # nothing for ever.
        if match_code is not None:
            settings_service.require_active_reference_value(
                session,
                category=CATEGORY_SUB_ASSET_SUBTYPE,
                code=match_code,
                country_pack_id=project.country_pack_id,
            )
        return
    if match_code is None:
        raise ValidationError(f"A {source_kind} premium needs a match code.")
    if source_kind == "phase":
        _require_phase_code(session, project=project, code=match_code)
    elif source_kind == "building":
        _require_building_code(session, project=project, code=match_code)
    elif source_kind == "area_type":
        _require_area_type_code(session, project=project, code=match_code)
    else:
        # unit_type, view_class, floor_band, orientation, accessibility,
        # garden_class: the same catalogue inventory validates a unit against,
        # so a rule cannot name a value no unit could ever carry. A typo like
        # 'SEAA_VEIW' saves happily and then prices nothing, which is the
        # failure that never announces itself.
        settings_service.require_active_reference_value(
            session,
            category=PREMIUM_REFERENCE_CATEGORIES[source_kind],
            code=match_code,
            country_pack_id=project.country_pack_id,
        )


def _require_custom_field_source(
    session: Session,
    *,
    project: Project,
    definition_id: uuid.UUID,
    option_code: str | None,
) -> None:
    """A custom-field premium must read a field this project's units can carry.

    The matcher supports exactly two unambiguous readings, and validation is
    what keeps it to two. A **boolean** field prices the unit when the answer is
    yes. An **option** field prices it when the answer is one named choice. Any
    other data type would need a comparison — greater than, contains, between —
    and that is an expression language, which this module does not have and is
    not getting.

    So a decimal, text, integer or date field is refused here rather than
    accepted and silently never matched.
    """
    definition = session.get(CustomFieldDefinition, definition_id)
    if definition is None:
        raise ValidationError("That custom field does not exist.")
    if definition.entity_type != inventory_models.ENTITY_UNIT:
        raise ValidationError("A premium can only read a unit custom field.")
    applicable = {
        item.id for item in inventory_fields.unit_definitions_of_project(session, project=project)
    }
    if definition.id not in applicable:
        # Covers another project's field, another country pack's field, one
        # that has been retired, and one whose validity window has closed.
        raise ValidationError("That custom field does not apply to units of this project.")
    if definition.data_type == "boolean":
        if option_code is not None:
            raise ValidationError("A boolean custom-field premium takes no option code.")
        return
    if definition.data_type != "option":
        raise ValidationError(
            f"A {definition.data_type} custom field cannot drive a premium. "
            "Use a boolean field, or an option field with an option code."
        )
    if option_code is None:
        raise ValidationError("An option custom-field premium must name the option it prices.")
    option = session.scalars(
        select(CustomFieldOption).where(
            CustomFieldOption.definition_id == definition.id,
            CustomFieldOption.code == option_code,
        )
    ).first()
    if option is None:
        raise ValidationError(f"'{option_code}' is not an option of that custom field.")
    if not option.is_active:
        raise ValidationError(f"The option '{option_code}' is no longer active.")


def _require_phase_code(session: Session, *, project: Project, code: str) -> None:
    found = session.scalars(
        select(Phase).where(Phase.project_id == project.id, Phase.code == code)
    ).first()
    if found is None:
        raise ValidationError(f"'{code}' is not a phase of this project.")


def _require_building_code(session: Session, *, project: Project, code: str) -> None:
    found = session.scalars(
        select(Building).where(Building.project_id == project.id, Building.code == code)
    ).first()
    if found is None:
        raise ValidationError(f"'{code}' is not a building of this project.")


def _require_area_type_code(session: Session, *, project: Project, code: str) -> None:
    found = session.scalars(
        select(AreaType).where(AreaType.project_id == project.id, AreaType.code == code)
    ).first()
    if found is None:
        raise ValidationError(f"'{code}' is not an area type of this project.")


def create_premium_rule(
    session: Session,
    *,
    project: Project,
    configuration: PricingConfiguration,
    actor: ActorContext,
    **fields: object,
) -> PricingPremiumRule:
    lock_project(session, project.id)
    session.refresh(configuration)
    _require_draft(configuration)
    fields["code"] = str(fields["code"]).strip().upper()
    if fields.get("match_code") is not None:
        fields["match_code"] = str(fields["match_code"]).strip()
    _validate_premium_rule(
        session,
        project=project,
        source_kind=fields["source_kind"],
        match_code=fields.get("match_code"),
        method=fields["method"],
        percentage_fraction=fields.get("percentage_fraction"),
        amount=fields.get("amount"),
        custom_field_definition_id=fields.get("custom_field_definition_id"),
        custom_option_code=fields.get("custom_option_code"),
    )
    rule = PricingPremiumRule(
        project_id=project.id,
        pricing_configuration_id=configuration.id,
        created_by_user_id=actor.user_id,
        **fields,
    )
    session.add(rule)
    _flush(session)
    record_event(
        session,
        action="pricing_premium_rule.created",
        entity_type=ENTITY_PREMIUM_RULE,
        entity_id=rule.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(rule, _PREMIUM_FIELDS),
    )
    session.commit()
    session.refresh(rule)
    return rule


def get_premium_rule(
    session: Session, *, project_id: uuid.UUID, rule_id: uuid.UUID
) -> PricingPremiumRule:
    rule = session.scalars(
        select(PricingPremiumRule).where(
            PricingPremiumRule.id == rule_id, PricingPremiumRule.project_id == project_id
        )
    ).first()
    if rule is None:
        raise NotFoundError("Pricing premium rule not found.")
    return rule


def update_premium_rule(
    session: Session,
    *,
    project: Project,
    rule: PricingPremiumRule,
    actor: ActorContext,
    **changes: object,
) -> PricingPremiumRule:
    updates = resolve_updates(changes, fields=_PREMIUM_UPDATABLE, clearable=_PREMIUM_CLEARABLE)
    lock_project(session, project.id)
    session.refresh(rule)
    configuration = get_configuration(
        session, project_id=project.id, configuration_id=rule.pricing_configuration_id
    )
    _require_draft(configuration)

    before = _snapshot(rule, _PREMIUM_FIELDS)
    for name, value in updates.items():
        setattr(rule, name, value)
    _validate_premium_rule(
        session,
        project=project,
        source_kind=rule.source_kind,
        match_code=rule.match_code,
        method=rule.method,
        percentage_fraction=rule.percentage_fraction,
        amount=rule.amount,
        custom_field_definition_id=rule.custom_field_definition_id,
        custom_option_code=rule.custom_option_code,
    )
    _flush(session)
    record_event(
        session,
        action="pricing_premium_rule.updated",
        entity_type=ENTITY_PREMIUM_RULE,
        entity_id=rule.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(rule, _PREMIUM_FIELDS),
    )
    session.commit()
    session.refresh(rule)
    return rule


# --------------------------------------------------------------------------- #
# Escalation rules and activations
# --------------------------------------------------------------------------- #


def list_escalation_rules(
    session: Session, *, project_id: uuid.UUID, configuration_id: uuid.UUID | None = None
) -> list[PricingEscalationRule]:
    statement = select(PricingEscalationRule).where(PricingEscalationRule.project_id == project_id)
    if configuration_id is not None:
        statement = statement.where(
            PricingEscalationRule.pricing_configuration_id == configuration_id
        )
    return list(
        session.scalars(
            statement.order_by(PricingEscalationRule.sequence, PricingEscalationRule.code)
        )
    )


def get_escalation_rule(
    session: Session, *, project_id: uuid.UUID, rule_id: uuid.UUID
) -> PricingEscalationRule:
    rule = session.scalars(
        select(PricingEscalationRule).where(
            PricingEscalationRule.id == rule_id, PricingEscalationRule.project_id == project_id
        )
    ).first()
    if rule is None:
        raise NotFoundError("Escalation rule not found.")
    return rule


#: What each trigger input is called when a person is told it is missing.
_TRIGGER_INPUT_LABELS = {
    "threshold_date": "a threshold date",
    "threshold_fraction": "a threshold share of inventory sold",
    "milestone_reference": "a construction milestone reference",
    "market_index_reference": "a market index reference",
}


def _validate_escalation_rule(
    *,
    trigger_type: str,
    trigger_inputs: dict[str, object],
    adjustment_method: str,
    adjustment_percentage_fraction: Decimal | None,
    adjustment_amount: Decimal | None,
) -> None:
    """A rule carries the fact its trigger is about, and no other.

    "Escalate at 30% sold" with no 30% recorded cannot be activated against
    evidence, because there is nothing to compare the evidence to. "Escalate on
    a milestone" naming no milestone is the same shape of hole. And a rule
    carrying two triggers' inputs is a rule two readers read two ways.

    The database says the same thing; this exists so a person is told which
    field is missing instead of receiving a CHECK violation as a 500.
    """
    required = ESCALATION_TRIGGER_INPUTS[trigger_type]
    if trigger_inputs.get(required) is None:
        raise ValidationError(
            f"A {trigger_type} escalation needs {_TRIGGER_INPUT_LABELS[required]}."
        )
    for name in ESCALATION_TRIGGER_INPUTS.values():
        if name != required and trigger_inputs.get(name) is not None:
            raise ValidationError(
                f"{name} applies to a different trigger. "
                f"A {trigger_type} escalation carries only {required}."
            )
    if adjustment_method == ADJUSTMENT_PERCENTAGE and adjustment_percentage_fraction is None:
        raise ValidationError("A percentage escalation needs adjustment_percentage_fraction.")
    if adjustment_method != ADJUSTMENT_PERCENTAGE and adjustment_amount is None:
        raise ValidationError("A fixed escalation needs adjustment_amount.")
    if adjustment_method == ADJUSTMENT_PERCENTAGE and adjustment_amount is not None:
        raise ValidationError("adjustment_amount applies only to a fixed escalation.")
    if adjustment_method != ADJUSTMENT_PERCENTAGE and adjustment_percentage_fraction is not None:
        raise ValidationError(
            "adjustment_percentage_fraction applies only to a percentage escalation."
        )


def create_escalation_rule(
    session: Session,
    *,
    project: Project,
    configuration: PricingConfiguration,
    actor: ActorContext,
    **fields: object,
) -> PricingEscalationRule:
    lock_project(session, project.id)
    session.refresh(configuration)
    _require_draft(configuration)
    fields["code"] = str(fields["code"]).strip().upper()
    scope_type = fields["scope_type"]
    if scope_type == ESCALATION_SCOPE_PHASE and fields.get("phase_id") is None:
        raise ValidationError("A phase-scoped escalation needs a phase.")
    if scope_type == ESCALATION_SCOPE_UNIT_TYPE and not fields.get("unit_type_code"):
        raise ValidationError("A unit-type-scoped escalation needs a unit type code.")
    if scope_type == ESCALATION_SCOPE_PROJECT and (
        fields.get("phase_id") is not None or fields.get("unit_type_code")
    ):
        raise ValidationError("A project-scoped escalation names no phase or unit type.")
    if scope_type == ESCALATION_SCOPE_UNIT_TYPE:
        settings_service.require_active_reference_value(
            session,
            category=CATEGORY_UNIT_TYPE,
            code=str(fields["unit_type_code"]),
            country_pack_id=project.country_pack_id,
        )
    _validate_escalation_rule(
        trigger_type=str(fields["trigger_type"]),
        trigger_inputs={name: fields.get(name) for name in ESCALATION_TRIGGER_INPUTS.values()},
        adjustment_method=str(fields["adjustment_method"]),
        adjustment_percentage_fraction=fields.get("adjustment_percentage_fraction"),  # type: ignore[arg-type]
        adjustment_amount=fields.get("adjustment_amount"),  # type: ignore[arg-type]
    )
    rule = PricingEscalationRule(
        project_id=project.id,
        pricing_configuration_id=configuration.id,
        created_by_user_id=actor.user_id,
        **fields,
    )
    session.add(rule)
    _flush(session)
    record_event(
        session,
        action="pricing_escalation_rule.created",
        entity_type=ENTITY_ESCALATION_RULE,
        entity_id=rule.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(rule, _ESCALATION_FIELDS),
    )
    session.commit()
    session.refresh(rule)
    return rule


def update_escalation_rule(
    session: Session,
    *,
    project: Project,
    rule: PricingEscalationRule,
    actor: ActorContext,
    **changes: object,
) -> PricingEscalationRule:
    updates = resolve_updates(
        changes, fields=_ESCALATION_UPDATABLE, clearable=_ESCALATION_CLEARABLE
    )
    lock_project(session, project.id)
    session.refresh(rule)
    configuration = get_configuration(
        session, project_id=project.id, configuration_id=rule.pricing_configuration_id
    )
    _require_draft(configuration)

    before = _snapshot(rule, _ESCALATION_FIELDS)
    for name, value in updates.items():
        setattr(rule, name, value)
    _validate_escalation_rule(
        trigger_type=rule.trigger_type,
        trigger_inputs={name: getattr(rule, name) for name in ESCALATION_TRIGGER_INPUTS.values()},
        adjustment_method=rule.adjustment_method,
        adjustment_percentage_fraction=rule.adjustment_percentage_fraction,
        adjustment_amount=rule.adjustment_amount,
    )
    _flush(session)
    record_event(
        session,
        action="pricing_escalation_rule.updated",
        entity_type=ENTITY_ESCALATION_RULE,
        entity_id=rule.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(rule, _ESCALATION_FIELDS),
    )
    session.commit()
    session.refresh(rule)
    return rule


def list_activations(
    session: Session, *, project_id: uuid.UUID
) -> list[PricingEscalationActivation]:
    return list(
        session.scalars(
            select(PricingEscalationActivation)
            .where(PricingEscalationActivation.project_id == project_id)
            .order_by(PricingEscalationActivation.effective_date.desc())
        )
    )


def get_activation(
    session: Session, *, project_id: uuid.UUID, activation_id: uuid.UUID
) -> PricingEscalationActivation:
    activation = session.scalars(
        select(PricingEscalationActivation).where(
            PricingEscalationActivation.id == activation_id,
            PricingEscalationActivation.project_id == project_id,
        )
    ).first()
    if activation is None:
        raise NotFoundError("Escalation activation not found.")
    return activation


def activate_escalation(
    session: Session,
    *,
    project: Project,
    rule: PricingEscalationRule,
    actor: ActorContext,
    effective_date: date,
    evidence_reference: str,
    reason: str,
    evidence_value: Decimal | None = None,
    evidence_date: date | None = None,
) -> PricingEscalationActivation:
    """Record that an escalation rule is now in force.

    Deliberately explicit for every trigger type, including ``date``. The system
    could evaluate a date itself, but activation is the moment a price policy
    starts moving money, and a policy that starts because a clock ticked — with
    no named person and no recorded reason — is exactly the silent repricing
    this module exists to prevent.

    Nothing here reprices anything. An activation makes the escalation available
    to the *next* price version generated; the prices already active keep saying
    what they said until somebody generates, approves and activates replacements.
    """
    detail = _require_reason(reason, detail="A reason is required to activate an escalation.")
    evidence = _require_reason(
        evidence_reference, detail="Evidence is required to activate an escalation."
    )
    lock_project(session, project.id)
    session.refresh(rule)
    if not rule.is_active:
        raise ConflictError("That escalation rule is not active.")
    configuration = get_configuration(
        session, project_id=project.id, configuration_id=rule.pricing_configuration_id
    )
    if configuration.status != STATUS_ACTIVE:
        raise ConflictError(
            "Only an escalation of the active pricing configuration can be activated."
        )
    _require_activation_evidence(
        rule,
        effective_date=effective_date,
        evidence_value=evidence_value,
        evidence_date=evidence_date,
    )

    activation = PricingEscalationActivation(
        project_id=project.id,
        pricing_escalation_rule_id=rule.id,
        effective_date=effective_date,
        evidence_value=evidence_value,
        evidence_date=evidence_date,
        evidence_reference=evidence,
        reason=detail,
        approved_by_user_id=actor.user_id,
    )
    session.add(activation)
    _flush(session)
    record_event(
        session,
        action="pricing_escalation.activated",
        entity_type=ENTITY_ESCALATION_ACTIVATION,
        entity_id=activation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=detail,
        after={
            "pricing_escalation_rule_id": rule.id,
            "effective_date": effective_date,
            "evidence_reference": evidence,
            "evidence_value": evidence_value,
        },
    )
    session.commit()
    session.refresh(activation)
    return activation


def _require_activation_evidence(
    rule: PricingEscalationRule,
    *,
    effective_date: date,
    evidence_value: Decimal | None,
    evidence_date: date | None,
) -> None:
    """The evidence has to actually satisfy the rule it is offered against.

    A date rule cannot start before its date. A sales rule stating 30% cannot be
    activated on evidence saying 12% — an approver signing that is signing a
    number the policy does not authorise, and the audit trail would record a
    correctly approved escalation that never became due.

    The two manually evidenced triggers get no derived check, because the
    transactions that would prove them do not exist yet. What they get is a
    date: an approver saying "certified on the 14th" leaves an audit entry
    saying *when* the fact was true, which "certified" alone does not.
    """
    if rule.trigger_type == TRIGGER_DATE:
        if effective_date < rule.threshold_date:
            raise ConflictError(
                f"This escalation is not eligible before {rule.threshold_date.isoformat()}."
            )
        return
    if rule.trigger_type == TRIGGER_SALES_PERCENTAGE:
        if evidence_value is None:
            raise ValidationError(
                "Activating a sales-percentage escalation needs the share of inventory sold "
                "as evidence."
            )
        if evidence_value < ZERO or evidence_value > ONE:
            raise ValidationError("The share of inventory sold is a fraction between 0 and 1.")
        if evidence_value < rule.threshold_fraction:
            raise ConflictError(
                f"This escalation becomes due at {rule.threshold_fraction}. "
                f"The evidence records {evidence_value}."
            )
        return
    if evidence_date is None:
        raise ValidationError("Activating this escalation needs the date the evidence was true.")


def reverse_activation(
    session: Session,
    *,
    project: Project,
    activation: PricingEscalationActivation,
    actor: ActorContext,
    reason: str,
) -> PricingEscalationActivation:
    """Withdraw an activation without erasing it.

    The wrong escalation having been in force for a week is itself a fact, and
    one somebody may need to reconcile a price against. So the row stays, the
    reversal is recorded on it, and a correction is a new activation.
    """
    detail = _require_reason(reason, detail="A reason is required to reverse an activation.")
    lock_project(session, project.id)
    session.refresh(activation)
    if not activation.is_active:
        raise ConflictError("That activation has already been reversed.")

    activation.is_active = False
    activation.reversed_at = func.now()
    activation.reversed_by_user_id = actor.user_id
    activation.reversal_reason = detail
    _flush(session)
    record_event(
        session,
        action="pricing_escalation.reversed",
        entity_type=ENTITY_ESCALATION_ACTIVATION,
        entity_id=activation.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=detail,
        after={"is_active": False},
    )
    session.commit()
    session.refresh(activation)
    return activation


# --------------------------------------------------------------------------- #
# Market benchmarks
# --------------------------------------------------------------------------- #


def list_benchmarks(session: Session, *, project_id: uuid.UUID) -> list[MarketBenchmark]:
    return list(
        session.scalars(
            select(MarketBenchmark)
            .where(MarketBenchmark.project_id == project_id)
            .order_by(MarketBenchmark.comparison_date.desc())
        )
    )


def get_benchmark(
    session: Session, *, project_id: uuid.UUID, benchmark_id: uuid.UUID
) -> MarketBenchmark:
    benchmark = session.scalars(
        select(MarketBenchmark).where(
            MarketBenchmark.id == benchmark_id, MarketBenchmark.project_id == project_id
        )
    ).first()
    if benchmark is None:
        raise NotFoundError("Market benchmark not found.")
    return benchmark


def _require_benchmark_currency(
    session: Session, *, project_id: uuid.UUID, currency_id: uuid.UUID
) -> None:
    """A benchmark is comparable only in the currency the project prices in.

    There is no FX table in this MVP and inventing one to make two numbers
    comparable would be worse than refusing: a deviation computed across a rate
    nobody governs is a number that looks like a fact.
    """
    configuration = active_configuration(session, project_id=project_id)
    if configuration is None:
        return
    if configuration.pricing_currency_id != currency_id:
        raise ValidationError(
            "A benchmark must be quoted in the same currency the project prices in. "
            "There is no conversion here."
        )


def create_benchmark(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    **fields: object,
) -> MarketBenchmark:
    lock_project(session, project.id)
    _require_active_currency(session, fields["currency_id"])  # type: ignore[arg-type]
    _require_benchmark_currency(
        session,
        project_id=project.id,
        currency_id=fields["currency_id"],  # type: ignore[arg-type]
    )
    benchmark = MarketBenchmark(project_id=project.id, created_by_user_id=actor.user_id, **fields)
    session.add(benchmark)
    _flush(session)
    record_event(
        session,
        action="market_benchmark.created",
        entity_type=ENTITY_BENCHMARK,
        entity_id=benchmark.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after=_snapshot(benchmark, _BENCHMARK_FIELDS),
    )
    session.commit()
    session.refresh(benchmark)
    return benchmark


def update_benchmark(
    session: Session,
    *,
    project: Project,
    benchmark: MarketBenchmark,
    actor: ActorContext,
    **changes: object,
) -> MarketBenchmark:
    updates = resolve_updates(changes, fields=_BENCHMARK_UPDATABLE, clearable=_BENCHMARK_CLEARABLE)
    lock_project(session, project.id)
    session.refresh(benchmark)
    before = _snapshot(benchmark, _BENCHMARK_FIELDS)
    for name, value in updates.items():
        setattr(benchmark, name, value)
    _flush(session)
    record_event(
        session,
        action="market_benchmark.updated",
        entity_type=ENTITY_BENCHMARK,
        entity_id=benchmark.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(benchmark, _BENCHMARK_FIELDS),
    )
    session.commit()
    session.refresh(benchmark)
    return benchmark


def select_benchmark(
    session: Session,
    *,
    project_id: uuid.UUID,
    phase_id: uuid.UUID | None,
    unit_type_code: str | None,
) -> MarketBenchmark | None:
    """The one benchmark a unit is compared against, by a stated precedence.

    Most specific first: the unit's type in its phase, then its type anywhere,
    then its phase, then the project. Never an average and never a guess — a
    deviation is only meaningful if everyone can say which observation it was
    measured from.

    Two equally specific active benchmarks cannot exist: a partial unique index
    over the scope, with NULLs treated as equal, refuses the second one.
    """
    candidates: list[tuple[uuid.UUID | None, str | None]] = []
    if unit_type_code and phase_id is not None:
        candidates.append((phase_id, unit_type_code))
    if unit_type_code:
        candidates.append((None, unit_type_code))
    if phase_id is not None:
        candidates.append((phase_id, None))
    candidates.append((None, None))

    for scope_phase, scope_type in candidates:
        statement = select(MarketBenchmark).where(
            MarketBenchmark.project_id == project_id,
            MarketBenchmark.is_active.is_(True),
        )
        statement = statement.where(
            MarketBenchmark.phase_id == scope_phase
            if scope_phase is not None
            else MarketBenchmark.phase_id.is_(None)
        )
        statement = statement.where(
            MarketBenchmark.unit_type_code == scope_type
            if scope_type is not None
            else MarketBenchmark.unit_type_code.is_(None)
        )
        found = session.scalars(statement).first()
        if found is not None:
            return found
    return None


# --------------------------------------------------------------------------- #
# The basis a price is calculated from, and frozen against
# --------------------------------------------------------------------------- #

#: The scale a deviation fraction is stored at, and the range the column holds.
_RATE_EXPONENT = Decimal("0.000001")
_RATE_LIMIT = Decimal("999.999999")


def _text(value: object) -> object:
    """A JSON-safe, order-stable rendering for the frozen basis.

    Decimals become strings and UUIDs become strings, for the same reason the
    audit trail does it: a JSON number is a float, and a float is not an
    acceptable carrier for an area a price was calculated from.
    """
    if isinstance(value, Decimal | uuid.UUID | date):
        return str(value)
    return value


def hierarchy_of(session: Session, unit: Unit) -> tuple[Phase, Building, Floor]:
    """The floor, building and phase a unit sits in.

    Read through the floor every time rather than from a column on the unit:
    PR-MVP-03 deliberately stores the hierarchy once, and a price that read a
    denormalised copy would be pricing a second answer to the same question.
    """
    floor = session.get(Floor, unit.floor_id)
    if floor is None:  # pragma: no cover - a unit cannot exist without its floor
        raise NotFoundError("Floor not found.")
    building = session.get(Building, floor.building_id)
    if building is None:  # pragma: no cover - guaranteed by a composite foreign key
        raise NotFoundError("Building not found.")
    phase = session.get(Phase, building.phase_id)
    if phase is None:  # pragma: no cover - guaranteed by a composite foreign key
        raise NotFoundError("Phase not found.")
    return phase, building, floor


def _sub_asset_detail(session: Session, *, unit_id: uuid.UUID) -> dict[str, dict[str, Any]]:
    """Live parking and storage attached to a unit, counted by subtype.

    Counted from the rows themselves — there is no ``parking_count`` column to
    disagree with them — and both keys are always present so two snapshots are
    comparable even when a unit has none of either.
    """
    rows = session.execute(
        select(
            InventorySubAsset.asset_type,
            InventorySubAsset.subtype_code,
            func.count(InventorySubAsset.id),
        )
        .where(
            InventorySubAsset.linked_unit_id == unit_id,
            InventorySubAsset.is_active.is_(True),
        )
        .group_by(InventorySubAsset.asset_type, InventorySubAsset.subtype_code)
    ).all()
    detail: dict[str, dict[str, Any]] = {
        "parking": {"total": 0, "subtypes": {}},
        "storage": {"total": 0, "subtypes": {}},
    }
    for asset_type, subtype, count in rows:
        bucket = detail.setdefault(asset_type, {"total": 0, "subtypes": {}})
        bucket["total"] += count
        bucket["subtypes"][subtype or ""] = count
    for bucket in detail.values():
        bucket["subtypes"] = dict(sorted(bucket["subtypes"].items()))
    return dict(sorted(detail.items()))


def _custom_values(
    session: Session, *, project: Project, unit: Unit
) -> tuple[dict[str, object], dict[uuid.UUID, object]]:
    """The unit's configurable values, by field key and by definition.

    Only definitions in force today that apply to this unit's type. Visibility
    is deliberately not applied: a premium a sensitive field drives must price
    the unit identically for every reader, exactly as PR-MVP-03 counts a hidden
    field toward completeness. What is withheld is the field's name, and the
    component carries the pricing rule's own label instead.
    """
    definitions = inventory_fields.definitions_for(
        session,
        entity_type="unit",
        project=project,
        unit_type_code=unit.unit_type_code,
    )
    if not definitions:
        return {}, {}
    by_id = {definition.id: definition for definition in definitions}
    rows = session.scalars(
        select(UnitCustomFieldValue).where(
            UnitCustomFieldValue.unit_id == unit.id,
            UnitCustomFieldValue.definition_id.in_(by_id.keys()),
        )
    )
    by_key: dict[str, object] = {}
    by_definition: dict[uuid.UUID, object] = {}
    for row in rows:
        definition = by_id[row.definition_id]
        by_key[definition.field_key] = row.value_json
        by_definition[row.definition_id] = row.value_json
    return dict(sorted(by_key.items())), by_definition


def descriptive_snapshot(session: Session, *, unit: Unit) -> dict[str, Any]:
    """What the unit was *called* when it was priced. Never compared.

    A reference, a number and an asset class are labels. Inventory deliberately
    does not clear ``pricing_approved`` when one of them is corrected, because
    renaming A-101 to A1-101 does not make it a different apartment — and a
    fingerprint that included them would then refuse the very approval inventory
    had just decided was still valid.

    They are kept because an auditor reading a two-year-old price wants to know
    which unit it was, in the words used at the time. They are kept *here*, apart
    from :func:`pricing_basis`, so that keeping them can never mean comparing
    them.
    """
    phase, building, floor = hierarchy_of(session, unit)
    return {
        "unit_reference": unit.unit_reference,
        "unit_number": unit.unit_number,
        "asset_class": unit.asset_class,
        "phase_code": phase.code,
        "building_code": building.code,
        "floor_code": floor.code,
    }


def pricing_basis(
    session: Session, *, project: Project, unit: Unit, schedule: UnitAreaSchedule
) -> dict[str, Any]:
    """Everything about the unit that the *calculation* reads, as it is now.

    This is the fingerprint a draft freezes and every later step compares
    against. Membership is a deliberate rule rather than a convenience: a fact
    belongs here only if changing it could change the arithmetic, which is
    exactly the set inventory clears ``pricing_approved`` for
    (:data:`~app.modules.inventory.service.PRICING_RELEVANT_UNIT_FIELDS`), plus
    the hierarchy premiums match on, the approved measurement, the priced
    sub-assets and the configurable values a premium can read.

    It holds no pricing policy — the version pins that by identifier — and no
    escalations, which are a commercial decision that produces new versions
    rather than invalidating existing ones. And it holds no labels: see
    :func:`descriptive_snapshot`.
    """
    phase, building, floor = hierarchy_of(session, unit)
    areas = {
        area_type.code: str(value.raw_area)
        for value, area_type in session.execute(
            select(UnitAreaValue, AreaType)
            .join(AreaType, AreaType.id == UnitAreaValue.area_type_id)
            .where(UnitAreaValue.unit_area_schedule_id == schedule.id)
        ).all()
    }
    values, _ = _custom_values(session, project=project, unit=unit)
    return {
        "unit": {
            "id": str(unit.id),
            "unit_type_code": unit.unit_type_code,
            "furnishing_specification_code": unit.furnishing_specification_code,
            "floor_band_code": unit.floor_band_code,
            "orientation_code": unit.orientation_code,
            "view_class_code": unit.view_class_code,
            "accessibility_code": unit.accessibility_code,
            "garden_class_code": unit.garden_class_code,
            "is_corner": unit.is_corner,
            "pool_access": unit.pool_access,
            "plot_coverage_fraction": _text(unit.plot_coverage_fraction),
        },
        # Codes, not only identifiers: a premium rule matches a phase or a
        # building by its code, so recoding one really does change what the
        # calculation would produce.
        "hierarchy": {
            "phase_id": str(phase.id),
            "phase_code": phase.code,
            "building_id": str(building.id),
            "building_code": building.code,
            "floor_id": str(floor.id),
        },
        "area_schedule": {
            "id": str(schedule.id),
            "revision_code": schedule.revision_code,
        },
        "areas": dict(sorted(areas.items())),
        "sub_assets": _sub_asset_detail(session, unit_id=unit.id),
        "custom_values": {key: _text(value) for key, value in values.items()},
    }


def _current_basis(session: Session, *, project: Project, unit: Unit) -> dict[str, Any] | None:
    """The unit's basis as it stands, or ``None`` when it has no approved areas."""
    schedule = inventory.approved_schedule(session, unit_id=unit.id)
    if schedule is None:
        return None
    return pricing_basis(session, project=project, unit=unit, schedule=schedule)


def _require_current_basis(session: Session, *, version: UnitPriceVersion) -> None:
    """Refuse to move a price forward when the unit has changed underneath it.

    A submitted, approved or activated price says "this unit, measured this way,
    with these features, costs this". If any of that has moved, the sentence is
    no longer true, and the fix is a new version rather than an approval that
    quietly means something else.

    Only the pricing fingerprint is compared. A label correction is not a change
    of unit, and refusing an approval over one would teach approvers that the
    message does not mean what it says.
    """
    unit = session.get(Unit, version.unit_id)
    if unit is None or unit.project_id != version.project_id:  # pragma: no cover - FK guaranteed
        raise NotFoundError("Unit not found.")
    project = session.get(Project, version.project_id)
    if project is None:  # pragma: no cover - FK guaranteed
        raise NotFoundError("Project not found.")
    current = _current_basis(session, project=project, unit=unit)
    if current is None:
        raise ConflictError("Unit pricing basis changed. Generate a new price version.")
    frozen = version.basis_snapshot_json.get("pricing_basis")
    if frozen != current:
        raise ConflictError("Unit pricing basis changed. Generate a new price version.")


# --------------------------------------------------------------------------- #
# Matching a unit against the configured rules
# --------------------------------------------------------------------------- #


def _area_inputs(
    session: Session,
    *,
    configuration: PricingConfiguration,
    schedule: UnitAreaSchedule,
) -> tuple[list[AreaInput], dict[str, Decimal], Decimal | None]:
    """The measured areas of a unit, paired with the rules that price them.

    An area with no rule is priced at nothing and says so by its absence from
    the breakdown; an area whose rule is inactive is the same. Both are
    deliberate configuration, not a silent zero.
    """
    rules = {
        rule.area_type_id: rule
        for rule in list_area_rules(session, configuration_id=configuration.id)
        if rule.is_active
    }
    rows = session.execute(
        select(UnitAreaValue, AreaType)
        .join(AreaType, AreaType.id == UnitAreaValue.area_type_id)
        .where(UnitAreaValue.unit_area_schedule_id == schedule.id)
        .order_by(AreaType.sort_order, AreaType.code)
    ).all()
    inputs: list[AreaInput] = []
    by_code: dict[str, Decimal] = {}
    internal_area: Decimal | None = None
    for value, area_type in rows:
        by_code[area_type.code] = value.raw_area
        rule = rules.get(area_type.id)
        if rule is None:
            continue
        if rule.pricing_method == AREA_METHOD_INTERNAL_BASE:
            internal_area = value.raw_area
        inputs.append(
            AreaInput(
                area_type_id=area_type.id,
                code=area_type.code,
                label=area_type.label,
                unit_of_measure=area_type.unit_of_measure,
                raw_area=value.raw_area,
                pricing_method=rule.pricing_method,
                rate_per_area=rule.rate_per_area,
                internal_rate_factor=rule.internal_rate_factor,
                area_rule_id=rule.id,
                sort_order=rule.sort_order,
            )
        )
    return inputs, by_code, internal_area


def _matches(
    rule: PricingPremiumRule,
    *,
    unit: Unit,
    phase: Phase,
    building: Building,
    areas: dict[str, Decimal],
    sub_assets: dict[str, dict[str, Any]],
    custom_values: dict[uuid.UUID, object],
) -> tuple[bool, Decimal, str | None]:
    """Whether one rule applies to one unit, and how much of it there is.

    A long, flat, explicit branch on a closed list of source kinds. It is longer
    than a lookup table would be and shorter than the expression evaluator a
    lookup table becomes: each branch names a real column, and there is nothing
    here that could ever be handed a string to execute.
    """
    kind = rule.source_kind
    if kind == "phase":
        return phase.code == rule.match_code, Decimal("1"), None
    if kind == "building":
        return building.code == rule.match_code, Decimal("1"), None
    if kind == "unit_type":
        return unit.unit_type_code == rule.match_code, Decimal("1"), None
    if kind == "view_class":
        return unit.view_class_code == rule.match_code, Decimal("1"), None
    if kind == "floor_band":
        return unit.floor_band_code == rule.match_code, Decimal("1"), None
    if kind == "orientation":
        return unit.orientation_code == rule.match_code, Decimal("1"), None
    if kind == "accessibility":
        return unit.accessibility_code == rule.match_code, Decimal("1"), None
    if kind == "garden_class":
        return unit.garden_class_code == rule.match_code, Decimal("1"), None
    if kind == "corner":
        return unit.is_corner, Decimal("1"), None
    if kind == "pool_access":
        return unit.pool_access, Decimal("1"), None
    if kind in PREMIUM_ASSET_SOURCES:
        bucket = sub_assets.get(kind, {"total": 0, "subtypes": {}})
        count = bucket["subtypes"].get(rule.match_code, 0) if rule.match_code else bucket["total"]
        return count > 0, Decimal(count), "asset"
    if kind == "area_type":
        area = areas.get(rule.match_code or "")
        if area is None or area <= 0:
            return False, Decimal("0"), None
        return True, area, "area"
    if kind == "custom_field":
        value = custom_values.get(rule.custom_field_definition_id)  # type: ignore[arg-type]
        if rule.custom_option_code is not None:
            return value == rule.custom_option_code, Decimal("1"), None
        # Without an option code the only unambiguous reading is a boolean fact.
        # "Any value at all" would make a premium fire on a comment field.
        return value is True, Decimal("1"), None
    return False, Decimal("0"), None  # pragma: no cover - the set is closed by a CHECK


def _premium_inputs(
    session: Session,
    *,
    configuration: PricingConfiguration,
    unit: Unit,
    phase: Phase,
    building: Building,
    areas: dict[str, Decimal],
    sub_assets: dict[str, dict[str, Any]],
    custom_values: dict[uuid.UUID, object],
    area_units: dict[str, str],
) -> list[PremiumInput]:
    """Every configured premium that this unit actually qualifies for."""
    inputs: list[PremiumInput] = []
    for rule in list_premium_rules(session, configuration_id=configuration.id):
        if not rule.is_active:
            continue
        applies, quantity, quantity_kind = _matches(
            rule,
            unit=unit,
            phase=phase,
            building=building,
            areas=areas,
            sub_assets=sub_assets,
            custom_values=custom_values,
        )
        if not applies:
            continue
        unit_of_measure = None
        if quantity_kind == "area":
            unit_of_measure = area_units.get(rule.match_code or "")
        elif quantity_kind == "asset":
            unit_of_measure = rule.source_kind
        inputs.append(
            PremiumInput(
                premium_rule_id=rule.id,
                code=rule.code,
                label=rule.label,
                source_kind=rule.source_kind,
                method=rule.method,
                percentage_fraction=rule.percentage_fraction,
                amount=rule.amount,
                eligible_base=rule.eligible_base,
                stacking_method=rule.stacking_method or configuration.premium_stacking_default,
                sequence=rule.sequence,
                quantity=quantity,
                quantity_unit=unit_of_measure,
            )
        )
    return inputs


def _escalation_inputs(
    session: Session,
    *,
    configuration: PricingConfiguration,
    unit: Unit,
    phase: Phase,
    as_of: date,
) -> list[EscalationInput]:
    """Activated escalations of the active policy that reach this unit.

    Scoped by the rule, dated by the activation, and drawn only from the
    configuration being priced under: a new pricing policy restates the
    escalations it wants rather than inheriting a superseded policy's.
    """
    rows = session.execute(
        select(PricingEscalationActivation, PricingEscalationRule)
        .join(
            PricingEscalationRule,
            PricingEscalationRule.id == PricingEscalationActivation.pricing_escalation_rule_id,
        )
        .where(
            PricingEscalationActivation.project_id == configuration.project_id,
            PricingEscalationActivation.is_active.is_(True),
            PricingEscalationActivation.effective_date <= as_of,
            PricingEscalationRule.is_active.is_(True),
            PricingEscalationRule.pricing_configuration_id == configuration.id,
        )
        .order_by(PricingEscalationRule.sequence, PricingEscalationRule.code)
    ).all()
    inputs: list[EscalationInput] = []
    for activation, rule in rows:
        if rule.scope_type == ESCALATION_SCOPE_PHASE and rule.phase_id != phase.id:
            continue
        if (
            rule.scope_type == ESCALATION_SCOPE_UNIT_TYPE
            and rule.unit_type_code != unit.unit_type_code
        ):
            continue
        inputs.append(
            EscalationInput(
                activation_id=activation.id,
                code=rule.code,
                label=rule.label,
                adjustment_method=rule.adjustment_method,
                adjustment_percentage_fraction=rule.adjustment_percentage_fraction,
                adjustment_amount=rule.adjustment_amount,
                cumulative=rule.cumulative,
                sequence=rule.sequence,
            )
        )
    return inputs


# --------------------------------------------------------------------------- #
# Market comparison
# --------------------------------------------------------------------------- #


def _deviation(price_per_area: Decimal, benchmark_price: Decimal) -> Decimal:
    raw = (price_per_area - benchmark_price) / benchmark_price
    quantised = raw.quantize(_RATE_EXPONENT, rounding=ROUND_HALF_UP)
    # The column holds six decimals in nine digits. A price a thousand times the
    # benchmark is a configuration error rather than a market position, and
    # storing it as an overflow would turn that error into a 500.
    if quantised > _RATE_LIMIT:
        return _RATE_LIMIT
    if quantised < -_RATE_LIMIT:
        return -_RATE_LIMIT
    return quantised


def benchmark_observation(benchmark: MarketBenchmark | None) -> dict[str, Any] | None:
    """The benchmark as it read at the moment a price was calculated.

    Frozen into the version rather than followed by reference. A benchmark row
    is governed configuration that people revise; reinterpreting a submitted
    price against a figure that arrived afterwards would silently rewrite what
    the approver was shown, and "within tolerance" would stop being a statement
    about a decision anybody actually made.

    Everything needed to reproduce the classification is here, plus the source
    and date needed to explain it.
    """
    if benchmark is None:
        return None
    return {
        "id": str(benchmark.id),
        "area_basis": benchmark.area_basis,
        "benchmark_price_per_area": str(benchmark.benchmark_price_per_area),
        "tolerance_fraction": str(benchmark.tolerance_fraction),
        "comparison_date": benchmark.comparison_date.isoformat(),
        "source_name": benchmark.source_name,
        "source_reference": benchmark.source_reference,
        "currency_id": str(benchmark.currency_id),
    }


def classify_against(
    observation: dict[str, Any] | None,
    *,
    reference_price: Decimal,
    internal_area: Decimal | None,
    weighted_area: Decimal | None,
) -> tuple[Decimal | None, Decimal | None, str]:
    """Where one price sits against one frozen benchmark observation.

    Pure arithmetic on the observation and the price handed in, so the same
    classification can be re-derived whenever the price changes — which is the
    whole point: an overridden draft that keeps the flag its pre-override price
    earned is a false signal on a management screen.
    """
    if observation is None:
        return None, None, FLAG_NONE
    benchmark_price = Decimal(observation["benchmark_price_per_area"])
    tolerance = Decimal(observation["tolerance_fraction"])
    area = internal_area if observation["area_basis"] == BASIS_INTERNAL else weighted_area
    if area is None or area <= 0:
        return benchmark_price, None, FLAG_NONE
    deviation = _deviation(money(reference_price / area), benchmark_price)
    if deviation > tolerance:
        flag = FLAG_ABOVE
    elif deviation < -tolerance:
        flag = FLAG_BELOW
    else:
        flag = FLAG_WITHIN
    return benchmark_price, deviation, flag


def compare_to_market(
    session: Session,
    *,
    project_id: uuid.UUID,
    phase_id: uuid.UUID,
    unit_type_code: str | None,
    currency_id: uuid.UUID,
    reference_price: Decimal,
    internal_area: Decimal | None,
    weighted_area: Decimal | None,
) -> tuple[MarketBenchmark | None, dict[str, Any] | None, Decimal | None, Decimal | None, str]:
    """Compare a price against the one benchmark that governs this unit."""
    benchmark = select_benchmark(
        session, project_id=project_id, phase_id=phase_id, unit_type_code=unit_type_code
    )
    if benchmark is None:
        return None, None, None, None, FLAG_NONE
    if benchmark.currency_id != currency_id:
        raise ValidationError(
            f"Benchmark '{benchmark.source_name}' is quoted in a different currency from "
            "this project's pricing. There is no conversion here."
        )
    observation = benchmark_observation(benchmark)
    price, deviation, flag = classify_against(
        observation,
        reference_price=reference_price,
        internal_area=internal_area,
        weighted_area=weighted_area,
    )
    return benchmark, observation, price, deviation, flag


def _apply_market(version: UnitPriceVersion) -> None:
    """Re-derive a version's market position from its own current final price.

    Called after anything that can move ``reference_price_ex_tax`` on a draft,
    and again immediately before submission, so the figure an approver reads was
    computed from the number they are approving — not from the number the rules
    first produced.
    """
    price, deviation, flag = classify_against(
        version.basis_snapshot_json.get("market_benchmark"),
        reference_price=version.reference_price_ex_tax,
        internal_area=version.internal_area_snapshot,
        weighted_area=version.weighted_area_snapshot,
    )
    version.market_benchmark_price_snapshot = price
    version.market_deviation_fraction = deviation
    version.market_flag = flag


# --------------------------------------------------------------------------- #
# Unit price versions
# --------------------------------------------------------------------------- #


def list_price_versions(
    session: Session, *, unit_id: uuid.UUID, internal: bool
) -> list[UnitPriceVersion]:
    """A unit's price history, newest first.

    ``internal`` decides whether anything other than live and historical prices
    is included. A sales advisor quoting from a draft would be quoting a number
    nobody has agreed to, so drafts, submissions and pending approvals are not
    theirs to see.
    """
    statement = select(UnitPriceVersion).where(UnitPriceVersion.unit_id == unit_id)
    if not internal:
        statement = statement.where(UnitPriceVersion.status.in_([STATUS_ACTIVE, STATUS_SUPERSEDED]))
    return list(session.scalars(statement.order_by(UnitPriceVersion.version_number.desc())))


def get_price_version(
    session: Session, *, project_id: uuid.UUID, version_id: uuid.UUID
) -> UnitPriceVersion:
    version = session.scalars(
        select(UnitPriceVersion).where(
            UnitPriceVersion.id == version_id, UnitPriceVersion.project_id == project_id
        )
    ).first()
    if version is None:
        raise NotFoundError("Price version not found.")
    return version


def active_price(session: Session, *, unit_id: uuid.UUID) -> UnitPriceVersion | None:
    return session.scalars(
        select(UnitPriceVersion).where(
            UnitPriceVersion.unit_id == unit_id, UnitPriceVersion.status == STATUS_ACTIVE
        )
    ).first()


def list_components(session: Session, *, version_id: uuid.UUID) -> list[UnitPriceComponent]:
    return list(
        session.scalars(
            select(UnitPriceComponent)
            .where(UnitPriceComponent.unit_price_version_id == version_id)
            .order_by(UnitPriceComponent.sequence)
        )
    )


def _totals_from(components: list[UnitPriceComponent]) -> dict[str, Decimal]:
    """Re-derive every stored total by adding up the lines a reader can see.

    Deliberately the only place totals come from, including after an override:
    a total computed any other way is a number that can disagree with the
    breakdown printed beneath it.
    """
    buckets = {
        "base_area_value": [COMPONENT_BASE_INTERNAL, COMPONENT_BASE_ATTACHED],
        "scope_adjustment_total": [COMPONENT_SCOPE_ADJUSTMENT],
        "premium_total": [
            COMPONENT_FEATURE_PREMIUM,
            COMPONENT_SUB_ASSET_PREMIUM,
            COMPONENT_PREMIUM_CAP,
        ],
        "premium_cap_adjustment": [COMPONENT_PREMIUM_CAP],
        "escalation_total": [COMPONENT_ESCALATION],
        "paid_upgrade_total": [COMPONENT_PAID_UPGRADE],
    }
    totals = dict.fromkeys(buckets, ZERO)
    reference = ZERO
    for component in components:
        reference += component.final_amount
        for name, types in buckets.items():
            if component.component_type in types:
                totals[name] += component.final_amount
    totals["reference_price_ex_tax"] = reference
    return totals


def _apply_totals(version: UnitPriceVersion, totals: dict[str, Decimal]) -> None:
    for name, value in totals.items():
        setattr(version, name, value)


def _per_area(price: Decimal, area: Decimal | None) -> Decimal | None:
    if area is None or area <= 0:
        return None
    return money(price / area)


def _build_version(
    session: Session,
    *,
    project: Project,
    unit: Unit,
    actor: ActorContext,
    configuration: PricingConfiguration,
    internal_rate_override: Decimal | None,
    override_reason: str | None,
    upgrades: tuple[UpgradeInput, ...],
    valid_from: date | None,
    change_reason: str | None,
) -> UnitPriceVersion:
    """Calculate and persist one draft price. Does not commit.

    The caller owns the transaction, because bulk generation is all-or-nothing:
    a half-generated price list is worse than a refused one, since nobody can
    tell which half was priced under which rules.
    """
    schedule = inventory.approved_schedule(session, unit_id=unit.id)
    if schedule is None:
        raise ConflictError(
            f"Unit {unit.unit_reference} has no approved area schedule to price from."
        )
    if not unit.is_active:
        raise ConflictError(f"Unit {unit.unit_reference} is not active.")

    phase, building, _ = hierarchy_of(session, unit)
    areas, areas_by_code, internal_area = _area_inputs(
        session, configuration=configuration, schedule=schedule
    )
    area_units = {area.code: area.unit_of_measure for area in areas}
    sub_assets = _sub_asset_detail(session, unit_id=unit.id)
    _, custom_by_definition = _custom_values(session, project=project, unit=unit)

    rate = configuration.base_internal_rate
    if internal_rate_override is not None:
        _require_reason(override_reason, detail="An overridden internal rate needs a reason.")
        rate = internal_rate_override

    # The effective date is a calculation input, not a label applied afterwards:
    # which escalations are in force depends on it. Resolve it once, here, and
    # store the same value on the version — a draft whose date could be edited
    # later would be a price calculated for one day and made effective on
    # another, with a different escalation set behind it.
    effective_from = valid_from or inventory_fields.business_today()
    _require_configuration_validity(configuration, effective_from=effective_from)
    as_of = effective_from
    source = PricingInput(
        base_internal_rate=rate,
        areas=tuple(areas),
        premiums=tuple(
            _premium_inputs(
                session,
                configuration=configuration,
                unit=unit,
                phase=phase,
                building=building,
                areas=areas_by_code,
                sub_assets=sub_assets,
                custom_values=custom_by_definition,
                area_units=area_units,
            )
        ),
        escalations=tuple(
            _escalation_inputs(
                session, configuration=configuration, unit=unit, phase=phase, as_of=as_of
            )
        ),
        upgrades=upgrades,
        maximum_premium_fraction=configuration.maximum_premium_fraction,
    )
    result = calculator.calculate(source)

    lines = inventory.area_lines(session, project_id=project.id, schedule=schedule)
    weighted_area = inventory.weighted_saleable_area(lines)
    benchmark, observation, benchmark_price, deviation, flag = compare_to_market(
        session,
        project_id=project.id,
        phase_id=phase.id,
        unit_type_code=unit.unit_type_code,
        currency_id=configuration.pricing_currency_id,
        reference_price=result.reference_price_ex_tax,
        internal_area=internal_area,
        weighted_area=weighted_area,
    )

    highest = session.scalar(
        select(func.max(UnitPriceVersion.version_number)).where(UnitPriceVersion.unit_id == unit.id)
    )
    version = UnitPriceVersion(
        project_id=project.id,
        unit_id=unit.id,
        version_number=(highest or 0) + 1,
        pricing_configuration_id=configuration.id,
        unit_area_schedule_id=schedule.id,
        status=STATUS_DRAFT,
        currency_id=configuration.pricing_currency_id,
        valid_from=effective_from,
        base_area_value=result.base_area_value,
        scope_adjustment_total=result.scope_adjustment_total,
        premium_total=result.premium_total,
        premium_cap_adjustment=result.premium_cap_adjustment,
        escalation_total=result.escalation_total,
        paid_upgrade_total=result.paid_upgrade_total,
        reference_price_ex_tax=result.reference_price_ex_tax,
        internal_area_snapshot=internal_area,
        weighted_area_snapshot=weighted_area,
        price_per_internal_area=_per_area(result.reference_price_ex_tax, internal_area),
        price_per_weighted_area=_per_area(result.reference_price_ex_tax, weighted_area),
        market_benchmark_id=benchmark.id if benchmark is not None else None,
        market_benchmark_price_snapshot=benchmark_price,
        market_deviation_fraction=deviation,
        market_flag=flag,
        basis_snapshot_json={
            "pricing_basis": pricing_basis(session, project=project, unit=unit, schedule=schedule),
            "descriptive": descriptive_snapshot(session, unit=unit),
            "market_benchmark": observation,
            "configuration": {
                "id": str(configuration.id),
                "version_number": configuration.version_number,
                "base_internal_rate": str(configuration.base_internal_rate),
                "applied_internal_rate": str(rate),
                "premium_stacking_default": configuration.premium_stacking_default,
                "maximum_premium_fraction": _text(configuration.maximum_premium_fraction),
            },
            "escalation_activation_ids": sorted(
                str(item.activation_id) for item in source.escalations
            ),
            "effective_from": effective_from.isoformat(),
        },
        change_reason=(change_reason or override_reason or None),
        created_by_user_id=actor.user_id,
    )
    session.add(version)
    _flush(session)

    for component in result.components:
        session.add(
            UnitPriceComponent(
                project_id=project.id,
                unit_price_version_id=version.id,
                sequence=component.sequence,
                component_type=component.component_type,
                code=component.code,
                label=component.label,
                quantity=component.quantity,
                unit_of_measure=component.unit_of_measure,
                basis_amount=component.basis_amount,
                rate=component.rate,
                factor=component.factor,
                calculated_amount=component.calculated_amount,
                final_amount=component.calculated_amount,
                area_rule_id=component.area_rule_id,
                premium_rule_id=component.premium_rule_id,
                escalation_activation_id=component.escalation_activation_id,
            )
        )
    _flush(session)
    record_event(
        session,
        action="unit_price_version.created",
        entity_type=ENTITY_PRICE_VERSION,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=change_reason,
        after=_snapshot(version, _VERSION_FIELDS),
    )
    return version


def generate_price_version(
    session: Session,
    *,
    project: Project,
    unit: Unit,
    actor: ActorContext,
    internal_rate_override: Decimal | None = None,
    override_reason: str | None = None,
    paid_upgrades: tuple[UpgradeInput, ...] = (),
    valid_from: date | None = None,
    change_reason: str | None = None,
) -> UnitPriceVersion:
    """Draft one price for one unit.

    Locks the project and then the unit, in that order, before reading the
    approved area schedule. Area approval takes the same unit lock, so the two
    serialise: a draft is never calculated from geometry that a newly approved
    schedule has already replaced.
    """
    project = lock_project(session, project.id)
    unit = inventory.lock_unit(session, project_id=project.id, unit_id=unit.id)
    configuration = active_configuration(session, project_id=project.id)
    if configuration is None:
        raise ConflictError(
            "This project has no active pricing configuration. Approve and activate one first."
        )
    try:
        version = _build_version(
            session,
            project=project,
            unit=unit,
            actor=actor,
            configuration=configuration,
            internal_rate_override=internal_rate_override,
            override_reason=override_reason,
            upgrades=paid_upgrades,
            valid_from=valid_from,
            change_reason=change_reason,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(version)
    return version


def generate_price_versions(
    session: Session,
    *,
    project: Project,
    units: list[Unit],
    actor: ActorContext,
    valid_from: date | None = None,
    change_reason: str | None = None,
) -> list[UnitPriceVersion]:
    """Draft prices for a selection of units, all of them or none.

    247 units is the reference development, and pricing them one request at a
    time is the thing that pushes the work back into a spreadsheet. Units are
    locked in a deterministic identifier order so two bulk runs cannot deadlock
    against each other, and one refusal rolls the whole batch back: a price list
    where some units were priced under one policy and the rest were not is worse
    than no price list.
    """
    if not units:
        raise ValidationError("Select at least one unit to price.")
    if len(units) > MAX_BULK_UNITS:
        raise ValidationError(f"One request may price at most {MAX_BULK_UNITS} units.")

    project = lock_project(session, project.id)
    configuration = active_configuration(session, project_id=project.id)
    if configuration is None:
        raise ConflictError(
            "This project has no active pricing configuration. Approve and activate one first."
        )
    created: list[UnitPriceVersion] = []
    try:
        for unit_id in sorted(unit.id for unit in units):
            locked = inventory.lock_unit(session, project_id=project.id, unit_id=unit_id)
            created.append(
                _build_version(
                    session,
                    project=project,
                    unit=locked,
                    actor=actor,
                    configuration=configuration,
                    internal_rate_override=None,
                    override_reason=None,
                    upgrades=(),
                    valid_from=valid_from,
                    change_reason=change_reason,
                )
            )
        record_event(
            session,
            action="unit_price_version.bulk_generated",
            entity_type=ENTITY_PRICE_VERSION,
            entity_id=project.id,
            correlation_id=actor.correlation_id,
            actor_user_id=actor.user_id,
            reason=change_reason,
            after={"units": len(created), "configuration_id": configuration.id},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    for version in created:
        session.refresh(version)
    return created


def update_price_version(
    session: Session,
    *,
    project: Project,
    version: UnitPriceVersion,
    actor: ActorContext,
    change_reason: str | None = None,
    overrides: list[dict[str, object]] | None = None,
) -> UnitPriceVersion:
    """Change a draft price, and only a draft.

    An override replaces one calculated line with a stated amount and a stated
    reason. Both are kept: the approver sees what the rules produced and what a
    person decided instead, which is the whole value of allowing an override at
    all. Once submitted, nothing here can run again.

    ``valid_from`` is deliberately absent. The effective date decided which
    escalations the calculation read, so moving it afterwards would leave a
    price whose components describe a different date from the one it claims.
    Changing the effective date means generating a new version.
    """
    lock_project(session, project.id)
    inventory.lock_unit(session, project_id=project.id, unit_id=version.unit_id)
    session.refresh(version)
    if version.status != STATUS_DRAFT:
        raise ConflictError("Only a draft price version can be changed.")

    before = _snapshot(version, _VERSION_FIELDS)
    if change_reason is not None:
        version.change_reason = change_reason.strip() or None

    if overrides:
        components = {
            component.sequence: component
            for component in list_components(session, version_id=version.id)
        }
        for entry in overrides:
            sequence = int(entry["sequence"])  # type: ignore[arg-type]
            component = components.get(sequence)
            if component is None:
                raise ValidationError(f"This price has no component {sequence}.")
            amount = entry.get("override_amount")
            if amount is None:
                component.override_amount = None
                component.override_reason = None
                component.final_amount = component.calculated_amount
                continue
            reason = _require_reason(
                entry.get("override_reason"),  # type: ignore[arg-type]
                detail=f"Component {sequence} needs a reason for its override.",
            )
            component.override_amount = Decimal(str(amount))
            component.override_reason = reason
            component.final_amount = component.override_amount
        session.flush()

    totals = _totals_from(list_components(session, version_id=version.id))
    _apply_totals(version, totals)
    version.price_per_internal_area = _per_area(
        version.reference_price_ex_tax, version.internal_area_snapshot
    )
    version.price_per_weighted_area = _per_area(
        version.reference_price_ex_tax, version.weighted_area_snapshot
    )
    # An override moved the price, so the market position it earned moved with
    # it. Leaving "within tolerance" beside a price that is no longer within it
    # is a false signal on the screen an approver decides from.
    _apply_market(version)
    _flush(session)
    record_event(
        session,
        action="unit_price_version.updated",
        entity_type=ENTITY_PRICE_VERSION,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=change_reason,
        before=before,
        after=_snapshot(version, _VERSION_FIELDS),
    )
    session.commit()
    session.refresh(version)
    return version


# --------------------------------------------------------------------------- #
# The price lifecycle
# --------------------------------------------------------------------------- #


def _validate_submittable(session: Session, *, version: UnitPriceVersion) -> None:
    """Everything an approver would otherwise have to check by hand.

    A clean submission must not be able to fail at approval for a reason the
    system already knew. The basis comparison is the load-bearing one: it is
    what stops an approval signing off geometry that has since been re-measured.
    """
    configuration = get_configuration(
        session,
        project_id=version.project_id,
        configuration_id=version.pricing_configuration_id,
    )
    if configuration.status != STATUS_ACTIVE:
        raise ConflictError(
            "This price was calculated under a pricing configuration that is no longer "
            "active. Generate a new price version."
        )
    if version.currency_id != configuration.pricing_currency_id:
        raise ConflictError("This price is not in the project's pricing currency.")
    _require_configuration_validity(configuration, effective_from=version.valid_from)
    components = list_components(session, version_id=version.id)
    if not components:
        raise ConflictError("This price has no components.")
    missing = [
        component.sequence
        for component in components
        if component.override_amount is not None and not (component.override_reason or "").strip()
    ]
    if missing:
        raise ValidationError(
            "Every overridden component needs a reason: " + ", ".join(str(m) for m in missing)
        )
    totals = _totals_from(components)
    if totals["reference_price_ex_tax"] != version.reference_price_ex_tax:
        raise ConflictError(
            "This price does not reconcile with its components. Generate a new version."
        )
    if version.reference_price_ex_tax <= ZERO:
        raise ValidationError("A price must be greater than zero before it can be submitted.")
    # The market position has to describe the price being moved, not the one the
    # rules first produced. Submission recalculates it a line above; every later
    # step re-checks, because from submission onwards the version is immutable
    # and a mismatch would mean something wrote to it that should not have.
    price, deviation, flag = classify_against(
        version.basis_snapshot_json.get("market_benchmark"),
        reference_price=version.reference_price_ex_tax,
        internal_area=version.internal_area_snapshot,
        weighted_area=version.weighted_area_snapshot,
    )
    if (
        version.market_benchmark_price_snapshot != price
        or version.market_deviation_fraction != deviation
        or version.market_flag != flag
    ):
        raise ConflictError(
            "This price's market comparison does not match its final amount. "
            "Generate a new version."
        )
    _require_current_basis(session, version=version)


def submit_price_version(
    session: Session,
    *,
    project: Project,
    version: UnitPriceVersion,
    actor: ActorContext,
    change_reason: str | None = None,
    commit: bool = True,
) -> UnitPriceVersion:
    lock_project(session, project.id)
    inventory.lock_unit(session, project_id=project.id, unit_id=version.unit_id)
    session.refresh(version)
    if version.status != STATUS_DRAFT:
        raise ConflictError("Only a draft price version can be submitted.")
    # The last moment this is still a draft, and so the last moment the market
    # position can be brought in line with the price actually being submitted.
    # From here the version is immutable and the figure has to already be right.
    _apply_market(version)
    _validate_submittable(session, version=version)

    before = _snapshot(version, _VERSION_FIELDS)
    version.status = STATUS_SUBMITTED
    version.submitted_at = func.now()
    version.submitted_by_user_id = actor.user_id
    if change_reason:
        version.change_reason = change_reason.strip()
    _flush(session)
    record_event(
        session,
        action="unit_price_version.submitted",
        entity_type=ENTITY_PRICE_VERSION,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=change_reason,
        before=before,
        after=_snapshot(version, _VERSION_FIELDS),
    )
    if commit:
        session.commit()
        session.refresh(version)
    return version


def return_price_version(
    session: Session,
    *,
    project: Project,
    version: UnitPriceVersion,
    actor: ActorContext,
    reason: str,
) -> UnitPriceVersion:
    detail = _require_reason(reason, detail="A reason is required to return a price version.")
    lock_project(session, project.id)
    inventory.lock_unit(session, project_id=project.id, unit_id=version.unit_id)
    session.refresh(version)
    if version.status != STATUS_SUBMITTED:
        raise ConflictError("Only a submitted price version can be returned.")

    before = _snapshot(version, _VERSION_FIELDS)
    version.status = STATUS_DRAFT
    version.submitted_at = None
    version.submitted_by_user_id = None
    version.change_reason = detail
    _flush(session)
    record_event(
        session,
        action="unit_price_version.returned",
        entity_type=ENTITY_PRICE_VERSION,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=detail,
        before=before,
        after=_snapshot(version, _VERSION_FIELDS),
    )
    session.commit()
    session.refresh(version)
    return version


def approve_price_version(
    session: Session,
    *,
    project: Project,
    version: UnitPriceVersion,
    actor: ActorContext,
    reason: str,
    commit: bool = True,
) -> UnitPriceVersion:
    """Sanction a submitted price. It is not yet the list price.

    Deliberately does not set ``pricing_approved`` on the unit. Approved means
    "may be activated"; active means "this is what the unit sells for", and a
    release gate that opened on the first of those would open on a price nobody
    had put live.
    """
    detail = _require_reason(reason, detail="A reason is required to approve a price version.")
    lock_project(session, project.id)
    inventory.lock_unit(session, project_id=project.id, unit_id=version.unit_id)
    session.refresh(version)
    if version.status != STATUS_SUBMITTED:
        raise ConflictError("Only a submitted price version can be approved.")
    require_different_checker(actor, maker_user_id=version.submitted_by_user_id)
    _validate_submittable(session, version=version)

    before = _snapshot(version, _VERSION_FIELDS)
    version.status = STATUS_APPROVED
    version.approved_at = func.now()
    version.approved_by_user_id = actor.user_id
    version.change_reason = detail
    _flush(session)
    record_event(
        session,
        action="unit_price_version.approved",
        entity_type=ENTITY_PRICE_VERSION,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        reason=detail,
        before=before,
        after=_snapshot(version, _VERSION_FIELDS),
    )
    if commit:
        session.commit()
        session.refresh(version)
    return version


def activate_price_version(
    session: Session,
    *,
    project: Project,
    version: UnitPriceVersion,
    actor: ActorContext,
    commit: bool = True,
) -> UnitPriceVersion:
    """Make an approved price the unit's list price.

    The only path in this system that sets ``Unit.pricing_approved``. There is
    no button, no PATCH and no override anywhere else, which is what makes the
    release gate mean something: a unit is releasable because a price was put
    live for it, not because somebody ticked a box.

    Project then unit, in that order, and the basis is re-read under the unit
    lock. An inventory change racing this either commits first — and the
    activation refuses, because the price no longer describes the unit — or
    commits after, and clears ``pricing_approved`` itself.
    """
    project = lock_project(session, project.id)
    unit = inventory.lock_unit(session, project_id=project.id, unit_id=version.unit_id)
    session.refresh(version)
    if version.status != STATUS_APPROVED:
        raise ConflictError("Only an approved price version can be activated.")
    # Active means *the unit's live list price*, so a price cannot become active
    # before the day it takes effect. Publishing next month's number today would
    # supersede the price the unit is actually being sold at, and every reader —
    # the register, Unit 360, a quote — would take the future figure for the
    # current one.
    #
    # Checked before anything is written, so a premature attempt leaves the
    # current price, its approval and the release gate exactly as they were. The
    # version simply stays approved until somebody activates it on a day it
    # governs: the same explicit, dated, human step a future pricing
    # configuration waits for, and for the same reason — nothing in this module
    # publishes a price because a clock ticked.
    today = inventory_fields.business_today()
    if version.valid_from > today:
        raise ConflictError(
            f"This price does not become effective until {version.valid_from.isoformat()}."
        )
    _validate_submittable(session, version=version)

    # The date the version was calculated for, and no other. Activation is
    # publication, not recalculation: supplying a different date here would put
    # a price live on a day its escalation set was never evaluated against.
    effective = version.valid_from
    current = active_price(session, unit_id=unit.id)
    before = _snapshot(version, _VERSION_FIELDS)
    if current is not None and current.id != version.id:
        superseded_before = _snapshot(current, _VERSION_FIELDS)
        current.status = STATUS_SUPERSEDED
        current.superseded_at = func.now()
        current.valid_to = effective
        session.flush()
        record_event(
            session,
            action="unit_price_version.superseded",
            entity_type=ENTITY_PRICE_VERSION,
            entity_id=current.id,
            correlation_id=actor.correlation_id,
            actor_user_id=actor.user_id,
            before=superseded_before,
            after=_snapshot(current, _VERSION_FIELDS),
        )

    version.status = STATUS_ACTIVE
    version.activated_at = func.now()
    version.activated_by_user_id = actor.user_id
    unit.pricing_approved = True
    _flush(session)
    record_event(
        session,
        action="unit_price_version.activated",
        entity_type=ENTITY_PRICE_VERSION,
        entity_id=version.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        before=before,
        after=_snapshot(version, _VERSION_FIELDS),
    )
    if commit:
        session.commit()
        session.refresh(version)
    return version


def bulk_transition(
    session: Session,
    *,
    project: Project,
    versions: list[UnitPriceVersion],
    actor: ActorContext,
    action: str,
    reason: str | None = None,
) -> list[UnitPriceVersion]:
    """Submit, approve or activate a selection of prices — all of them or none.

    One transaction, because a half-approved price list is a price list nobody
    can publish: some units would be sellable at a sanctioned number and the
    rest at last month's, with nothing on screen saying which.
    """
    if not versions:
        raise ValidationError("Select at least one price version.")
    if len(versions) > MAX_BULK_UNITS:
        raise ValidationError(f"One request may act on at most {MAX_BULK_UNITS} price versions.")

    handlers = {
        "submit": lambda version: submit_price_version(
            session,
            project=project,
            version=version,
            actor=actor,
            change_reason=reason,
            commit=False,
        ),
        "approve": lambda version: approve_price_version(
            session,
            project=project,
            version=version,
            actor=actor,
            reason=reason or "",
            commit=False,
        ),
        "activate": lambda version: activate_price_version(
            session, project=project, version=version, actor=actor, commit=False
        ),
    }
    handler = handlers.get(action)
    if handler is None:  # pragma: no cover - the route restricts the action
        raise ValidationError("Unknown bulk pricing action.")

    ordered = sorted(versions, key=lambda version: (version.unit_id, version.version_number))
    changed: list[UnitPriceVersion] = []
    try:
        for version in ordered:
            changed.append(handler(version))
        record_event(
            session,
            action=f"unit_price_version.bulk_{action}",
            entity_type=ENTITY_PRICE_VERSION,
            entity_id=project.id,
            correlation_id=actor.correlation_id,
            actor_user_id=actor.user_id,
            reason=reason,
            after={"versions": len(changed)},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    for version in changed:
        session.refresh(version)
    return changed


# --------------------------------------------------------------------------- #
# Reading a unit's pricing
# --------------------------------------------------------------------------- #


def repricing_required(unit: Unit, *, active: UnitPriceVersion | None) -> bool:
    """Whether a live price has been left describing a unit that has changed.

    The price stays exactly as it was — it is what the unit was offered at, and
    deleting it would erase a commercial fact. What changes is that inventory
    cleared ``pricing_approved``, so the unit cannot be released until somebody
    prices it again.
    """
    return active is not None and not unit.pricing_approved


def price_register(
    session: Session,
    *,
    project: Project,
    visible_units: Select[tuple[uuid.UUID]] | None,
    phase_id: uuid.UUID | None = None,
    building_id: uuid.UUID | None = None,
    unit_type_code: str | None = None,
    market_flag: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[tuple[Unit, UnitPriceVersion | None]], dict[str, int]]:
    """A page of units with their live price, and totals over the whole set.

    The counts describe every unit the filters select and the caller may see —
    not the page. PR-MVP-02 shipped a permit aggregate summed over one page and
    PR-MVP-03 removed a release aggregate for the same reason; a management
    total that silently means "of the twenty on screen" is the bug being avoided
    a third time.
    """
    statement = (
        select(Unit)
        .join(Floor, Floor.id == Unit.floor_id)
        .join(Building, Building.id == Floor.building_id)
        .where(Unit.project_id == project.id, Unit.is_active.is_(True))
    )
    if visible_units is not None:
        statement = statement.where(Unit.id.in_(visible_units))
    if phase_id is not None:
        statement = statement.where(Building.phase_id == phase_id)
    if building_id is not None:
        statement = statement.where(Floor.building_id == building_id)
    if unit_type_code is not None:
        statement = statement.where(Unit.unit_type_code == unit_type_code)

    joined = statement.add_columns(UnitPriceVersion).outerjoin(
        UnitPriceVersion,
        (UnitPriceVersion.unit_id == Unit.id) & (UnitPriceVersion.status == STATUS_ACTIVE),
    )
    if market_flag is not None:
        joined = joined.where(UnitPriceVersion.market_flag == market_flag)

    rows = session.execute(joined.order_by(Unit.unit_reference).limit(limit).offset(offset)).all()
    # The same query without the page window. Counting a page and calling the
    # answer a project total is the aggregate bug this codebase has now fixed
    # twice; it is not shipping a third.
    every = session.execute(joined).all()
    totals = {
        "total": len(every),
        "priced": sum(1 for _, version in every if version is not None),
        "not_priced": sum(1 for _, version in every if version is None),
        "repricing_required": sum(
            1 for unit, version in every if repricing_required(unit, active=version)
        ),
    }
    return [(unit, version) for unit, version in rows], totals


# --------------------------------------------------------------------------- #
# Quote preview
# --------------------------------------------------------------------------- #


def _applicable_taxes(
    session: Session, *, country_pack_id: uuid.UUID, as_of: date
) -> list[TaxRule]:
    """Every configured sale tax in force on ``as_of`` for this country.

    Read from the settings module's own configuration rather than a second tax
    model. If a jurisdiction has none configured, the answer is "not configured"
    and not a guessed percentage: an invented rate on a quote is worse than an
    absent one, because somebody will believe it.
    """
    return list(
        session.scalars(
            select(TaxRule)
            .where(
                TaxRule.country_pack_id == country_pack_id,
                TaxRule.applies_to == "sale",
                TaxRule.is_active.is_(True),
                TaxRule.valid_from <= as_of,
                (TaxRule.valid_to.is_(None)) | (TaxRule.valid_to >= as_of),
            )
            .order_by(TaxRule.tax_code)
        )
    )


def _tax_lines(rules: list[TaxRule], *, net: Decimal) -> list[dict[str, Any]]:
    """Tax on a net contract price, each rule computed on its own stated basis.

    ``net_amount`` means the configured rate applies to the amount as given.
    ``gross_amount`` means the amount is already tax-inclusive, so the tax
    inside it is ``net x rate / (1 + rate)``. Two different arithmetic rules,
    both real, and the configuration says which — this does not choose.
    """
    lines: list[dict[str, Any]] = []
    for rule in rules:
        if rule.calculation_basis == "gross_amount":
            amount = money(net * rule.rate_fraction / (Decimal("1") + rule.rate_fraction))
        else:
            amount = money(net * rule.rate_fraction)
        lines.append(
            {
                "tax_code": rule.tax_code,
                "label": rule.label,
                "rate_fraction": rule.rate_fraction,
                "calculation_basis": rule.calculation_basis,
                "amount": amount,
            }
        )
    return lines


def _approval_flags(
    session: Session,
    *,
    project: Project,
    gross: Decimal,
    concession: Decimal,
) -> dict[str, Any]:
    """Whether this quote would need sanctioning, read from country thresholds.

    Uses the approval-threshold configuration PR-MVP-01 already governs rather
    than a second approval table. Nothing is persisted: the actual sale
    exception, with its recorded decision, belongs to PR-MVP-05.
    """
    result: dict[str, Any] = {
        "approval_required": False,
        "approval_reason": None,
        "threshold_rate_fraction": None,
        "threshold_amount": None,
        "required_role": None,
    }
    try:
        thresholds = settings_service.get_approval_thresholds(
            session, country_pack_id=project.country_pack_id
        )
    except NotFoundError:
        return result

    result["threshold_rate_fraction"] = thresholds.discount_review_rate_fraction
    result["threshold_amount"] = thresholds.discount_review_amount
    reasons: list[str] = []
    if thresholds.discount_review_rate_fraction is not None and gross > ZERO:
        fraction = (concession / gross).quantize(_RATE_EXPONENT, rounding=ROUND_HALF_UP)
        if fraction > thresholds.discount_review_rate_fraction:
            reasons.append(
                f"The concession is {fraction} of the quoted price, above the "
                f"{thresholds.discount_review_rate_fraction} review threshold."
            )
    if (
        thresholds.discount_review_amount is not None
        and concession > thresholds.discount_review_amount
    ):
        reasons.append(
            f"The concession exceeds the {thresholds.discount_review_amount} review threshold."
        )
    if reasons:
        result["approval_required"] = True
        result["approval_reason"] = " ".join(reasons)
        if thresholds.pricing_requires_commercial_approval:
            result["required_role"] = "approver_cfo"
        elif thresholds.pricing_requires_finance_approval:
            result["required_role"] = "finance"
    return result


def quote_preview(
    session: Session,
    *,
    project: Project,
    unit: Unit,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    """Model a commercial offer against a unit's live price, writing nothing.

    No client, no reservation, no sale, no stored exception — this is arithmetic
    on a screen, and PR-MVP-05 owns the transaction that freezes any of it.

    The distinction the whole function exists to preserve: a **price
    concession** reduces what the buyer contracts to pay, and a **seller cost**
    does not. A 5,000 furniture package on a 200,000 unit leaves the contract at
    200,000 and the seller's net revenue at 195,000. Folding the two together
    produces a contract price nobody agreed to and a commission base that is
    wrong, so they are separate lines here and separate subtotals in the result.
    """
    active = active_price(session, unit_id=unit.id)
    if active is None:
        raise ConflictError("This unit has no active price to quote from.")
    # A live price whose unit has since changed stays readable — it is what the
    # unit was offered at, and history is not deleted here. What it may not do
    # is become the basis of a *new* commercial offer: inventory already
    # withdrew the pricing approval, and quoting from it anyway would step
    # around the release gate rather than through it.
    #
    # Two checks rather than one. ``pricing_approved`` is the flag inventory
    # maintains and the register displays; the basis comparison is the same
    # arithmetic every transition runs, and catches a drift the flag missed.
    if not unit.pricing_approved:
        raise ConflictError("This unit requires repricing before a quote can be prepared.")
    try:
        _require_current_basis(session, version=active)
    except ConflictError as exc:
        raise ConflictError("This unit requires repricing before a quote can be prepared.") from exc
    configuration = get_configuration(
        session,
        project_id=project.id,
        configuration_id=active.pricing_configuration_id,
    )

    def amount(name: str) -> Decimal:
        value = inputs.get(name)
        return money(Decimal(str(value)) if value is not None else ZERO)

    reference = active.reference_price_ex_tax
    paid_upgrade = amount("paid_upgrade_amount")

    plan_fraction = inputs.get("payment_plan_adjustment_fraction")
    if plan_fraction is None:
        plan_fraction = configuration.default_payment_plan_adjustment_fraction
    plan_fraction = Decimal(str(plan_fraction)) if plan_fraction is not None else ZERO
    plan_adjustment = money(reference * plan_fraction)

    gross = reference + paid_upgrade + plan_adjustment

    discount_fraction = inputs.get("discount_fraction")
    discount_fraction = Decimal(str(discount_fraction)) if discount_fraction is not None else ZERO
    percentage_discount = money(gross * discount_fraction)
    fixed_discount = amount("discount_amount")
    cash_discount = percentage_discount + fixed_discount
    seller_credit = amount("seller_credit")

    net_contract = gross - cash_discount - seller_credit
    if net_contract < ZERO:
        raise ValidationError("The concessions on this quote exceed the price.")

    package_cost = amount("package_cost")
    upgrade_allowance_cost = amount("upgrade_allowance_cost")
    commission_support = amount("commission_support")
    financing_subsidy = amount("financing_subsidy")
    extended_terms_npv_cost = amount("extended_terms_npv_cost")
    seller_costs = money(
        package_cost
        + upgrade_allowance_cost
        + commission_support
        + financing_subsidy
        + extended_terms_npv_cost
    )
    effective_net_revenue = net_contract - seller_costs

    as_of = inventory_fields.business_today()
    tax_rules = _applicable_taxes(session, country_pack_id=project.country_pack_id, as_of=as_of)
    # Tax is charged on what the buyer contracts to pay, never on the seller's
    # net revenue: a package the seller absorbs does not reduce the taxable
    # consideration, and computing it the other way would understate the tax and
    # mix a seller cost into a buyer figure.
    taxes = _tax_lines(tax_rules, net=net_contract)
    # Quantised even when it is zero: a figure that leaves as "0" beside others
    # that leave as "0.00" reads as a different kind of number, and a quote is
    # one place where every amount should look like an amount.
    tax_total = money(sum((line["amount"] for line in taxes), ZERO))
    buyer_paid_fees = amount("buyer_paid_fees")
    total_payable = net_contract + tax_total + buyer_paid_fees

    approval = _approval_flags(
        session, project=project, gross=gross, concession=cash_discount + seller_credit
    )
    return {
        "unit_id": unit.id,
        "unit_reference": unit.unit_reference,
        "unit_price_version_id": active.id,
        "version_number": active.version_number,
        "currency_id": active.currency_id,
        "approved_reference_price_ex_tax": reference,
        "paid_upgrade_price": paid_upgrade,
        "payment_plan_price_adjustment": plan_adjustment,
        "payment_plan_adjustment_fraction": plan_fraction,
        "gross_quoted_price_ex_tax": gross,
        "cash_discount": cash_discount,
        "seller_credit": seller_credit,
        "net_contract_price_ex_tax": net_contract,
        "seller_package_cost": package_cost,
        "upgrade_allowance_cost": upgrade_allowance_cost,
        "commission_support": commission_support,
        "financing_subsidy": financing_subsidy,
        "extended_terms_npv_cost": extended_terms_npv_cost,
        "seller_cost_total": seller_costs,
        "effective_net_revenue_preview": effective_net_revenue,
        "tax_status": "configured" if tax_rules else "not_configured",
        "tax_treatment_code": configuration.tax_treatment_code,
        "taxes": taxes,
        "tax_total": tax_total,
        "buyer_paid_fees": buyer_paid_fees,
        "total_buyer_payable_preview": total_payable,
        "offer_valid_days": configuration.offer_valid_days,
        "price_lock_days": configuration.price_lock_days,
        "reservation_expiry_days": configuration.reservation_expiry_days,
        **approval,
    }
