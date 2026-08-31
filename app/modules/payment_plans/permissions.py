"""Who may schedule money, who may sanction the schedule, and who may see it.

The separations are the ones PR-MVP-05 already established, applied to a
different question.

**Collections owns the operational schedule.** They prepare it, correct the
draft, generate the recurring dates, put it forward and maintain the forecast
and ownership of live instalments. They do not sanction their own work.

**The Approver / CFO sanctions.** Approval of a payment schedule is a financial
decision about when this company gets paid, and it belongs to the office that
already sanctions discounts and gate waivers — not to whoever prepared it, and
not to the System Administrator, because administering a platform is not
authority over its receivables.

**Visibility is inherited, never restated.** A payment plan is exactly as
visible as the sale it schedules, which is exactly as visible as the unit that
was sold. The narrowing is imported from sales rather than reimplemented: two
copies of a phase rule are one copy that eventually disagrees, and the way that
disagreement surfaces is a contract value appearing to somebody who was never
granted the phase.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, PermissionDeniedError
from app.modules.access.dependencies import ActiveActor, ActorContext, DbSession
from app.modules.projects.models import Project
from app.modules.projects.permissions import require_project_access
from app.modules.sales.models import Client, SaleContract
from app.modules.sales.permissions import restricts_clients_to_own, visible_unit_ids

# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #

#: Who may open the payment plans workspace at all.
#:
#: Design / Engineering is absent for the same reason it is absent from sales:
#: their work ends at the unit. Everyone else with a stake in whether the
#: company gets paid is here, narrowed further by phase and by advisor
#: assignment below.
PLAN_READER_ROLES = frozenset(
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

#: Who may create a plan, edit its draft schedule and put it forward.
#:
#: Collections, and deliberately nobody else. Finance reads the schedule and
#: the CFO sanctions it; neither drafts it, because the department that will
#: have to chase these dates is the department that should be choosing them.
PLAN_WRITER_ROLES = frozenset({"collections"})

#: Who may sanction a schedule, and decide a manually attested trigger.
PLAN_APPROVER_ROLES = frozenset({"approver_cfo"})

#: Who may maintain a live plan's operational fields — the forecast date for a
#: contingent instalment, and who is chasing it. Not a contractual change, so
#: not a new version, but still audited and still Collections' to make.
PLAN_OPERATIONS_ROLES = frozenset({"collections"})

#: Roles a user must hold to be named as an instalment's owner. An arbitrary
#: user identifier is not somebody who chases payments.
INSTALLMENT_OWNER_ROLES = frozenset({"collections", "sales_operations"})

_FORBIDDEN = "You do not have permission to perform this action."
_MAKER = "The person who prepared this may not approve it."
_PLAN_NOT_FOUND = "Payment plan not found."
_SALE_NOT_FOUND = "Sale contract not found."


def _require_any(actor: ActorContext, roles: frozenset[str], detail: str) -> None:
    if not actor.role_keys.intersection(roles):
        raise PermissionDeniedError(detail)


def require_plan_reader(actor: ActorContext) -> None:
    """Gate the payment plans workspace."""
    _require_any(actor, PLAN_READER_ROLES, _FORBIDDEN)


def require_plan_writer(actor: ActorContext) -> None:
    """Gate creating a plan and editing the draft schedule."""
    _require_any(actor, PLAN_WRITER_ROLES, "Only Collections may prepare a payment plan.")


def require_plan_approver(actor: ActorContext) -> None:
    """Gate approving or rejecting a version, and deciding a manual trigger."""
    _require_any(actor, PLAN_APPROVER_ROLES, "Only an Approver / CFO may sanction this.")


def require_plan_operator(actor: ActorContext) -> None:
    """Gate forecast and ownership maintenance on a live schedule."""
    _require_any(actor, PLAN_OPERATIONS_ROLES, _FORBIDDEN)


def require_different_checker(actor: ActorContext, *, maker_user_id: uuid.UUID | None) -> None:
    """Refuse an approval by the person who asked for it.

    Applied to whoever submitted, not whoever first created the draft: the
    submitter is the one asserting the schedule is right, and theirs is the
    signature the approval exists to be independent of.
    """
    if maker_user_id is not None and maker_user_id == actor.user_id:
        raise PermissionDeniedError(_MAKER)


# --------------------------------------------------------------------------- #
# Row and phase scoping
# --------------------------------------------------------------------------- #


def visible_sale_ids(
    session: Session, *, project_id: uuid.UUID, actor: ActorContext
) -> Select[tuple[uuid.UUID]] | None:
    """A subquery of sale ids this caller may see, or ``None`` for no narrowing.

    Both of sales' restrictions apply, because a plan must be exactly as
    visible as its sale: the phase the unit sits in, and — for an advisor who
    is nothing else — the buyers assigned to them.
    """
    units = visible_unit_ids(session, project_id=project_id, actor=actor)
    advisor_scoped = restricts_clients_to_own(actor)
    if units is None and not advisor_scoped:
        return None
    statement = select(SaleContract.id).where(SaleContract.project_id == project_id)
    if units is not None:
        statement = statement.where(SaleContract.unit_id.in_(units))
    if advisor_scoped:
        statement = statement.where(
            SaleContract.client_id.in_(
                select(Client.id).where(
                    Client.project_id == project_id,
                    Client.owner_advisor_user_id == actor.user_id,
                )
            )
        )
    return statement


def require_visible_sale(
    session: Session, *, project: Project, sale_id: uuid.UUID, actor: ActorContext
) -> SaleContract:
    """Load a sale of this project the caller may see, or raise 404.

    A sale in a phase the caller was not granted answers exactly as a sale that
    does not exist. A 403 would confirm the identifier is real, and confirming
    that a hidden phase contains a particular contract is the disclosure phase
    scoping exists to prevent.
    """
    statement = select(SaleContract).where(
        SaleContract.id == sale_id, SaleContract.project_id == project.id
    )
    allowed = visible_sale_ids(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(SaleContract.id.in_(allowed))
    sale = session.scalars(statement).first()
    if sale is None:
        raise NotFoundError(_SALE_NOT_FOUND)
    return sale


def plan_not_found() -> NotFoundError:
    """The one refusal for a plan the caller may not see or that is not there."""
    return NotFoundError(_PLAN_NOT_FOUND)


def accessible_project_for_plans(
    project_id: Annotated[uuid.UUID, Path()],
    session: DbSession,
    actor: ActiveActor,
) -> Project:
    """Resolve ``{project_id}`` to a project the caller may open."""
    return require_project_access(session, project_id=project_id, actor=actor)


PlanProject = Annotated[Project, Depends(accessible_project_for_plans)]
