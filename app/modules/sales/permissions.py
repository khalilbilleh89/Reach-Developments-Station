"""Who may sell, who may approve, who may see a buyer's passport number.

Three separations run through this file, and none of them is a policy engine.

**Maker is not checker.** The person who prepares a discount does not sanction
it, and the person who prepares a contract does not waive its payment gate. That
is two role sets and one comparison of user identifiers.

**Administration is not business authority.** A System Administrator configures
the platform. They do not approve exceptions, waive gates, record registry
events, or read buyers' identity documents by default. A role that silently
contains every other role is how financial and privacy control become
decorative.

**One department cannot clear another's concern.** Legal grants legal clearance,
Collections grants collection clearance, and delivery readiness belongs to the
people who built the thing. Sales Operations completes a handover; it does not
sign off all three gates first.

Phase visibility is imported from inventory rather than restated: a sale must be
exactly as visible as the unit it is a sale of, and two copies of that rule are
one copy that eventually disagrees.

Personal data is decided here, before serialisation, and never in the browser.
``visible_party_fields`` returns the set of columns a caller may be shown; a
route that wants fewer fields asks for fewer fields, it does not fetch the row
and trust React to omit them.
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
from app.modules.sales.models import Client

# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #

#: Who may open the sales workspace at all. Everyone with a stake in a sale —
#: and deliberately not Design / Engineering, whose work ends at the unit.
SALES_READER_ROLES = frozenset(
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

#: Who may see the money on a deal: the quote waterfall, the concessions, the
#: seller cost, the frozen taxes. Executive Viewer is here for the approved
#: contract totals; the advisor for their own deals.
SALES_FINANCIAL_READER_ROLES = frozenset(
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

#: Who may read a buyer's identity documents, tax identifier, contact details
#: and address.
#:
#: Not the Project Manager, who runs a development and does not need a passport
#: number to do it. Not Finance, who needs the money and not the person. Not the
#: Executive Viewer, who reads totals. Not the System Administrator, because
#: administering a database is not authority over the people in it. The
#: assigned advisor is admitted separately, per client, by ``may_read_client_pii``.
CLIENT_PII_ROLES = frozenset({"sales_operations", "legal", "collections", "auditor"})

#: Columns on a buyer party that are personal data. Named once so a route cannot
#: quietly serialise one this file never considered.
PARTY_PII_FIELDS = frozenset(
    {
        "tax_id",
        "identity_document_type",
        "identity_document_number",
        "poa_reference",
        "representative_name",
    }
)

#: Columns on a client that are personal data.
CLIENT_PII_FIELDS = frozenset({"email", "phone", "address"})

# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #

#: Who may create and correct a buyer record and its parties.
CLIENT_WRITER_ROLES = frozenset({"sales_operations", "sales_advisor"})

#: Who may prepare a reservation and the commercial terms on it.
RESERVATION_WRITER_ROLES = frozenset({"sales_operations", "sales_advisor"})

#: Who may turn a reservation into a contract, put it forward for signature and
#: activate it. Narrower than reservation preparation on purpose: an advisor
#: prepares terms, the desk commits the company to them.
SALE_WRITER_ROLES = frozenset({"sales_operations"})

#: Who may attest that deposit or first-payment evidence exists. Attestation,
#: not cash: PR-MVP-07 owns receipts, and this right must never be read as
#: authority to record money received.
GATE_EVIDENCE_ROLES = frozenset({"sales_operations"})

#: Who may waive a gate, or sanction a quote exception. One office, and not the
#: administrator: the ability to configure a system is not the authority to let
#: a unit go without the deposit the project requires.
FINANCIAL_APPROVER_ROLES = frozenset({"approver_cfo"})

#: Who may record what the registry did.
LEGAL_WRITER_ROLES = frozenset({"legal"})

#: Who may open and advance a cancellation. Legal is included because a
#: developer-default process and a registry withdrawal are their work.
CANCELLATION_WRITER_ROLES = frozenset({"sales_operations", "legal"})

#: Who may run a handover: schedule it, record snagging, complete it once every
#: configured clearance is in place.
HANDOVER_WRITER_ROLES = frozenset({"sales_operations"})

#: Who owns each clearance. The whole point of the gate is that one department
#: cannot clear another's concern, so this map is the separation, stated once.
CLEARANCE_OWNER_ROLES: dict[str, frozenset[str]] = {
    "legal": frozenset({"legal"}),
    "collection": frozenset({"collections"}),
    "delivery": frozenset({"project_manager", "design_engineering"}),
}

#: Who may set the project's sales policy.
SALES_POLICY_ROLES = frozenset({"system_admin", "project_manager"})

#: Roles a user must hold to be named as the advisor on a deal. An arbitrary
#: user identifier is not a salesperson.
ADVISOR_ROLES = frozenset({"sales_advisor", "sales_operations"})

_FORBIDDEN_DETAIL = "You do not have permission to perform this action."
_MAKER_DETAIL = "The person who prepared this may not approve it."
_SETUP_DETAIL = "Finalize the project setup before recording sales."
_CLIENT_NOT_FOUND = "Client not found."
_UNIT_NOT_FOUND = "Unit not found."


def _require_any(actor: ActorContext, roles: frozenset[str], detail: str) -> None:
    if not actor.role_keys.intersection(roles):
        raise PermissionDeniedError(detail)


def require_sales_reader(actor: ActorContext) -> None:
    """Gate the sales workspace."""
    _require_any(actor, SALES_READER_ROLES, _FORBIDDEN_DETAIL)


def require_client_writer(actor: ActorContext) -> None:
    """Gate creating and correcting buyers and their parties."""
    _require_any(actor, CLIENT_WRITER_ROLES, _FORBIDDEN_DETAIL)


def require_reservation_writer(actor: ActorContext) -> None:
    """Gate reservation preparation and its commercial terms."""
    _require_any(actor, RESERVATION_WRITER_ROLES, _FORBIDDEN_DETAIL)


def require_sale_writer(actor: ActorContext) -> None:
    """Gate contract creation, submission and activation."""
    _require_any(actor, SALE_WRITER_ROLES, _FORBIDDEN_DETAIL)


def require_gate_evidence_recorder(actor: ActorContext) -> None:
    """Gate attesting that deposit or first-payment evidence exists."""
    _require_any(actor, GATE_EVIDENCE_ROLES, _FORBIDDEN_DETAIL)


def require_financial_approver(actor: ActorContext) -> None:
    """Gate exception approval, gate waivers and cancellation financial terms."""
    _require_any(
        actor,
        FINANCIAL_APPROVER_ROLES,
        "Only an Approver / CFO may sanction this.",
    )


def require_legal_writer(actor: ActorContext) -> None:
    """Gate recording what the registry did."""
    _require_any(actor, LEGAL_WRITER_ROLES, "Only Legal may record a legal event.")


def require_cancellation_writer(actor: ActorContext) -> None:
    """Gate opening and advancing a cancellation."""
    _require_any(actor, CANCELLATION_WRITER_ROLES, _FORBIDDEN_DETAIL)


def require_handover_writer(actor: ActorContext) -> None:
    """Gate running a handover."""
    _require_any(actor, HANDOVER_WRITER_ROLES, _FORBIDDEN_DETAIL)


def require_sales_policy_writer(actor: ActorContext) -> None:
    """Gate the project's sales policy."""
    _require_any(actor, SALES_POLICY_ROLES, _FORBIDDEN_DETAIL)


