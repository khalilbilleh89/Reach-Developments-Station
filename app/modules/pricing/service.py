"""
pricing.service

Application-layer orchestration for pricing workflows.
Validates domain invariants and coordinates repository and engine calls.
"""

from datetime import datetime, timezone
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.pricing.engines.pricing_engine import PricingInputs, run_pricing
from app.modules.pricing.models import (
    CHANGE_TYPE_APPROVAL,
    CHANGE_TYPE_ARCHIVE,
    CHANGE_TYPE_INITIAL,
    CHANGE_TYPE_MANUAL_UPDATE,
    CHANGE_TYPE_OVERRIDE,
)
from app.modules.pricing.override_rules import assert_override_allowed, calculate_override_percent
from app.modules.pricing.premium_rules import calculate_premium_breakdown
from app.modules.pricing.repository import UnitPricingAttributesRepository, UnitPricingRepository, PricingHistoryRepository
from app.modules.pricing.schemas import (
    DEFAULT_CURRENCY,
    PremiumBreakdownResponse,
    PricingAuditEntry,
    PricingAuditTrailResponse,
    PricingHistoryResponse,
    PricingOverrideRequest,
    PricingReadinessResponse,
    ProjectPriceSummaryItem,
    ProjectPriceSummaryResponse,
    UnitPricingAttributesCreate,
    UnitPricingAttributesResponse,
    UnitPricingDetailResponse,
    UnitPriceResponse,
    UnitPricingResponse,
)
from app.modules.pricing.status_rules import ARCHIVED_STATUS, is_immutable, is_restricted_status
from app.modules.units.repository import UnitRepository


