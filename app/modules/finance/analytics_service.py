"""
finance.analytics_service

Builds and stores analytics fact records from operational financial engines.

Responsibilities:
  - Read recognized revenue records from RevenueRecognitionService.
  - Read paid installments and group by project / month for collections.
  - Read receivable aging buckets from CollectionsAgingService.
  - Materialize results into fact_revenue, fact_collections, and
    fact_receivables_snapshot tables.

All source data comes from the existing operational financial engines.
This service does NOT change operational tables.

The rebuild process:
  1. Truncates existing fact rows for each table (full rebuild).
  2. Re-inserts all fact rows from the current state of operational data.

This can be triggered via the POST /finance/analytics/rebuild endpoint,
an admin action, or a scheduled task.
"""

from __future__ import annotations

from datetime import date
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.buildings.models import Building
from app.modules.collections.aging_engine import (
    ALL_BUCKETS,
    BUCKET_1_30,
    BUCKET_31_60,
    BUCKET_61_90,
    BUCKET_90_PLUS,
    BUCKET_CURRENT,
    calculate_receivable_age,
    classify_receivable_bucket,
)
from app.modules.finance.constants import RECEIVABLE_STATUSES
from app.modules.finance.models import FactCollections, FactReceivablesSnapshot, FactRevenue
from app.modules.finance.revenue_recognition import (
    ContractRevenueData,
    calculate_contract_revenue_recognition,
)
from app.modules.finance.schemas import AnalyticsRebuildResponse
from app.modules.floors.models import Floor
from app.modules.phases.models import Phase
from app.modules.projects.models import Project
from app.modules.sales.models import ContractPaymentSchedule, SalesContract
from app.modules.units.models import Unit
from app.shared.enums.sales import ContractPaymentStatus


