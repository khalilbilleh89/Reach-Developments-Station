"""Project, land, planning, permit and document logic.

Records facts and enforces the rules that keep them coherent. It calculates
nothing beyond date arithmetic over values it already holds: there is no
valuation, no yield, no forecast and no scoring here.

Every mutation writes its audit event inside the same transaction as the change
and commits once, so a change and its accountability record cannot come apart.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.patching import resolve_updates
from app.modules.access.models import ROLE_SYSTEM_ADMIN, User
from app.modules.audit.service import record_event
from app.modules.projects.models import (
    CATEGORY_DOCUMENT_TYPE,
    CATEGORY_OWNERSHIP_TYPE,
    CATEGORY_PERMIT_TYPE,
    CATEGORY_PROJECT_TYPE,
    CATEGORY_TITLE_STATUS,
    CATEGORY_ZONING_CLASS,
    PERMIT_STATUS_NOT_STARTED,
    PERMIT_STATUSES,
    PHASE_SCOPE_ALL,
    PROJECT_STATUS_SETUP,
    DocumentReference,
    LandParcel,
    Permit,
    PermitStatusEvent,
    PlanningControl,
    Project,
    UserProjectAccess,
)
from app.modules.settings.models import CountryPack, Currency
from app.modules.settings.service import require_active_reference_value

ENTITY_PROJECT = "project"
ENTITY_PROJECT_ACCESS = "project_access"
ENTITY_LAND_PARCEL = "land_parcel"
ENTITY_PLANNING_CONTROL = "planning_control"
ENTITY_PERMIT = "permit"
ENTITY_DOCUMENT_REFERENCE = "document_reference"

#: The fixed role a project manager must hold. Assigning a manager does not
#: create a second role concept; it points at someone who already has this one.
ROLE_PROJECT_MANAGER = "project_manager"

#: A project code is typed, read aloud and quoted in correspondence, so it is
#: kept to characters that survive all three.
_PROJECT_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{2,32}$")

#: Constraint names mapped to the conflict a client should see. The application
#: checks first for a clear message; this catches the race where two requests
#: both pass that check and the database decides between them.
_CODE_CONSTRAINT = "uq_projects_code"
_ACCESS_CONSTRAINT = "uq_user_project_access_project_id_user_id"
_PLOT_CONSTRAINT = "uq_land_parcels_project_id_plot_number"
_PERMIT_CODE_CONSTRAINT = "uq_permits_project_id_permit_code"
_PLANNING_CONSTRAINT = "uq_planning_controls_parcel_id"


def _snapshot(instance: object, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: getattr(instance, field) for field in fields}


def _flush(session: Session, *, constraint: str, detail: str) -> None:
    """Flush, turning one anticipated unique violation into a clean conflict.

    Only the named constraint is translated. Any other integrity error is a bug
    or an unanticipated invariant, and swallowing it as a 409 would hide it.
    """
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        violated = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if violated == constraint:
            raise ConflictError(detail) from None
        raise


# --------------------------------------------------------------------------- #
# Shared validation
# --------------------------------------------------------------------------- #


def _require_active_currency(session: Session, currency_id: uuid.UUID, *, label: str) -> Currency:
    currency = session.get(Currency, currency_id)
    if currency is None:
        raise ValidationError(f"{label} does not exist.")
    if not currency.is_active:
        raise ValidationError(f"{label} must be active.")
    return currency


def _require_active_country_pack(session: Session, country_pack_id: uuid.UUID) -> CountryPack:
    pack = session.get(CountryPack, country_pack_id)
    if pack is None:
        raise ValidationError("Country pack does not exist.")
    if not pack.is_active:
        raise ValidationError("Country pack must be active.")
    return pack


def _require_active_user(session: Session, user_id: uuid.UUID, *, label: str) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise ValidationError(f"{label} does not exist.")
    if not user.is_active:
        raise ValidationError(f"{label} must be an active user.")
    return user


def _require_ordered_dates(start: date | None, end: date | None, *, detail: str) -> None:
    if start is not None and end is not None and end < start:
        raise ValidationError(detail)


# --------------------------------------------------------------------------- #
# Project access
# --------------------------------------------------------------------------- #

_ACCESS_FIELDS = ("id", "project_id", "user_id", "is_active")


def _find_access(
    session: Session, *, project_id: uuid.UUID, user_id: uuid.UUID
) -> UserProjectAccess | None:
    return session.scalars(
        select(UserProjectAccess).where(
            UserProjectAccess.project_id == project_id,
            UserProjectAccess.user_id == user_id,
        )
    ).first()


def list_project_access(session: Session, *, project_id: uuid.UUID) -> list[UserProjectAccess]:
    """Every membership row, revoked ones included: access history is the point."""
    return list(
        session.scalars(
            select(UserProjectAccess)
            .where(UserProjectAccess.project_id == project_id)
            .order_by(UserProjectAccess.granted_at)
        )
    )


def _ensure_access(
    session: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> UserProjectAccess:
    """Grant access if it is missing, reactivate it if it was revoked.

    Does not commit: the caller owns the transaction, so granting a manager
    their access and recording the assignment either both happen or neither
    does. Idempotent — re-granting an active membership changes nothing and
    writes no event, so repeated calls do not litter the audit trail.
    """
    existing = _find_access(session, project_id=project_id, user_id=user_id)
    if existing is not None and existing.is_active:
        return existing

    if existing is not None:
        before = _snapshot(existing, _ACCESS_FIELDS)
        existing.is_active = True
        existing.granted_at = func.now()
        existing.granted_by_user_id = actor_user_id
        existing.revoked_at = None
        existing.revoked_by_user_id = None
        session.flush()
        record_event(
            session,
            action="project_access.reactivated",
            entity_type=ENTITY_PROJECT_ACCESS,
            entity_id=existing.id,
            correlation_id=correlation_id,
            actor_user_id=actor_user_id,
            before=before,
            after=_snapshot(existing, _ACCESS_FIELDS),
        )
        return existing

    access = UserProjectAccess(
        project_id=project_id,
        user_id=user_id,
        is_active=True,
        granted_by_user_id=actor_user_id,
    )
    session.add(access)
    _flush(
        session,
        constraint=_ACCESS_CONSTRAINT,
        detail="That user already has an access record for this project.",
    )
    record_event(
        session,
        action="project_access.granted",
        entity_type=ENTITY_PROJECT_ACCESS,
        entity_id=access.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        after=_snapshot(access, _ACCESS_FIELDS),
    )
    return access


def grant_project_access(
    session: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> UserProjectAccess:
    """Give a user access to a project, or restore access they used to have."""
    _require_active_user(session, user_id, label="User")
    access = _ensure_access(
        session,
        project_id=project_id,
        user_id=user_id,
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    session.commit()
    session.refresh(access)
    return access


def revoke_project_access(
    session: Session,
    *,
    project: Project,
    user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> UserProjectAccess:
    """Withdraw access, keeping the row so the history stays readable."""
    # Lock the project before reading the manager, so a concurrent assignment of
    # this same user as manager cannot commit against a stale "not the manager"
    # reading of it. Both sides of the invariant queue on the same row.
    project = lock_project(session, project.id)
    access = _find_access(session, project_id=project.id, user_id=user_id)
    if access is None:
        raise NotFoundError("That user has no access record for this project.")
    if project.project_manager_user_id == user_id:
        raise ConflictError(
            "The assigned project manager cannot lose access. "
            "Reassign or clear the project manager first."
        )
    if not access.is_active:
        return access

    before = _snapshot(access, _ACCESS_FIELDS)
    access.is_active = False
    access.revoked_at = func.now()
    access.revoked_by_user_id = actor_user_id
    session.flush()
    record_event(
        session,
        action="project_access.revoked",
        entity_type=ENTITY_PROJECT_ACCESS,
        entity_id=access.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after=_snapshot(access, _ACCESS_FIELDS),
    )
    session.commit()
    session.refresh(access)
    return access


# --------------------------------------------------------------------------- #
# Projects
# --------------------------------------------------------------------------- #

_PROJECT_FIELDS = (
    "id",
    "code",
    "name",
    "developer_entity",
    "country_pack_id",
    "city",
    "location",
    "latitude",
    "longitude",
    "project_type_code",
    "status",
    "base_currency_id",
    "reporting_currency_id",
    "fiscal_year_start_month",
    "planned_start",
    "planned_completion",
    "project_manager_user_id",
)

#: ``code`` is absent on purpose: a project code is immutable once issued.
_PROJECT_UPDATABLE = (
    "name",
    "developer_entity",
    "country_pack_id",
    "city",
    "location",
    "latitude",
    "longitude",
    "project_type_code",
    "status",
    "base_currency_id",
    "reporting_currency_id",
    "fiscal_year_start_month",
    "planned_start",
    "planned_completion",
    "project_manager_user_id",
)
_PROJECT_CLEARABLE = frozenset(
    {
        "city",
        "location",
        "latitude",
        "longitude",
        "project_type_code",
        "planned_start",
        "planned_completion",
        "project_manager_user_id",
    }
)

#: Changing the legal or monetary basis of a project after work has started
#: would silently restate every amount already recorded against it. Allowed
#: only while the project is still being set up, and then only while the
#: guards below still hold.
_BASIS_FIELDS = ("country_pack_id", "base_currency_id", "reporting_currency_id")


def lock_project(session: Session, project_id: uuid.UUID) -> Project:
    """Take the project row for update and return the persisted state.

    The project row is the synchronisation point for anything whose invariant
    spans more than one of its records — the manager/access pairing, the permit
    prerequisite graph, and from PR-MVP-03 the inventory hierarchy. Locking it
    first means two requests decide in sequence against committed state rather
    than each against its own stale read.

    Public because inventory needs the same lock and must take it through a
    contract rather than by reaching into this module's queries: one lock, one
    ordering, one place to change it.
    """
    locked = session.scalars(
        select(Project)
        .where(Project.id == project_id)
        .with_for_update()
        # Without this, SQLAlchemy takes the lock but hands back the copy
        # already in the identity map — so the row would be locked and the
        # attributes still stale, which is the failure this lock exists to
        # prevent. Nothing has been mutated yet at any call site, so there are
        # no pending changes for the refresh to discard.
        .execution_options(populate_existing=True)
    ).first()
    if locked is None:
        raise NotFoundError("Project not found.")
    return locked


def _guard_base_currency_change(session: Session, project_id: uuid.UUID) -> None:
    """Refuse to re-denominate money that has already been recorded.

    Changing the base currency does not touch the stored numbers — it changes
    what they *mean*. A parcel bought for 1,000,000 JOD would silently become
    1,000,000 USD. There is no FX and no restatement in this MVP, and inventing
    one here would be worse than refusing.
    """
    has_money = session.scalars(
        select(LandParcel.id)
        .where(
            LandParcel.project_id == project_id,
            (LandParcel.purchase_price.is_not(None)) | (LandParcel.acquisition_fees.is_not(None)),
        )
        .limit(1)
        .union_all(
            select(Permit.id)
            .where(Permit.project_id == project_id, Permit.fee_amount.is_not(None))
            .limit(1)
        )
    ).first()
    if has_money is not None:
        raise ConflictError(
            "Project base currency cannot be changed after monetary amounts have been recorded."
        )


def _guard_country_pack_change(session: Session, project_id: uuid.UUID) -> None:
    """Refuse to move recorded records under a different jurisdiction.

    Parcels, permits and document references carry codes validated against the
    country pack that was current when they were entered — ownership type, title
    status, zoning class, permit type, document type. Repointing the project at
    another country would leave every one of them describing the wrong legal
    regime, and reconciling that is a controlled migration, not a field edit.
    """
    for model in (LandParcel, PlanningControl, Permit, DocumentReference):
        existing = session.scalars(
            select(model.id).where(model.project_id == project_id).limit(1)
        ).first()
        if existing is not None:
            raise ConflictError(
                "Country pack cannot be changed after project land, planning, "
                "permits or documents have been recorded."
            )


def normalize_project_code(code: str) -> str:
    """Uppercase and validate a project code.

    Case is normalised rather than rejected so that a code typed in lower case
    is still the same project, but the stored form is canonical: uniqueness is
    enforced on the stored value.
    """
    candidate = code.strip()
    if not _PROJECT_CODE_PATTERN.match(candidate):
        raise ValidationError(
            "Project code must be 2 to 32 characters using letters, digits, hyphen or underscore."
        )
    return candidate.upper()


def _has_active_access(session: Session, *, project_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    access = _find_access(session, project_id=project_id, user_id=user_id)
    return access is not None and access.is_active


def _assign_project_manager(
    session: Session,
    *,
    project: Project,
    user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_is_system_admin: bool,
    correlation_id: uuid.UUID,
) -> None:
    """Validate a manager, and settle who is allowed to give them access.

    Two rules meet here and both have to hold. A manager who cannot open the
    project is not managing it — so an administrator's assignment creates the
    access row in the same transaction. But project membership is security
    administration, reserved to a System Administrator; if assigning a manager
    also granted access, any Project Manager could add whoever they liked to a
    project simply by naming them. So a non-administrator may only hand the role
    to someone who is already a member.
    """
    user = _require_active_user(session, user_id, label="Project manager")
    if ROLE_PROJECT_MANAGER not in user.role_keys:
        raise ValidationError("The project manager must hold the Project Manager role.")

    if not actor_is_system_admin and not _has_active_access(
        session, project_id=project.id, user_id=user_id
    ):
        raise ConflictError(
            "Only a System Administrator can grant project access. Add the user to "
            "the project before assigning them as project manager."
        )

    access = _ensure_access(
        session,
        project_id=project.id,
        user_id=user_id,
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    _widen_manager_phase_scope(
        session,
        access=access,
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )


def _widen_manager_phase_scope(
    session: Session,
    *,
    access: UserProjectAccess,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> None:
    """Give the incoming manager the whole project back.

    The rule is that the assigned project manager sees every phase. Inventory
    already refuses to narrow the manager, but that only closes one direction:
    narrow an ordinary member first and assign them second, and the same
    forbidden state arrives by the other road. Widening here closes it, and the
    caller's project lock makes the two orders serialise against each other.

    The column lives on this module's own membership row, so nothing about
    phases needs to be imported to fix it — only the value that means "all of
    them", which projects already owns.
    """
    if access.phase_scope == PHASE_SCOPE_ALL:
        return
    before = {"phase_scope": access.phase_scope}
    access.phase_scope = PHASE_SCOPE_ALL
    session.flush()
    record_event(
        session,
        action="project_access.phase_scope_changed",
        entity_type=ENTITY_PROJECT_ACCESS,
        entity_id=access.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after={"phase_scope": access.phase_scope},
    )


def _require_project_member(
    session: Session, *, project_id: uuid.UUID, user_id: uuid.UUID, label: str
) -> User:
    """Refuse to make someone responsible for a project they cannot open.

    A System Administrator reaches every project without a membership row, so
    they qualify. For anyone else this is deliberately a check and not a grant:
    creating access from permit editing would hand every technical writer a
    route into security administration.
    """
    user = _require_active_user(session, user_id, label=label)
    if ROLE_SYSTEM_ADMIN in user.role_keys:
        return user
    if not _has_active_access(session, project_id=project_id, user_id=user_id):
        raise ValidationError(f"{label} must already have access to this project.")
    return user


def create_project(
    session: Session,
    *,
    actor_user_id: uuid.UUID,
    actor_is_system_admin: bool,
    correlation_id: uuid.UUID,
    code: str,
    name: str,
    developer_entity: str,
    country_pack_id: uuid.UUID,
    base_currency_id: uuid.UUID,
    reporting_currency_id: uuid.UUID,
    city: str | None = None,
    location: str | None = None,
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
    project_type_code: str | None = None,
    status: str = PROJECT_STATUS_SETUP,
    fiscal_year_start_month: int | None = None,
    planned_start: date | None = None,
    planned_completion: date | None = None,
    project_manager_user_id: uuid.UUID | None = None,
) -> Project:
    normalized = normalize_project_code(code)
    pack = _require_active_country_pack(session, country_pack_id)
    _require_active_currency(session, base_currency_id, label="Base currency")
    _require_active_currency(session, reporting_currency_id, label="Reporting currency")
    _require_ordered_dates(
        planned_start,
        planned_completion,
        detail="Planned completion must not be earlier than planned start.",
    )
    if project_type_code is not None:
        require_active_reference_value(
            session,
            category=CATEGORY_PROJECT_TYPE,
            code=project_type_code,
            country_pack_id=country_pack_id,
        )

    if session.scalars(select(Project).where(Project.code == normalized)).first() is not None:
        raise ConflictError("A project with that code already exists.")

    project = Project(
        code=normalized,
        name=name.strip(),
        developer_entity=developer_entity.strip(),
        country_pack_id=country_pack_id,
        city=city.strip() if city else None,
        location=location.strip() if location else None,
        latitude=latitude,
        longitude=longitude,
        project_type_code=project_type_code,
        status=status,
        base_currency_id=base_currency_id,
        reporting_currency_id=reporting_currency_id,
        # The country pack sets the opening fiscal baseline; the project owns it
        # from then on.
        fiscal_year_start_month=(
            pack.fiscal_year_start_month
            if fiscal_year_start_month is None
            else fiscal_year_start_month
        ),
        planned_start=planned_start,
        planned_completion=planned_completion,
        created_by_user_id=actor_user_id,
    )
    session.add(project)
    _flush(
        session,
        constraint=_CODE_CONSTRAINT,
        detail="A project with that code already exists.",
    )

    record_event(
        session,
        action="project.created",
        entity_type=ENTITY_PROJECT,
        entity_id=project.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        after=_snapshot(project, _PROJECT_FIELDS),
    )

    # A System Administrator reaches every project without a membership row, so
    # granting one would be noise. Anyone else who creates a project must be
    # able to open it afterwards.
    if not actor_is_system_admin:
        _ensure_access(
            session,
            project_id=project.id,
            user_id=actor_user_id,
            actor_user_id=actor_user_id,
            correlation_id=correlation_id,
        )

    if project_manager_user_id is not None:
        _assign_project_manager(
            session,
            project=project,
            user_id=project_manager_user_id,
            actor_user_id=actor_user_id,
            actor_is_system_admin=actor_is_system_admin,
            correlation_id=correlation_id,
        )
        project.project_manager_user_id = project_manager_user_id
        session.flush()

    session.commit()
    session.refresh(project)
    return project


def update_project(
    session: Session,
    *,
    project: Project,
    actor_user_id: uuid.UUID,
    actor_is_system_admin: bool,
    correlation_id: uuid.UUID,
    **changes: object,
) -> Project:
    updates = resolve_updates(changes, fields=_PROJECT_UPDATABLE, clearable=_PROJECT_CLEARABLE)

    # The manager/access pairing is decided below against this row, and a
    # concurrent access revocation must queue behind it rather than race it.
    project = lock_project(session, project.id)

    basis_changes = [
        field
        for field in _BASIS_FIELDS
        if field in updates and updates[field] != getattr(project, field)
    ]
    if basis_changes and project.status != PROJECT_STATUS_SETUP:
        raise ConflictError(
            "The country pack and currencies can only be changed while the project "
            "is still in setup."
        )

    # Setup is the opening configuration state, not a state to come back to.
    # Without this, the basis lock would be trivially reversible: leave setup,
    # return to it, and change the currency after all.
    if updates.get("status") == PROJECT_STATUS_SETUP and project.status != PROJECT_STATUS_SETUP:
        raise ConflictError("A project cannot return to setup once it has left it.")

    if "base_currency_id" in updates and updates["base_currency_id"] != project.base_currency_id:
        _guard_base_currency_change(session, project.id)
    if "country_pack_id" in updates and updates["country_pack_id"] != project.country_pack_id:
        _guard_country_pack_change(session, project.id)

    if "country_pack_id" in updates:
        _require_active_country_pack(session, updates["country_pack_id"])  # type: ignore[arg-type]
    if "base_currency_id" in updates:
        _require_active_currency(
            session,
            updates["base_currency_id"],  # type: ignore[arg-type]
            label="Base currency",
        )
    if "reporting_currency_id" in updates:
        _require_active_currency(
            session,
            updates["reporting_currency_id"],  # type: ignore[arg-type]
            label="Reporting currency",
        )

    # Validate the window the row will actually hold, not just whichever end the
    # request happened to name.
    _require_ordered_dates(
        updates.get("planned_start", project.planned_start),  # type: ignore[arg-type]
        updates.get("planned_completion", project.planned_completion),  # type: ignore[arg-type]
        detail="Planned completion must not be earlier than planned start.",
    )
    # Validate the type the row will hold against the pack it will belong to —
    # moving country revalidates the code already on the project, not only a
    # code the request happens to name.
    resulting_pack = updates.get("country_pack_id", project.country_pack_id)
    resulting_type = updates.get("project_type_code", project.project_type_code)
    if resulting_type is not None and (
        "project_type_code" in updates or resulting_pack != project.country_pack_id
    ):
        require_active_reference_value(
            session,
            category=CATEGORY_PROJECT_TYPE,
            code=resulting_type,  # type: ignore[arg-type]
            country_pack_id=resulting_pack,  # type: ignore[arg-type]
        )

    before = _snapshot(project, _PROJECT_FIELDS)
    new_manager = updates.get("project_manager_user_id", project.project_manager_user_id)
    if new_manager is not None and new_manager != project.project_manager_user_id:
        _assign_project_manager(
            session,
            project=project,
            user_id=new_manager,  # type: ignore[arg-type]
            actor_user_id=actor_user_id,
            actor_is_system_admin=actor_is_system_admin,
            correlation_id=correlation_id,
        )

    for field, value in updates.items():
        setattr(project, field, value)
    session.flush()
    record_event(
        session,
        action="project.updated",
        entity_type=ENTITY_PROJECT,
        entity_id=project.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after=_snapshot(project, _PROJECT_FIELDS),
    )
    session.commit()
    session.refresh(project)
    return project


def permit_summary(session: Session, project_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    """Permit counts per project, in one grouped query rather than per row."""
    if not project_ids:
        return {}
    today = date.today()
    rows = session.execute(
        select(
            Permit.project_id,
            func.count(Permit.id),
            func.count(Permit.id).filter(Permit.is_blocking.is_(True)),
            func.count(Permit.id).filter(Permit.is_critical_path.is_(True)),
            func.count(Permit.id).filter(_sla_overdue_clause(today)),
        )
        .where(Permit.project_id.in_(project_ids))
        .group_by(Permit.project_id)
    ).all()
    return {
        row[0]: {
            "permit_count": row[1],
            "blocking_permit_count": row[2],
            "critical_path_permit_count": row[3],
            "overdue_permit_count": row[4],
        }
        for row in rows
    }


def parcel_counts(session: Session, project_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not project_ids:
        return {}
    rows = session.execute(
        select(LandParcel.project_id, func.count(LandParcel.id))
        .where(LandParcel.project_id.in_(project_ids))
        .group_by(LandParcel.project_id)
    ).all()
    return {row[0]: row[1] for row in rows}


# --------------------------------------------------------------------------- #
# Land parcels
# --------------------------------------------------------------------------- #

_PARCEL_FIELDS = (
    "id",
    "project_id",
    "plot_number",
    "title_deed_number",
    "cadastral_reference",
    "land_area",
    "area_unit",
    "ownership_type_code",
    "ownership_share_fraction",
    "acquisition_date",
    "purchase_price",
    "acquisition_fees",
    "seller",
    "title_status_code",
    "zoning_class_code",
    "frontage",
    "road_access",
    "topography",
    "geotechnical_status",
    "contamination_status",
    "flood_drainage_status",
    "archaeology_heritage_status",
    "power_available",
    "water_available",
    "sewer_available",
    "stormwater_available",
    "telecom_available",
    "utility_notes",
    "easements",
    "encroachments",
    "constraints_notes",
    "is_active",
)

#: ``plot_number`` stays editable: it is a label from the title record, not the
#: identity, and early registrations are often corrected against the deed.
_PARCEL_UPDATABLE = tuple(field for field in _PARCEL_FIELDS if field not in {"id", "project_id"})
_PARCEL_CLEARABLE = frozenset(
    field
    for field in _PARCEL_UPDATABLE
    if field not in {"plot_number", "land_area", "area_unit", "is_active"}
)

#: The parcel fields denominated in the project's base currency. Writing one is
#: what establishes a monetary fact the currency can no longer be changed under.
_PARCEL_MONEY_FIELDS = frozenset({"purchase_price", "acquisition_fees"})

#: Reference-backed parcel codes and the category each is drawn from.
_PARCEL_REFERENCE_FIELDS = {
    "ownership_type_code": CATEGORY_OWNERSHIP_TYPE,
    "title_status_code": CATEGORY_TITLE_STATUS,
    "zoning_class_code": CATEGORY_ZONING_CLASS,
}


def list_parcels(session: Session, *, project_id: uuid.UUID) -> list[LandParcel]:
    return list(
        session.scalars(
            select(LandParcel)
            .where(LandParcel.project_id == project_id)
            .order_by(LandParcel.plot_number)
        )
    )


def get_parcel(session: Session, *, project_id: uuid.UUID, parcel_id: uuid.UUID) -> LandParcel:
    """Load a parcel *within* a project.

    Scoped by project on purpose. Loading by primary key alone and checking the
    project afterwards is the shape that lets one project's identifier be
    substituted into another project's path.
    """
    parcel = session.scalars(
        select(LandParcel).where(LandParcel.id == parcel_id, LandParcel.project_id == project_id)
    ).first()
    if parcel is None:
        raise NotFoundError("Land parcel not found.")
    return parcel


def _validate_parcel_codes(
    session: Session, *, country_pack_id: uuid.UUID, values: dict[str, Any]
) -> None:
    for field, category in _PARCEL_REFERENCE_FIELDS.items():
        code = values.get(field)
        if code is not None:
            require_active_reference_value(
                session, category=category, code=code, country_pack_id=country_pack_id
            )


def create_parcel(
    session: Session,
    *,
    project: Project,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    plot_number: str,
    land_area: Decimal,
    area_unit: str | None = None,
    **fields: object,
) -> LandParcel:
    # The country pack decides which ownership, title and zoning codes are legal
    # here, so read it under the project lock: a concurrent move to another
    # jurisdiction must either land first — and be validated against — or wait
    # behind this parcel and then be refused by the country-pack guard, which
    # will now see a child record. There is no third outcome.
    project = lock_project(session, project.id)

    _validate_parcel_codes(session, country_pack_id=project.country_pack_id, values=fields)
    if area_unit is None:
        pack = session.get(CountryPack, project.country_pack_id)
        area_unit = pack.area_unit if pack is not None else "sqm"

    existing = session.scalars(
        select(LandParcel).where(
            LandParcel.project_id == project.id,
            LandParcel.plot_number == plot_number.strip(),
        )
    ).first()
    if existing is not None:
        raise ConflictError("A parcel with that plot number already exists in this project.")

    parcel = LandParcel(
        project_id=project.id,
        plot_number=plot_number.strip(),
        land_area=land_area,
        area_unit=area_unit,
        **{key: value for key, value in fields.items() if key in _PARCEL_UPDATABLE},
    )
    session.add(parcel)
    _flush(
        session,
        constraint=_PLOT_CONSTRAINT,
        detail="A parcel with that plot number already exists in this project.",
    )
    record_event(
        session,
        action="land_parcel.created",
        entity_type=ENTITY_LAND_PARCEL,
        entity_id=parcel.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        after=_snapshot(parcel, _PARCEL_FIELDS),
    )
    session.commit()
    session.refresh(parcel)
    return parcel


def update_parcel(
    session: Session,
    *,
    project: Project,
    parcel: LandParcel,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **changes: object,
) -> LandParcel:
    updates = resolve_updates(changes, fields=_PARCEL_UPDATABLE, clearable=_PARCEL_CLEARABLE)

    # A parcel carrying no cost does not lock the base currency, so the write
    # that first puts money on it is the one that has to serialise against a
    # currency change. Locking whenever the amount is named — rather than only
    # when it moves from null — costs one row lock and removes the case
    # analysis.
    if not _PARCEL_MONEY_FIELDS.isdisjoint(updates):
        project = lock_project(session, project.id)

    _validate_parcel_codes(session, country_pack_id=project.country_pack_id, values=dict(updates))
    if "plot_number" in updates and updates["plot_number"] != parcel.plot_number:
        clash = session.scalars(
            select(LandParcel).where(
                LandParcel.project_id == project.id,
                LandParcel.plot_number == updates["plot_number"],
            )
        ).first()
        if clash is not None:
            raise ConflictError("A parcel with that plot number already exists in this project.")

    before = _snapshot(parcel, _PARCEL_FIELDS)
    for field, value in updates.items():
        setattr(parcel, field, value)
    _flush(
        session,
        constraint=_PLOT_CONSTRAINT,
        detail="A parcel with that plot number already exists in this project.",
    )
    record_event(
        session,
        action="land_parcel.updated",
        entity_type=ENTITY_LAND_PARCEL,
        entity_id=parcel.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after=_snapshot(parcel, _PARCEL_FIELDS),
    )
    session.commit()
    session.refresh(parcel)
    return parcel


# --------------------------------------------------------------------------- #
# Planning controls
# --------------------------------------------------------------------------- #

_PLANNING_FIELDS = (
    "id",
    "project_id",
    "parcel_id",
    "permitted_uses",
    "site_coverage_rate_fraction",
    "far_ratio",
    "maximum_gfa",
    "maximum_floors",
    "maximum_height",
    "front_setback",
    "side_setback",
    "rear_setback",
    "parking_requirement",
    "minimum_plot_area",
    "minimum_frontage",
    "density",
    "exclusions",
    "variance_required",
    "variance_notes",
)

_PLANNING_WRITABLE = tuple(
    field for field in _PLANNING_FIELDS if field not in {"id", "project_id", "parcel_id"}
)


def get_planning_control(
    session: Session, *, project_id: uuid.UUID, parcel_id: uuid.UUID
) -> PlanningControl:
    control = session.scalars(
        select(PlanningControl).where(
            PlanningControl.parcel_id == parcel_id,
            PlanningControl.project_id == project_id,
        )
    ).first()
    if control is None:
        raise NotFoundError("Planning controls have not been recorded for this parcel.")
    return control


def write_planning_control(
    session: Session,
    *,
    project: Project,
    parcel: LandParcel,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    values: dict[str, Any],
) -> PlanningControl:
    """Create or replace the current planning envelope for a parcel.

    A full replacement rather than a patch: these values are read together as
    one authority's set of controls, and a half-updated envelope would describe
    a planning position that does not exist.
    """
    control = session.scalars(
        select(PlanningControl).where(
            PlanningControl.parcel_id == parcel.id,
            PlanningControl.project_id == project.id,
        )
    ).first()
    created = control is None
    before = None if created else _snapshot(control, _PLANNING_FIELDS)

    if control is None:
        control = PlanningControl(project_id=project.id, parcel_id=parcel.id)
        session.add(control)

    for field in _PLANNING_WRITABLE:
        setattr(control, field, values.get(field))
    # ``variance_required`` is NOT NULL; an omitted flag means "no variance".
    control.variance_required = bool(values.get("variance_required", False))

    _flush(
        session,
        constraint=_PLANNING_CONSTRAINT,
        detail="Planning controls already exist for this parcel.",
    )
    record_event(
        session,
        action="planning_control.created" if created else "planning_control.updated",
        entity_type=ENTITY_PLANNING_CONTROL,
        entity_id=control.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after=_snapshot(control, _PLANNING_FIELDS),
    )
    session.commit()
    session.refresh(control)
    return control


# --------------------------------------------------------------------------- #
# Permits
# --------------------------------------------------------------------------- #

_PERMIT_FIELDS = (
    "id",
    "project_id",
    "parcel_id",
    "permit_code",
    "permit_type_code",
    "authority",
    "authority_reference",
    "prerequisite_permit_id",
    "owner_user_id",
    "consultant",
    "status",
    "status_effective_date",
    "planned_submission_date",
    "forecast_submission_date",
    "actual_submission_date",
    "accepted_for_review_date",
    "comments_received_date",
    "resubmission_date",
    "planned_issue_date",
    "forecast_issue_date",
    "issue_date",
    "expiry_date",
    "renewal_date",
    "statutory_sla_days",
    "fee_amount",
    "conditions",
    "is_blocking",
    "is_critical_path",
    "next_action",
    "escalation_owner_user_id",
    "notes",
)

#: ``status`` and ``status_effective_date`` are absent: status moves only
#: through :func:`transition_permit`, so an ordinary update cannot rewrite the
#: register's history by setting a column.
_PERMIT_UPDATABLE = (
    "parcel_id",
    "permit_type_code",
    "authority",
    "authority_reference",
    "prerequisite_permit_id",
    "owner_user_id",
    "consultant",
    "planned_submission_date",
    "forecast_submission_date",
    "actual_submission_date",
    "accepted_for_review_date",
    "comments_received_date",
    "resubmission_date",
    "planned_issue_date",
    "forecast_issue_date",
    "issue_date",
    "expiry_date",
    "renewal_date",
    "statutory_sla_days",
    "fee_amount",
    "conditions",
    "is_blocking",
    "is_critical_path",
    "next_action",
    "escalation_owner_user_id",
    "notes",
)
_PERMIT_CLEARABLE = frozenset(
    field
    for field in _PERMIT_UPDATABLE
    if field not in {"permit_type_code", "authority", "is_blocking", "is_critical_path"}
)

#: Once an application is with the authority, these say *which* application the
#: record is. Editing them afterwards would silently repoint the record at a
#: different submission. ``permit_code`` is immutable from creation and so is
#: not listed here — it is simply never updatable.
_PERMIT_IDENTITY_FIELDS = ("parcel_id", "permit_type_code", "authority")

#: Statuses from which the application has reached the authority, so identity is
#: frozen. ``not_started`` and ``preparing`` are the only states before that.
_PRE_SUBMISSION_STATUSES = frozenset({"not_started", "preparing"})

#: The permitted moves. An explicit table, deliberately readable end to end:
#: the alternative is a configurable transition language, which is a workflow
#: engine wearing a different hat.
PERMIT_TRANSITIONS: dict[str, frozenset[str]] = {
    "not_started": frozenset({"preparing", "on_hold", "withdrawn"}),
    "preparing": frozenset({"submitted", "on_hold", "withdrawn"}),
    "submitted": frozenset(
        {"accepted_for_review", "comments_received", "rejected", "on_hold", "withdrawn"}
    ),
    "accepted_for_review": frozenset(
        {
            "comments_received",
            "approved_with_conditions",
            "issued",
            "rejected",
            "on_hold",
            "withdrawn",
        }
    ),
    "comments_received": frozenset({"resubmission", "rejected", "on_hold", "withdrawn"}),
    "resubmission": frozenset(
        {
            "accepted_for_review",
            "comments_received",
            "approved_with_conditions",
            "issued",
            "rejected",
            "on_hold",
            "withdrawn",
        }
    ),
    "approved_with_conditions": frozenset({"issued", "expired", "on_hold", "withdrawn"}),
    "issued": frozenset({"expired", "renewed"}),
    "expired": frozenset({"renewed"}),
    "renewed": frozenset({"expired"}),
    "rejected": frozenset({"preparing", "withdrawn"}),
    "on_hold": frozenset(
        {
            "preparing",
            "submitted",
            "accepted_for_review",
            "comments_received",
            "resubmission",
            "approved_with_conditions",
            "issued",
            "withdrawn",
        }
    ),
    # Terminal. A withdrawn application is gone; a new one gets a new record.
    "withdrawn": frozenset(),
}

#: Moves a person has to explain. Each one either stops the application or
#: restarts it after a refusal, and "why" is the part that matters later.
_REASON_REQUIRED = frozenset({"rejected", "on_hold", "withdrawn", "preparing"})

#: Which milestone a transition establishes, when that date is not already set.
_MILESTONE_FOR_STATUS = {
    "submitted": "actual_submission_date",
    "accepted_for_review": "accepted_for_review_date",
    "comments_received": "comments_received_date",
    "resubmission": "resubmission_date",
    "issued": "issue_date",
    "expired": "expiry_date",
    "renewed": "renewal_date",
}

#: A prerequisite counts as met only when the permit it names actually exists in
#: force. ``approved_with_conditions`` deliberately does not qualify: conditions
#: are exactly what is not yet satisfied.
_SATISFYING_STATUSES = frozenset({"issued", "renewed"})

#: Bound on prerequisite-chain traversal. Chains are a handful of permits deep;
#: the bound exists so a cycle introduced by some future path cannot hang a
#: request while the cycle check itself is what catches the real case.
_MAX_PREREQUISITE_DEPTH = 64


def _sla_overdue_clause(today: date) -> ColumnElement[bool]:
    """The one definition of an overdue permit, as SQL.

    PostgreSQL adds a plain integer to a date as days. This mirrors
    :func:`derive_permit_metrics` exactly — the register's summary and each
    row's own ``sla_overdue`` must never be able to disagree about what overdue
    means, which they would the moment the rule were written out twice.
    """
    return (Permit.statutory_sla_days.is_not(None)) & (
        Permit.status_effective_date + Permit.statutory_sla_days < today
    )


def _permit_filters(
    *,
    project_id: uuid.UUID,
    status: str | None,
    permit_type_code: str | None,
    parcel_id: uuid.UUID | None,
    is_blocking: bool | None,
    is_critical_path: bool | None,
) -> list[ColumnElement[bool]]:
    """The WHERE clauses shared by the page query and the summary query.

    Built once so the counts can never describe a different population from the
    rows they are reported alongside.
    """
    clauses: list[ColumnElement[bool]] = [Permit.project_id == project_id]
    if status is not None:
        clauses.append(Permit.status == status)
    if permit_type_code is not None:
        clauses.append(Permit.permit_type_code == permit_type_code)
    if parcel_id is not None:
        clauses.append(Permit.parcel_id == parcel_id)
    if is_blocking is not None:
        clauses.append(Permit.is_blocking.is_(is_blocking))
    if is_critical_path is not None:
        clauses.append(Permit.is_critical_path.is_(is_critical_path))
    return clauses


def list_permits(
    session: Session,
    *,
    project_id: uuid.UUID,
    status: str | None = None,
    permit_type_code: str | None = None,
    parcel_id: uuid.UUID | None = None,
    is_blocking: bool | None = None,
    is_critical_path: bool | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[Permit]:
    clauses = _permit_filters(
        project_id=project_id,
        status=status,
        permit_type_code=permit_type_code,
        parcel_id=parcel_id,
        is_blocking=is_blocking,
        is_critical_path=is_critical_path,
    )
    return list(
        session.scalars(
            select(Permit).where(*clauses).order_by(Permit.permit_code).limit(limit).offset(offset)
        )
    )


def permit_register_totals(
    session: Session,
    *,
    project_id: uuid.UUID,
    status: str | None = None,
    permit_type_code: str | None = None,
    parcel_id: uuid.UUID | None = None,
    is_blocking: bool | None = None,
    is_critical_path: bool | None = None,
    today: date | None = None,
) -> dict[str, int]:
    """Counts over the whole matching set, not over the page being returned.

    A register that reports the size of one page under the name ``total`` is
    telling a manager there are fifty permits when there are two hundred and
    fifty. Aggregated in SQL, so no row leaves the database to be counted.
    """
    clauses = _permit_filters(
        project_id=project_id,
        status=status,
        permit_type_code=permit_type_code,
        parcel_id=parcel_id,
        is_blocking=is_blocking,
        is_critical_path=is_critical_path,
    )
    overdue = _sla_overdue_clause(today or date.today())
    row = session.execute(
        select(
            func.count(Permit.id),
            func.count(Permit.id).filter(Permit.is_blocking.is_(True)),
            func.count(Permit.id).filter(Permit.is_critical_path.is_(True)),
            func.count(Permit.id).filter(overdue),
        ).where(*clauses)
    ).one()
    return {
        "total": row[0],
        "blocking_count": row[1],
        "critical_path_count": row[2],
        "sla_overdue_count": row[3],
    }


def get_permit(session: Session, *, project_id: uuid.UUID, permit_id: uuid.UUID) -> Permit:
    """Load a permit within a project. Scoped for the same reason parcels are."""
    permit = session.scalars(
        select(Permit).where(Permit.id == permit_id, Permit.project_id == project_id)
    ).first()
    if permit is None:
        raise NotFoundError("Permit not found.")
    return permit


def _lock_permit(session: Session, *, project_id: uuid.UUID, permit_id: uuid.UUID) -> Permit:
    """Take the permit row for update and return its committed state.

    Status is a read-then-write decision, so the row the rules are evaluated
    against must be the locked one, not the copy the route loaded earlier. Two
    requests reading ``submitted`` could otherwise both find a valid exit and
    each append an event claiming to follow it, leaving a history that forks and
    a current status decided by whichever write landed last.
    """
    permit = session.scalars(
        select(Permit)
        .where(Permit.id == permit_id, Permit.project_id == project_id)
        .with_for_update()
        # See ``_lock_project``: the lock alone would return stale attributes.
        .execution_options(populate_existing=True)
    ).first()
    if permit is None:
        raise NotFoundError("Permit not found.")
    return permit


def list_status_history(session: Session, *, permit_id: uuid.UUID) -> list[PermitStatusEvent]:
    return list(
        session.scalars(
            select(PermitStatusEvent)
            .where(PermitStatusEvent.permit_id == permit_id)
            .order_by(PermitStatusEvent.effective_date, PermitStatusEvent.changed_at)
        )
    )


def _require_prerequisite(
    session: Session,
    *,
    project_id: uuid.UUID,
    permit_id: uuid.UUID | None,
    prerequisite_id: uuid.UUID,
) -> Permit:
    """Validate a prerequisite link, refusing self-reference and cycles.

    Walks the existing chain from the proposed prerequisite. A plain bounded
    walk over a handful of rows — a dependency graph library would be a large
    answer to a small question.
    """
    if permit_id is not None and prerequisite_id == permit_id:
        raise ValidationError("A permit cannot be its own prerequisite.")

    prerequisite = session.scalars(
        select(Permit).where(Permit.id == prerequisite_id, Permit.project_id == project_id)
    ).first()
    if prerequisite is None:
        raise ValidationError("The prerequisite permit must belong to this project.")

    seen: set[uuid.UUID] = set()
    current = prerequisite
    for _ in range(_MAX_PREREQUISITE_DEPTH):
        if permit_id is not None and current.id == permit_id:
            raise ValidationError("That prerequisite would create a circular dependency.")
        if current.id in seen or current.prerequisite_permit_id is None:
            return prerequisite
        seen.add(current.id)
        next_permit = session.get(Permit, current.prerequisite_permit_id)
        if next_permit is None:
            return prerequisite
        current = next_permit
    raise ValidationError("The prerequisite chain is too deep to validate.")


def _validate_permit_links(
    session: Session,
    *,
    project: Project,
    permit_id: uuid.UUID | None,
    values: dict[str, Any],
) -> None:
    """Check every reference a permit makes stays inside this project."""
    parcel_id = values.get("parcel_id")
    if parcel_id is not None:
        get_parcel(session, project_id=project.id, parcel_id=parcel_id)

    permit_type_code = values.get("permit_type_code")
    if permit_type_code is not None:
        require_active_reference_value(
            session,
            category=CATEGORY_PERMIT_TYPE,
            code=permit_type_code,
            country_pack_id=project.country_pack_id,
        )

    prerequisite_id = values.get("prerequisite_permit_id")
    if prerequisite_id is not None:
        _require_prerequisite(
            session,
            project_id=project.id,
            permit_id=permit_id,
            prerequisite_id=prerequisite_id,
        )

    for field, label in (
        ("owner_user_id", "Permit owner"),
        ("escalation_owner_user_id", "Escalation owner"),
    ):
        user_id = values.get(field)
        if user_id is not None:
            _require_project_member(session, project_id=project.id, user_id=user_id, label=label)


def create_permit(
    session: Session,
    *,
    project: Project,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    permit_code: str,
    permit_type_code: str,
    authority: str,
    status_effective_date: date | None = None,
    **fields: object,
) -> Permit:
    # Everything below is decided against the project: the permit type against
    # its country pack, the parcel and prerequisite against its children, the
    # responsible users against its membership — and ``fee_amount`` may be the
    # first money recorded under its base currency. Read that project under
    # lock so a basis change cannot commit alongside this permit and leave it
    # validated against a jurisdiction the project has already left.
    project = lock_project(session, project.id)

    values = dict(fields)
    values["permit_type_code"] = permit_type_code
    _validate_permit_links(session, project=project, permit_id=None, values=values)

    code = permit_code.strip()
    existing = session.scalars(
        select(Permit).where(Permit.project_id == project.id, Permit.permit_code == code)
    ).first()
    if existing is not None:
        raise ConflictError("A permit with that code already exists in this project.")

    permit = Permit(
        project_id=project.id,
        permit_code=code,
        permit_type_code=permit_type_code,
        authority=authority.strip(),
        status=PERMIT_STATUS_NOT_STARTED,
        status_effective_date=status_effective_date or date.today(),
        **{key: value for key, value in fields.items() if key in _PERMIT_UPDATABLE},
    )
    session.add(permit)
    _flush(
        session,
        constraint=_PERMIT_CODE_CONSTRAINT,
        detail="A permit with that code already exists in this project.",
    )
    record_event(
        session,
        action="permit.created",
        entity_type=ENTITY_PERMIT,
        entity_id=permit.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        after=_snapshot(permit, _PERMIT_FIELDS),
    )
    session.commit()
    session.refresh(permit)
    return permit


def update_permit(
    session: Session,
    *,
    project: Project,
    permit: Permit,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **changes: object,
) -> Permit:
    updates = resolve_updates(changes, fields=_PERMIT_UPDATABLE, clearable=_PERMIT_CLEARABLE)

    # Lock order is always project first, then permit. Writing a prerequisite
    # link makes PostgreSQL take a key-share lock on the referenced permit's
    # parent row, so a path that took the permit first and the project second
    # would deadlock against one doing the reverse.
    #
    # A cycle is a property of the whole chain rather than of one row, so a
    # prerequisite change serialises on the project that owns the chain:
    # otherwise "A depends on B" and "B depends on A" each validate against a
    # graph that does not yet contain the other, and both commit.
    #
    # ``fee_amount`` joins it for a different reason: a permit with no fee does
    # not lock the base currency, so the write that first puts money on it is
    # the one that has to serialise against a currency change.
    if "prerequisite_permit_id" in updates or "fee_amount" in updates:
        project = lock_project(session, project.id)

    # The freeze is decided by the permit's status, so read it under lock: a
    # concurrent transition to ``submitted`` must either land before this update
    # is judged, or wait behind it — never run alongside it and leave a
    # submitted application whose identity changed as it was submitted.
    permit = _lock_permit(session, project_id=project.id, permit_id=permit.id)

    if permit.status not in _PRE_SUBMISSION_STATUSES:
        frozen = [
            field
            for field in _PERMIT_IDENTITY_FIELDS
            if field in updates and updates[field] != getattr(permit, field)
        ]
        if frozen:
            raise ConflictError(
                "The parcel, permit type and authority are fixed once the application "
                "has been submitted."
            )

    _validate_permit_links(session, project=project, permit_id=permit.id, values=dict(updates))

    before = _snapshot(permit, _PERMIT_FIELDS)
    for field, value in updates.items():
        setattr(permit, field, value)
    session.flush()
    record_event(
        session,
        action="permit.updated",
        entity_type=ENTITY_PERMIT,
        entity_id=permit.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after=_snapshot(permit, _PERMIT_FIELDS),
    )
    session.commit()
    session.refresh(permit)
    return permit


def transition_permit(
    session: Session,
    *,
    permit: Permit,
    to_status: str,
    effective_date: date,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    reason: str | None = None,
    notes: str | None = None,
) -> Permit:
    """Move a permit to a new state, appending the event that records the move.

    One transaction: the appended event, the permit's new current state, any
    milestone date it establishes and the audit entry all commit together, so
    the register can never show a status whose history is missing.
    """
    # Re-read under lock: every rule below is decided against committed state,
    # and the lock is held until this transaction commits.
    permit = _lock_permit(session, project_id=permit.project_id, permit_id=permit.id)

    from_status = permit.status
    if to_status not in PERMIT_STATUSES:
        raise ValidationError("Unknown permit status.")
    if to_status == from_status:
        raise ConflictError("The permit is already in that status.")
    if to_status not in PERMIT_TRANSITIONS[from_status]:
        raise ConflictError(f"A permit cannot move from {from_status} to {to_status}.")
    # ``preparing`` needs a reason only when it restarts a refused application;
    # the very first move off ``not_started`` is just work beginning.
    if (
        to_status in _REASON_REQUIRED
        and from_status != PERMIT_STATUS_NOT_STARTED
        and not (reason or "").strip()
    ):
        raise ValidationError(f"A reason is required when moving a permit to {to_status}.")
    if effective_date < permit.status_effective_date:
        raise ValidationError(
            "The effective date cannot be earlier than the current status effective date."
        )

    before = _snapshot(permit, _PERMIT_FIELDS)
    event = PermitStatusEvent(
        permit_id=permit.id,
        from_status=from_status,
        to_status=to_status,
        effective_date=effective_date,
        reason=reason.strip() if reason else None,
        notes=notes.strip() if notes else None,
        changed_by_user_id=actor_user_id,
    )
    session.add(event)

    permit.status = to_status
    permit.status_effective_date = effective_date

    # Establish the milestone this move represents, but never overwrite a date
    # somebody recorded explicitly: theirs is the corrected one.
    milestone = _MILESTONE_FOR_STATUS.get(to_status)
    if milestone is not None and getattr(permit, milestone) is None:
        setattr(permit, milestone, effective_date)

    session.flush()
    record_event(
        session,
        action="permit.status_changed",
        entity_type=ENTITY_PERMIT,
        entity_id=permit.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        reason=event.reason,
        before=before,
        after=_snapshot(permit, _PERMIT_FIELDS),
    )
    session.commit()
    session.refresh(permit)
    return permit


def derive_permit_metrics(
    session: Session, permit: Permit, *, today: date | None = None
) -> dict[str, Any]:
    """Governance figures derived at read time, never stored.

    Storing them would make them true only until the next day. Every definition
    here is deterministic given the permit and the date.
    """
    now = today or date.today()
    days_in_stage = (now - permit.status_effective_date).days

    sla_days_remaining: int | None = None
    if permit.statutory_sla_days is not None:
        sla_days_remaining = permit.statutory_sla_days - days_in_stage

    # Actual beats forecast: once something has happened, the estimate of it is
    # no longer the interesting number.
    submitted = permit.actual_submission_date or permit.forecast_submission_date
    submission_variance_days: int | None = None
    if submitted is not None and permit.planned_submission_date is not None:
        submission_variance_days = (submitted - permit.planned_submission_date).days

    issued = permit.issue_date or permit.forecast_issue_date
    issue_variance_days: int | None = None
    if issued is not None and permit.planned_issue_date is not None:
        issue_variance_days = (issued - permit.planned_issue_date).days

    prerequisite_satisfied = True
    if permit.prerequisite_permit_id is not None:
        prerequisite = session.get(Permit, permit.prerequisite_permit_id)
        prerequisite_satisfied = (
            prerequisite is not None and prerequisite.status in _SATISFYING_STATUSES
        )

    return {
        "days_in_stage": days_in_stage,
        "sla_days_remaining": sla_days_remaining,
        "sla_overdue": sla_days_remaining is not None and sla_days_remaining < 0,
        "submission_variance_days": submission_variance_days,
        "issue_variance_days": issue_variance_days,
        "prerequisite_satisfied": prerequisite_satisfied,
        "expired_flag": permit.status == "expired",
    }


# --------------------------------------------------------------------------- #
# Document references
# --------------------------------------------------------------------------- #

_DOCUMENT_FIELDS = (
    "id",
    "project_id",
    "parcel_id",
    "permit_id",
    "title",
    "document_type_code",
    "reference_number",
    "external_url",
    "notes",
    "is_active",
)

_DOCUMENT_UPDATABLE = (
    "title",
    "document_type_code",
    "reference_number",
    "external_url",
    "notes",
    "is_active",
)
_DOCUMENT_CLEARABLE = frozenset({"reference_number", "notes"})


def list_documents(
    session: Session,
    *,
    project_id: uuid.UUID,
    parcel_id: uuid.UUID | None = None,
    permit_id: uuid.UUID | None = None,
    document_type_code: str | None = None,
    is_active: bool | None = None,
) -> list[DocumentReference]:
    statement = select(DocumentReference).where(DocumentReference.project_id == project_id)
    if parcel_id is not None:
        statement = statement.where(DocumentReference.parcel_id == parcel_id)
    if permit_id is not None:
        statement = statement.where(DocumentReference.permit_id == permit_id)
    if document_type_code is not None:
        statement = statement.where(DocumentReference.document_type_code == document_type_code)
    if is_active is not None:
        statement = statement.where(DocumentReference.is_active.is_(is_active))
    return list(session.scalars(statement.order_by(DocumentReference.title)))


def get_document(
    session: Session, *, project_id: uuid.UUID, document_id: uuid.UUID
) -> DocumentReference:
    document = session.scalars(
        select(DocumentReference).where(
            DocumentReference.id == document_id,
            DocumentReference.project_id == project_id,
        )
    ).first()
    if document is None:
        raise NotFoundError("Document reference not found.")
    return document


def create_document(
    session: Session,
    *,
    project: Project,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    title: str,
    document_type_code: str,
    external_url: str,
    parcel_id: uuid.UUID | None = None,
    permit_id: uuid.UUID | None = None,
    reference_number: str | None = None,
    notes: str | None = None,
) -> DocumentReference:
    # The document type is drawn from the project's country pack, so the same
    # lock applies here: this reference is one of the child records that makes
    # the jurisdiction permanent, and it must not be created against a pack the
    # project is concurrently leaving.
    project = lock_project(session, project.id)

    if parcel_id is not None and permit_id is not None:
        raise ValidationError("A document reference attaches to a parcel or a permit, not to both.")
    if parcel_id is not None:
        get_parcel(session, project_id=project.id, parcel_id=parcel_id)
    if permit_id is not None:
        get_permit(session, project_id=project.id, permit_id=permit_id)
    require_active_reference_value(
        session,
        category=CATEGORY_DOCUMENT_TYPE,
        code=document_type_code,
        country_pack_id=project.country_pack_id,
    )

    document = DocumentReference(
        project_id=project.id,
        parcel_id=parcel_id,
        permit_id=permit_id,
        title=title.strip(),
        document_type_code=document_type_code,
        reference_number=reference_number.strip() if reference_number else None,
        external_url=external_url,
        notes=notes.strip() if notes else None,
        created_by_user_id=actor_user_id,
    )
    session.add(document)
    session.flush()
    record_event(
        session,
        action="document_reference.created",
        entity_type=ENTITY_DOCUMENT_REFERENCE,
        entity_id=document.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        after=_snapshot(document, _DOCUMENT_FIELDS),
    )
    session.commit()
    session.refresh(document)
    return document


def update_document(
    session: Session,
    *,
    project: Project,
    document: DocumentReference,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **changes: object,
) -> DocumentReference:
    updates = resolve_updates(changes, fields=_DOCUMENT_UPDATABLE, clearable=_DOCUMENT_CLEARABLE)
    if updates.get("document_type_code") is not None:
        require_active_reference_value(
            session,
            category=CATEGORY_DOCUMENT_TYPE,
            code=updates["document_type_code"],  # type: ignore[arg-type]
            country_pack_id=project.country_pack_id,
        )

    before = _snapshot(document, _DOCUMENT_FIELDS)
    for field, value in updates.items():
        setattr(document, field, value)
    session.flush()
    record_event(
        session,
        action="document_reference.updated",
        entity_type=ENTITY_DOCUMENT_REFERENCE,
        entity_id=document.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after=_snapshot(document, _DOCUMENT_FIELDS),
    )
    session.commit()
    session.refresh(document)
    return document