class PricingService:
    def __init__(self, db: Session) -> None:
        self.attrs_repo = UnitPricingAttributesRepository(db)
        self.pricing_repo = UnitPricingRepository(db)
        self.unit_repo = UnitRepository(db)
        self._db = db

    # ------------------------------------------------------------------
    # Attribute management
    # ------------------------------------------------------------------

    def set_pricing_attributes(
        self, unit_id: str, data: UnitPricingAttributesCreate
    ) -> UnitPricingAttributesResponse:
        """Create or replace pricing attributes for a unit."""
        unit = self.unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        attrs = self.attrs_repo.upsert(unit_id, data)
        return UnitPricingAttributesResponse.model_validate(attrs)

    def get_pricing_attributes(self, unit_id: str) -> UnitPricingAttributesResponse:
        """Get the pricing attributes for a unit."""
        unit = self.unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        attrs = self.attrs_repo.get_by_unit(unit_id)
        if not attrs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No pricing attributes found for unit '{unit_id}'.",
            )
        return UnitPricingAttributesResponse.model_validate(attrs)

    # ------------------------------------------------------------------
    # Price calculation
    # ------------------------------------------------------------------

    def _resolve_unit_area(self, unit) -> float:
        """Resolve effective unit area: gross_area if set, else internal_area."""
        if unit.gross_area is not None:
            return float(unit.gross_area)
        return float(unit.internal_area)

    def _validate_pricing_attributes(self, attrs, unit_id: str) -> None:
        """Raise 422 if any required pricing attribute is missing."""
        for field in self._REQUIRED_PRICING_FIELDS:
            if getattr(attrs, field) is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Pricing attribute '{field}' is required but missing for unit '{unit_id}'.",
                )

    _REQUIRED_PRICING_FIELDS = (
        "base_price_per_sqm",
        "floor_premium",
        "view_premium",
        "corner_premium",
        "size_adjustment",
        "custom_adjustment",
    )

    def _has_complete_pricing_attributes(self, attrs) -> bool:
        """Return True if all required pricing attributes are present, False otherwise."""
        return all(getattr(attrs, field) is not None for field in self._REQUIRED_PRICING_FIELDS)

    def _run_pricing_for_area(self, unit_area: float, attrs):
        """Build PricingInputs from a unit area and stored attributes and run the engine."""
        return run_pricing(
            PricingInputs(
                unit_area=unit_area,
                base_price_per_sqm=float(attrs.base_price_per_sqm),
                floor_premium=float(attrs.floor_premium),
                view_premium=float(attrs.view_premium),
                corner_premium=float(attrs.corner_premium),
                size_adjustment=float(attrs.size_adjustment),
                custom_adjustment=float(attrs.custom_adjustment),
            )
        )

    def __compute_readiness(
        self,
        unit_id: str,
        attrs: "UnitPricingAttributes | None",
    ) -> "PricingReadinessResponse":
        """Compute readiness from already-loaded attrs without re-fetching the unit.

        Callers are responsible for verifying the unit exists before calling
        this helper.  This avoids an extra DB round-trip when ``attrs`` has
        already been loaded by the calling method.
        """
        if not attrs:
            return PricingReadinessResponse(
                unit_id=unit_id,
                is_ready_for_pricing=False,
                missing_required_fields=list(self._REQUIRED_PRICING_FIELDS),
                readiness_reason=(
                    "No pricing attributes record exists for this unit. "
                    "Set the numerical engine inputs (base price, premiums, adjustments) "
                    "before calculating a price."
                ),
            )
        missing = [
            field
            for field in self._REQUIRED_PRICING_FIELDS
            if getattr(attrs, field) is None
        ]
        if missing:
            return PricingReadinessResponse(
                unit_id=unit_id,
                is_ready_for_pricing=False,
                missing_required_fields=missing,
                readiness_reason=(
                    f"The following required pricing engine fields are not set: "
                    f"{', '.join(missing)}."
                ),
            )
        return PricingReadinessResponse(
            unit_id=unit_id,
            is_ready_for_pricing=True,
            missing_required_fields=[],
            readiness_reason=None,
        )

    def get_pricing_readiness(self, unit_id: str) -> "PricingReadinessResponse":
        """Return explicit pricing readiness for a unit.

        Inspects the stored UnitPricingAttributes record and returns which
        required numerical engine fields (if any) are still missing.

        This is the source of truth consumed by the pricing inspection page so
        the UI shows specific missing fields rather than a generic message.
        """
        unit = self.unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        attrs = self.attrs_repo.get_by_unit(unit_id)
        return self.__compute_readiness(unit_id, attrs)

    def get_unit_pricing_detail(self, unit_id: str) -> "UnitPricingDetailResponse":
        """Assemble the full pricing detail for a unit as one coherent payload.

        Returns all three pricing layers:
          - engine_inputs (Layer 2): stored numerical engine inputs.
          - pricing_readiness (Layer 3a): current readiness state.
          - pricing_record (Layer 3b): stored commercial pricing record.

        Qualitative attributes (Layer 1) are managed by the pricing_attributes
        module and are returned separately from its own endpoint.
        """
        from app.modules.pricing.repository import UnitPricingRepository
        from app.modules.pricing.schemas import UnitPricingResponse

        unit = self.unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )

        attrs = self.attrs_repo.get_by_unit(unit_id)
        readiness = self.__compute_readiness(unit_id, attrs)

        pricing_repo = UnitPricingRepository(self._db)
        pricing_record_orm = pricing_repo.get_by_unit_id(unit_id)

        return UnitPricingDetailResponse(
            unit_id=unit_id,
            engine_inputs=(
                UnitPricingAttributesResponse.model_validate(attrs) if attrs else None
            ),
            pricing_readiness=readiness,
            pricing_record=(
                UnitPricingResponse.model_validate(pricing_record_orm)
                if pricing_record_orm
                else None
            ),
        )

    def calculate_unit_price(self, unit_id: str) -> UnitPriceResponse:
        """Calculate the final price for a single unit."""
        unit = self.unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        attrs = self.attrs_repo.get_by_unit(unit_id)
        if not attrs:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Pricing attributes must be set before calculating price for unit '{unit_id}'.",
            )
        self._validate_pricing_attributes(attrs, unit_id)

        unit_area = self._resolve_unit_area(unit)
        outputs = self._run_pricing_for_area(unit_area, attrs)

        # Inherit currency from the formal pricing record; default to platform default.
        pricing_record = self.pricing_repo.get_by_unit_id(unit_id)
        currency = pricing_record.currency if pricing_record else DEFAULT_CURRENCY

        return UnitPriceResponse(
            unit_id=unit_id,
            unit_area=unit_area,
            base_unit_price=outputs.base_unit_price,
            premium_total=outputs.premium_total,
            final_unit_price=outputs.final_unit_price,
            currency=currency,
        )

    def calculate_project_price_summary(self, project_id: str) -> ProjectPriceSummaryResponse:
        """Calculate pricing for all priced units in a project."""
        from app.modules.projects.repository import ProjectRepository
        from app.modules.units.models import Unit
        from app.modules.floors.models import Floor
        from app.modules.buildings.models import Building
        from app.modules.phases.models import Phase

        project_repo = ProjectRepository(self._db)
        project = project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found.",
            )

        # Fetch all units for this project via hierarchy join
        units = (
            self._db.query(Unit)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .all()
        )

        unit_ids = [u.id for u in units]
        attrs_list = self.attrs_repo.list_by_unit_ids(unit_ids)
        attrs_by_unit = {a.unit_id: a for a in attrs_list}
        units_by_id = {u.id: u for u in units}

        items: List[ProjectPriceSummaryItem] = []
        total_value = 0.0

        for uid, attrs in attrs_by_unit.items():
            unit = units_by_id[uid]
            # Skip units with incomplete attributes
            if not self._has_complete_pricing_attributes(attrs):
                continue

            unit_area = self._resolve_unit_area(unit)
            outputs = self._run_pricing_for_area(unit_area, attrs)
            items.append(
                ProjectPriceSummaryItem(
                    unit_id=uid,
                    unit_area=unit_area,
                    base_unit_price=outputs.base_unit_price,
                    premium_total=outputs.premium_total,
                    final_unit_price=outputs.final_unit_price,
                )
            )
            total_value += outputs.final_unit_price

        return ProjectPriceSummaryResponse(
            project_id=project_id,
            total_units_priced=len(items),
            total_value=total_value,
            items=items,
        )

    def get_premium_breakdown(self, pricing_id: str) -> PremiumBreakdownResponse:
        """Return a detailed premium breakdown for a pricing record.

        Looks up the formal UnitPricing record by *pricing_id*, then assembles
        the full premium breakdown from UnitPricingAttributes (if available).

        When no UnitPricingAttributes record exists for the unit,
        ``has_engine_breakdown`` is False and all engine-derived fields are
        None.  The formal pricing record values are always included.

        Raises HTTP 404 when the pricing record does not exist.
        """
        pricing_record = self.pricing_repo.get_by_id(pricing_id)
        if not pricing_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pricing record '{pricing_id}' not found.",
            )

        unit_id = pricing_record.unit_id
        attrs = self.attrs_repo.get_by_unit(unit_id)

        if attrs and self._has_complete_pricing_attributes(attrs):
            unit = self.unit_repo.get_by_id(unit_id)
            unit_area = self._resolve_unit_area(unit) if unit else None
            if unit_area is not None:
                breakdown = calculate_premium_breakdown(
                    unit_id=unit_id,
                    unit_area=unit_area,
                    base_price_per_sqm=float(attrs.base_price_per_sqm),
                    floor_premium=float(attrs.floor_premium),
                    view_premium=float(attrs.view_premium),
                    corner_premium=float(attrs.corner_premium),
                    size_adjustment=float(attrs.size_adjustment),
                    custom_adjustment=float(attrs.custom_adjustment),
                )
                return PremiumBreakdownResponse(
                    pricing_id=pricing_id,
                    unit_id=unit_id,
                    base_price=float(pricing_record.base_price),
                    manual_adjustment=float(pricing_record.manual_adjustment),
                    final_price=float(pricing_record.final_price),
                    currency=pricing_record.currency,
                    has_engine_breakdown=True,
                    base_price_per_sqm=breakdown.base_price_per_sqm,
                    unit_area=breakdown.unit_area,
                    engine_base_unit_price=breakdown.base_unit_price,
                    floor_premium=breakdown.floor_premium,
                    view_premium=breakdown.view_premium,
                    corner_premium=breakdown.corner_premium,
                    size_adjustment=breakdown.size_adjustment,
                    custom_adjustment=breakdown.custom_adjustment,
                    premium_total=breakdown.premium_total,
                    engine_final_unit_price=breakdown.final_unit_price,
                )

        # No complete attributes — return formal record values only.
        return PremiumBreakdownResponse(
            pricing_id=pricing_id,
            unit_id=unit_id,
            base_price=float(pricing_record.base_price),
            manual_adjustment=float(pricing_record.manual_adjustment),
            final_price=float(pricing_record.final_price),
            currency=pricing_record.currency,
            has_engine_breakdown=False,
            base_price_per_sqm=None,
            unit_area=None,
            engine_base_unit_price=None,
            floor_premium=None,
            view_premium=None,
            corner_premium=None,
            size_adjustment=None,
            custom_adjustment=None,
            premium_total=None,
            engine_final_unit_price=None,
        )



