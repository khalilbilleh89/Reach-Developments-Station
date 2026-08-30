"""Sales and legal routes: clients, reservations, contracts, registry, handover.

Handlers validate, authorise and orchestrate. Every rule about what may happen
lives in the service; every rule about who may reach it lives in
``permissions.py``. A route that decided either for itself would be the one that
later disagrees with the rest.

Status is never a PATCH. Activating a reservation, submitting a contract,
recording a registration and completing a handover are four different acts with
four different rights and four different sets of preconditions, so each has its
own route. A status column a client could set would be an approval a client
could grant itself.

There are no DELETE routes. A reservation expires, a contract is cancelled, a
legal event is reversed by another event, a clearance is revoked and kept. The
record of the wrong thing having been believed is itself a fact somebody will
need.

Personal data is chosen here, per caller, before serialisation: the two party
read models differ by which columns exist on them, not by which are blanked.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.modules.access.dependencies import ActiveActor, ActorContext, DbSession
from app.modules.projects.models import Project
from app.modules.sales import service
from app.modules.sales.models import Client, HandoverRecord, Reservation, SaleContract
from app.modules.sales.permissions import (
    SalesProject,
    may_read_client_pii,
    require_sales_reader,
)
from app.modules.sales.schemas import (
    AdjustmentCreateRequest,
    AdjustmentRead,
    AdjustmentUpdateRequest,
    CancellationAdvanceRequest,
    CancellationCompleteRequest,
    CancellationCreateRequest,
    CancellationRead,
    ClearanceRead,
    ClientCreateRequest,
    ClientRead,
    ClientSummaryRead,
    ClientUpdateRequest,
    EvidenceRequest,
    ExceptionDecisionRequest,
    HandoverCompleteRequest,
    HandoverCreateRequest,
    HandoverDetailRead,
    HandoverRead,
    HandoverUpdateRequest,
    LegalEventCreateRequest,
    LegalEventRead,
    LegalEventReverseRequest,
    LegalTimelineRead,
    PartyCreateRequest,
    PartyRead,
    PartySummaryRead,
    PartyUpdateRequest,
    ReasonRequest,
    ReservationActivateRequest,
    ReservationCloseRequest,
    ReservationCreateRequest,
    ReservationDetailRead,
    ReservationExtendRequest,
    ReservationRead,
    ReservationRecalculateRequest,
    ReservationStatusEventRead,
    ReservationUpdateRequest,
    SaleActivateRequest,
    SaleCreateRequest,
    SaleDetailRead,
    SalePartyDetailRead,
    SalePartyRead,
    SaleRead,
    SalesPolicyRead,
    SalesPolicyWriteRequest,
    SalesRegisterRead,
    SalesRegisterRow,
    SalesRegisterTotals,
    SaleSubmitRequest,
    SaleTaxLineRead,
    SaleUpdateRequest,
    ShareReconciliationRead,
)

router = APIRouter(prefix="/projects", tags=["sales"])

_MAX_PAGE = 500


# --------------------------------------------------------------------------- #
# Project policy
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/sales/policy",
    response_model=SalesPolicyRead,
    summary="The gates this project puts in front of title transfer and handover",
)
def read_policy(session: DbSession, actor: ActiveActor, project: SalesProject) -> SalesPolicyRead:
    require_sales_reader(actor)
    return SalesPolicyRead.model_validate(service.policy_for(session, project=project))


@router.put(
    "/{project_id}/sales/policy",
    response_model=SalesPolicyRead,
    summary="Set this project's sales gates",
)
def write_policy(
    payload: SalesPolicyWriteRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> SalesPolicyRead:
    policy = service.write_policy(session, project=project, actor=actor, **payload.model_dump())
    return SalesPolicyRead.model_validate(policy)


# --------------------------------------------------------------------------- #
# Clients
# --------------------------------------------------------------------------- #


def _client_read(actor: ActorContext, client: Client) -> ClientRead | ClientSummaryRead:
    """Choose the response shape this caller is entitled to.

    Two models, not one model with blanked fields. A caller who may not see a
    buyer's contact details gets a response on which those fields do not exist,
    so there is no path by which they reach the wire.
    """
    if may_read_client_pii(actor, client=client):
        return ClientRead.model_validate(client)
    return ClientSummaryRead.model_validate(client)


@router.get(
    "/{project_id}/sales/clients",
    response_model=list[ClientRead | ClientSummaryRead],
    summary="Buyers on this project",
)
def list_clients(
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
    search: Annotated[str | None, Query(max_length=200)] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> list[ClientRead | ClientSummaryRead]:
    clients = service.list_clients(
        session, project=project, actor=actor, search=search, is_active=is_active
    )
    return [_client_read(actor, client) for client in clients]


@router.post(
    "/{project_id}/sales/clients",
    response_model=ClientRead | ClientSummaryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a buyer",
)
def create_client(
    payload: ClientCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ClientRead | ClientSummaryRead:
    client = service.create_client(
        session, project=project, actor=actor, **payload.model_dump(exclude_unset=True)
    )
    return _client_read(actor, client)


@router.get(
    "/{project_id}/sales/clients/{client_id}",
    response_model=ClientRead | ClientSummaryRead,
    summary="One buyer",
)
def read_client(
    client_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ClientRead | ClientSummaryRead:
    client = service.get_client(session, project=project, client_id=client_id, actor=actor)
    return _client_read(actor, client)


@router.patch(
    "/{project_id}/sales/clients/{client_id}",
    response_model=ClientRead | ClientSummaryRead,
    summary="Correct a buyer's record",
)
def update_client(
    client_id: uuid.UUID,
    payload: ClientUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ClientRead | ClientSummaryRead:
    client = service.update_client(
        session,
        project=project,
        client_id=client_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    return _client_read(actor, client)


@router.get(
    "/{project_id}/sales/clients/{client_id}/parties",
    response_model=list[PartyRead | PartySummaryRead],
    summary="The named buyers on one client record",
)
def list_parties(
    client_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> list[PartyRead | PartySummaryRead]:
    client = service.get_client(session, project=project, client_id=client_id, actor=actor)
    parties = service.list_parties(session, client=client)
    if may_read_client_pii(actor, client=client):
        return [PartyRead.model_validate(party) for party in parties]
    return [PartySummaryRead.model_validate(party) for party in parties]


@router.get(
    "/{project_id}/sales/clients/{client_id}/share-reconciliation",
    response_model=ShareReconciliationRead,
    summary="Whether this client's buyers add up to a whole unit",
)
def read_share_reconciliation(
    client_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ShareReconciliationRead:
    require_sales_reader(actor)
    client = service.get_client(session, project=project, client_id=client_id, actor=actor)
    total = service.active_share_total(session, client=client)
    return ShareReconciliationRead(total_share_fraction=total, reconciled=total == service.ONE)


@router.post(
    "/{project_id}/sales/clients/{client_id}/parties",
    response_model=PartyRead | PartySummaryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a named buyer",
)
def create_party(
    client_id: uuid.UUID,
    payload: PartyCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> PartyRead | PartySummaryRead:
    client = service.get_client(session, project=project, client_id=client_id, actor=actor)
    party = service.create_party(
        session,
        project=project,
        client=client,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    if may_read_client_pii(actor, client=client):
        return PartyRead.model_validate(party)
    return PartySummaryRead.model_validate(party)


@router.patch(
    "/{project_id}/sales/client-parties/{party_id}",
    response_model=PartyRead | PartySummaryRead,
    summary="Correct a named buyer",
)
def update_party(
    party_id: uuid.UUID,
    payload: PartyUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> PartyRead | PartySummaryRead:
    party = service.update_party(
        session,
        project=project,
        party_id=party_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    client = service.get_client(session, project=project, client_id=party.client_id, actor=actor)
    if may_read_client_pii(actor, client=client):
        return PartyRead.model_validate(party)
    return PartySummaryRead.model_validate(party)


# --------------------------------------------------------------------------- #
# Reservations
# --------------------------------------------------------------------------- #


def _reservation_detail(session: DbSession, reservation: Reservation) -> ReservationDetailRead:
    """A reservation with its inputs, its history and the frozen calculation."""
    return ReservationDetailRead(
        reservation=ReservationRead.model_validate(reservation),
        adjustments=[
            AdjustmentRead.model_validate(item)
            for item in service.list_adjustments(session, reservation=reservation)
        ],
        events=[
            ReservationStatusEventRead.model_validate(item)
            for item in service.list_reservation_events(session, reservation=reservation)
        ],
        quote_snapshot=reservation.quote_snapshot_json or {},
        closure_required=service.requires_closure(
            reservation, today=service.inventory_fields.business_today()
        ),
    )


@router.get(
    "/{project_id}/sales/reservations",
    response_model=list[ReservationRead],
    summary="Reservations on this project",
)
def list_reservations(
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
    reservation_status: Annotated[str | None, Query(max_length=16, alias="status")] = None,
    unit_id: Annotated[uuid.UUID | None, Query()] = None,
    client_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[ReservationRead]:
    reservations = service.list_reservations(
        session,
        project=project,
        actor=actor,
        status=reservation_status,
        unit_id=unit_id,
        client_id=client_id,
    )
    return [ReservationRead.model_validate(item) for item in reservations]


@router.post(
    "/{project_id}/sales/reservations",
    response_model=ReservationDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Open a reservation and freeze the unit's live quote",
)
def create_reservation(
    payload: ReservationCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ReservationDetailRead:
    reservation = service.create_reservation(
        session, project=project, actor=actor, **payload.model_dump(exclude_unset=True)
    )
    return _reservation_detail(session, reservation)


@router.get(
    "/{project_id}/sales/reservations/{reservation_id}",
    response_model=ReservationDetailRead,
    summary="One reservation, its inputs, its history and its frozen quote",
)
def read_reservation(
    reservation_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ReservationDetailRead:
    reservation = service.get_reservation(
        session, project=project, reservation_id=reservation_id, actor=actor
    )
    return _reservation_detail(session, reservation)


@router.patch(
    "/{project_id}/sales/reservations/{reservation_id}",
    response_model=ReservationDetailRead,
    summary="Correct a reservation in preparation",
)
def update_reservation(
    reservation_id: uuid.UUID,
    payload: ReservationUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ReservationDetailRead:
    reservation = service.update_reservation(
        session,
        project=project,
        reservation_id=reservation_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    return _reservation_detail(session, reservation)


@router.post(
    "/{project_id}/sales/reservations/{reservation_id}/recalculate",
    response_model=ReservationDetailRead,
    summary="Re-run the quote, withdrawing any standing approval",
)
def recalculate_reservation(
    reservation_id: uuid.UUID,
    payload: ReservationRecalculateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ReservationDetailRead:
    reservation = service.recalculate_reservation(
        session,
        project=project,
        reservation_id=reservation_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    return _reservation_detail(session, reservation)


@router.get(
    "/{project_id}/sales/reservations/{reservation_id}/adjustments",
    response_model=list[AdjustmentRead],
    summary="The commercial inputs behind a reservation's quote",
)
def list_adjustments(
    reservation_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> list[AdjustmentRead]:
    reservation = service.get_reservation(
        session, project=project, reservation_id=reservation_id, actor=actor
    )
    return [
        AdjustmentRead.model_validate(item)
        for item in service.list_adjustments(session, reservation=reservation)
    ]


@router.post(
    "/{project_id}/sales/reservations/{reservation_id}/adjustments",
    response_model=ReservationDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a commercial input and re-freeze the quote",
)
def create_adjustment(
    reservation_id: uuid.UUID,
    payload: AdjustmentCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ReservationDetailRead:
    service.create_adjustment(
        session,
        project=project,
        reservation_id=reservation_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    reservation = service.get_reservation(
        session, project=project, reservation_id=reservation_id, actor=actor
    )
    return _reservation_detail(session, reservation)


@router.patch(
    "/{project_id}/sales/reservation-adjustments/{adjustment_id}",
    response_model=AdjustmentRead,
    summary="Revise a commercial input",
)
def update_adjustment(
    adjustment_id: uuid.UUID,
    payload: AdjustmentUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> AdjustmentRead:
    adjustment = service.update_adjustment(
        session,
        project=project,
        adjustment_id=adjustment_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    return AdjustmentRead.model_validate(adjustment)


@router.post(
    "/{project_id}/sales/reservations/{reservation_id}/submit-exception",
    response_model=ReservationDetailRead,
    summary="Put a quote that breaches the thresholds forward for sanction",
)
def submit_exception(
    reservation_id: uuid.UUID,
    payload: ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ReservationDetailRead:
    reservation = service.submit_exception(
        session,
        project=project,
        reservation_id=reservation_id,
        actor=actor,
        reason=payload.reason,
    )
    return _reservation_detail(session, reservation)


@router.post(
    "/{project_id}/sales/reservations/{reservation_id}/approve-exception",
    response_model=ReservationDetailRead,
    summary="Sanction or refuse a submitted exception",
)
def decide_exception(
    reservation_id: uuid.UUID,
    payload: ExceptionDecisionRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ReservationDetailRead:
    reservation = service.decide_exception(
        session,
        project=project,
        reservation_id=reservation_id,
        actor=actor,
        approved=payload.approved,
        reason=payload.reason,
    )
    return _reservation_detail(session, reservation)


@router.post(
    "/{project_id}/sales/reservations/{reservation_id}/confirm-deposit",
    response_model=ReservationDetailRead,
    summary="Record that deposit evidence exists. Not a receipt",
)
def confirm_deposit(
    reservation_id: uuid.UUID,
    payload: EvidenceRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ReservationDetailRead:
    reservation = service.confirm_deposit(
        session,
        project=project,
        reservation_id=reservation_id,
        actor=actor,
        evidence_reference=payload.evidence_reference,
    )
    return _reservation_detail(session, reservation)


@router.post(
    "/{project_id}/sales/reservations/{reservation_id}/waive-deposit",
    response_model=ReservationDetailRead,
    summary="Let a reservation proceed without its deposit",
)
def waive_deposit(
    reservation_id: uuid.UUID,
    payload: ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ReservationDetailRead:
    reservation = service.waive_deposit(
        session,
        project=project,
        reservation_id=reservation_id,
        actor=actor,
        reason=payload.reason,
    )
    return _reservation_detail(session, reservation)


@router.post(
    "/{project_id}/sales/reservations/{reservation_id}/activate",
    response_model=ReservationDetailRead,
    summary="Commit the unit to this buyer",
)
def activate_reservation(
    reservation_id: uuid.UUID,
    payload: ReservationActivateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ReservationDetailRead:
    reservation = service.activate_reservation(
        session,
        project=project,
        reservation_id=reservation_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    return _reservation_detail(session, reservation)


@router.post(
    "/{project_id}/sales/reservations/{reservation_id}/extend",
    response_model=ReservationDetailRead,
    summary="Push a live reservation's expiry out",
)
def extend_reservation(
    reservation_id: uuid.UUID,
    payload: ReservationExtendRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ReservationDetailRead:
    reservation = service.extend_reservation(
        session,
        project=project,
        reservation_id=reservation_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    return _reservation_detail(session, reservation)


@router.post(
    "/{project_id}/sales/reservations/{reservation_id}/expire",
    response_model=ReservationDetailRead,
    summary="Close a reservation that has run past its expiry",
)
def expire_reservation(
    reservation_id: uuid.UUID,
    payload: ReservationActivateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ReservationDetailRead:
    reservation = service.expire_reservation(
        session,
        project=project,
        reservation_id=reservation_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    return _reservation_detail(session, reservation)


@router.post(
    "/{project_id}/sales/reservations/{reservation_id}/cancel",
    response_model=ReservationDetailRead,
    summary="End a live reservation on a recorded reason",
)
def cancel_reservation(
    reservation_id: uuid.UUID,
    payload: ReservationCloseRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ReservationDetailRead:
    reservation = service.cancel_reservation(
        session,
        project=project,
        reservation_id=reservation_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    return _reservation_detail(session, reservation)


# --------------------------------------------------------------------------- #
# Sale contracts
# --------------------------------------------------------------------------- #


def _legal_timeline(session: DbSession, sale: SaleContract) -> LegalTimelineRead:
    events = service.list_legal_events(session, sale=sale)
    effective = service.effective_legal_events(session, sale_id=sale.id)
    return LegalTimelineRead(
        events=[LegalEventRead.model_validate(event) for event in events],
        effective_event_ids=[event.id for event in effective],
        legal_status=service.derived_legal_status(effective),
    )


def _handover_payload(
    session: DbSession, project: Project, sale: SaleContract, handover: HandoverRecord
) -> HandoverDetailRead:
    """A handover, every clearance recorded on it, and what still blocks it."""
    return HandoverDetailRead(
        handover=HandoverRead.model_validate(handover),
        clearances=[
            ClearanceRead.model_validate(item)
            for item in service.list_clearances(session, handover=handover)
        ],
        blockers=service.handover_blockers(session, project=project, sale=sale, handover=handover),
    )


def _handover_detail(
    session: DbSession, project: Project, sale: SaleContract
) -> HandoverDetailRead | None:
    handover = service.get_handover(session, project=project, sale=sale)
    if handover is None:
        return None
    return _handover_payload(session, project, sale, handover)


def _sale_detail(
    session: DbSession, actor: ActorContext, project: Project, sale: SaleContract
) -> SaleDetailRead:
    """A contract with everything hanging off it, personal data decided per caller."""
    client = service.get_client(session, project=project, client_id=sale.client_id, actor=actor)
    parties = service.list_sale_parties(session, sale=sale)
    cancellation = service.get_cancellation(session, project=project, sale=sale)
    return SaleDetailRead(
        sale=SaleRead.model_validate(sale),
        parties=(
            [SalePartyDetailRead.model_validate(party) for party in parties]
            if may_read_client_pii(actor, client=client)
            else [SalePartyRead.model_validate(party) for party in parties]
        ),
        tax_lines=[
            SaleTaxLineRead.model_validate(line)
            for line in service.list_sale_tax_lines(session, sale=sale)
        ],
        legal=_legal_timeline(session, sale),
        cancellation=(
            CancellationRead.model_validate(cancellation) if cancellation is not None else None
        ),
        handover=_handover_detail(session, project, sale),
        quote_snapshot=sale.reservation_quote_snapshot_json or {},
    )


@router.get(
    "/{project_id}/sales/contracts",
    response_model=list[SaleRead],
    summary="Sale contracts on this project",
)
def list_sales(
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
    sale_status: Annotated[str | None, Query(max_length=24, alias="status")] = None,
    unit_id: Annotated[uuid.UUID | None, Query()] = None,
    client_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[SaleRead]:
    sales = service.list_sales(
        session,
        project=project,
        actor=actor,
        status=sale_status,
        unit_id=unit_id,
        client_id=client_id,
    )
    return [SaleRead.model_validate(item) for item in sales]


@router.post(
    "/{project_id}/sales/contracts",
    response_model=SaleDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Draw up a contract on a live reservation",
)
def create_sale(
    payload: SaleCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> SaleDetailRead:
    sale = service.create_sale(
        session, project=project, actor=actor, **payload.model_dump(exclude_unset=True)
    )
    return _sale_detail(session, actor, project, sale)


@router.get(
    "/{project_id}/sales/contracts/{sale_id}",
    response_model=SaleDetailRead,
    summary="One contract, its frozen terms, parties, taxes and timelines",
)
def read_sale(
    sale_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> SaleDetailRead:
    sale = service.get_sale(session, project=project, sale_id=sale_id, actor=actor)
    return _sale_detail(session, actor, project, sale)


@router.patch(
    "/{project_id}/sales/contracts/{sale_id}",
    response_model=SaleDetailRead,
    summary="Correct a draft contract's references and attribution",
)
def update_sale(
    sale_id: uuid.UUID,
    payload: SaleUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> SaleDetailRead:
    sale = service.update_sale(
        session,
        project=project,
        sale_id=sale_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    return _sale_detail(session, actor, project, sale)


@router.post(
    "/{project_id}/sales/contracts/{sale_id}/submit",
    response_model=SaleDetailRead,
    summary="Hand the unit's commitment from the reservation to the contract",
)
def submit_sale(
    sale_id: uuid.UUID,
    payload: SaleSubmitRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> SaleDetailRead:
    sale = service.submit_sale(
        session,
        project=project,
        sale_id=sale_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    return _sale_detail(session, actor, project, sale)


@router.post(
    "/{project_id}/sales/contracts/{sale_id}/confirm-first-payment",
    response_model=SaleDetailRead,
    summary="Record that first-payment evidence exists. Not a receipt",
)
def confirm_first_payment(
    sale_id: uuid.UUID,
    payload: EvidenceRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> SaleDetailRead:
    sale = service.confirm_first_payment(
        session,
        project=project,
        sale_id=sale_id,
        actor=actor,
        evidence_reference=payload.evidence_reference,
    )
    return _sale_detail(session, actor, project, sale)


@router.post(
    "/{project_id}/sales/contracts/{sale_id}/waive-first-payment",
    response_model=SaleDetailRead,
    summary="Let a contract activate without its first payment",
)
def waive_first_payment(
    sale_id: uuid.UUID,
    payload: ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> SaleDetailRead:
    sale = service.waive_first_payment(
        session, project=project, sale_id=sale_id, actor=actor, reason=payload.reason
    )
    return _sale_detail(session, actor, project, sale)


@router.post(
    "/{project_id}/sales/contracts/{sale_id}/activate",
    response_model=SaleDetailRead,
    summary="Make the contract live and the unit contracted",
)
def activate_sale(
    sale_id: uuid.UUID,
    payload: SaleActivateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> SaleDetailRead:
    sale = service.activate_sale(
        session,
        project=project,
        sale_id=sale_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    return _sale_detail(session, actor, project, sale)


# --------------------------------------------------------------------------- #
# Legal timeline
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/sales/contracts/{sale_id}/legal-events",
    response_model=LegalTimelineRead,
    summary="A contract's legal timeline",
)
def list_legal_events(
    sale_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> LegalTimelineRead:
    sale = service.get_sale(session, project=project, sale_id=sale_id, actor=actor)
    return _legal_timeline(session, sale)


@router.post(
    "/{project_id}/sales/contracts/{sale_id}/legal-events",
    response_model=LegalTimelineRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record what the registry, the notary or the parties did",
)
def record_legal_event(
    sale_id: uuid.UUID,
    payload: LegalEventCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> LegalTimelineRead:
    service.record_legal_event(
        session,
        project=project,
        sale_id=sale_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    sale = service.get_sale(session, project=project, sale_id=sale_id, actor=actor)
    return _legal_timeline(session, sale)


@router.post(
    "/{project_id}/sales/legal-events/{event_id}/reverse",
    response_model=LegalTimelineRead,
    summary="Withdraw a legal event by recording another that says so",
)
def reverse_legal_event(
    event_id: uuid.UUID,
    payload: LegalEventReverseRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> LegalTimelineRead:
    correction = service.reverse_legal_event(
        session,
        project=project,
        event_id=event_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    sale = service.get_sale(
        session, project=project, sale_id=correction.sale_contract_id, actor=actor
    )
    return _legal_timeline(session, sale)


# --------------------------------------------------------------------------- #
# Cancellation
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/sales/contracts/{sale_id}/cancellation",
    response_model=CancellationRead | None,
    summary="The cancellation case on a contract, if there is one",
)
def read_cancellation(
    sale_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> CancellationRead | None:
    sale = service.get_sale(session, project=project, sale_id=sale_id, actor=actor)
    cancellation = service.get_cancellation(session, project=project, sale=sale)
    return CancellationRead.model_validate(cancellation) if cancellation is not None else None


@router.post(
    "/{project_id}/sales/contracts/{sale_id}/cancellation",
    response_model=CancellationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Open the controlled process that ends a contract",
)
def start_cancellation(
    sale_id: uuid.UUID,
    payload: CancellationCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> CancellationRead:
    cancellation = service.start_cancellation(
        session,
        project=project,
        sale_id=sale_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    return CancellationRead.model_validate(cancellation)


@router.post(
    "/{project_id}/sales/cancellations/{cancellation_id}/approve-financial-terms",
    response_model=CancellationRead,
    summary="Sanction the forfeiture and refund a cancellation proposes",
)
def approve_cancellation_terms(
    cancellation_id: uuid.UUID,
    payload: ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> CancellationRead:
    cancellation = service.approve_cancellation_terms(
        session,
        project=project,
        cancellation_id=cancellation_id,
        actor=actor,
        reason=payload.reason,
    )
    return CancellationRead.model_validate(cancellation)


@router.post(
    "/{project_id}/sales/cancellations/{cancellation_id}/advance",
    response_model=CancellationRead,
    summary="Move a cancellation case one named step along",
)
def advance_cancellation(
    cancellation_id: uuid.UUID,
    payload: CancellationAdvanceRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> CancellationRead:
    cancellation = service.advance_cancellation(
        session,
        project=project,
        cancellation_id=cancellation_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    return CancellationRead.model_validate(cancellation)


@router.post(
    "/{project_id}/sales/cancellations/{cancellation_id}/complete",
    response_model=CancellationRead,
    summary="End the contract and take the unit back as returned",
)
def complete_cancellation(
    cancellation_id: uuid.UUID,
    payload: CancellationCompleteRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> CancellationRead:
    cancellation = service.complete_cancellation(
        session,
        project=project,
        cancellation_id=cancellation_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    return CancellationRead.model_validate(cancellation)


# --------------------------------------------------------------------------- #
# Handover
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/sales/contracts/{sale_id}/handover",
    response_model=HandoverDetailRead | None,
    summary="The handover record on a contract, its clearances and what blocks it",
)
def read_handover(
    sale_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> HandoverDetailRead | None:
    sale = service.get_sale(session, project=project, sale_id=sale_id, actor=actor)
    return _handover_detail(session, project, sale)


@router.post(
    "/{project_id}/sales/contracts/{sale_id}/handover",
    response_model=HandoverDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Open the operational record for handing the unit over",
)
def create_handover(
    sale_id: uuid.UUID,
    payload: HandoverCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> HandoverDetailRead:
    handover = service.create_handover(
        session,
        project=project,
        sale_id=sale_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    sale = service.get_sale(session, project=project, sale_id=sale_id, actor=actor)
    return _handover_payload(session, project, sale, handover)


@router.patch(
    "/{project_id}/sales/handovers/{handover_id}",
    response_model=HandoverDetailRead,
    summary="Record inspection, snagging and scheduling",
)
def update_handover(
    handover_id: uuid.UUID,
    payload: HandoverUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> HandoverDetailRead:
    handover = service.update_handover(
        session,
        project=project,
        handover_id=handover_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    sale = service.get_sale(
        session, project=project, sale_id=handover.sale_contract_id, actor=actor
    )
    return _handover_payload(session, project, sale, handover)


@router.post(
    "/{project_id}/sales/handovers/{handover_id}/clearances/{clearance_type}",
    response_model=ClearanceRead,
    summary="Sign off one department's concern about handing this unit over",
)
def grant_clearance(
    handover_id: uuid.UUID,
    clearance_type: str,
    payload: EvidenceRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ClearanceRead:
    clearance = service.grant_clearance(
        session,
        project=project,
        handover_id=handover_id,
        clearance_type=clearance_type,
        actor=actor,
        evidence_reference=payload.evidence_reference,
    )
    return ClearanceRead.model_validate(clearance)


@router.post(
    "/{project_id}/sales/handovers/{handover_id}/clearances/{clearance_type}/revoke",
    response_model=ClearanceRead,
    summary="Withdraw a clearance, keeping the record of it having been given",
)
def revoke_clearance(
    handover_id: uuid.UUID,
    clearance_type: str,
    payload: ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> ClearanceRead:
    clearance = service.revoke_clearance(
        session,
        project=project,
        handover_id=handover_id,
        clearance_type=clearance_type,
        actor=actor,
        reason=payload.reason,
    )
    return ClearanceRead.model_validate(clearance)


@router.post(
    "/{project_id}/sales/handovers/{handover_id}/complete",
    response_model=HandoverDetailRead,
    summary="Hand the unit over, once every configured gate has been passed",
)
def complete_handover(
    handover_id: uuid.UUID,
    payload: HandoverCompleteRequest,
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
) -> HandoverDetailRead:
    handover = service.complete_handover(
        session,
        project=project,
        handover_id=handover_id,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    sale = service.get_sale(
        session, project=project, sale_id=handover.sale_contract_id, actor=actor
    )
    return _handover_payload(session, project, sale, handover)


# --------------------------------------------------------------------------- #
# The sales register
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/sales/register",
    response_model=SalesRegisterRead,
    summary="Where every unit stands commercially, legally and on delivery",
)
def read_register(
    session: DbSession,
    actor: ActiveActor,
    project: SalesProject,
    phase_id: Annotated[uuid.UUID | None, Query()] = None,
    building_id: Annotated[uuid.UUID | None, Query()] = None,
    commercial_status: Annotated[str | None, Query(max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=_MAX_PAGE)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SalesRegisterRead:
    rows, totals, total = service.sales_register(
        session,
        project=project,
        actor=actor,
        phase_id=phase_id,
        building_id=building_id,
        commercial_status=commercial_status,
        limit=limit,
        offset=offset,
    )
    return SalesRegisterRead(
        rows=[SalesRegisterRow(**row) for row in rows],
        totals=SalesRegisterTotals(**totals),
        total=total,
    )