def require_clearance_owner(actor: ActorContext, *, clearance_type: str) -> None:
    """Gate one clearance to the department that owns the concern behind it."""
    owners = CLEARANCE_OWNER_ROLES.get(clearance_type)
    if owners is None or not actor.role_keys.intersection(owners):
        raise PermissionDeniedError(
            f"Only the team that owns the {clearance_type} clearance may change it."
        )


def require_different_checker(actor: ActorContext, *, maker_user_id: uuid.UUID | None) -> None:
    """Refuse an approval by the person who asked for it.

    Applied to the submitter rather than the original author: the person who put
    the exception forward is the one asserting it is justified, and theirs is
    the signature the approval exists to be independent of.
    """
    if maker_user_id is not None and maker_user_id == actor.user_id:
        raise PermissionDeniedError(_MAKER_DETAIL)


def require_operational_project(project: Project) -> None:
    """Refuse sales while the project's basis can still be rewritten.

    Stated here rather than imported from pricing, for the same reason pricing
    states it rather than importing it from inventory: a contract is denominated
    in a currency and validated against a country pack, and PR-MVP-02 lets a
    project in ``setup`` change both underneath whatever was agreed.
    """
    if project.status == "setup":
        raise ConflictError(_SETUP_DETAIL)


# --------------------------------------------------------------------------- #
# Personal data
# --------------------------------------------------------------------------- #


