"""Who may price, who may approve, and who may only look.

Pricing is the first module in this system where the person preparing a number
and the person sanctioning it must not be the same person. That is the whole
content of this file: a small set of named rights, and one rule that a maker is
not their own checker.

Two things are deliberately absent. There is no approval engine — approval is
two role checks and one comparison of user identifiers. And there is no
inheritance from System Administrator: an administrator configures the system,
which is not the same authority as sanctioning a selling price, and a role that
silently contains every other role is how financial control becomes decorative.

Phase visibility is not re-implemented here. It is imported from inventory,
because a unit's price must be exactly as visible as the unit, and two copies of
that rule are one copy that eventually disagrees.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.modules.access.dependencies import ActiveActor, ActorContext, DbSession
from app.modules.inventory.models import Building, Floor, Unit
from app.modules.inventory.permissions import visible_phase_ids
from app.modules.projects.models import Project
from app.modules.projects.permissions import require_project_access

#: Who may prepare pricing: build a configuration, write rules, generate draft
#: prices, record benchmarks and submit for approval. Finance is here because
#: pricing is their work; the Project Manager because they run the development;
#: the System Administrator because somebody has to be able to set the system
#: up before Finance exists.
PRICING_WRITER_ROLES = frozenset({"system_admin", "project_manager", "finance"})

#: Who may sanction and release a price. Exactly one role, and deliberately not
#: the administrator: the ability to configure a system is not the authority to
#: approve what it charges.
PRICING_APPROVER_ROLES = frozenset({"approver_cfo"})

#: Who may see prices that are not yet live — drafts, submissions, approvals
#: awaiting activation. A sales advisor quoting from a draft is quoting a number
#: nobody has agreed to.
INTERNAL_PRICE_ROLES = frozenset(
    {
        "system_admin",
        "project_manager",
        "finance",
        "approver_cfo",
        "executive_viewer",
        "auditor",
    }
)

#: Who may run a quote preview. Sales advisors and sales operations do this all
#: day; it writes nothing and creates no client, reservation or sale.
QUOTE_PREVIEW_ROLES = frozenset(
    {
        "system_admin",
        "project_manager",
        "finance",
        "approver_cfo",
        "sales_operations",
        "sales_advisor",
        "executive_viewer",
    }
)

_FORBIDDEN_DETAIL = "You do not have permission to perform this action."
_APPROVER_DETAIL = "Only an Approver / CFO may approve or activate a price."
_MAKER_DETAIL = "The person who prepared a price may not approve it."
_SETUP_DETAIL = "Finalize the project setup before configuring pricing."


def require_pricing_writer(actor: ActorContext) -> None:
    """Gate configuration, rules, benchmarks and draft price preparation."""
    if not actor.role_keys.intersection(PRICING_WRITER_ROLES):
        raise PermissionDeniedError(_FORBIDDEN_DETAIL)


def require_pricing_approver(actor: ActorContext) -> None:
    """Gate approval, activation and escalation activation.

    A System Administrator holding this would make the maker/checker rule a
    formality: administrators are routinely the people who also prepare the
    data. The separation only means something if the second signature is a
    different office.
    """
    if not actor.role_keys.intersection(PRICING_APPROVER_ROLES):
        raise PermissionDeniedError(_APPROVER_DETAIL)


def require_internal_price_reader(actor: ActorContext) -> None:
    """Gate anything that is not yet the live list price."""
    if not actor.role_keys.intersection(INTERNAL_PRICE_ROLES):
        raise PermissionDeniedError(_FORBIDDEN_DETAIL)


def require_quote_reader(actor: ActorContext) -> None:
    """Gate the quote preview."""
    if not actor.role_keys.intersection(QUOTE_PREVIEW_ROLES):
        raise PermissionDeniedError(_FORBIDDEN_DETAIL)


def sees_internal_prices(actor: ActorContext) -> bool:
    """Whether this caller may be shown anything other than the active price."""
    return bool(actor.role_keys.intersection(INTERNAL_PRICE_ROLES))


def require_different_checker(actor: ActorContext, *, maker_user_id: uuid.UUID | None) -> None:
    """Refuse an approval by the person who prepared or submitted the thing.

    Applied on the submitting user rather than the original author: the person
    who put a price forward is the one asserting it is right, and they are the
    signature the approval is meant to be independent of.
    """
    if maker_user_id is not None and maker_user_id == actor.user_id:
        raise PermissionDeniedError(_MAKER_DETAIL)


def require_operational_project(project: Project) -> None:
    """Refuse pricing while the project's basis can still be rewritten.

    The same rule inventory applies, for the same reason and stated separately
    rather than imported: a price is denominated in a currency and validated
    against a country pack, both of which PR-MVP-02 lets a project in ``setup``
    change underneath whatever was priced against them.
    """
    if project.status == "setup":
        raise ConflictError(_SETUP_DETAIL)


def visible_units_for_pricing(
    statement: Select[tuple[Unit]],
    session: Session,
    *,
    project_id: uuid.UUID,
    actor: ActorContext,
) -> Select[tuple[Unit]]:
    """Narrow a unit query to the phases the caller may see."""
    allowed = visible_phase_ids(session, project_id=project_id, actor=actor)
    if allowed is None:
        return statement
    return statement.where(
        Unit.id.in_(
            select(Unit.id)
            .join(Floor, Floor.id == Unit.floor_id)
            .join(Building, Building.id == Floor.building_id)
            .where(Building.phase_id.in_(allowed))
        )
    )


def visible_unit_ids(
    session: Session, *, project_id: uuid.UUID, actor: ActorContext
) -> Select[tuple[uuid.UUID]] | None:
    """A subquery of unit ids this caller may see, or ``None`` for no narrowing.

    Used to filter price versions in SQL. A price register that fetched a
    project's prices and dropped the hidden ones afterwards would put the
    numbers in memory, in the query plan and one refactor from the response.
    """
    allowed = visible_phase_ids(session, project_id=project_id, actor=actor)
    if allowed is None:
        return None
    return (
        select(Unit.id)
        .join(Floor, Floor.id == Unit.floor_id)
        .join(Building, Building.id == Floor.building_id)
        .where(Building.phase_id.in_(allowed))
    )


def require_priceable_unit(
    session: Session, *, project: Project, unit_id: uuid.UUID, actor: ActorContext
) -> Unit:
    """Load a unit of this project the caller may see, or raise 404.

    Scoped by project and phase in one query. A unit in a phase the caller was
    not granted answers exactly as a unit that does not exist, on price reads
    and quote previews alike — a 403 would confirm the identifier is real.
    """
    statement = select(Unit).where(Unit.id == unit_id, Unit.project_id == project.id)
    unit = session.scalars(
        visible_units_for_pricing(statement, session, project_id=project.id, actor=actor)
    ).first()
    if unit is None:
        raise NotFoundError("Unit not found.")
    return unit


def accessible_project_for_pricing(
    project_id: Annotated[uuid.UUID, Path()],
    session: DbSession,
    actor: ActiveActor,
) -> Project:
    """Resolve ``{project_id}`` to a project the caller may open."""
    return require_project_access(session, project_id=project_id, actor=actor)


PricingProject = Annotated[Project, Depends(accessible_project_for_pricing)]
