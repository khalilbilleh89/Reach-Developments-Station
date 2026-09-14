"""Explicit owner-approved erasure of a removed unit and its closed history.

This narrowly scoped maintenance operation is the exception documented in
DELETION_POLICY.md. The ownership map is explicit; foreign-key inspection is
only a safety check and never expands what may be deleted.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, NamedTuple

from sqlalchemy import MetaData, Table, delete, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.collections import models as cm
from app.modules.commissions import models as commissions
from app.modules.construction.models import UnitStageEvent
from app.modules.inventory import models as im
from app.modules.inventory.schemas import UnitPurgePreview, UnitPurgeRequest
from app.modules.payment_plans import models as pm
from app.modules.pricing import models as prices
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.sales import models as sm
from app.modules.unit_economics.models import UnitCost


class Scope(NamedTuple):
    table: Table
    owner_column: str
    parent: str
    label: str


# Parents precede children. Delete in reverse order. Shared project versions,
# clients, settings, users, and audit/report snapshots are deliberately absent.
SCOPES = (
    Scope(im.Unit.__table__, "id", "units", "Unit"),
    Scope(im.UnitAreaSchedule.__table__, "unit_id", "units", "Area schedules"),
    Scope(
        im.UnitAreaValue.__table__,
        "unit_area_schedule_id",
        "unit_area_schedules",
        "Area measurements",
    ),
    Scope(im.UnitCustomFieldValue.__table__, "unit_id", "units", "Custom field values"),
    Scope(im.UnitFeature.__table__, "unit_id", "units", "Features"),
    Scope(im.UnitDocument.__table__, "unit_id", "units", "Document links"),
    Scope(im.UnitStatusEvent.__table__, "unit_id", "units", "Unit status history"),
    Scope(im.InventorySubAsset.__table__, "linked_unit_id", "units", "Attached parking/storage"),
    Scope(im.CommonArea.__table__, "apartment_id", "units", "Assigned common areas"),
    Scope(prices.UnitPriceVersion.__table__, "unit_id", "units", "Price versions"),
    Scope(
        prices.UnitPriceComponent.__table__,
        "unit_price_version_id",
        "unit_price_versions",
        "Price components",
    ),
    Scope(sm.Reservation.__table__, "unit_id", "units", "Reservations"),
    Scope(
        sm.ReservationAdjustment.__table__,
        "reservation_id",
        "reservations",
        "Reservation adjustments",
    ),
    Scope(
        sm.ReservationStatusEvent.__table__, "reservation_id", "reservations", "Reservation history"
    ),
    Scope(sm.SaleContract.__table__, "unit_id", "units", "Sale contracts"),
    Scope(sm.SaleContractParty.__table__, "sale_contract_id", "sale_contracts", "Contract parties"),
    Scope(
        sm.SaleContractTaxLine.__table__, "sale_contract_id", "sale_contracts", "Contract tax lines"
    ),
    Scope(sm.SaleLegalEvent.__table__, "sale_contract_id", "sale_contracts", "Legal history"),
    Scope(
        sm.SaleCancellation.__table__, "sale_contract_id", "sale_contracts", "Cancellation history"
    ),
    Scope(sm.HandoverRecord.__table__, "sale_contract_id", "sale_contracts", "Handovers"),
    Scope(sm.HandoverClearance.__table__, "handover_id", "handover_records", "Handover clearances"),
    Scope(pm.PaymentPlan.__table__, "sale_contract_id", "sale_contracts", "Payment plans"),
    Scope(
        pm.PaymentPlanVersion.__table__, "payment_plan_id", "payment_plans", "Payment plan versions"
    ),
    Scope(
        pm.PaymentPlanInstallment.__table__,
        "payment_plan_version_id",
        "payment_plan_versions",
        "Installments",
    ),
    Scope(
        pm.InstallmentTriggerEvent.__table__,
        "installment_id",
        "payment_plan_installments",
        "Installment events",
    ),
    Scope(cm.CollectionReceipt.__table__, "sale_contract_id", "sale_contracts", "Receipt history"),
    Scope(
        cm.CollectionAction.__table__, "sale_contract_id", "sale_contracts", "Collection actions"
    ),
    Scope(cm.CollectionDispute.__table__, "sale_contract_id", "sale_contracts", "Disputes"),
    Scope(cm.CollectionWaiver.__table__, "sale_contract_id", "sale_contracts", "Waivers"),
    Scope(cm.CollectionRestructure.__table__, "sale_contract_id", "sale_contracts", "Restructures"),
    Scope(
        cm.CollectionReceiptAllocation.__table__,
        "sale_contract_id",
        "sale_contracts",
        "Receipt allocations",
    ),
    Scope(cm.CollectionRefund.__table__, "sale_contract_id", "sale_contracts", "Refund history"),
    Scope(commissions.CommissionGrant.__table__, "unit_id", "units", "Commission grants"),
    Scope(
        commissions.CommissionAllocation.__table__,
        "commission_id",
        "commission_grants",
        "Commission allocations",
    ),
    Scope(UnitCost.__table__, "unit_id", "units", "Unit cost entries"),
    Scope(UnitStageEvent.__table__, "unit_id", "units", "Construction progress history"),
)
MAX_RECORDS = 10000


def _plan(
    session: Session, *, project: Project, actor: ActorContext, unit_id: uuid.UUID
) -> tuple[UnitPurgePreview, dict[str, list[dict[str, Any]]]]:
    if not actor.is_master_admin:
        raise PermissionDeniedError("Only Master Administrator may purge a unit's history.")
    lock_project(session, project.id)
    rows: dict[str, list[dict[str, Any]]] = {}
    identifiers: dict[str, set[uuid.UUID]] = {"units": {unit_id}}
    total = 0
    for scope in SCOPES:
        table = scope.table
        statement = select(table).where(table.c[scope.owner_column].in_(identifiers[scope.parent]))
        if "project_id" in table.c:
            statement = statement.where(table.c.project_id == project.id)
        # Parent locks also prevent unseen FK children from being inserted while
        # the plan is checked and deleted. Every row is reread from PostgreSQL.
        selected = session.execute(
            statement.order_by(table.c.id).limit(MAX_RECORDS + 1).with_for_update()
        ).mappings()
        rows[table.name] = [dict(row) for row in selected]
        total += len(rows[table.name])
        if total > MAX_RECORDS:
            raise ConflictError(
                "This history is too large for an interactive purge. No data changed."
            )
        identifiers[table.name] = {row["id"] for row in rows[table.name]}
        if table.name == "units" and not rows[table.name]:
            raise NotFoundError("Unit not found.")

    unit = rows["units"][0]
    blockers = []
    if unit["removed_at"] is None:
        blockers.append("Remove this unit from current Inventory before purging its history.")
    transactions = []
    for table, number, allowed, label in (
        (
            "reservations",
            "reservation_number",
            {"cancelled", "expired", "converted"},
            "Reservation",
        ),
        ("sale_contracts", "sale_number", {"cancelled"}, "Sale"),
    ):
        for row in rows[table]:
            transactions.append({"kind": label, "reference": row[number], "status": row["status"]})
            if row["status"] not in allowed:
                blockers.append(
                    f"{label} {row[number]} is {row['status']}; close it before purging."
                )
    for table, label in (("collection_receipts", "receipt"), ("collection_refunds", "refund")):
        if any(row["status"] == "confirmed" for row in rows[table]):
            blockers.append(
                f"Confirmed {label} cash remains. Reverse it through Collections first."
            )

    # A row owned by this unit must not also belong to a different unit's
    # sale/price/schedule. Do not delete the other side of a shared relationship.
    for scope in SCOPES:
        for fk in scope.table.foreign_keys:
            parent = fk.column.table.name
            if (
                parent in identifiers
                and fk.column.name == "id"
                and any(
                    row[fk.parent.name] is not None
                    and row[fk.parent.name] not in identifiers[parent]
                    for row in rows[scope.table.name]
                )
            ):
                blockers.append(
                    f"{scope.label} reference other unit history; review the shared link."
                )

    # Check actual DB constraints, including tables unknown to this application
    # version. An unreviewed CASCADE/SET NULL must never erase or alter other data.
    known = {scope.table.name: scope.table for scope in SCOPES}
    connection = session.connection()
    for (_, child_name), constraints in inspect(connection).get_multi_foreign_keys().items():
        for constraint in constraints:
            parent = constraint["referred_table"]
            if parent not in identifiers or not identifiers[parent]:
                continue
            for child_column, parent_column in zip(
                constraint["constrained_columns"], constraint["referred_columns"], strict=True
            ):
                if parent_column != "id":
                    continue
                table = known.get(child_name)
                if table is None:
                    table = Table(child_name, MetaData(), autoload_with=connection)
                outside = table.c[child_column].in_(identifiers[parent])
                if child_name in identifiers:
                    outside &= table.c.id.not_in(identifiers[child_name])
                if (
                    session.scalar(select(table.c[child_column]).where(outside).limit(1))
                    is not None
                ):
                    label = next(
                        (scope.label for scope in SCOPES if scope.table.name == child_name),
                        "Shared project records",
                    )
                    blockers.append(
                        f"{label} outside this purge still depend on the selected history."
                    )

    fingerprint = hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()
    preview = UnitPurgePreview(
        unit_id=unit_id,
        unit_reference=unit["unit_reference"],
        fingerprint=fingerprint,
        counts=[
            {"label": scope.label, "count": len(rows[scope.table.name])}
            for scope in SCOPES
            if rows[scope.table.name]
        ],
        total_records=total,
        transactions=transactions,
        blockers=sorted(set(blockers)),
    )
    return preview, rows


def preview_purge(
    session: Session, *, project: Project, actor: ActorContext, unit_id: uuid.UUID
) -> UnitPurgePreview:
    preview, _ = _plan(session, project=project, actor=actor, unit_id=unit_id)
    session.rollback()  # read-only preview; release its consistent-snapshot locks
    return preview


def purge_unit(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    unit_id: uuid.UUID,
    request: UnitPurgeRequest,
) -> None:
    preview, rows = _plan(session, project=project, actor=actor, unit_id=unit_id)
    if request.confirm_reference != preview.unit_reference or not request.reason.strip():
        raise ValidationError("Type the exact unit reference and give a reason for purging.")
    if request.fingerprint != preview.fingerprint:
        raise ConflictError("The unit's history changed. Refresh the preview and confirm it again.")
    if preview.blockers:
        raise ConflictError(" ".join(preview.blockers))
    try:
        for scope in reversed(SCOPES):
            if rows[scope.table.name]:
                session.execute(
                    delete(scope.table).where(
                        scope.table.c.id.in_([row["id"] for row in rows[scope.table.name]])
                    )
                )
        record_event(
            session,
            action="unit.purged",
            entity_type="unit",
            entity_id=unit_id,
            actor_user_id=actor.user_id,
            correlation_id=actor.correlation_id,
            reason=request.reason.strip(),
            before={
                "project_id": str(project.id),
                "reference": preview.unit_reference,
                "counts": [item.model_dump() for item in preview.counts],
                "transactions": [item.model_dump() for item in preview.transactions],
                "fingerprint": preview.fingerprint,
            },
            after={"unit_deleted": True, "linked_history_deleted": True},
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError(
            "Linked records changed or are shared. Nothing was purged; refresh the preview."
        ) from exc
