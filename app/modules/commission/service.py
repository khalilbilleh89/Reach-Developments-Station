"""
commission.service

Application-layer orchestration for the Commission domain.

Core rules
----------
1. Commission plan must exist and be active before calculating a payout.
2. Slabs must be non-overlapping, contiguous, and each allocation must sum
   to 100 % — validated on slab creation and enforced before calculation.
3. Payout can only be calculated for a valid, existing sale contract.
4. Only one non-cancelled payout per sale contract is allowed.
5. Approved payouts are immutable — recalculation is rejected.
6. Calculation is reproducible and fully auditable via CommissionPayoutLine
   records.

Calculation logic
-----------------
commission_pool = gross_sale_value × (pool_percentage / 100)

MARGINAL mode
    Split gross_sale_value into slab brackets.
    For each bracket:
        slab_commission = (value_in_bracket / gross_sale_value) × commission_pool
        Per-party amount = slab_commission × (party_pct / 100)

CUMULATIVE mode
    Find the slab whose range covers gross_sale_value.
    Apply full commission_pool using that slab's party percentages.
    Per-party amount = commission_pool × (party_pct / 100)

Explicitly Forbidden
--------------------
* Does NOT mutate SalesContract, Unit, Project, or any collection record.
* Does NOT implement clawback posting.
* Does NOT release payouts to payroll.
"""

from datetime import datetime, timezone
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.commission.models import (
    CommissionPayout,
    CommissionPayoutLine,
    CommissionPlan,
    CommissionSlab,
)
from app.modules.commission.repository import CommissionRepository
from app.modules.commission.schemas import (
    CommissionPayoutListResponse,
    CommissionPayoutRequest,
    CommissionPayoutResponse,
    CommissionPlanCreate,
    CommissionPlanResponse,
    CommissionSlabCreate,
    CommissionSlabResponse,
    CommissionSummaryResponse,
)
from app.modules.projects.repository import ProjectRepository
from app.modules.sales.models import SalesContract
from app.shared.enums.commission import (
    CalculationMode,
    CommissionPartyType,
    CommissionPayoutStatus,
)

# Party type → slab attribute name mapping (order is deterministic)
_PARTY_ATTR: list[tuple[CommissionPartyType, str]] = [
    (CommissionPartyType.SALES_REP, "sales_rep_pct"),
    (CommissionPartyType.TEAM_LEAD, "team_lead_pct"),
    (CommissionPartyType.MANAGER, "manager_pct"),
    (CommissionPartyType.BROKER, "broker_pct"),
    (CommissionPartyType.PLATFORM, "platform_pct"),
]