def may_read_client_pii(actor: ActorContext, *, client: Client) -> bool:
    """Whether this caller may be shown this buyer's contact and identity data.

    Two ways in: a role whose work needs it, or being the advisor this buyer was
    assigned to. Everyone else — including the Project Manager, Finance, the
    Executive Viewer and the System Administrator — gets the commercial summary
    with the personal fields absent, not blanked.
    """
    if actor.role_keys.intersection(CLIENT_PII_ROLES):
        return True
    return (
        client.owner_advisor_user_id is not None and client.owner_advisor_user_id == actor.user_id
    )


def visible_party_fields(actor: ActorContext, *, client: Client) -> frozenset[str]:
    """The buyer-party columns this caller may be shown.

    Returned as a set the serialiser consults, so restriction happens before a
    response object exists. A field that is not in this set is never read out of
    the row, which is a different thing from being read and then hidden.
    """
    if may_read_client_pii(actor, client=client):
        return PARTY_PII_FIELDS
    return frozenset()


# --------------------------------------------------------------------------- #
# Row and phase scoping
# --------------------------------------------------------------------------- #


def visible_unit_ids(
    session: Session, *, project_id: uuid.UUID, actor: ActorContext
) -> Select[tuple[uuid.UUID]] | None:
    """A subquery of unit ids this caller may see, or ``None`` for no narrowing.

    Every sales list narrows on this in SQL. A register that fetched a project's
    reservations and dropped the hidden ones afterwards would put contract
    prices for phases the caller was never granted into memory, the query plan,
    and one refactor from the response body.
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


def require_sellable_unit(
    session: Session, *, project: Project, unit_id: uuid.UUID, actor: ActorContext
) -> Unit:
    """Load a unit of this project the caller may see, or raise 404.

    A unit in a phase the caller was not granted answers exactly as a unit that
    does not exist. A 403 would confirm the identifier is real, which is the
    whole thing phase scoping exists to prevent.
    """
    statement = select(Unit).where(Unit.id == unit_id, Unit.project_id == project.id)
    allowed = visible_unit_ids(session, project_id=project.id, actor=actor)
    if allowed is not None:
        statement = statement.where(Unit.id.in_(allowed))
    unit = session.scalars(statement).first()
    if unit is None:
        raise NotFoundError(_UNIT_NOT_FOUND)
    return unit


def restricts_clients_to_own(actor: ActorContext) -> bool:
    """Whether this caller sees only the buyers assigned to them.

    True for a Sales Advisor who is nothing else. An advisor who is also Sales
    Operations is doing the desk's job and sees the desk's book.
    """
    if actor.role_keys.intersection(
        {"system_admin", "project_manager", "sales_operations", "legal", "collections"}
    ):
        return False
    if actor.role_keys.intersection({"finance", "approver_cfo", "executive_viewer", "auditor"}):
        return False
    return "sales_advisor" in actor.role_keys


def visible_clients(
    statement: Select[tuple[Client]], *, actor: ActorContext
) -> Select[tuple[Client]]:
    """Narrow a client query to the buyers this caller may see.

    Applied in SQL, on the way in. An advisor asking for another advisor's buyer
    by identifier gets the same empty result as one asking for a buyer that was
    never created, and the route turns that into a 404.
    """
    if not restricts_clients_to_own(actor):
        return statement
    return statement.where(Client.owner_advisor_user_id == actor.user_id)


def require_visible_client(
    session: Session, *, project: Project, client_id: uuid.UUID, actor: ActorContext
) -> Client:
    """Load a buyer of this project the caller may see, or raise 404."""
    statement = select(Client).where(Client.id == client_id, Client.project_id == project.id)
    client = session.scalars(visible_clients(statement, actor=actor)).first()
    if client is None:
        raise NotFoundError(_CLIENT_NOT_FOUND)
    return client


def accessible_project_for_sales(
    project_id: Annotated[uuid.UUID, Path()],
    session: DbSession,
    actor: ActiveActor,
) -> Project:
    """Resolve ``{project_id}`` to a project the caller may open."""
    return require_project_access(session, project_id=project_id, actor=actor)


SalesProject = Annotated[Project, Depends(accessible_project_for_sales)]