class UnitPricingService:
    """Service for managing formal per-unit pricing records.

    Computes final_price = base_price + manual_adjustment server-side.
    Validates that the resulting final_price is non-negative.

    Hardened lifecycle rules:
    - A unit must be ready for pricing before creating a new record.
    - Pricing records become immutable after approval.
    - Only one active (non-archived) record per unit is permitted.
    - Approved pricing must precede reservation/sales eligibility.
    """

    def __init__(self, db: Session) -> None:
        self._pricing_repo = UnitPricingRepository(db)
        self._history_repo = PricingHistoryRepository(db)
        self._unit_repo = UnitRepository(db)
        self._db = db

    # ------------------------------------------------------------------
    # Readiness enforcement
    # ------------------------------------------------------------------

    def assert_unit_ready_for_pricing(self, unit_id: str) -> None:
        """Raise HTTP 422 when *unit_id* is not ready for pricing operations.

        Delegates to UnitService which owns the readiness definition.
        Raises HTTP 404 when the unit does not exist.
        """
        from app.modules.units.service import UnitService
        UnitService(self._db).assert_unit_ready_for_pricing(unit_id)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_unit_pricing(self, unit_id: str):
        """Return the active pricing record for a unit, or raise 404 if not found."""
        from app.modules.pricing.schemas import UnitPricingResponse

        unit = self._unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        record = self._pricing_repo.get_by_unit_id(unit_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active pricing record found for unit '{unit_id}'.",
            )
        return UnitPricingResponse.model_validate(record)

    def get_active_pricing(self, unit_id: str):
        """Return the active pricing record, or None when none exists.

        Does not raise on missing — callers can decide how to handle None.
        """
        from app.modules.pricing.schemas import UnitPricingResponse

        record = self._pricing_repo.get_by_unit_id(unit_id)
        if record is None:
            return None
        return UnitPricingResponse.model_validate(record)

    def get_pricing_history(self, unit_id: str) -> "PricingHistoryResponse":
        """Return all pricing records for *unit_id*, including archived, newest first."""
        from app.modules.pricing.schemas import UnitPricingResponse

        unit = self._unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )
        records = self._pricing_repo.get_all_by_unit_id(unit_id)
        items = [UnitPricingResponse.model_validate(r) for r in records]
        return PricingHistoryResponse(unit_id=unit_id, total=len(items), items=items)

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create_pricing(self, unit_id: str, data) -> "UnitPricingResponse":
        """Create a new pricing record for *unit_id* under the hardened lifecycle.

        Enforces that the unit is ready for pricing (status 'available').
        Archives any existing active pricing record before creating a new one.
        Restricted statuses (approved, archived) are rejected — the record starts
        as 'draft' by default, but may be created as 'submitted' or 'reviewed'
        if those values are explicitly supplied.
        """
        from app.modules.pricing.schemas import UnitPricingCreate, UnitPricingResponse

        # Gate: unit must be ready for pricing.
        self.assert_unit_ready_for_pricing(unit_id)

        payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else dict(data)
        base_price = payload.get("base_price", 0.0)
        manual_adjustment = payload.get("manual_adjustment", 0.0)
        currency = payload.get("currency", "AED")
        notes = payload.get("notes", None)
        # Schema accepts draft/submitted/reviewed; blocks approved/archived.
        # Default to draft here as an additional safety net.
        pricing_status = payload.get("pricing_status", "draft")

        final_price = base_price + manual_adjustment
        if final_price < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Resulting final_price ({final_price}) would be negative. "
                    "Adjust base_price or manual_adjustment."
                ),
            )

        # Archive any existing active record before creating the new one.
        # Update the status first, then record the ARCHIVE history entry so that
        # the audit log reflects the state *after* the archive transition.
        superseded = self._pricing_repo.get_by_unit_id(unit_id)
        if superseded is not None:
            archived = self._pricing_repo.update_for_unit(superseded, pricing_status=ARCHIVED_STATUS)
            self._history_repo.record_change(
                pricing_id=archived.id,
                unit_id=archived.unit_id,
                change_type=CHANGE_TYPE_ARCHIVE,
                base_price=float(archived.base_price),
                manual_adjustment=float(archived.manual_adjustment),
                final_price=float(archived.final_price),
                pricing_status=archived.pricing_status,
                currency=archived.currency,
                override_reason=archived.override_reason,
                override_requested_by=archived.override_requested_by,
                override_approved_by=archived.override_approved_by,
            )

        record = self._pricing_repo.create_for_unit(
            unit_id,
            base_price=base_price,
            manual_adjustment=manual_adjustment,
            final_price=final_price,
            currency=currency,
            pricing_status=pricing_status,
            notes=notes,
        )
        # Record history entry for the new pricing record.
        self._history_repo.record_change(
            pricing_id=record.id,
            unit_id=unit_id,
            change_type=CHANGE_TYPE_INITIAL,
            base_price=float(record.base_price),
            manual_adjustment=float(record.manual_adjustment),
            final_price=float(record.final_price),
            pricing_status=record.pricing_status,
            currency=record.currency,
        )
        return UnitPricingResponse.model_validate(record)

    def approve_pricing(self, pricing_id: str, approved_by: str) -> "UnitPricingResponse":
        """Approve a pricing record, making it immutable and sales-eligible.

        Sets pricing_status to 'approved', records the approver and timestamp.
        Raises 404 when the record is not found.
        Raises 422 when the record is already approved or archived.
        """
        from app.modules.pricing.schemas import UnitPricingResponse

        record = self._pricing_repo.get_by_id(pricing_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pricing record '{pricing_id}' not found.",
            )
        if record.pricing_status == "approved":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Pricing record is already approved.",
            )
        if record.pricing_status == "archived":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Archived pricing records cannot be approved.",
            )
        record = self._pricing_repo.update_for_unit(
            record,
            pricing_status="approved",
            approved_by=approved_by,
            approval_date=datetime.now(timezone.utc),
        )
        self._history_repo.record_change(
            pricing_id=record.id,
            unit_id=record.unit_id,
            change_type=CHANGE_TYPE_APPROVAL,
            base_price=float(record.base_price),
            manual_adjustment=float(record.manual_adjustment),
            final_price=float(record.final_price),
            pricing_status=record.pricing_status,
            currency=record.currency,
            actor=approved_by,
        )
        return UnitPricingResponse.model_validate(record)

    def save_unit_pricing(self, unit_id: str, data):
        """Create or update the pricing record for a unit (backward-compatible upsert).

        Calculates final_price = base_price + manual_adjustment.
        Rejects the operation if the resulting final_price would be negative.
        Rejects the operation if the existing active record is approved (immutable).
        Enforces unit readiness when creating a new pricing record.
        Client-supplied ``pricing_status`` values of 'approved' or 'archived' are
        stripped — approval requires the dedicated endpoint, archival is automatic.
        """
        from app.modules.pricing.schemas import UnitPricingCreate, UnitPricingResponse

        unit = self._unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found.",
            )

        # Resolve field values — merge with existing record if present
        existing = self._pricing_repo.get_by_unit_id(unit_id)

        # Readiness gate: unit must be ready for pricing when creating a new record.
        if existing is None:
            self.assert_unit_ready_for_pricing(unit_id)

        # Immutability gate: approved records cannot be edited.
        if existing and is_immutable(existing.pricing_status):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Pricing record is '{existing.pricing_status}' and cannot be edited. "
                    "Create a new pricing record to supersede it."
                ),
            )

        payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else dict(data)

        base_price = payload.get("base_price", float(existing.base_price) if existing else 0.0)
        manual_adjustment = payload.get(
            "manual_adjustment",
            float(existing.manual_adjustment) if existing else 0.0,
        )
        currency = payload.get("currency", existing.currency if existing else "AED")

        # Strip restricted status values — approval must go through the
        # dedicated approval endpoint, archival is handled by supersede.
        requested_status = payload.get("pricing_status")
        if requested_status and is_restricted_status(requested_status):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Cannot set pricing_status to '{requested_status}' via this endpoint. "
                    "Use POST /pricing/{id}/approve to approve, or POST /units/{id}/pricing "
                    "to supersede (which archives the current record automatically)."
                ),
            )
        pricing_status = requested_status if requested_status else (
            existing.pricing_status if existing else "draft"
        )
        notes = payload.get("notes", existing.notes if existing else None)

        final_price = base_price + manual_adjustment
        if final_price < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Resulting final_price ({final_price}) would be negative. "
                    "Adjust base_price or manual_adjustment."
                ),
            )

        record = self._pricing_repo.upsert_for_unit(
            unit_id,
            base_price=base_price,
            manual_adjustment=manual_adjustment,
            final_price=final_price,
            currency=currency,
            pricing_status=pricing_status,
            notes=notes,
        )
        change_type = CHANGE_TYPE_INITIAL if existing is None else CHANGE_TYPE_MANUAL_UPDATE
        self._history_repo.record_change(
            pricing_id=record.id,
            unit_id=unit_id,
            change_type=change_type,
            base_price=float(record.base_price),
            manual_adjustment=float(record.manual_adjustment),
            final_price=float(record.final_price),
            pricing_status=record.pricing_status,
            currency=record.currency,
        )
        return UnitPricingResponse.model_validate(record)

    def get_project_pricing(self, project_id: str) -> "dict[str, UnitPricingResponse]":
        """Return all active pricing records for units in a project, keyed by unit_id."""
        from app.modules.pricing.schemas import UnitPricingResponse

        records = self._pricing_repo.list_by_project(project_id)
        return {r.unit_id: UnitPricingResponse.model_validate(r) for r in records}

    def update_pricing_by_id(self, pricing_id: str, data) -> "UnitPricingResponse":
        """Update a specific pricing record by its ID.

        Rejected when the record is in an immutable state (approved or archived).
        Recomputes final_price = base_price + existing manual_adjustment.

        ``pricing_status`` cannot be changed here — status progression occurs
        only through dedicated lifecycle endpoints (POST /pricing/{id}/approve
        for approval, POST /units/{id}/pricing to supersede).

        ``manual_adjustment`` cannot be changed here — pricing overrides must
        use POST /pricing/{id}/override, which enforces role-based authority
        thresholds and records a full audit trail.
        """
        from app.modules.pricing.schemas import UnitPricingResponse

        record = self._pricing_repo.get_by_id(pricing_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pricing record '{pricing_id}' not found.",
            )
        if is_immutable(record.pricing_status):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Pricing record is '{record.pricing_status}' and cannot be edited. "
                    "Create a new pricing record to supersede it."
                ),
            )

        payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else dict(data)

        base_price = payload.get("base_price", float(record.base_price))
        # manual_adjustment is governed — always preserve the existing value here.
        # Use POST /pricing/{id}/override to change the adjustment.
        manual_adjustment = float(record.manual_adjustment)
        final_price = base_price + manual_adjustment

        if final_price < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Resulting final_price ({final_price}) would be negative. "
                    "Adjust base_price or use POST /pricing/{id}/override."
                ),
            )

        update_kwargs: dict = {
            "base_price": base_price,
            "final_price": final_price,
        }
        # Only base_price/currency/notes are writable; pricing_status and
        # manual_adjustment are excluded.
        for field in ("currency", "notes"):
            if field in payload:
                update_kwargs[field] = payload[field]

        record = self._pricing_repo.update_for_unit(record, **update_kwargs)
        self._history_repo.record_change(
            pricing_id=record.id,
            unit_id=record.unit_id,
            change_type=CHANGE_TYPE_MANUAL_UPDATE,
            base_price=float(record.base_price),
            manual_adjustment=float(record.manual_adjustment),
            final_price=float(record.final_price),
            pricing_status=record.pricing_status,
            currency=record.currency,
        )
        return UnitPricingResponse.model_validate(record)

    def apply_pricing_override(
        self, pricing_id: str, data: PricingOverrideRequest
    ) -> "UnitPricingResponse":
        """Apply a governed price override to a pricing record.

        Validates that the requested override is within the authority threshold
        for the caller's role before applying it.  The ``override_amount``
        replaces the current ``manual_adjustment``; ``final_price`` is
        recomputed as ``base_price + override_amount``.

        Override governance rules
        -------------------------
        - ≤ 2% of base_price: Sales Manager can self-approve.
        - ≤ 5% of base_price: Development Director can self-approve.
        - > 5% of base_price: CEO required.

        Raises HTTP 404 when the pricing record does not exist.
        Raises HTTP 422 when the record is approved or archived (immutable).
        Raises HTTP 422 when the override exceeds the caller's role authority.
        Raises HTTP 422 when the resulting final_price would be negative.
        """
        record = self._pricing_repo.get_by_id(pricing_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pricing record '{pricing_id}' not found.",
            )

        if is_immutable(record.pricing_status):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Pricing record is '{record.pricing_status}' and cannot be overridden. "
                    "Create a new pricing record to supersede it."
                ),
            )

        base_price = float(record.base_price)
        override_amount = data.override_amount
        override_percent = calculate_override_percent(override_amount, base_price)

        # Validate governance — raises HTTP 422 when not allowed.
        assert_override_allowed(data.role, override_percent)

        final_price = base_price + override_amount
        if final_price < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Resulting final_price ({final_price}) would be negative. "
                    "Adjust override_amount."
                ),
            )

        record = self._pricing_repo.update_for_unit(
            record,
            manual_adjustment=override_amount,
            final_price=final_price,
            override_reason=data.override_reason,
            override_requested_by=data.requested_by,
            override_approved_by=data.requested_by,
        )
        self._history_repo.record_change(
            pricing_id=record.id,
            unit_id=record.unit_id,
            change_type=CHANGE_TYPE_OVERRIDE,
            base_price=float(record.base_price),
            manual_adjustment=float(record.manual_adjustment),
            final_price=float(record.final_price),
            pricing_status=record.pricing_status,
            currency=record.currency,
            override_reason=data.override_reason,
            override_requested_by=data.requested_by,
            override_approved_by=data.requested_by,
            actor=data.requested_by,
        )
        return UnitPricingResponse.model_validate(record)

    def get_pricing_audit_trail(self, pricing_id: str) -> "PricingAuditTrailResponse":
        """Return the full audit trail for a pricing record, oldest first.

        Raises HTTP 404 when the pricing record does not exist.
        """
        record = self._pricing_repo.get_by_id(pricing_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pricing record '{pricing_id}' not found.",
            )
        entries = self._history_repo.get_by_pricing_id(pricing_id)
        return PricingAuditTrailResponse(
            pricing_id=pricing_id,
            unit_id=record.unit_id,
            total=len(entries),
            entries=[PricingAuditEntry.model_validate(e) for e in entries],
        )

