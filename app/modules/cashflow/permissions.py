"""Who may see the project's cash, and who may move it.

Cash is the one figure that decides whether a development survives the quarter,
and the reading list here is short for the same reason unit economics' is: being
able to see a unit, a contract or a receipt is not a reason to see the whole
development's funding position. A Sales Advisor who could read the peak deficit
would know exactly how badly the company needs their next deal to close.

Four separations, each with a specific failure behind it.

**Recording is not paying, and the confirmer is never the recorder.** A
development or financing movement becomes cash only when a second person says it
did — compared by user identifier, because one user holding Finance and Approver
/ CFO is one pair of eyes. The same applies to an escrow release, which is the
act that makes restricted money spendable.

**Finance prepares a forecast; the Approver / CFO approves it.** A cashflow
forecast is what a funding conversation with a bank is built on. One person
writing the monthly schedule and signing it is one person deciding what the
company will tell its lender.

**The System Administrator has no financial authority.** They may read —
running the platform means being able to diagnose it — and they may confirm
nothing, approve nothing and activate nothing.

**A partial view of a project total is refused, not filtered.** This is the rule
that matters most here, because cash makes the alternative tempting. Bank cash
is *project* cash: it is not held in per-phase accounts, so there is no honest
way to answer "Phase A's closing balance". A phase-scoped reader shown a filtered
total would get a number that is neither the project's nor their phase's, with
nothing on screen to say which. Every whole-project cash surface therefore
requires whole-project access, and the source drill-downs that genuinely belong
to a phase keep the phase narrowing they already have.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Path

from app.core.errors import NotFoundError, PermissionDeniedError
from app.modules.access.dependencies import ActiveActor, ActorContext, DbSession
from app.modules.inventory.permissions import visible_phase_ids
from app.modules.projects.models import Project
from app.modules.projects.permissions import require_project_access

# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #

#: Who may see the project's cash position, funding requirement and returns.
#:
#: Notably absent: Sales Advisor, Sales Operations, Legal, Design / Engineering
#: and Collections. Collections is the interesting exclusion — its users work
#: with customer cash every day and keep every collections surface they already
#: have. What they do not get through this module is the development cost side,
#: the financing arrangements and the funding gap, none of which is needed to
#: chase a buyer and all of which would be a wider disclosure than their job.
CASHFLOW_READER_ROLES = frozenset(
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

#: Who may prepare a cashflow forecast and record cash this module owns.
#: Project Manager joins Finance on forecast preparation because the monthly
#: shape of construction spend is a delivery judgement before it is a financial
#: one; the confirming and approving sets below are where the control sits.
CASHFLOW_PREPARER_ROLES = frozenset({"finance", "project_manager"})

#: Who may record a development or financing movement, a restriction or a
#: release. Finance alone: these are disbursements and bank instructions.
CASHFLOW_RECORDER_ROLES = frozenset({"finance"})

#: Who may confirm that cash actually moved. A second Finance user or the
#: Approver / CFO — the identifier comparison below is what makes "a second
#: Finance user" mean a genuinely different person.
CASHFLOW_CONFIRMER_ROLES = frozenset({"finance", "approver_cfo"})

#: Who may approve a submitted cashflow forecast. Deliberately narrower than the
#: confirmer set: approving the statement the company will fund itself against
#: is not the same authority as confirming that a consultant was paid.
CASHFLOW_APPROVER_ROLES = frozenset({"approver_cfo"})

#: Who may put an approved forecast in force.
CASHFLOW_ACTIVATOR_ROLES = frozenset({"finance", "approver_cfo"})

_FORBIDDEN = "You do not have permission to perform this action."
_MAKER = "The person who recorded this may not confirm it."
_SUBMITTER = "The person who submitted this forecast may not approve it."
_NO_FORECAST = "Cashflow forecast not found."
_NO_MOVEMENT = "Movement not found."
_NO_RESTRICTION = "Restriction not found."
_NO_RELEASE = "Release not found."


def _require_any(actor: ActorContext, roles: frozenset[str], detail: str) -> None:
    if not actor.role_keys.intersection(roles):
        raise PermissionDeniedError(detail)


def require_cashflow_reader(actor: ActorContext) -> None:
    """Gate every cash figure this module produces."""
    _require_any(actor, CASHFLOW_READER_ROLES, _FORBIDDEN)


def require_cashflow_preparer(actor: ActorContext) -> None:
    """Gate creating a forecast version and writing its lines."""
    _require_any(
        actor,
        CASHFLOW_PREPARER_ROLES,
        "Only Finance or a Project Manager may prepare a cashflow forecast.",
    )


def require_cashflow_recorder(actor: ActorContext) -> None:
    """Gate recording cash this module owns, and escrow."""
    _require_any(actor, CASHFLOW_RECORDER_ROLES, "Only Finance may record this.")


def require_cashflow_confirmer(actor: ActorContext) -> None:
    """Gate confirming that cash moved.

    The System Administrator is not in this set and must never be added to it:
    the person who can reach the database is not the person who says money left
    the bank.
    """
    _require_any(
        actor,
        CASHFLOW_CONFIRMER_ROLES,
        "Only a second Finance user or an Approver / CFO may confirm cash movement.",
    )


def require_cashflow_approver(actor: ActorContext) -> None:
    """Gate approving or rejecting a submitted forecast."""
    _require_any(
        actor,
        CASHFLOW_APPROVER_ROLES,
        "Only an Approver / CFO may approve a cashflow forecast.",
    )


def require_cashflow_activator(actor: ActorContext) -> None:
    """Gate putting an approved forecast in force."""
    _require_any(
        actor,
        CASHFLOW_ACTIVATOR_ROLES,
        "Only Finance or an Approver / CFO may activate a cashflow forecast.",
    )


def require_different_confirmer(actor: ActorContext, *, recorded_by_user_id: uuid.UUID) -> None:
    """Refuse a confirmation by the person who recorded the movement."""
    if recorded_by_user_id == actor.user_id:
        raise PermissionDeniedError(_MAKER)


def require_different_approver(actor: ActorContext, *, submitted_by_user_id: uuid.UUID) -> None:
    """Refuse an approval by the person who submitted the forecast."""
    if submitted_by_user_id == actor.user_id:
        raise PermissionDeniedError(_SUBMITTER)


# --------------------------------------------------------------------------- #
# Scope
# --------------------------------------------------------------------------- #


def require_whole_project_scope(
    session: DbSession, *, project_id: uuid.UUID, actor: ActorContext
) -> None:
    """Gate every project cash surface on access to the whole project.

    There is no per-phase bank account. Opening cash, restricted cash, the
    funding gap, the peak deficit, NPV and IRR are all properties of the
    development as a whole, and the only way to give a phase-scoped reader a
    number is to invent an allocation of cash to phases that the business does
    not have.

    So this refuses rather than filters. A caller narrowed to Phase A who could
    open the cash position would be shown a total assembled from part of the
    project and labelled as the project's — the specific failure PR-MVP-07 and
    PR-MVP-09 both already refused, arriving here through a different door.
    """
    if visible_phase_ids(session, project_id=project_id, actor=actor) is not None:
        raise PermissionDeniedError(
            "The project's cash position is a whole-project figure: there is no "
            "per-phase bank account to report, so a phase-scoped view of it would "
            "be a total that is neither the project's nor your own. This needs "
            "whole-project access."
        )


def forecast_not_found() -> NotFoundError:
    """The one refusal for a forecast that is missing or wrongly parented."""
    return NotFoundError(_NO_FORECAST)


def movement_not_found() -> NotFoundError:
    """The one refusal for a movement that is missing or wrongly parented."""
    return NotFoundError(_NO_MOVEMENT)


def restriction_not_found() -> NotFoundError:
    """The one refusal for a restriction that is missing or wrongly parented."""
    return NotFoundError(_NO_RESTRICTION)


def release_not_found() -> NotFoundError:
    """The one refusal for a release that is missing or wrongly parented."""
    return NotFoundError(_NO_RELEASE)


# --------------------------------------------------------------------------- #
# Route dependency
# --------------------------------------------------------------------------- #


def accessible_project_for_cashflow(
    project_id: Annotated[uuid.UUID, Path()],
    session: DbSession,
    actor: ActiveActor,
) -> Project:
    """Resolve ``{project_id}`` to a project whose cash the caller may read.

    Three gates in one dependency, in the order that keeps a refusal from
    leaking: membership first, so a non-member sees a project-shaped 404 rather
    than a 403 confirming the project exists; then the reading list; then whole-
    project scope, because every route hanging off this one is a project total.
    """
    project = require_project_access(session, project_id=project_id, actor=actor)
    require_cashflow_reader(actor)
    require_whole_project_scope(session, project_id=project.id, actor=actor)
    return project


#: The dependency every project cashflow route hangs off.
CashflowProject = Annotated[Project, Depends(accessible_project_for_cashflow)]
