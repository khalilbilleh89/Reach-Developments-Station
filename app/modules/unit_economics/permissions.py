"""Who may see what a unit costs, and who may decide it.

Cost and margin are the most sensitive numbers this platform holds. A sale price
is negotiated in the open with the buyer; the developer's margin on it is not,
and an advisor who can see both has an argument for a discount that the company
never agreed to make available. So the reading list here is deliberately shorter
than the one for sales, payment plans or collections, and being able to see a
unit is not a reason to see what it earns.

Three separations, each with a specific failure behind it.

**Finance proposes a cost basis; a second person approves it.** An allocation
version decides what every unit in the project costs, which decides every margin
anybody reports. One person moving a soft-cost pool and signing their own change
is one person restating the project's profitability.

**The maker is never the checker, by identifier.** A user who holds Finance and
Approver / CFO is still one pair of eyes. Checked against the user who submitted
the version rather than against a role.

**The System Administrator has no financial authority.** They may read — running
the platform means being able to diagnose it — and they may approve nothing,
activate nothing and record nothing. Administering the software that stores the
margin is not authority over the margin.

Row scoping is inherited rather than restated. A unit's economics is exactly as
visible as the unit, so the phase narrowing is imported from sales, which
imports it from inventory. A second copy of a phase rule is a copy waiting to
disagree, and the way that disagreement surfaces is a cost breakdown for a phase
somebody was never granted.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, PermissionDeniedError
from app.modules.access.dependencies import ActiveActor, ActorContext, DbSession
from app.modules.inventory.models import Unit
from app.modules.projects.models import Project
from app.modules.projects.permissions import require_project_access
from app.modules.sales.models import SaleContract
from app.modules.sales.permissions import visible_unit_ids

# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #

#: Who may see cost, profit and margin at all.
#:
#: Notably absent: Sales Advisor, Sales Operations, Legal, Collections and
#: Design / Engineering. Each of them can already see the unit, the price and
#: in some cases the contract — none of them needs the developer's margin on it,
#: and the advisor in particular has a direct interest in knowing how much room
#: there is to discount.
ECONOMICS_READER_ROLES = frozenset(
    {
        "system_admin",
        "project_manager",
        "finance",
        "approver_cfo",
        "executive_viewer",
        "auditor",
    }
)

# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #

#: Who may build a cost basis, record a unit cost and reverse one. Finance owns
#: the numbers; nobody else proposes them.
ECONOMICS_WRITER_ROLES = frozenset({"finance"})

#: Who may approve a submitted allocation version. Either a second Finance user
#: or the Approver / CFO — the maker/checker rule below is what makes "a second
#: Finance user" mean a genuinely different person.
ECONOMICS_APPROVER_ROLES = frozenset({"finance", "approver_cfo"})

_FORBIDDEN = "You do not have permission to perform this action."
_MAKER = "The person who submitted this cost basis may not approve it."
_NO_VERSION = "Allocation version not found."
_NO_POOL = "Cost pool not found."
_NO_COST = "Unit cost not found."
_NO_UNIT = "Unit not found."
_NO_SALE = "Sale contract not found."


def _require_any(actor: ActorContext, roles: frozenset[str], detail: str) -> None:
    if not actor.role_keys.intersection(roles):
        raise PermissionDeniedError(detail)


def require_economics_reader(actor: ActorContext) -> None:
    """Gate every cost, profit and margin figure this module produces."""
    _require_any(actor, ECONOMICS_READER_ROLES, _FORBIDDEN)


def require_economics_writer(actor: ActorContext) -> None:
    """Gate building a cost basis and recording a unit cost."""
    _require_any(actor, ECONOMICS_WRITER_ROLES, "Only Finance may do this.")


def require_economics_approver(actor: ActorContext) -> None:
    """Gate approving or rejecting a submitted allocation version.

    The System Administrator is not in this set and must never be added to it:
    the whole point of the separation is that the person who can reach the
    database is not the person who signs off what it says.
    """
    _require_any(
        actor,
        ECONOMICS_APPROVER_ROLES,
        "Only a second Finance user or an Approver / CFO may approve a cost basis.",
    )


def require_different_approver(actor: ActorContext, *, submitted_by_user_id: uuid.UUID) -> None:
    """Refuse an approval by the person who submitted the version."""
    if submitted_by_user_id == actor.user_id:
        raise PermissionDeniedError(_MAKER)


# --------------------------------------------------------------------------- #
# Row and phase scoping
# --------------------------------------------------------------------------- #


def visible_units(
    session: Session, *, project_id: uuid.UUID, actor: ActorContext
) -> Select[tuple[uuid.UUID]] | None:
    """A subquery of unit ids this caller may see, or ``None`` for no narrowing.

    Imported from sales rather than rewritten. Applied in SQL on every register
    and every drill-down, because a register that fetched the project's costs
    and dropped the hidden rows afterwards would have put them in memory, in the
    query plan, and one refactor from the response body.
    """
    return visible_unit_ids(session, project_id=project_id, actor=actor)


def require_visible_unit(
    session: Session, *, project: Project, unit_id: uuid.UUID, actor: ActorContext
) -> Unit:
    """Load a unit of this project the caller may see, or raise 404.

    A unit in a phase the caller was not granted answers exactly as a unit that
    does not exist. A 403 would confirm the identifier names something real,
    which is what phase scoping exists to prevent.
    """
    statement = select(Unit).where(Unit.id == unit_id, Unit.project_id == project.id)
    allowed = visible_units(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(Unit.id.in_(allowed))
    unit = session.scalars(statement).first()
    if unit is None:
        raise NotFoundError(_NO_UNIT)
    return unit


def require_visible_sale(
    session: Session, *, project: Project, sale_id: uuid.UUID, actor: ActorContext
) -> SaleContract:
    """Load a sale of this project the caller may see, or raise 404."""
    statement = select(SaleContract).where(
        SaleContract.id == sale_id, SaleContract.project_id == project.id
    )
    allowed = visible_units(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(SaleContract.unit_id.in_(allowed))
    sale = session.scalars(statement).first()
    if sale is None:
        raise NotFoundError(_NO_SALE)
    return sale


def version_not_found() -> NotFoundError:
    """The one refusal for a version that is missing or wrongly parented."""
    return NotFoundError(_NO_VERSION)


def pool_not_found() -> NotFoundError:
    """The one refusal for a pool that is missing, hidden or wrongly parented."""
    return NotFoundError(_NO_POOL)


def unit_cost_not_found() -> NotFoundError:
    """The one refusal for a unit cost that is missing, hidden or wrongly parented."""
    return NotFoundError(_NO_COST)


def accessible_project_for_economics(
    project_id: Annotated[uuid.UUID, Path()],
    session: DbSession,
    actor: ActiveActor,
) -> Project:
    """Resolve ``{project_id}`` to a project the caller may open."""
    return require_project_access(session, project_id=project_id, actor=actor)


EconomicsProject = Annotated[Project, Depends(accessible_project_for_economics)]
