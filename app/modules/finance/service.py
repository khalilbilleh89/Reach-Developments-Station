"""
finance.service

Service layer for project-level financial summary computation.

Business rules enforced here:
  - Project must exist before any aggregation is attempted.
  - All aggregation is read-only; no records are created or mutated.
  - total_receivable = max(0, total_contract_value - total_collected)
    Clamped to zero to remain non-negative when receipts exceed contract
    value (e.g. due to rounding or adjusted contracts).
  - collection_ratio = min(total_collected / total_contract_value, 1.0)
    Clamped to 1.0 so over-collection never produces a ratio > 1.
    Defaults to 0.0 when total_contract_value is zero.
  - units_available is derived from the unit status counts, not from
    total_units - units_sold, so that reserved units are excluded from
    both buckets consistently.
"""

from typing import List, cast

from fastapi import HTTPException
from sqlalchemy import case, distinct, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.collections.aging_engine import (
    ALL_BUCKETS,
    BUCKET_1_30,
    BUCKET_31_60,
    BUCKET_61_90,
    BUCKET_90_PLUS,
    BUCKET_CURRENT,
    AgingBucket,
    calculate_receivable_age,
    classify_receivable_bucket,
)
from app.modules.finance.constants import RECEIVABLE_STATUSES
from app.modules.finance.repository import FinanceSummaryRepository
from app.modules.finance.revenue_recognition import (
    ContractRevenueData,
    calculate_contract_revenue_recognition,
)
from app.modules.finance.schemas import (
    AgingBucketSummary,
    CollectionsAlertListResponse,
    CollectionsAlertResponse,
    ContractAgingResponse,
    MatchedInstallmentAllocation,
    MatchReceiptRequest,
    PortfolioAgingResponse,
    PortfolioRevenueOverviewResponse,
    ProjectAgingResponse,
    ProjectFinanceSummaryResponse,
    ProjectRevenueSummaryResponse,
    ReceiptMatchResult,
    RevenueRecognitionResponse,
)
from app.modules.projects.models import Project
from app.modules.sales.models import ContractPaymentSchedule, SalesContract
from app.modules.units.models import Unit
from app.modules.floors.models import Floor
from app.modules.buildings.models import Building
from app.modules.phases.models import Phase
from app.shared.enums.sales import ContractPaymentStatus

# Alias kept for module-internal use; canonical definition lives in constants.py.
_RECEIVABLE_STATUSES = RECEIVABLE_STATUSES


class FinanceSummaryService:
    """Computes aggregated financial metrics for a project."""

    def __init__(self, db: Session) -> None:
        self.repo = FinanceSummaryRepository(db)
        self.db = db

    def get_project_summary(self, project_id: str) -> ProjectFinanceSummaryResponse:
        """Return the aggregated financial summary for a project.

        Raises HTTP 404 if the project does not exist.
        All derived monetary values are clamped to prevent invalid schema
        states when accounting data contains over-collection or rounding.
        The summary currency is sourced from the project's base_currency so
        callers know the denomination of all returned monetary totals.
        """
        project = self._require_project(project_id)

        unit_counts = self.repo.get_unit_counts_by_project(project_id)
        contract_agg = self.repo.get_contract_aggregates_by_project(project_id)
        total_collected = round(self.repo.sum_collected_by_project(project_id), 2)

        total_contract_value = round(contract_agg.total_value, 2)
        total_receivable = round(max(0.0, total_contract_value - total_collected), 2)

        if total_contract_value > 0:
            collection_ratio = round(
                min(total_collected / total_contract_value, 1.0), 6
            )
        else:
            collection_ratio = 0.0

        average_unit_price = round(contract_agg.average_price, 2)

        return ProjectFinanceSummaryResponse(
            project_id=project_id,
            total_units=unit_counts.total,
            units_sold=unit_counts.sold,
            units_available=unit_counts.available,
            total_contract_value=total_contract_value,
            total_collected=total_collected,
            total_receivable=total_receivable,
            collection_ratio=collection_ratio,
            average_unit_price=average_unit_price,
            currency=project.base_currency,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_project(self, project_id: str) -> Project:
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id!r} not found.",
            )
        return project