class AnalyticsService:
    """Rebuilds the analytics fact layer from operational financial data.

    Internally queries:
      - SalesContract + ContractPaymentSchedule — for revenue and collections.
      - Outstanding installments — for receivable aging snapshots.

    All writes go to the three analytics fact tables only.  Operational
    tables are never modified.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rebuild_financial_analytics(self) -> AnalyticsRebuildResponse:
        """Rebuild all three analytics fact tables.

        Executes the three build functions in order:
          1. build_revenue_fact()
          2. build_collections_fact()
          3. build_receivable_snapshot()

        Returns a summary of how many rows were inserted into each table.
        """
        revenue_count = self.build_revenue_fact()
        collections_count = self.build_collections_fact()
        snapshot_count = self.build_receivable_snapshot()

        return AnalyticsRebuildResponse(
            revenue_facts_created=revenue_count,
            collections_facts_created=collections_count,
            receivable_snapshots_created=snapshot_count,
        )

    def build_revenue_fact(self) -> int:
        """Rebuild fact_revenue from the revenue recognition engine.

        Steps:
          1. Delete all existing fact_revenue rows.
          2. Load all contracts with their project / unit associations.
          3. For each contract with paid installments, group paid amounts
             by calendar month of payment (paid_at).
          4. Insert one FactRevenue row per (project, unit, month).

        Returns the number of rows inserted.
        """
        # Clear existing facts.
        self.db.query(FactRevenue).delete()
        self.db.flush()

        # Load all contracts with project / unit chain.
        rows = (
            self.db.query(SalesContract, Phase.project_id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .all()
        )

        if not rows:
            self.db.commit()
            return 0

        # Build a mapping: contract_id → (project_id, unit_id, contract_price)
        contract_meta: dict[str, tuple[str, str, float]] = {
            contract.id: (str(project_id), str(contract.unit_id), float(contract.contract_price))
            for contract, project_id in rows
        }

        # Load all paid installments with their paid_at timestamp.
        paid_installments = (
            self.db.query(ContractPaymentSchedule)
            .filter(
                ContractPaymentSchedule.contract_id.in_(list(contract_meta.keys())),
                ContractPaymentSchedule.status == ContractPaymentStatus.PAID.value,
                ContractPaymentSchedule.paid_at.isnot(None),
            )
            .all()
        )

        # Group by (project_id, unit_id, month) → total paid amount.
        # month is derived from paid_at.
        group: dict[tuple[str, str, str], float] = {}
        contract_value_by_unit: dict[tuple[str, str], float] = {}

        for inst in paid_installments:
            meta = contract_meta.get(inst.contract_id)
            if meta is None:
                continue
            project_id, unit_id, contract_price = meta

            # Store contract value per (project_id, unit_id) for context.
            contract_value_by_unit.setdefault((project_id, unit_id), contract_price)

            paid_at_date = inst.paid_at.date() if hasattr(inst.paid_at, "date") else inst.paid_at
            month_key = f"{paid_at_date.year:04d}-{paid_at_date.month:02d}"

            key = (project_id, unit_id, month_key)
            group[key] = group.get(key, 0.0) + float(inst.amount)

        # Insert FactRevenue rows.
        inserted = 0
        for (project_id, unit_id, month), recognized in group.items():
            contract_value = contract_value_by_unit.get((project_id, unit_id), 0.0)
            fact = FactRevenue(
                project_id=project_id,
                unit_id=unit_id,
                month=month,
                recognized_revenue=round(recognized, 2),
                contract_value=round(contract_value, 2),
            )
            self.db.add(fact)
            inserted += 1

        self.db.commit()
        return inserted

    def build_collections_fact(self) -> int:
        """Rebuild fact_collections from paid installment payment data.

        Steps:
          1. Delete all existing fact_collections rows.
          2. Load all paid installments grouped by project and month.
          3. Insert one FactCollections row per (project, month, payment_method).

        payment_method defaults to 'bank_transfer' as the source schema
        does not carry a structured payment-method field.

        Returns the number of rows inserted.
        """
        # Clear existing facts.
        self.db.query(FactCollections).delete()
        self.db.flush()

        # Load all contracts with their project chain.
        rows = (
            self.db.query(SalesContract, Phase.project_id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .all()
        )

        if not rows:
            self.db.commit()
            return 0

        contract_to_project: dict[str, str] = {
            contract.id: str(project_id) for contract, project_id in rows
        }

        # Load all paid installments.
        paid_installments = (
            self.db.query(ContractPaymentSchedule)
            .filter(
                ContractPaymentSchedule.contract_id.in_(list(contract_to_project.keys())),
                ContractPaymentSchedule.status == ContractPaymentStatus.PAID.value,
                ContractPaymentSchedule.paid_at.isnot(None),
            )
            .all()
        )

        # Group by (project_id, month, payment_method) → (total amount, payment_date).
        group: dict[tuple[str, str, str], tuple[float, date]] = {}

        for inst in paid_installments:
            project_id = contract_to_project.get(inst.contract_id)
            if project_id is None:
                continue

            paid_at_date = inst.paid_at.date() if hasattr(inst.paid_at, "date") else inst.paid_at
            month_key = f"{paid_at_date.year:04d}-{paid_at_date.month:02d}"
            payment_method = "bank_transfer"

            key = (project_id, month_key, payment_method)
            existing_amount, _ = group.get(key, (0.0, paid_at_date))
            group[key] = (existing_amount + float(inst.amount), paid_at_date)

        # Insert FactCollections rows.
        inserted = 0
        for (project_id, month, payment_method), (amount, payment_date) in group.items():
            fact = FactCollections(
                project_id=project_id,
                payment_date=payment_date,
                month=month,
                amount=round(amount, 2),
                payment_method=payment_method,
            )
            self.db.add(fact)
            inserted += 1

        self.db.commit()
        return inserted

    def build_receivable_snapshot(self) -> int:
        """Rebuild fact_receivables_snapshot from the current aging state.

        Steps:
          1. Delete all existing fact_receivables_snapshot rows for today.
          2. Load all outstanding installments per project.
          3. Classify each installment into aging buckets.
          4. Insert one FactReceivablesSnapshot row per project.

        The snapshot_date is set to today.

        Returns the number of rows inserted.
        """
        today = date.today()

        # Clear existing facts for today's snapshot (allow historical snapshots
        # on different dates to coexist).
        self.db.query(FactReceivablesSnapshot).filter(
            FactReceivablesSnapshot.snapshot_date == today
        ).delete()
        self.db.flush()

        # Load all projects.
        projects = self.db.query(Project).all()
        if not projects:
            self.db.commit()
            return 0

        # Load all outstanding installments with their project chain.
        outstanding_rows = (
            self.db.query(ContractPaymentSchedule, Phase.project_id)
            .join(SalesContract, ContractPaymentSchedule.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(ContractPaymentSchedule.status.in_(RECEIVABLE_STATUSES))
            .all()
        )

        # Group by project_id.
        project_installments: dict[str, list] = {}
        for inst, project_id in outstanding_rows:
            pid = str(project_id)
            if pid not in project_installments:
                project_installments[pid] = []
            project_installments[pid].append(inst)

        inserted = 0
        for project in projects:
            installments = project_installments.get(project.id, [])

            # Classify installments into aging buckets.
            bucket_amounts: dict[str, float] = {b: 0.0 for b in ALL_BUCKETS}

            for inst in installments:
                days_overdue = calculate_receivable_age(inst.due_date, today)
                bucket = classify_receivable_bucket(days_overdue)
                bucket_amounts[bucket] = bucket_amounts[bucket] + float(inst.amount)

            # Map aging engine buckets to snapshot columns.
            # current + 1-30 → bucket_0_30 (current + short overdue)
            bucket_0_30 = round(
                bucket_amounts.get(BUCKET_CURRENT, 0.0) + bucket_amounts.get(BUCKET_1_30, 0.0),
                2,
            )
            bucket_31_60 = round(bucket_amounts.get(BUCKET_31_60, 0.0), 2)
            bucket_61_90 = round(bucket_amounts.get(BUCKET_61_90, 0.0), 2)
            bucket_90_plus = round(bucket_amounts.get(BUCKET_90_PLUS, 0.0), 2)
            total_receivables = round(
                bucket_0_30 + bucket_31_60 + bucket_61_90 + bucket_90_plus, 2
            )

            snapshot = FactReceivablesSnapshot(
                project_id=project.id,
                snapshot_date=today,
                total_receivables=total_receivables,
                bucket_0_30=bucket_0_30,
                bucket_31_60=bucket_31_60,
                bucket_61_90=bucket_61_90,
                bucket_90_plus=bucket_90_plus,
            )
            self.db.add(snapshot)
            inserted += 1

        self.db.commit()
        return inserted
