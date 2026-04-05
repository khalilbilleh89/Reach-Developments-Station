"""
payment_plans.service

Service-layer orchestration for payment plan templates and schedule generation.

Business rules enforced here:
  - Only `standard_installments` plan type is currently implemented
  - Template must exist and be active before generating a schedule
  - Contract must exist and have a positive contract_price
  - generate_schedule_for_contract refuses if a schedule already exists (use regenerate)
  - Generated schedule amounts must sum to contract_price within rounding tolerance
  - Regeneration validates everything and generates in memory BEFORE replacing existing rows
    so a contract is never left without a schedule on failure
  - No receipt rows are created; no revenue recognition logic here
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.constants.currency import DEFAULT_CURRENCY
from app.modules.payment_plans.models import PaymentPlanTemplate, PaymentSchedule
from app.modules.payment_plans.repository import (
    PaymentPlanTemplateRepository,
    PaymentScheduleRepository,
)
from app.modules.payment_plans.schemas import (
    PaymentPlanCreate,
    PaymentPlanGenerateRequest,
    PaymentPlanResponse,
    PaymentPlanTemplateCreate,
    PaymentPlanTemplateList,
    PaymentPlanTemplateResponse,
    PaymentPlanTemplateUpdate,
    PaymentScheduleListResponse,
    PaymentScheduleResponse,
)
from app.modules.payment_plans.template_engine import generate_schedule
from app.modules.sales.models import SalesContract
from app.shared.enums.finance import PaymentPlanType, PaymentScheduleStatus

_ROUNDING_TOLERANCE = 0.02  # maximum allowable rounding drift in currency units

# Only plan types whose generation logic is implemented.  Reject others explicitly
# rather than silently falling back to standard-installment behaviour.
_SUPPORTED_PLAN_TYPES: frozenset[str] = frozenset(
    {PaymentPlanType.STANDARD_INSTALLMENTS.value}
)


class PaymentPlanService:
    def __init__(self, db: Session) -> None:
        self.template_repo = PaymentPlanTemplateRepository(db)
        self.schedule_repo = PaymentScheduleRepository(db)
        self.db = db

    # ------------------------------------------------------------------
    # Template management
    # ------------------------------------------------------------------

    def create_template(
        self, data: PaymentPlanTemplateCreate
    ) -> PaymentPlanTemplateResponse:
        self._require_supported_plan_type(data.plan_type)
        template = self.template_repo.create(data)
        return PaymentPlanTemplateResponse.model_validate(template)

    def get_template(self, template_id: str) -> PaymentPlanTemplateResponse:
        template = self._require_template(template_id)
        return PaymentPlanTemplateResponse.model_validate(template)

    def list_templates(
        self, skip: int = 0, limit: int = 100
    ) -> PaymentPlanTemplateList:
        templates = self.template_repo.list(skip=skip, limit=limit)
        total = self.template_repo.count()
        return PaymentPlanTemplateList(
            items=[PaymentPlanTemplateResponse.model_validate(t) for t in templates],
            total=total,
        )

    def update_template(
        self, template_id: str, data: PaymentPlanTemplateUpdate
    ) -> PaymentPlanTemplateResponse:
        template = self._require_template(template_id)

        if data.plan_type is not None:
            self._require_supported_plan_type(data.plan_type)

        # Merge incoming values with stored values and validate the effective total.
        # Schema-level already catches when BOTH fields are supplied together; this
        # covers the case where only ONE is being changed.
        effective_down = (
            data.down_payment_percent
            if data.down_payment_percent is not None
            else float(template.down_payment_percent)
        )
        effective_handover = (
            data.handover_percent
            if data.handover_percent is not None
            else (
                float(template.handover_percent) if template.handover_percent else 0.0
            )
        )
        if effective_down + effective_handover > 100.0:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Effective down_payment_percent ({effective_down}) + "
                    f"handover_percent ({effective_handover}) must not exceed 100."
                ),
            )

        updated = self.template_repo.update(template, data)
        return PaymentPlanTemplateResponse.model_validate(updated)

    # ------------------------------------------------------------------
    # Schedule generation
    # ------------------------------------------------------------------

    def generate_schedule_for_contract(
        self, request: PaymentPlanGenerateRequest
    ) -> PaymentScheduleListResponse:
        """Generate and persist payment schedule rows for a contract.

        Raises 409 if the contract already has schedule rows — callers should
        use the regenerate endpoint to replace an existing schedule.
        """
        contract = self._require_contract(request.contract_id)
        template = self._require_active_template(request.template_id)
        self._require_supported_plan_type(template.plan_type)

        # Prevent duplicate schedules: require explicit use of regenerate endpoint.
        existing = self.schedule_repo.list_by_contract(contract.id)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Contract {contract.id!r} already has a payment schedule "
                    f"({len(existing)} rows). Use the regenerate endpoint to replace it."
                ),
            )

        rows = self._build_schedule_rows(contract, template, request.start_date)
        persisted = self.schedule_repo.bulk_create(rows)
        return self._build_list_response(contract.id, persisted, contract.currency)

    def get_schedule_for_contract(
        self, contract_id: str
    ) -> PaymentScheduleListResponse:
        """Retrieve persisted schedule rows for a contract."""
        contract = self._require_contract(contract_id)
        rows = self.schedule_repo.list_by_contract(contract_id)
        return self._build_list_response(contract_id, rows, contract.currency)

    def regenerate_schedule_for_contract(
        self, contract_id: str, request: PaymentPlanGenerateRequest
    ) -> PaymentScheduleListResponse:
        """Replace an existing schedule with a newly generated one, atomically.

        Safety guarantee: all validation and in-memory generation happen BEFORE
        the existing rows are touched.  If anything fails, the old schedule is
        left intact.
        """
        if request.contract_id != contract_id:
            raise HTTPException(
                status_code=400,
                detail="contract_id in request body must match the URL parameter.",
            )

        contract = self._require_contract(contract_id)
        template = self._require_active_template(request.template_id)
        self._require_supported_plan_type(template.plan_type)

        # Generate and validate in memory first — existing rows are untouched.
        rows = self._build_schedule_rows(contract, template, request.start_date)

        # Now atomically delete old rows and insert new rows in a single commit.
        self.schedule_repo.replace_for_contract(contract_id, rows)

        persisted = self.schedule_repo.list_by_contract(contract_id)
        return self._build_list_response(contract_id, persisted, contract.currency)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_schedule_rows(
        self,
        contract: SalesContract,
        template: PaymentPlanTemplate,
        start_date: Optional[date],
    ) -> List[dict]:
        """Generate schedule lines in memory, validate total, and return row dicts."""
        effective_start = start_date or date.today()
        contract_price = float(contract.contract_price)

        lines = generate_schedule(
            contract_id=contract.id,
            template_id=template.id,
            contract_price=contract_price,
            number_of_installments=template.number_of_installments,
            down_payment_percent=float(template.down_payment_percent),
            installment_frequency=template.installment_frequency,
            start_date=effective_start,
            handover_percent=(
                float(template.handover_percent) if template.handover_percent else None
            ),
        )

        self._validate_schedule_total(lines, contract_price)

        contract_currency = getattr(contract, "currency", DEFAULT_CURRENCY) or DEFAULT_CURRENCY
        return [
            {
                "contract_id": contract.id,
                "template_id": template.id,
                "installment_number": line.installment_number,
                "due_date": line.due_date,
                "due_amount": line.due_amount,
                "currency": contract_currency,
                "status": PaymentScheduleStatus.PENDING.value,
                "notes": line.notes,
            }
            for line in lines
        ]

    def _require_template(self, template_id: str) -> PaymentPlanTemplate:
        template = self.template_repo.get_by_id(template_id)
        if not template:
            raise HTTPException(
                status_code=404, detail=f"Template {template_id!r} not found."
            )
        return template

    def _require_active_template(self, template_id: str) -> PaymentPlanTemplate:
        template = self._require_template(template_id)
        if not template.is_active:
            raise HTTPException(
                status_code=422,
                detail=f"Template {template_id!r} is inactive and cannot be used for generation.",
            )
        return template

    def _require_contract(self, contract_id: str) -> SalesContract:
        contract = (
            self.db.query(SalesContract).filter(SalesContract.id == contract_id).first()
        )
        if not contract:
            raise HTTPException(
                status_code=404, detail=f"Contract {contract_id!r} not found."
            )
        if not contract.contract_price or float(contract.contract_price) <= 0:
            raise HTTPException(
                status_code=422,
                detail=f"Contract {contract_id!r} has no valid contract price.",
            )
        return contract

    @staticmethod
    def _require_supported_plan_type(plan_type: str) -> None:
        """Raise 422 if the plan type is not yet implemented by the generation engine."""
        if plan_type not in _SUPPORTED_PLAN_TYPES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Plan type {plan_type!r} is not yet implemented. "
                    f"Supported types: {sorted(_SUPPORTED_PLAN_TYPES)}."
                ),
            )

    @staticmethod
    def _validate_schedule_total(lines: list, contract_price: float) -> None:
        total = sum(line.due_amount for line in lines)
        drift = abs(total - contract_price)
        if drift > _ROUNDING_TOLERANCE:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Schedule total {total:.2f} deviates from contract price "
                    f"{contract_price:.2f} by {drift:.4f} — exceeds rounding tolerance."
                ),
            )

    @staticmethod
    def _build_list_response(
        contract_id: str, rows: List[PaymentSchedule], currency: str = DEFAULT_CURRENCY
    ) -> PaymentScheduleListResponse:
        items = [PaymentScheduleResponse.model_validate(r) for r in rows]
        return PaymentScheduleListResponse(
            contract_id=contract_id,
            items=items,
            total=len(items),
            total_due=round(sum(i.due_amount for i in items), 2),
            currency=currency,
        )

    # ------------------------------------------------------------------
    # PR029 — simplified payment plan creation and retrieval
    # ------------------------------------------------------------------

    def create_payment_plan(self, data: PaymentPlanCreate) -> PaymentPlanResponse:
        """Create a payment plan for a contract without pre-registering a template.

        This convenience method creates a temporary named template scoped to the
        request and immediately generates the installment schedule, returning a
        plan-centric response that wraps the underlying schedule rows.

        Business rules enforced:
          - Contract must exist and have a positive contract price
          - One payment plan (schedule) per contract — use regenerate to replace
          - Installment totals must equal contract price within rounding tolerance

        Transactional guarantee:
          Template creation and schedule row insertion are executed inside a
          single DB transaction. If either step fails the entire operation is
          rolled back, leaving no orphaned template or partial schedule behind.
          IntegrityError (e.g. duplicate installment numbers from a concurrent
          request) is converted to a 409 response.
        """
        from sqlalchemy.exc import IntegrityError

        contract = self._require_contract(data.contract_id)

        # Guard: one plan per contract.
        existing = self.schedule_repo.list_by_contract(contract.id)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Contract {contract.id!r} already has a payment plan "
                    f"({len(existing)} installments). "
                    "Use the regenerate endpoint to replace it."
                ),
            )

        template_data = PaymentPlanTemplateCreate(
            name=data.plan_name,
            plan_type=PaymentPlanType.STANDARD_INSTALLMENTS,
            down_payment_percent=data.down_payment_percent,
            number_of_installments=data.number_of_installments,
            installment_frequency=data.installment_frequency,
            is_active=True,
        )
        self._require_supported_plan_type(template_data.plan_type)

        # --- single atomic transaction -----------------------------------
        # Add template + schedule rows in memory and commit once so that a
        # failure in schedule generation cannot leave an orphaned template.
        try:
            template = PaymentPlanTemplate(**template_data.model_dump())
            self.db.add(template)
            self.db.flush()  # obtain template.id without committing

            rows = self._build_schedule_rows(contract, template, data.start_date)
            schedule_objs = [PaymentSchedule(**row) for row in rows]
            for obj in schedule_objs:
                self.db.add(obj)

            self.db.commit()
            self.db.refresh(template)
            for obj in schedule_objs:
                self.db.refresh(obj)
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail=(
                    f"A payment plan for contract {contract.id!r} already exists "
                    "or a concurrent request created one. Please refresh and try again."
                ),
            )
        # -----------------------------------------------------------------

        # Re-query ordered rows so _build_plan_response gets correct ordering.
        persisted = self.schedule_repo.list_by_contract(contract.id)
        return self._build_plan_response(template.name, template.plan_type, persisted, contract.currency)

    def get_schedule_item(self, schedule_item_id: str) -> PaymentScheduleResponse:
        """Return a single payment schedule item by its ID."""
        row = self.schedule_repo.get_by_id(schedule_item_id)
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Payment schedule item {schedule_item_id!r} not found.",
            )
        return PaymentScheduleResponse.model_validate(row)

    def get_contract_payment_plan(self, contract_id: str) -> PaymentPlanResponse:
        """Return the payment plan for a contract as a plan-centric response."""
        contract = self._require_contract(contract_id)
        rows = self.schedule_repo.list_by_contract(contract_id)
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No payment plan found for contract {contract_id!r}.",
            )
        # Derive plan name from the template if available.
        plan_name = rows[0].template.name if rows[0].template else "Payment Plan"
        plan_type = (
            rows[0].template.plan_type
            if rows[0].template
            else PaymentPlanType.STANDARD_INSTALLMENTS.value
        )
        return self._build_plan_response(plan_name, plan_type, rows, contract.currency)

    def list_contract_installments(
        self, contract_id: str
    ) -> PaymentScheduleListResponse:
        """List all installments for a contract (alias for get_schedule_for_contract)."""
        return self.get_schedule_for_contract(contract_id)

    @staticmethod
    def _build_plan_response(
        plan_name: str,
        plan_type: str,
        rows: List[PaymentSchedule],
        currency: str = DEFAULT_CURRENCY,
    ) -> PaymentPlanResponse:
        """Build a PaymentPlanResponse from a list of persisted schedule rows."""
        from datetime import datetime as dt, timezone

        items = [PaymentScheduleResponse.model_validate(r) for r in rows]
        now = dt.now(timezone.utc)
        # Use min/max across all rows so the plan-level timestamps are correct
        # regardless of the ordering of the rows list (which is by installment
        # number, not by creation/update time).
        created_at = min([r.created_at for r in rows], default=now)
        updated_at = max([r.updated_at for r in rows], default=now)
        # Use the template id of the first row as the plan id (stable for the contract).
        plan_id = (
            rows[0].template_id
            if rows and rows[0].template_id
            else rows[0].id
            if rows
            else ""
        )
        contract_id = rows[0].contract_id if rows else ""
        return PaymentPlanResponse(
            id=plan_id,
            contract_id=contract_id,
            plan_name=plan_name,
            plan_type=plan_type,
            installments=items,
            total_installments=len(items),
            total_due=round(sum(i.due_amount for i in items), 2),
            currency=currency,
            created_at=created_at,
            updated_at=updated_at,
        )
