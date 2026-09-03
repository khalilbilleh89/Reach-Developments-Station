"""Who may see what the build costs, and who may commit the company to it.

Construction holds the developer's cost side: what was authorised, what has been
signed with contractors, what has been certified and what has been paid out.
None of it is a buyer's business, and most of it is not a salesperson's either,
so the reading list here is short and being able to see a unit is not a reason
to see what building it cost.

Four separations, each with a specific failure behind it.

**Reading construction is not reading the project.** Sales Advisor, Sales
Operations, Legal and Collections are all absent below. Each of them can see
units, contracts, schedules or receipts through their own module; none of them
needs the contractor's rates, and an advisor who knows the build cost of a unit
has an argument for a discount the company never agreed to make available.

**The person who prepares is never the person who approves.** A budget, a
contract, a variation, a certificate and a payment each have a maker and a
checker, and the checker is compared by user identifier rather than by role: a
user holding both Finance and Approver / CFO is still one pair of eyes.

**The System Administrator has no financial authority.** They may read — running
the platform means being able to diagnose it — and they may approve nothing,
activate nothing, certify nothing and confirm no payment. Administering the
database that stores a commitment is not authority over the commitment.

**A partial view of a project total is worse than no total.** A phase-scoped
reader who opened a budget would be shown "the project's budget" with the hidden
phases' lines quietly removed — a number that is not the project's budget, is not
their phase's budget, and carries no sign that anything is missing. So every
whole-project financial surface requires whole-project access, and the technical
records that genuinely belong to one phase stay available.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, PermissionDeniedError
from app.modules.access.dependencies import ActiveActor, ActorContext, DbSession
from app.modules.inventory.permissions import visible_phase_ids
from app.modules.projects.models import Project
from app.modules.projects.permissions import require_project_access

# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #

#: Who may see the construction workspace at all.
#:
#: Design / Engineering is here and is not in the unit economics reader set,
#: which is the difference between the two modules: what the build costs the
#: developer is information the people running the build need, and what margin
#: a unit earns is not.
CONSTRUCTION_READER_ROLES = frozenset(
    {
        "system_admin",
        "project_manager",
        "design_engineering",
        "finance",
        "approver_cfo",
        "executive_viewer",
        "auditor",
    }
)

# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #

#: Who may maintain the cost breakdown and prepare a budget or a contract for
#: someone else to authorise. Preparation is not authorisation: nothing in this
#: set commits the company to anything on its own.
CONSTRUCTION_PREPARER_ROLES = frozenset({"project_manager", "finance"})

#: Who may run the build's technical record — milestones, progress, evidence and
#: the certificates that evidence work done.
CONSTRUCTION_TECHNICAL_ROLES = frozenset({"project_manager", "design_engineering", "finance"})

#: Who may certify a progress certificate. Certification is what turns a
#: contractor's claim into cost and, where a milestone depends on it, into a
#: buyer's payable instalment — so it sits with the people accountable for the
#: build and for the money, never with whoever drafted the valuation.
CONSTRUCTION_CERTIFIER_ROLES = frozenset({"project_manager", "design_engineering", "finance"})

#: Who may record an invoice, prepare a payment and maintain the forecast.
CONSTRUCTION_FINANCE_ROLES = frozenset({"finance"})

#: Who may approve a variation within the country pack's review threshold, and
#: who may confirm that cash has left. Two Finance users are a genuine pair of
#: eyes once the maker/checker rule below has compared their identifiers.
CONSTRUCTION_CHECKER_ROLES = frozenset({"finance", "approver_cfo"})

#: Who may approve a budget, approve a forecast, and approve a variation at or
#: above the configured review amount. The System Administrator is not here and
#: must never be added: the point of the separation is that the person who can
#: reach the database is not the person who signs what it says.
CONSTRUCTION_APPROVER_ROLES = frozenset({"approver_cfo"})

#: Who may put a governed basis into force once it is approved.
CONSTRUCTION_ACTIVATOR_ROLES = frozenset({"finance", "approver_cfo"})

_FORBIDDEN = "You do not have permission to perform this action."
_MAKER = "The person who submitted this may not approve it."
_RECORDER = "The person who recorded this payment may not confirm it."

_NO_COST_CODE = "Cost code not found."
_NO_BUDGET = "Budget version not found."
_NO_CONTRACT = "Contract not found."
_NO_VARIATION = "Variation not found."
_NO_CERTIFICATE = "Certificate not found."
_NO_INVOICE = "Invoice not found."
_NO_PAYMENT = "Payment not found."
_NO_MILESTONE = "Milestone not found."
_NO_FORECAST = "Forecast version not found."


def _require_any(actor: ActorContext, roles: frozenset[str], detail: str) -> None:
    if not actor.role_keys.intersection(roles):
        raise PermissionDeniedError(detail)


def require_construction_reader(actor: ActorContext) -> None:
    """Gate every figure this module produces."""
    _require_any(actor, CONSTRUCTION_READER_ROLES, _FORBIDDEN)


def require_construction_preparer(actor: ActorContext) -> None:
    """Gate maintaining cost codes and preparing a budget or contract."""
    _require_any(
        actor,
        CONSTRUCTION_PREPARER_ROLES,
        "Only a Project Manager or Finance may prepare this.",
    )


def require_construction_technical(actor: ActorContext) -> None:
    """Gate the milestone and certificate workflow."""
    _require_any(
        actor,
        CONSTRUCTION_TECHNICAL_ROLES,
        "Only a Project Manager, Design / Engineering or Finance may do this.",
    )


def require_construction_certifier(actor: ActorContext) -> None:
    """Gate certifying work and certifying a milestone."""
    _require_any(
        actor,
        CONSTRUCTION_CERTIFIER_ROLES,
        "Only a Project Manager, Design / Engineering or Finance may certify this.",
    )


def require_construction_finance(actor: ActorContext) -> None:
    """Gate invoices, payment preparation and forecast input."""
    _require_any(actor, CONSTRUCTION_FINANCE_ROLES, "Only Finance may do this.")


def require_construction_checker(actor: ActorContext) -> None:
    """Gate a standard variation approval and a payment confirmation."""
    _require_any(
        actor,
        CONSTRUCTION_CHECKER_ROLES,
        "Only a second Finance user or an Approver / CFO may do this.",
    )


def require_construction_approver(actor: ActorContext) -> None:
    """Gate a budget approval, a forecast approval and an escalated variation.

    The threshold that decides whether a variation lands here is the country
    pack's ``construction_variation_review_amount``, evaluated on the server
    against the absolute value of the change. A large omission is as much a
    scope decision as a large addition.
    """
    _require_any(
        actor,
        CONSTRUCTION_APPROVER_ROLES,
        "Only an Approver / CFO may approve this.",
    )


def require_construction_activator(actor: ActorContext) -> None:
    """Gate putting an approved budget or forecast into force."""
    _require_any(
        actor,
        CONSTRUCTION_ACTIVATOR_ROLES,
        "Only Finance or an Approver / CFO may activate this.",
    )


def require_different_approver(
    actor: ActorContext, *, submitted_by_user_id: uuid.UUID | None
) -> None:
    """Refuse an approval by the person who submitted the thing being approved."""
    if submitted_by_user_id is not None and submitted_by_user_id == actor.user_id:
        raise PermissionDeniedError(_MAKER)


def require_different_confirmer(actor: ActorContext, *, recorded_by_user_id: uuid.UUID) -> None:
    """Refuse a payment confirmation by the person who recorded it.

    Money leaving the project gets the same discipline as money arriving. A
    single Finance user who can both prepare and release a disbursement is the
    control failure every construction fraud case has in common.
    """
    if recorded_by_user_id == actor.user_id:
        raise PermissionDeniedError(_RECORDER)


# --------------------------------------------------------------------------- #
# Scope
# --------------------------------------------------------------------------- #


def require_whole_project_scope(
    session: Session, *, project_id: uuid.UUID, actor: ActorContext
) -> None:
    """Gate every whole-project financial surface on access to the whole project.

    A budget, a forecast, a project summary and a reconciliation are all
    statements about the entire development. Narrowed to a caller's phases they
    would print a number labelled "the project's control budget" that is not the
    project's control budget and is not their phase's either — and, unlike a
    register with rows missing, nothing about the figure says so.

    The alternative of filtering is worse than refusing, and PR-MVP-07 refused a
    summary of an unstated subset for the same reason. Phase-scoped users keep
    the technical records that genuinely belong to their phase.
    """
    if visible_phase_ids(session, project_id=project_id, actor=actor) is not None:
        raise PermissionDeniedError(
            "Construction budgets, forecasts and totals cover the whole project, "
            "including phases outside your access. Your role can read the "
            "construction records of the phases you are scoped to, but not the "
            "project's financial position."
        )


def has_whole_project_scope(
    session: Session, *, project_id: uuid.UUID, actor: ActorContext
) -> bool:
    """Whether this caller sees the whole project, for a record that spans it.

    A contract, a certificate or an invoice belongs to the project rather than
    to a phase: its cost codes may reach across several. Rather than filter its
    money down to the caller's phases and present the remainder as the record,
    such a record answers 404 for a narrowed caller — a subtotal labelled as a
    contract value is a lie a reader has no way to detect.
    """
    return visible_phase_ids(session, project_id=project_id, actor=actor) is None


def cost_code_not_found() -> NotFoundError:
    """The one refusal for a cost code that is missing or wrongly parented."""
    return NotFoundError(_NO_COST_CODE)


def budget_not_found() -> NotFoundError:
    """The one refusal for a budget version that is missing or wrongly parented."""
    return NotFoundError(_NO_BUDGET)


def contract_not_found() -> NotFoundError:
    """The one refusal for a contract that is missing, hidden or wrongly parented."""
    return NotFoundError(_NO_CONTRACT)


def variation_not_found() -> NotFoundError:
    """The one refusal for a variation that is missing or wrongly parented."""
    return NotFoundError(_NO_VARIATION)


def certificate_not_found() -> NotFoundError:
    """The one refusal for a certificate that is missing or wrongly parented."""
    return NotFoundError(_NO_CERTIFICATE)


def invoice_not_found() -> NotFoundError:
    """The one refusal for an invoice that is missing or wrongly parented."""
    return NotFoundError(_NO_INVOICE)


def payment_not_found() -> NotFoundError:
    """The one refusal for a payment that is missing or wrongly parented."""
    return NotFoundError(_NO_PAYMENT)


def milestone_not_found() -> NotFoundError:
    """The one refusal for a milestone that is missing or wrongly parented."""
    return NotFoundError(_NO_MILESTONE)


def forecast_not_found() -> NotFoundError:
    """The one refusal for a forecast version that is missing or wrongly parented."""
    return NotFoundError(_NO_FORECAST)


def accessible_project_for_construction(
    project_id: Annotated[uuid.UUID, Path()],
    session: DbSession,
    actor: ActiveActor,
) -> Project:
    """Resolve ``{project_id}`` to a project whose construction the caller may read."""
    project = require_project_access(session, project_id=project_id, actor=actor)
    require_construction_reader(actor)
    return project


ConstructionProject = Annotated[Project, Depends(accessible_project_for_construction)]


def project_for_whole_project_finance(
    project_id: Annotated[uuid.UUID, Path()],
    session: DbSession,
    actor: ActiveActor,
) -> Project:
    """Resolve ``{project_id}`` for a route that exposes a whole-project total."""
    project = require_project_access(session, project_id=project_id, actor=actor)
    require_construction_reader(actor)
    require_whole_project_scope(session, project_id=project.id, actor=actor)
    return project


#: For every route that returns a project-wide financial position — the summary,
#: the reconciliation, budgets and forecasts. A dependency rather than a line in
#: each handler, because the failure mode of the alternative is one route
#: somebody forgot, and that route hands a phase-scoped reader the whole
#: project's cost.
GovernedConstructionProject = Annotated[Project, Depends(project_for_whole_project_finance)]