# ---------------------------------------------------------------------------
# Revenue Recognition Service
# ---------------------------------------------------------------------------


class RevenueRecognitionService:
    """Computes recognized and deferred revenue from payment schedule data.

    Recognition model: cash-based.
      recognized_revenue = SUM(amount) for installments with status='paid'
      deferred_revenue   = contract_total − recognized_revenue

    All computations are read-only; no records are created or mutated.
    Recognition values are never stored persistently — they are computed
    on every request from current payment schedule state.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_contract_revenue(self, contract_id: str) -> RevenueRecognitionResponse:
        """Return revenue recognition data for a single contract.

        Raises HTTP 404 if the contract does not exist.
        """
        contract = (
            self.db.query(SalesContract).filter(SalesContract.id == contract_id).first()
        )
        if not contract:
            raise HTTPException(
                status_code=404,
                detail=f"Contract {contract_id!r} not found.",
            )
        paid_amount = self._sum_paid_installments(contract_id)
        data = ContractRevenueData(
            contract_id=contract_id,
            contract_total=float(contract.contract_price),
            paid_amount=paid_amount,
        )
        return calculate_contract_revenue_recognition(data)

    def get_project_revenue(self, project_id: str) -> ProjectRevenueSummaryResponse:
        """Return aggregated revenue recognition for all contracts in a project.

        Raises HTTP 404 if the project does not exist.
        Uses a single grouped query to sum paid installments for all contracts
        in the project, avoiding N+1 round-trips.
        """
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id!r} not found.",
            )

        contracts = self._get_project_contracts(project_id)
        if not contracts:
            return ProjectRevenueSummaryResponse(
                project_id=project_id,
                total_contract_value=0.0,
                total_recognized_revenue=0.0,
                total_deferred_revenue=0.0,
                overall_recognition_percentage=0.0,
                contract_count=0,
                contracts=[],
                currency=project.base_currency,
            )

        contract_ids = [c.id for c in contracts]
        paid_map = self._sum_paid_installments_bulk(contract_ids)

        contract_details: List[RevenueRecognitionResponse] = []
        for contract in contracts:
            paid_amount = paid_map.get(contract.id, 0.0)
            data = ContractRevenueData(
                contract_id=contract.id,
                contract_total=float(contract.contract_price),
                paid_amount=paid_amount,
            )
            contract_details.append(calculate_contract_revenue_recognition(data))

        total_contract_value = round(sum(r.contract_total for r in contract_details), 2)
        total_recognized = round(sum(r.recognized_revenue for r in contract_details), 2)
        total_deferred = round(sum(r.deferred_revenue for r in contract_details), 2)

        if total_contract_value > 0:
            overall_pct = round(
                min(total_recognized / total_contract_value * 100, 100.0), 4
            )
        else:
            overall_pct = 0.0

        return ProjectRevenueSummaryResponse(
            project_id=project_id,
            total_contract_value=total_contract_value,
            total_recognized_revenue=total_recognized,
            total_deferred_revenue=total_deferred,
            overall_recognition_percentage=overall_pct,
            contract_count=len(contract_details),
            contracts=contract_details,
            currency=project.base_currency,
        )

    def get_total_recognized_revenue(self) -> PortfolioRevenueOverviewResponse:
        """Return portfolio-wide revenue recognition overview.

        Aggregates across all contracts in all projects.
        Uses a single grouped query to sum paid installments for all contracts,
        avoiding N+1 round-trips.
        """
        # Fetch all contracts with their project_id in a single JOIN query.
        rows = (
            self.db.query(SalesContract, Phase.project_id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .all()
        )

        if not rows:
            return PortfolioRevenueOverviewResponse(
                total_contract_value=0.0,
                total_recognized_revenue=0.0,
                total_deferred_revenue=0.0,
                overall_recognition_percentage=0.0,
                project_count=0,
                contract_count=0,
                currencies=[],
            )

        contract_ids = [contract.id for contract, _ in rows]
        paid_map = self._sum_paid_installments_bulk(contract_ids)

        total_contract_value = 0.0
        total_recognized = 0.0
        total_deferred = 0.0
        project_ids: set[str] = set()
        contract_currencies: set[str] = set()

        for contract, project_id in rows:
            paid_amount = paid_map.get(contract.id, 0.0)
            data = ContractRevenueData(
                contract_id=contract.id,
                contract_total=float(contract.contract_price),
                paid_amount=paid_amount,
            )
            result = calculate_contract_revenue_recognition(data)
            total_contract_value += result.contract_total
            total_recognized += result.recognized_revenue
            total_deferred += result.deferred_revenue
            project_ids.add(project_id)
            if hasattr(contract, "currency") and contract.currency:
                contract_currencies.add(contract.currency)

        total_contract_value = round(total_contract_value, 2)
        total_recognized = round(total_recognized, 2)
        total_deferred = round(total_deferred, 2)

        if total_contract_value > 0:
            overall_pct = round(
                min(total_recognized / total_contract_value * 100, 100.0), 4
            )
        else:
            overall_pct = 0.0

        return PortfolioRevenueOverviewResponse(
            total_contract_value=total_contract_value,
            total_recognized_revenue=total_recognized,
            total_deferred_revenue=total_deferred,
            overall_recognition_percentage=overall_pct,
            project_count=len(project_ids),
            contract_count=len(rows),
            currencies=sorted(contract_currencies),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sum_paid_installments_bulk(self, contract_ids: List[str]) -> dict:
        """Return a dict mapping contract_id → paid amount for all given IDs.

        Executes a single grouped query instead of one query per contract.
        Contracts with no paid installments are absent from the returned dict
        (callers should use `.get(id, 0.0)`).
        """
        if not contract_ids:
            return {}
        rows = (
            self.db.query(
                ContractPaymentSchedule.contract_id,
                func.sum(ContractPaymentSchedule.amount),
            )
            .filter(
                ContractPaymentSchedule.contract_id.in_(contract_ids),
                ContractPaymentSchedule.status == ContractPaymentStatus.PAID.value,
            )
            .group_by(ContractPaymentSchedule.contract_id)
            .all()
        )
        return {cid: float(total) for cid, total in rows}

    def _sum_paid_installments(self, contract_id: str) -> float:
        """Return SUM(amount) for all paid installments of a single contract.

        Used only by get_contract_revenue() which looks up a single contract.
        For bulk lookups across many contracts, use _sum_paid_installments_bulk.
        """
        result = (
            self.db.query(func.coalesce(func.sum(ContractPaymentSchedule.amount), 0))
            .filter(
                ContractPaymentSchedule.contract_id == contract_id,
                ContractPaymentSchedule.status == ContractPaymentStatus.PAID.value,
            )
            .scalar()
        )
        return float(result)

    def _get_project_contracts(self, project_id: str) -> list:
        """Return all SalesContracts belonging to a project."""
        return (
            self.db.query(SalesContract)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .all()
        )


# ---------------------------------------------------------------------------
# Collections Aging Service
# ---------------------------------------------------------------------------


def _build_bucket_summaries(
    bucket_amounts: dict[AgingBucket, float],
    bucket_counts: dict[AgingBucket, int],
) -> List[AgingBucketSummary]:
    """Return a list of AgingBucketSummary in canonical bucket order."""
    return [
        AgingBucketSummary(
            bucket=b,
            amount=round(bucket_amounts.get(b, 0.0), 2),
            installment_count=bucket_counts.get(b, 0),
        )
        for b in ALL_BUCKETS
    ]


class CollectionsAgingService:
    """Computes receivable aging buckets from payment schedule data.

    Aging model:
      Outstanding installments are those with status in PENDING or OVERDUE.
      PAID and CANCELLED installments are excluded from aging calculations.
      Each installment is classified into one of five buckets based on how
      many days past its due_date it falls on the reference date (today).

      Buckets:
        current  — due_date >= reference_date (not yet overdue)
        1-30     — 1 to 30 days overdue
        31-60    — 31 to 60 days overdue
        61-90    — 61 to 90 days overdue
        90+      — more than 90 days overdue

    All computations are read-only; no records are created or mutated.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_contract_aging(self, contract_id: str) -> ContractAgingResponse:
        """Return receivable aging breakdown for a single contract.

        Raises HTTP 404 if the contract does not exist.
        """
        contract = (
            self.db.query(SalesContract).filter(SalesContract.id == contract_id).first()
        )
        if not contract:
            raise HTTPException(
                status_code=404,
                detail=f"Contract {contract_id!r} not found.",
            )

        from datetime import date

        today = date.today()
        installments = (
            self.db.query(ContractPaymentSchedule)
            .filter(
                ContractPaymentSchedule.contract_id == contract_id,
                ContractPaymentSchedule.status.in_(_RECEIVABLE_STATUSES),
            )
            .all()
        )

        paid_amount = self._sum_paid_for_contract(contract_id)
        contract_total = float(contract.contract_price)

        bucket_amounts: dict[AgingBucket, float] = {b: 0.0 for b in ALL_BUCKETS}
        bucket_counts: dict[AgingBucket, int] = {b: 0 for b in ALL_BUCKETS}

        for inst in installments:
            days_overdue = calculate_receivable_age(inst.due_date, today)
            bucket = classify_receivable_bucket(days_overdue)
            amount = float(inst.amount)
            bucket_amounts[bucket] = bucket_amounts[bucket] + amount
            bucket_counts[bucket] = bucket_counts[bucket] + 1

        outstanding = round(sum(bucket_amounts.values()), 2)

        return ContractAgingResponse(
            contract_id=contract_id,
            contract_total=round(contract_total, 2),
            paid_amount=round(paid_amount, 2),
            outstanding_amount=outstanding,
            aging_buckets=_build_bucket_summaries(bucket_amounts, bucket_counts),
            currency=contract.currency,
        )

    def get_project_aging(self, project_id: str) -> ProjectAgingResponse:
        """Return aggregated receivable aging for all outstanding installments
        in a project.

        Raises HTTP 404 if the project does not exist.
        Uses a single SQL join to avoid N+1 queries.
        """
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id!r} not found.",
            )

        from datetime import date

        today = date.today()
        rows = self._get_outstanding_installments_for_project(project_id)

        bucket_amounts: dict[AgingBucket, float] = {b: 0.0 for b in ALL_BUCKETS}
        bucket_counts: dict[AgingBucket, int] = {b: 0 for b in ALL_BUCKETS}

        for inst in rows:
            days_overdue = calculate_receivable_age(inst.due_date, today)
            bucket = classify_receivable_bucket(days_overdue)
            amount = float(inst.amount)
            bucket_amounts[bucket] = bucket_amounts[bucket] + amount
            bucket_counts[bucket] = bucket_counts[bucket] + 1

        total_outstanding = round(sum(bucket_amounts.values()), 2)
        total_count = sum(bucket_counts.values())

        return ProjectAgingResponse(
            project_id=project_id,
            total_outstanding=total_outstanding,
            installment_count=total_count,
            aging_buckets=_build_bucket_summaries(bucket_amounts, bucket_counts),
            currency=project.base_currency,
        )

    def get_portfolio_aging(self) -> PortfolioAgingResponse:
        """Return portfolio-wide receivable aging distribution.

        Aggregates outstanding installments using SQL-level CASE + GROUP BY,
        so the database returns at most 5 aggregated rows instead of loading
        the full schedule dataset into Python.

        A separate scalar query counts the number of distinct projects that
        carry outstanding receivables.

        Only PENDING and OVERDUE installments are counted; PAID and CANCELLED
        are excluded.
        """
        from datetime import date, timedelta

        today = date.today()
        d30 = today - timedelta(days=30)
        d60 = today - timedelta(days=60)
        d90 = today - timedelta(days=90)

        # Build a portable CASE expression using Python-computed date cutoffs.
        # Bucket constants are used directly to keep SQL output aligned with the
        # canonical labels defined in aging_engine.py.
        # Date comparisons work identically in SQLite (tests) and PostgreSQL (prod).
        bucket_expr = case(
            (ContractPaymentSchedule.due_date >= today, BUCKET_CURRENT),
            (ContractPaymentSchedule.due_date >= d30, BUCKET_1_30),
            (ContractPaymentSchedule.due_date >= d60, BUCKET_31_60),
            (ContractPaymentSchedule.due_date >= d90, BUCKET_61_90),
            else_=BUCKET_90_PLUS,
        )

        base_query = self._outstanding_installments_base_query()

        # Aggregate by bucket in SQL — returns at most 5 rows.
        bucket_rows = (
            base_query.with_entities(
                bucket_expr.label("bucket"),
                func.sum(ContractPaymentSchedule.amount).label("amount"),
                func.count(ContractPaymentSchedule.id).label("cnt"),
            )
            .group_by(bucket_expr)
            .all()
        )

        # Count distinct projects with outstanding receivables.
        project_count: int = (
            base_query.with_entities(func.count(distinct(Phase.project_id))).scalar()
            or 0
        )

        bucket_amounts: dict[AgingBucket, float] = {b: 0.0 for b in ALL_BUCKETS}
        bucket_counts: dict[AgingBucket, int] = {b: 0 for b in ALL_BUCKETS}

        for bucket_label, amount, cnt in bucket_rows:
            # Defensive guard: bucket_label is produced by the CASE expression
            # using canonical BUCKET_* constants, so it will always be a valid
            # AgingBucket. This check guards against unexpected DB states.
            if bucket_label not in ALL_BUCKETS:
                continue
            b = cast(AgingBucket, bucket_label)
            bucket_amounts[b] = round(float(amount), 2)
            bucket_counts[b] = int(cnt)

        total_outstanding = round(sum(bucket_amounts.values()), 2)
        total_count = sum(bucket_counts.values())

        # Collect distinct currencies present in outstanding installments.
        currencies: list[str] = sorted(set(
            row[0]
            for row in base_query.with_entities(
                ContractPaymentSchedule.currency
            ).distinct().all()
            if row[0]
        ))

        return PortfolioAgingResponse(
            total_outstanding=total_outstanding,
            installment_count=total_count,
            project_count=project_count,
            aging_buckets=_build_bucket_summaries(bucket_amounts, bucket_counts),
            currencies=currencies,
        )

    def get_project_receivables_map(self) -> dict[str, float]:
        """Return a mapping of project_id → total outstanding receivables.

        Executes a single GROUP BY query across all projects.  Only PENDING
        and OVERDUE installments are included; PAID and CANCELLED are excluded.

        Used by TreasuryMonitoringService to compute per-project exposure
        without issuing N+1 queries.
        """
        rows = (
            self._outstanding_installments_base_query()
            .with_entities(
                Phase.project_id,
                func.sum(ContractPaymentSchedule.amount),
            )
            .group_by(Phase.project_id)
            .all()
        )
        return {str(pid): float(total) for pid, total in rows}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _outstanding_installments_base_query(self):
        """Return a base query for all outstanding installments portfolio-wide.

        The query joins ContractPaymentSchedule forward through the
        contract → unit → floor → building → phase chain and filters to
        PENDING and OVERDUE statuses only.

        Callers use ``with_entities()`` to build specific aggregations on
        top of this base, ensuring the join chain is defined in one place.
        """
        return (
            self.db.query(ContractPaymentSchedule)
            .join(
                SalesContract, ContractPaymentSchedule.contract_id == SalesContract.id
            )
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(ContractPaymentSchedule.status.in_(_RECEIVABLE_STATUSES))
        )

    def _sum_paid_for_contract(self, contract_id: str) -> float:
        result = (
            self.db.query(func.coalesce(func.sum(ContractPaymentSchedule.amount), 0))
            .filter(
                ContractPaymentSchedule.contract_id == contract_id,
                ContractPaymentSchedule.status == ContractPaymentStatus.PAID.value,
            )
            .scalar()
        )
        return float(result)

    def _get_outstanding_installments_for_project(self, project_id: str) -> list:
        """Return all outstanding ContractPaymentSchedule rows for a project.

        Only PENDING and OVERDUE installments are returned; PAID and CANCELLED
        are excluded.
        """
        return (
            self.db.query(ContractPaymentSchedule)
            .join(
                SalesContract, ContractPaymentSchedule.contract_id == SalesContract.id
            )
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(
                Phase.project_id == project_id,
                ContractPaymentSchedule.status.in_(_RECEIVABLE_STATUSES),
            )
            .all()
        )


