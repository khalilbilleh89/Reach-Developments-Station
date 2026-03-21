"""
finance.analytics_service

Builds and stores analytics fact records from operational financial engines.

Responsibilities:
  - Read paid installments grouped by project/unit/month for revenue facts.
  - Read paid installments grouped by project/month for collections facts.
  - Read outstanding installment aging from operational data for snapshot facts.
  - Materialize results into fact_revenue, fact_collections, and
    fact_receivables_snapshot tables.

All source data comes from the existing operational financial engines.
This service does NOT change operational tables.

The rebuild process:
  1. fact_revenue and fact_collections are fully rebuilt — all existing rows
     are deleted and re-inserted from the current state of operational data.
  2. fact_receivables_snapshot is rebuilt only for the current snapshot date
     (today) — rows for today are deleted and re-inserted; historical snapshot
     rows from prior dates remain unchanged.

Rebuild is atomic: all three builders execute inside a single transaction.
A failure in any builder triggers a full rollback so dashboards never see a
partially rebuilt fact layer.

This can be triggered via the POST /finance/analytics/rebuild endpoint,
an admin action, or a scheduled task.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
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

    Rebuild atomicity: rebuild_financial_analytics() executes all three
    builders inside a single transaction.  Builders do not commit; the
    caller is responsible for the transaction boundary.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rebuild_financial_analytics(self) -> AnalyticsRebuildResponse:
        """Rebuild all three analytics fact tables atomically.

        Executes the three builders inside a single transaction:
          1. build_revenue_fact()
          2. build_collections_fact()
          3. build_receivable_snapshot()

        Commits on success; rolls back on any failure so dashboards never
        see a partially rebuilt fact layer.

        Returns a summary of how many rows were inserted into each table.
        """
        try:
            revenue_count = self.build_revenue_fact()
            collections_count = self.build_collections_fact()
            snapshot_count = self.build_receivable_snapshot()
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise

        return AnalyticsRebuildResponse(
            revenue_facts_created=revenue_count,
            collections_facts_created=collections_count,
            receivable_snapshots_created=snapshot_count,
        )

    def build_revenue_fact(self) -> int:
        """Rebuild fact_revenue from paid installment data.

        Uses a single DB-side GROUP BY across the contract → project / unit
        join chain to aggregate recognized revenue per (project, unit, month)
        without loading individual installment objects into Python.

        Steps:
          1. Delete all existing fact_revenue rows.
          2. Aggregate paid installments by (project_id, unit_id, month) in SQL.
          3. Fetch the total contract value per (project_id, unit_id) for context.
          4. Insert one FactRevenue row per (project, unit, month).

        The month is derived from the paid_at timestamp of each installment.

        Returns the number of rows inserted.  Does not commit; the caller
        (rebuild_financial_analytics) owns the transaction boundary.
        """
        self.db.query(FactRevenue).delete()
        self.db.flush()

        year_expr = func.extract("year", ContractPaymentSchedule.paid_at)
        month_expr = func.extract("month", ContractPaymentSchedule.paid_at)

        agg_rows = (
            self.db.query(
                Phase.project_id,
                SalesContract.unit_id,
                year_expr.label("paid_year"),
                month_expr.label("paid_month"),
                func.sum(ContractPaymentSchedule.amount).label("recognized"),
            )
            .select_from(ContractPaymentSchedule)
            .join(SalesContract, ContractPaymentSchedule.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(
                ContractPaymentSchedule.status == ContractPaymentStatus.PAID.value,
                ContractPaymentSchedule.paid_at.isnot(None),
            )
            .group_by(Phase.project_id, SalesContract.unit_id, year_expr, month_expr)
            .all()
        )

        if not agg_rows:
            return 0

        # Fetch total contract value per (project_id, unit_id) for context.
        contract_value_rows = (
            self.db.query(
                Phase.project_id,
                SalesContract.unit_id,
                func.sum(SalesContract.contract_price).label("contract_value"),
            )
            .select_from(SalesContract)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .group_by(Phase.project_id, SalesContract.unit_id)
            .all()
        )
        contract_value_map: dict[tuple[str, str], float] = {
            (str(pid), str(uid)): float(cv)
            for pid, uid, cv in contract_value_rows
        }

        inserted = 0
        for project_id, unit_id, paid_year, paid_month, recognized in agg_rows:
            month_key = f"{int(paid_year):04d}-{int(paid_month):02d}"
            contract_value = contract_value_map.get((str(project_id), str(unit_id)), 0.0)
            fact = FactRevenue(
                project_id=str(project_id),
                unit_id=str(unit_id),
                month=month_key,
                recognized_revenue=round(float(recognized), 2),
                contract_value=round(contract_value, 2),
            )
            self.db.add(fact)
            inserted += 1

        self.db.flush()
        return inserted

    def build_collections_fact(self) -> int:
        """Rebuild fact_collections from paid installment data.

        Uses a single DB-side GROUP BY to aggregate collected payments per
        (project_id, month, payment_method) without loading individual
        installment objects into Python.

        payment_date is set to the first day of the month — a deterministic,
        month-aligned marker that is stable across repeated rebuilds.

        payment_method defaults to 'bank_transfer' as the source schema
        does not carry a structured payment-method field.

        Steps:
          1. Delete all existing fact_collections rows.
          2. Aggregate paid installments by (project_id, year, month) in SQL.
          3. Insert one FactCollections row per (project, month, payment_method).

        Returns the number of rows inserted.  Does not commit; the caller
        (rebuild_financial_analytics) owns the transaction boundary.
        """
        self.db.query(FactCollections).delete()
        self.db.flush()

        year_expr = func.extract("year", ContractPaymentSchedule.paid_at)
        month_expr = func.extract("month", ContractPaymentSchedule.paid_at)

        agg_rows = (
            self.db.query(
                Phase.project_id,
                year_expr.label("paid_year"),
                month_expr.label("paid_month"),
                func.sum(ContractPaymentSchedule.amount).label("total_amount"),
            )
            .select_from(ContractPaymentSchedule)
            .join(SalesContract, ContractPaymentSchedule.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(
                ContractPaymentSchedule.status == ContractPaymentStatus.PAID.value,
                ContractPaymentSchedule.paid_at.isnot(None),
            )
            .group_by(Phase.project_id, year_expr, month_expr)
            .all()
        )

        inserted = 0
        for project_id, paid_year, paid_month, total_amount in agg_rows:
            year_int = int(paid_year)
            month_int = int(paid_month)
            month_key = f"{year_int:04d}-{month_int:02d}"
            # Use the first day of the month as a deterministic, month-aligned
            # payment_date marker.  This value is stable across repeated rebuilds.
            payment_date = date(year_int, month_int, 1)
            fact = FactCollections(
                project_id=str(project_id),
                payment_date=payment_date,
                month=month_key,
                amount=round(float(total_amount), 2),
                payment_method="bank_transfer",
            )
            self.db.add(fact)
            inserted += 1

        self.db.flush()
        return inserted

    def build_receivable_snapshot(self) -> int:
        """Rebuild today's receivable aging snapshot per project.

        Rebuilds only rows for today's snapshot_date; historical snapshots
        from prior dates remain unchanged.

        Steps:
          1. Delete existing fact_receivables_snapshot rows for today.
          2. Load all outstanding installments per project.
          3. Classify each installment into aging buckets.
          4. Insert one FactReceivablesSnapshot row per project.

        The snapshot_date is set to today.

        Returns the number of rows inserted.  Does not commit; the caller
        (rebuild_financial_analytics) owns the transaction boundary.
        """
        today = date.today()

        # Clear only today's snapshot rows; historical rows remain.
        self.db.query(FactReceivablesSnapshot).filter(
            FactReceivablesSnapshot.snapshot_date == today
        ).delete()
        self.db.flush()

        projects = self.db.query(Project).all()
        if not projects:
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

        self.db.flush()
        return inserted