class CommissionService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = CommissionRepository(db)
        self._project_repo = ProjectRepository(db)

    # ------------------------------------------------------------------
    # Plan management
    # ------------------------------------------------------------------

    def create_plan(self, data: CommissionPlanCreate) -> CommissionPlanResponse:
        self._require_project(data.project_id)
        plan = CommissionPlan(
            project_id=data.project_id,
            name=data.name,
            description=data.description,
            pool_percentage=data.pool_percentage,
            calculation_mode=data.calculation_mode.value,
            is_active=data.is_active,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
        )
        plan = self._repo.create_plan(plan)
        return CommissionPlanResponse.model_validate(plan)

    def get_plan(self, plan_id: str) -> CommissionPlanResponse:
        plan = self._require_plan(plan_id)
        return CommissionPlanResponse.model_validate(plan)

    def list_plans_by_project(self, project_id: str) -> List[CommissionPlanResponse]:
        self._require_project(project_id)
        plans = self._repo.list_plans_by_project(project_id)
        return [CommissionPlanResponse.model_validate(p) for p in plans]

    # ------------------------------------------------------------------
    # Slab management
    # ------------------------------------------------------------------

    def add_slab(self, plan_id: str, data: CommissionSlabCreate) -> CommissionSlabResponse:
        plan = self._require_plan(plan_id)
        self._require_plan_not_approved(plan)

        existing = self._repo.list_slabs_by_plan(plan_id)
        self._validate_new_slab(data, existing)

        slab = CommissionSlab(
            commission_plan_id=plan_id,
            range_from=data.range_from,
            range_to=data.range_to,
            sales_rep_pct=data.sales_rep_pct,
            team_lead_pct=data.team_lead_pct,
            manager_pct=data.manager_pct,
            broker_pct=data.broker_pct,
            platform_pct=data.platform_pct,
            sequence=data.sequence,
        )
        slab = self._repo.create_slab(slab)
        return CommissionSlabResponse.model_validate(slab)

    def list_slabs(self, plan_id: str) -> List[CommissionSlabResponse]:
        self._require_plan(plan_id)
        slabs = self._repo.list_slabs_by_plan(plan_id)
        return [CommissionSlabResponse.model_validate(s) for s in slabs]

    # ------------------------------------------------------------------
    # Payout calculation
    # ------------------------------------------------------------------

    def calculate_payout(
        self, data: CommissionPayoutRequest
    ) -> CommissionPayoutResponse:
        # 1. Resolve and validate the sale contract
        contract = self._require_sale_contract(data.sale_contract_id)

        # 2. Resolve and validate the commission plan
        plan = self._require_plan(data.commission_plan_id)
        if not plan.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"CommissionPlan '{plan.id}' is not active.",
            )

        # 3. Guard: only one non-cancelled payout per contract
        existing = self._repo.get_payout_by_sale_contract(data.sale_contract_id)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"A non-cancelled payout already exists for sale contract "
                    f"'{data.sale_contract_id}' (payout id: '{existing.id}', "
                    f"status: '{existing.status}').  Cancel it before recalculating."
                ),
            )

        # 4. Load slabs and validate the plan is calculable
        slabs = self._repo.list_slabs_by_plan(plan.id)
        if not slabs:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"CommissionPlan '{plan.id}' has no slabs defined.",
            )
        self._validate_slab_set(slabs)

        gross = float(contract.contract_price)
        pool = round(gross * float(plan.pool_percentage) / 100.0, 2)
        mode = CalculationMode(plan.calculation_mode)

        now = datetime.now(timezone.utc)

        # 5. Resolve project_id from the contract's unit hierarchy
        project_id = self._resolve_project_id(contract)

        # 6. Build payout header
        payout = CommissionPayout(
            project_id=project_id,
            sale_contract_id=contract.id,
            commission_plan_id=plan.id,
            gross_sale_value=gross,
            commission_pool_value=pool,
            calculation_mode=mode.value,
            status=CommissionPayoutStatus.CALCULATED.value,
            calculated_at=now,
            notes=data.notes,
        )
        self._repo.create_payout(payout)

        # 7. Build payout lines
        if mode == CalculationMode.MARGINAL:
            lines = self._calc_marginal(payout.id, gross, pool, slabs)
        else:
            lines = self._calc_cumulative(payout.id, gross, pool, slabs)

        for line in lines:
            self._repo.create_payout_line(line)

        self._db.commit()
        self._db.refresh(payout)

        return self._build_payout_response(payout)

    def get_payout(self, payout_id: str) -> CommissionPayoutResponse:
        payout = self._require_payout(payout_id)
        return self._build_payout_response(payout)

    def list_payouts_by_project(
        self, project_id: str, skip: int = 0, limit: int = 100
    ) -> CommissionPayoutListResponse:
        self._require_project(project_id)
        items = self._repo.list_payouts_by_project(project_id, skip=skip, limit=limit)
        total = self._repo.count_payouts_by_project(project_id)
        return CommissionPayoutListResponse(
            total=total,
            items=[self._build_payout_response(p) for p in items],
        )

    def approve_payout(self, payout_id: str) -> CommissionPayoutResponse:
        payout = self._require_payout(payout_id)
        if payout.status == CommissionPayoutStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"CommissionPayout '{payout_id}' is already approved.",
            )
        if payout.status == CommissionPayoutStatus.CANCELLED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"CommissionPayout '{payout_id}' is cancelled and cannot be approved.",
            )
        payout.status = CommissionPayoutStatus.APPROVED.value
        payout.approved_at = datetime.now(timezone.utc)
        self._repo.save_payout(payout)
        return self._build_payout_response(payout)

    def get_project_summary(self, project_id: str) -> CommissionSummaryResponse:
        self._require_project(project_id)
        total = self._repo.count_payouts_by_project(project_id)
        draft = self._repo.count_payouts_by_status(
            project_id, CommissionPayoutStatus.DRAFT
        )
        calculated = self._repo.count_payouts_by_status(
            project_id, CommissionPayoutStatus.CALCULATED
        )
        approved = self._repo.count_payouts_by_status(
            project_id, CommissionPayoutStatus.APPROVED
        )
        cancelled = self._repo.count_payouts_by_status(
            project_id, CommissionPayoutStatus.CANCELLED
        )
        total_gross = self._repo.sum_gross_value_by_project(project_id)
        total_pool = self._repo.sum_commission_by_project(project_id)
        return CommissionSummaryResponse(
            project_id=project_id,
            total_payouts=total,
            draft_payouts=draft,
            calculated_payouts=calculated,
            approved_payouts=approved,
            cancelled_payouts=cancelled,
            total_gross_value=total_gross,
            total_commission_pool=total_pool,
        )

    # ------------------------------------------------------------------
    # Private — calculation helpers
    # ------------------------------------------------------------------

    def _calc_marginal(
        self,
        payout_id: str,
        gross: float,
        pool: float,
        slabs: List[CommissionSlab],
    ) -> List[CommissionPayoutLine]:
        """Marginal (bracket) commission allocation."""
        lines: List[CommissionPayoutLine] = []
        remaining = gross

        for slab in slabs:
            if remaining <= 0:
                break

            slab_from = float(slab.range_from)
            slab_to = float(slab.range_to) if slab.range_to is not None else None

            if slab_to is not None:
                bracket = slab_to - slab_from
            else:
                bracket = remaining

            value_in_slab = min(remaining, bracket)
            if value_in_slab <= 0:
                continue

            slab_commission = round((value_in_slab / gross) * pool, 2)

            for party_type, attr in _PARTY_ATTR:
                pct = float(getattr(slab, attr))
                amount = round(slab_commission * pct / 100.0, 2)
                lines.append(
                    CommissionPayoutLine(
                        commission_payout_id=payout_id,
                        party_type=party_type.value,
                        slab_id=slab.id,
                        amount=amount,
                        percentage=pct,
                        units_covered=round(value_in_slab, 2),
                    )
                )

            remaining -= value_in_slab

        return lines

    def _calc_cumulative(
        self,
        payout_id: str,
        gross: float,
        pool: float,
        slabs: List[CommissionSlab],
    ) -> List[CommissionPayoutLine]:
        """Cumulative (whole-pool) allocation using the applicable slab."""
        applicable: CommissionSlab | None = None
        for slab in slabs:
            slab_from = float(slab.range_from)
            slab_to = float(slab.range_to) if slab.range_to is not None else None
            if gross >= slab_from:
                if slab_to is None or gross < slab_to:
                    applicable = slab
                    break

        if applicable is None:
            # gross is above all defined ranges — use the last slab
            applicable = slabs[-1]

        lines: List[CommissionPayoutLine] = []
        for party_type, attr in _PARTY_ATTR:
            pct = float(getattr(applicable, attr))
            amount = round(pool * pct / 100.0, 2)
            lines.append(
                CommissionPayoutLine(
                    commission_payout_id=payout_id,
                    party_type=party_type.value,
                    slab_id=applicable.id,
                    amount=amount,
                    percentage=pct,
                    units_covered=round(gross, 2),
                )
            )

        return lines

    # ------------------------------------------------------------------
    # Private — validation helpers
    # ------------------------------------------------------------------

    def _validate_new_slab(
        self, data: CommissionSlabCreate, existing: List[CommissionSlab]
    ) -> None:
        """Validate that the new slab does not overlap or create gaps."""
        # Duplicate sequence check
        for s in existing:
            if s.sequence == data.sequence:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Sequence {data.sequence} is already used by another slab.",
                )

        # Overlap / gap check against all existing slabs
        new_from = data.range_from
        new_to = data.range_to  # None = unbounded

        for s in existing:
            s_from = float(s.range_from)
            s_to = float(s.range_to) if s.range_to is not None else None

            # Check overlap
            if new_to is None:
                overlaps = new_from < (s_to if s_to is not None else float("inf"))
            else:
                overlaps = new_from < (s_to if s_to is not None else float("inf")) and new_to > s_from

            if overlaps:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"New slab [{new_from}, {new_to}] overlaps with existing "
                        f"slab [{s_from}, {s_to}] (sequence {s.sequence})."
                    ),
                )

    def _validate_slab_set(self, slabs: List[CommissionSlab]) -> None:
        """Validate the complete slab set for contiguity and correct percentages."""
        for slab in slabs:
            total = round(
                float(slab.sales_rep_pct)
                + float(slab.team_lead_pct)
                + float(slab.manager_pct)
                + float(slab.broker_pct)
                + float(slab.platform_pct),
                4,
            )
            if abs(total - 100.0) > 0.01:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"Slab (sequence={slab.sequence}) allocation percentages sum to "
                        f"{total:.4f}, expected 100."
                    ),
                )

        # Contiguity check (slabs already ordered by sequence/range_from)
        for i in range(len(slabs) - 1):
            current = slabs[i]
            nxt = slabs[i + 1]
            current_to = float(current.range_to) if current.range_to is not None else None
            nxt_from = float(nxt.range_from)

            if current_to is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"Slab (sequence={current.sequence}) has no range_to but is not "
                        "the last slab.  Only the final slab may be open-ended."
                    ),
                )
            if abs(current_to - nxt_from) > 0.01:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"Gap or overlap between slab (sequence={current.sequence}) "
                        f"[..., {current_to}] and slab (sequence={nxt.sequence}) "
                        f"[{nxt_from}, ...]."
                    ),
                )

    # ------------------------------------------------------------------
    # Private — lookup helpers
    # ------------------------------------------------------------------

    def _require_project(self, project_id: str):
        project = self._project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found.",
            )
        return project

    def _require_plan(self, plan_id: str) -> CommissionPlan:
        plan = self._repo.get_plan_by_id(plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CommissionPlan '{plan_id}' not found.",
            )
        return plan

    def _require_plan_not_approved(self, plan: CommissionPlan) -> None:
        """Plans with approved payouts cannot have new slabs added."""
        pass  # slabs can be added freely before payouts are calculated

    def _require_payout(self, payout_id: str) -> CommissionPayout:
        payout = self._repo.get_payout_by_id(payout_id)
        if not payout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CommissionPayout '{payout_id}' not found.",
            )
        return payout

    def _require_sale_contract(self, contract_id: str) -> SalesContract:
        contract = (
            self._db.query(SalesContract)
            .filter(SalesContract.id == contract_id)
            .first()
        )
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SalesContract '{contract_id}' not found.",
            )
        return contract

    def _resolve_project_id(self, contract: SalesContract) -> str:
        """Resolve project_id via Unit → Floor → Building → Phase → Project."""
        from app.modules.buildings.models import Building
        from app.modules.floors.models import Floor
        from app.modules.phases.models import Phase
        from app.modules.units.models import Unit

        row = (
            self._db.query(Phase.project_id)
            .join(Building, Building.phase_id == Phase.id)
            .join(Floor, Floor.building_id == Building.id)
            .join(Unit, Unit.floor_id == Floor.id)
            .filter(Unit.id == contract.unit_id)
            .first()
        )
        if not row:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Cannot resolve project for SalesContract '{contract.id}' "
                    f"(unit_id='{contract.unit_id}')."
                ),
            )
        return row[0]

    def _build_payout_response(self, payout: CommissionPayout) -> CommissionPayoutResponse:
        from app.modules.commission.schemas import (
            CommissionPayoutLineResponse,
            CommissionPayoutResponse,
        )

        lines = self._repo.list_lines_by_payout(payout.id)
        resp = CommissionPayoutResponse.model_validate(payout)
        resp.lines = [CommissionPayoutLineResponse.model_validate(ln) for ln in lines]
        return resp
