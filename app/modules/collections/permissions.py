"""Who may record cash, who may confirm it, and who may see any of it.

Three separations, and each exists because of a specific way money goes missing.

**Collections records; Finance confirms.** The department chasing the money is
not the department that gets to declare it arrived. A recorded receipt is a
claim — usually a true one, occasionally a transfer that bounced, a duplicate,
or an optimistic reading of a screenshot — and it moves no balance until
somebody with sight of the bank account says it did.

**The recorder is never the confirmer, by identifier.** Checked against the
user who recorded the receipt, not merely against a role, because a person who
holds both Collections and Finance would otherwise be a complete maker/checker
pair on their own.

**The System Administrator has no financial authority.** They can see the
ledger — administering a platform means being able to diagnose it — and they
can confirm nothing, approve nothing and clear nothing. Administering the
software that records the money is not authority over the money.

Visibility is inherited rather than restated. A receipt is exactly as visible
as the sale it belongs to, which is exactly as visible as the unit that was
sold, so the narrowing is imported from payment plans — which imports it from
sales — instead of being written a third time. Three copies of a phase rule is
two copies waiting to disagree, and the way that disagreement surfaces is a
buyer's payment history appearing to somebody who was never granted the phase.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy import Select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, PermissionDeniedError
from app.modules.access.dependencies import ActiveActor, ActorContext, DbSession
from app.modules.payment_plans.permissions import visible_sale_ids
from app.modules.projects.models import Project
from app.modules.projects.permissions import require_project_access
from app.modules.sales.models import SaleContract

# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #

#: Who may open the collections workspace at all.
#:
#: The same set that may read a payment plan, for the obvious reason: a
#: schedule nobody can check against receipts is half a story, and the people
#: entitled to the first half are entitled to the second.
COLLECTION_READER_ROLES = frozenset(
    {
        "system_admin",
        "project_manager",
        "sales_operations",
        "sales_advisor",
        "legal",
        "collections",
        "finance",
        "approver_cfo",
        "executive_viewer",
        "auditor",
    }
)

# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #

#: Who may record receipts and refund requests, allocate confirmed cash, log
#: chases, open disputes, ask for a waiver, raise and apply a restructure, and
#: sign the collections clearance.
COLLECTION_WRITER_ROLES = frozenset({"collections"})

#: Who may confirm that money actually moved, in either direction, and reverse
#: a confirmation that turns out to be wrong.
FINANCE_ROLES = frozenset({"finance"})

#: Who may sanction an operational waiver. The same office that sanctions the
#: schedule itself, because pausing enforcement is a concession with a cost.
WAIVER_APPROVER_ROLES = frozenset({"approver_cfo"})

_FORBIDDEN = "You do not have permission to perform this action."
_MAKER = "The person who recorded this may not confirm it."
_MAKER_WAIVER = "The person who asked for this waiver may not approve it."
_SALE_NOT_FOUND = "Sale contract not found."
_RECEIPT_NOT_FOUND = "Receipt not found."


def _require_any(actor: ActorContext, roles: frozenset[str], detail: str) -> None:
    if not actor.role_keys.intersection(roles):
        raise PermissionDeniedError(detail)


def require_collection_reader(actor: ActorContext) -> None:
    """Gate the collections workspace."""
    _require_any(actor, COLLECTION_READER_ROLES, _FORBIDDEN)


def require_collection_writer(actor: ActorContext) -> None:
    """Gate everything Collections does with its own ledger."""
    _require_any(actor, COLLECTION_WRITER_ROLES, "Only Collections may do this.")


def require_finance(actor: ActorContext) -> None:
    """Gate confirming and reversing a movement of actual cash."""
    _require_any(actor, FINANCE_ROLES, "Only Finance may confirm that money moved.")


def require_waiver_approver(actor: ActorContext) -> None:
    """Gate deciding a collection waiver."""
    _require_any(actor, WAIVER_APPROVER_ROLES, "Only an Approver / CFO may decide a waiver.")


def require_different_confirmer(actor: ActorContext, *, recorded_by_user_id: uuid.UUID) -> None:
    """Refuse a confirmation by the person who recorded the transaction.

    By identifier, not by role. Somebody holding both Collections and Finance
    still cannot be both halves of the pair: the point of the second signature
    is that a second pair of eyes saw the bank, and their own eyes are the ones
    already counted.
    """
    if recorded_by_user_id == actor.user_id:
        raise PermissionDeniedError(_MAKER)


def require_different_waiver_approver(
    actor: ActorContext, *, submitted_by_user_id: uuid.UUID
) -> None:
    """Refuse an approval by the person who asked for the concession."""
    if submitted_by_user_id == actor.user_id:
        raise PermissionDeniedError(_MAKER_WAIVER)


# --------------------------------------------------------------------------- #
# Row and phase scoping
# --------------------------------------------------------------------------- #


def visible_sales(
    session: Session, *, project_id: uuid.UUID, actor: ActorContext
) -> Select[tuple[uuid.UUID]] | None:
    """A subquery of sale ids this caller may see, or ``None`` for no narrowing.

    Imported wholesale from payment plans. Collections must be exactly as
    narrow as the schedule it collects against — anything else would be a route
    through which a phase-scoped advisor could read a contract value they were
    refused two screens earlier.
    """
    return visible_sale_ids(session, project_id=project_id, actor=actor)


def require_visible_sale(
    session: Session, *, project: Project, sale_id: uuid.UUID, actor: ActorContext
) -> SaleContract:
    """Load a sale of this project the caller may see, or raise 404."""
    from sqlalchemy import select

    statement = select(SaleContract).where(
        SaleContract.id == sale_id, SaleContract.project_id == project.id
    )
    allowed = visible_sales(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(SaleContract.id.in_(allowed))
    sale = session.scalars(statement).first()
    if sale is None:
        raise NotFoundError(_SALE_NOT_FOUND)
    return sale


def receipt_not_found() -> NotFoundError:
    """The one refusal for a receipt that is missing, hidden or wrongly parented."""
    return NotFoundError(_RECEIPT_NOT_FOUND)


def accessible_project_for_collections(
    project_id: Annotated[uuid.UUID, Path()],
    session: DbSession,
    actor: ActiveActor,
) -> Project:
    """Resolve ``{project_id}`` to a project the caller may open."""
    return require_project_access(session, project_id=project_id, actor=actor)


CollectionProject = Annotated[Project, Depends(accessible_project_for_collections)]