# ---------------------------------------------------------------------------
# Collections Alert Service
# ---------------------------------------------------------------------------


class CollectionsAlertService:
    """Manages the lifecycle of collections alerts for overdue installments.

    Alerts are generated by evaluating outstanding installments against the
    threshold rules defined in collections_alert_engine.py.

    Duplicate prevention: only one active (unresolved) alert per
    (contract_id, installment_id, alert_type) is allowed.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_overdue_alerts(
        self,
        severity: str | None = None,
    ) -> CollectionsAlertListResponse:
        """Return all active (unresolved) collections alerts.

        Parameters
        ----------
        severity:
            Optional filter — one of ``warning``, ``critical``, ``high_risk``.
        """
        from app.modules.collections.models import CollectionsAlert

        query = self.db.query(CollectionsAlert).filter(
            CollectionsAlert.resolved_at.is_(None)
        )
        if severity:
            query = query.filter(CollectionsAlert.severity == severity)

        alerts = query.order_by(CollectionsAlert.created_at.desc()).all()
        items = [self._to_response(a) for a in alerts]
        return CollectionsAlertListResponse(items=items, total=len(items))

    def generate_alerts(self) -> CollectionsAlertListResponse:
        """Scan all outstanding installments and create new alerts where needed.

        Existing active alerts for the same (contract_id, installment_id,
        alert_type) are not duplicated.

        Returns the full active alert list after generation.
        """
        from datetime import date

        from app.modules.collections.collections_alert_engine import (
            InstallmentSnapshot,
            generate_overdue_alerts,
        )
        from app.modules.collections.models import CollectionsAlert

        today = date.today()

        outstanding = (
            self.db.query(ContractPaymentSchedule)
            .filter(ContractPaymentSchedule.status.in_(_RECEIVABLE_STATUSES))
            .all()
        )

        snapshots = [
            InstallmentSnapshot(
                id=inst.id,
                contract_id=inst.contract_id,
                due_date=inst.due_date,
                outstanding_balance=float(inst.amount),
            )
            for inst in outstanding
        ]

        candidates = generate_overdue_alerts(snapshots, today)

        for candidate in candidates:
            # Check for existing active alert to avoid duplicates.
            existing = (
                self.db.query(CollectionsAlert)
                .filter(
                    CollectionsAlert.contract_id == candidate.contract_id,
                    CollectionsAlert.installment_id == candidate.installment_id,
                    CollectionsAlert.alert_type == candidate.alert_type.value,
                    CollectionsAlert.resolved_at.is_(None),
                )
                .first()
            )
            if existing:
                continue

            alert = CollectionsAlert(
                contract_id=candidate.contract_id,
                installment_id=candidate.installment_id,
                alert_type=candidate.alert_type.value,
                severity=candidate.severity.value,
                days_overdue=candidate.days_overdue,
                outstanding_balance=candidate.outstanding_balance,
            )
            self.db.add(alert)
            try:
                self.db.flush()
            except IntegrityError:
                # A concurrent insert raced past the check-then-insert guard and
                # triggered the DB-level partial unique index.  Roll back the
                # failed flush and skip this candidate.
                self.db.rollback()
                continue

        self.db.commit()
        return self.get_overdue_alerts()

    def resolve_alert(
        self, alert_id: str, notes: str | None = None
    ) -> CollectionsAlertResponse:
        """Mark an alert as resolved.

        Raises HTTP 404 if the alert does not exist.
        Raises HTTP 422 if the alert is already resolved.
        """
        from datetime import datetime, timezone

        from app.modules.collections.models import CollectionsAlert

        alert = (
            self.db.query(CollectionsAlert)
            .filter(CollectionsAlert.id == alert_id)
            .first()
        )
        if not alert:
            raise HTTPException(
                status_code=404, detail=f"Alert {alert_id!r} not found."
            )
        if alert.resolved_at is not None:
            raise HTTPException(
                status_code=422,
                detail=f"Alert {alert_id!r} is already resolved.",
            )
        alert.resolved_at = datetime.now(timezone.utc)
        if notes is not None:
            alert.notes = notes
        self.db.commit()
        self.db.refresh(alert)
        return self._to_response(alert)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_response(alert: object) -> CollectionsAlertResponse:
        """Convert a CollectionsAlert ORM object to a response schema."""
        return CollectionsAlertResponse(
            alert_id=alert.id,
            contract_id=alert.contract_id,
            installment_id=alert.installment_id,
            alert_type=alert.alert_type,
            severity=alert.severity,
            days_overdue=alert.days_overdue,
            outstanding_balance=float(alert.outstanding_balance),
            created_at=alert.created_at,
            resolved_at=alert.resolved_at,
            notes=alert.notes,
        )


# ---------------------------------------------------------------------------
# Receipt Matching Service
# ---------------------------------------------------------------------------


class ReceiptMatchingService:
    """Matches incoming payments to outstanding installment obligations.

    Wraps the pure-function engine in receipt_matching_service.py with
    database access to fetch installment data.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def match_payment(self, request: MatchReceiptRequest) -> ReceiptMatchResult:
        """Match a payment amount to outstanding installments for a contract.

        Steps:
        1. Validate the contract exists.
        2. Fetch all outstanding (PENDING / OVERDUE) installments.
        3. Run the matching engine.
        4. Return the match result.

        Raises HTTP 404 if the contract does not exist.
        """
        from app.modules.collections.receipt_matching_service import (
            InstallmentObligation,
            match_payment_to_installments,
        )

        contract = (
            self.db.query(SalesContract)
            .filter(SalesContract.id == request.contract_id)
            .first()
        )
        if not contract:
            raise HTTPException(
                status_code=404,
                detail=f"Contract {request.contract_id!r} not found.",
            )

        outstanding = (
            self.db.query(ContractPaymentSchedule)
            .filter(
                ContractPaymentSchedule.contract_id == request.contract_id,
                ContractPaymentSchedule.status.in_(_RECEIVABLE_STATUSES),
            )
            .order_by(ContractPaymentSchedule.installment_number)
            .all()
        )

        obligations = [
            InstallmentObligation(
                id=inst.id,
                installment_number=inst.installment_number,
                outstanding_amount=float(inst.amount),
            )
            for inst in outstanding
        ]

        engine_result = match_payment_to_installments(
            request.payment_amount, obligations
        )

        allocations = [
            MatchedInstallmentAllocation(
                installment_id=inst_id,
                allocated_amount=amount,
            )
            for inst_id, amount in engine_result.allocated_amounts.items()
        ]

        return ReceiptMatchResult(
            contract_id=request.contract_id,
            payment_amount=round(request.payment_amount, 2),
            strategy=engine_result.strategy.value,
            matched_installment_ids=engine_result.matched_installment_ids,
            allocations=allocations,
            unallocated_amount=engine_result.unallocated_amount,
        )
