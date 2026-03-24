"""
construction.schemas

Pydantic request/response contracts for the Construction domain.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.shared.enums.construction import (
    ConstructionStatus,
    ContractorStatus,
    ContractorType,
    EngineeringStatus,
    MilestoneStatus,
    ProcurementPackageStatus,
    ProcurementPackageType,
)


# ── ConstructionScope ────────────────────────────────────────────────────────


class ConstructionScopeCreate(BaseModel):
    project_id: Optional[str] = None
    phase_id: Optional[str] = None
    building_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    status: ConstructionStatus = ConstructionStatus.PLANNED
    start_date: Optional[date] = None
    target_end_date: Optional[date] = None

    @model_validator(mode="after")
    def require_at_least_one_link(self) -> "ConstructionScopeCreate":
        if not any([self.project_id, self.phase_id, self.building_id]):
            raise ValueError(
                "At least one of project_id, phase_id, or building_id must be provided."
            )
        return self


class ConstructionScopeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[ConstructionStatus] = None
    start_date: Optional[date] = None
    target_end_date: Optional[date] = None


class ConstructionScopeResponse(BaseModel):
    id: str
    project_id: Optional[str]
    phase_id: Optional[str]
    building_id: Optional[str]
    name: str
    description: Optional[str]
    status: ConstructionStatus
    start_date: Optional[date]
    target_end_date: Optional[date]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConstructionScopeList(BaseModel):
    items: List[ConstructionScopeResponse]
    total: int


# ── ConstructionMilestone ────────────────────────────────────────────────────


class ConstructionMilestoneCreate(BaseModel):
    scope_id: str
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    sequence: int = Field(..., ge=1)
    duration_days: Optional[int] = Field(None, ge=0)
    status: MilestoneStatus = MilestoneStatus.PENDING
    target_date: Optional[date] = None
    completion_date: Optional[date] = None
    notes: Optional[str] = None


class ConstructionMilestoneUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    sequence: Optional[int] = Field(None, ge=1)
    duration_days: Optional[int] = Field(None, ge=0)
    status: Optional[MilestoneStatus] = None
    target_date: Optional[date] = None
    completion_date: Optional[date] = None
    notes: Optional[str] = None


class ConstructionMilestoneResponse(BaseModel):
    id: str
    scope_id: str
    name: str
    description: Optional[str]
    sequence: int
    duration_days: Optional[int]
    status: MilestoneStatus
    target_date: Optional[date]
    completion_date: Optional[date]
    notes: Optional[str]
    actual_start_day: Optional[int]
    actual_finish_day: Optional[int]
    progress_percent: Optional[float]
    last_progress_update_at: Optional[datetime]
    planned_cost: Optional[Decimal]
    actual_cost: Optional[Decimal]
    cost_last_updated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConstructionMilestoneList(BaseModel):
    items: List[ConstructionMilestoneResponse]
    total: int


# ── ConstructionProgressUpdate ───────────────────────────────────────────────


class ProgressUpdateCreate(BaseModel):
    progress_percent: int = Field(..., ge=0, le=100)
    status_note: Optional[str] = None
    reported_by: Optional[str] = Field(None, max_length=255)
    reported_at: Optional[datetime] = None

    @field_validator("reported_at")
    @classmethod
    def normalize_reported_at_to_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        from datetime import timezone

        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class ProgressUpdateResponse(BaseModel):
    id: str
    milestone_id: str
    progress_percent: int
    status_note: Optional[str]
    reported_by: Optional[str]
    reported_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("reported_at")
    @classmethod
    def ensure_reported_at_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        from datetime import timezone

        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class ProgressUpdateList(BaseModel):
    items: List[ProgressUpdateResponse]
    total: int


# ── ConstructionEngineeringItem ──────────────────────────────────────────────


class EngineeringItemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    status: EngineeringStatus = EngineeringStatus.PENDING
    item_type: Optional[str] = Field(None, max_length=100)
    consultant_name: Optional[str] = Field(None, max_length=255)
    consultant_cost: Optional[Decimal] = None
    target_date: Optional[date] = None
    completion_date: Optional[date] = None
    notes: Optional[str] = None

    @field_validator("consultant_cost")
    @classmethod
    def cost_non_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("consultant_cost must be non-negative.")
        return v


class EngineeringItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[EngineeringStatus] = None
    item_type: Optional[str] = Field(None, max_length=100)
    consultant_name: Optional[str] = Field(None, max_length=255)
    consultant_cost: Optional[Decimal] = None
    target_date: Optional[date] = None
    completion_date: Optional[date] = None
    notes: Optional[str] = None

    @field_validator("consultant_cost")
    @classmethod
    def cost_non_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("consultant_cost must be non-negative.")
        return v


class EngineeringItemResponse(BaseModel):
    id: str
    scope_id: str
    title: str
    description: Optional[str]
    status: EngineeringStatus
    item_type: Optional[str]
    consultant_name: Optional[str]
    consultant_cost: Optional[Decimal]
    target_date: Optional[date]
    completion_date: Optional[date]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EngineeringItemList(BaseModel):
    items: List[EngineeringItemResponse]
    total: int


# ── ConstructionCostItem ─────────────────────────────────────────────────────

COST_CATEGORIES = {
    "materials",
    "labor",
    "equipment",
    "subcontractor",
    "consultant",
    "permits",
    "utilities",
    "site_overheads",
    "other",
}

COST_TYPES = {"budget", "commitment", "actual"}


class ConstructionCostItemCreate(BaseModel):
    cost_category: str = Field(..., min_length=1, max_length=50)
    cost_type: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., min_length=1, max_length=500)
    vendor_name: Optional[str] = Field(None, max_length=255)
    budget_amount: Decimal = Field(default=Decimal("0.00"))
    committed_amount: Decimal = Field(default=Decimal("0.00"))
    actual_amount: Decimal = Field(default=Decimal("0.00"))
    currency: str = Field(default="AED", max_length=10)
    cost_date: Optional[date] = None
    notes: Optional[str] = None

    @field_validator("cost_category")
    @classmethod
    def validate_cost_category(cls, v: str) -> str:
        if v not in COST_CATEGORIES:
            raise ValueError(
                f"cost_category must be one of: {', '.join(sorted(COST_CATEGORIES))}"
            )
        return v

    @field_validator("cost_type")
    @classmethod
    def validate_cost_type(cls, v: str) -> str:
        if v not in COST_TYPES:
            raise ValueError(
                f"cost_type must be one of: {', '.join(sorted(COST_TYPES))}"
            )
        return v

    @field_validator("budget_amount", "committed_amount", "actual_amount")
    @classmethod
    def amounts_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Amount must be non-negative.")
        return v

    @model_validator(mode="after")
    def at_least_one_nonzero_amount(self) -> "ConstructionCostItemCreate":
        if (
            self.budget_amount == 0
            and self.committed_amount == 0
            and self.actual_amount == 0
        ):
            raise ValueError(
                "At least one of budget_amount, committed_amount, or actual_amount must be non-zero."
            )
        return self


class ConstructionCostItemUpdate(BaseModel):
    cost_category: Optional[str] = Field(None, min_length=1, max_length=50)
    cost_type: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    vendor_name: Optional[str] = Field(None, max_length=255)
    budget_amount: Optional[Decimal] = None
    committed_amount: Optional[Decimal] = None
    actual_amount: Optional[Decimal] = None
    currency: Optional[str] = Field(None, max_length=10)
    cost_date: Optional[date] = None
    notes: Optional[str] = None

    @field_validator("cost_category")
    @classmethod
    def validate_cost_category(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in COST_CATEGORIES:
            raise ValueError(
                f"cost_category must be one of: {', '.join(sorted(COST_CATEGORIES))}"
            )
        return v

    @field_validator("cost_type")
    @classmethod
    def validate_cost_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in COST_TYPES:
            raise ValueError(
                f"cost_type must be one of: {', '.join(sorted(COST_TYPES))}"
            )
        return v

    @field_validator("budget_amount", "committed_amount", "actual_amount")
    @classmethod
    def amounts_non_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Amount must be non-negative.")
        return v


class ConstructionCostItemResponse(BaseModel):
    id: str
    scope_id: str
    cost_category: str
    cost_type: str
    description: str
    vendor_name: Optional[str]
    budget_amount: Decimal
    committed_amount: Decimal
    actual_amount: Decimal
    variance_to_budget: Decimal
    variance_to_commitment: Decimal
    currency: str
    cost_date: Optional[date]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_variance(
        cls, item: object
    ) -> "ConstructionCostItemResponse":
        from decimal import Decimal as D

        budget = getattr(item, "budget_amount", D("0.00")) or D("0.00")
        committed = getattr(item, "committed_amount", D("0.00")) or D("0.00")
        actual = getattr(item, "actual_amount", D("0.00")) or D("0.00")
        return cls(
            id=getattr(item, "id"),
            scope_id=getattr(item, "scope_id"),
            cost_category=getattr(item, "cost_category"),
            cost_type=getattr(item, "cost_type"),
            description=getattr(item, "description"),
            vendor_name=getattr(item, "vendor_name", None),
            budget_amount=budget,
            committed_amount=committed,
            actual_amount=actual,
            variance_to_budget=actual - budget,
            variance_to_commitment=actual - committed,
            currency=getattr(item, "currency", "AED"),
            cost_date=getattr(item, "cost_date", None),
            notes=getattr(item, "notes", None),
            created_at=getattr(item, "created_at"),
            updated_at=getattr(item, "updated_at"),
        )


class ConstructionCostItemList(BaseModel):
    items: List[ConstructionCostItemResponse]
    total: int


class CategoryCostBreakdown(BaseModel):
    budget: Decimal
    committed: Decimal
    actual: Decimal
    variance_to_budget: Decimal
    variance_to_commitment: Decimal


class ConstructionCostSummary(BaseModel):
    scope_id: str
    total_budget: Decimal
    total_committed: Decimal
    total_actual: Decimal
    total_variance_to_budget: Decimal
    total_variance_to_commitment: Decimal
    by_category: Dict[str, CategoryCostBreakdown]


# ── Construction Dashboard ───────────────────────────────────────────────────


class ConstructionDashboardScopeSummary(BaseModel):
    scope_id: str
    scope_name: str
    engineering_items_total: int
    engineering_items_open: int
    engineering_items_completed: int
    milestones_total: int
    milestones_completed: int
    milestones_overdue: int
    latest_progress_percent: Optional[int]
    total_budget: Decimal
    total_committed: Decimal
    total_actual: Decimal
    variance_to_budget: Decimal
    variance_to_commitment: Decimal


class ConstructionDashboardResponse(BaseModel):
    project_id: str
    scopes_total: int
    scopes_active: int
    engineering_items_open_total: int
    milestones_overdue_total: int
    total_budget: Decimal
    total_committed: Decimal
    total_actual: Decimal
    variance_to_budget: Decimal
    variance_to_commitment: Decimal
    scopes: List[ConstructionDashboardScopeSummary]


# ── Milestone Dependency ─────────────────────────────────────────────────────


class MilestoneDependencyCreate(BaseModel):
    """Create a finish-to-start dependency between two milestones."""

    predecessor_id: str = Field(..., description="ID of the predecessor milestone")
    successor_id: str = Field(..., description="ID of the successor milestone")
    lag_days: int = Field(default=0, ge=0, description="Waiting days after predecessor finishes")

    @model_validator(mode="after")
    def no_self_dependency(self) -> "MilestoneDependencyCreate":
        if self.predecessor_id == self.successor_id:
            raise ValueError("A milestone cannot depend on itself.")
        return self


class MilestoneDependencyResponse(BaseModel):
    id: str
    predecessor_id: str
    successor_id: str
    lag_days: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MilestoneDependencyList(BaseModel):
    items: List[MilestoneDependencyResponse]
    total: int


# ── Schedule Results ─────────────────────────────────────────────────────────


class SchedulePhaseRow(BaseModel):
    """CPM output row for a single milestone."""

    milestone_id: str
    milestone_name: str
    duration_days: int
    earliest_start: int
    earliest_finish: int
    latest_start: int
    latest_finish: int
    total_float: int
    is_critical: bool
    delay_days: int


class ScopeScheduleResponse(BaseModel):
    """Full CPM schedule result for a construction scope."""

    scope_id: str
    project_duration: int
    critical_path: List[str]
    phases: List[SchedulePhaseRow]


class CriticalPathResponse(BaseModel):
    """Critical path summary for a construction scope."""

    scope_id: str
    project_duration: int
    critical_path_milestone_ids: List[str]
    critical_path_milestone_names: List[str]
    total_phases: int
    critical_phases: int


# ── Milestone Progress Update ────────────────────────────────────────────────


class MilestoneProgressUpdate(BaseModel):
    """Request body for POST /construction/milestones/{id}/progress."""

    progress_percent: float = Field(..., ge=0.0, le=100.0)
    actual_start_day: Optional[int] = Field(None, ge=0)
    actual_finish_day: Optional[int] = Field(None, ge=0)

    @model_validator(mode="after")
    def validate_progress_rules(self) -> "MilestoneProgressUpdate":
        if self.progress_percent > 0 and self.actual_start_day is None:
            raise ValueError("actual_start_day is required when progress_percent > 0.")
        if self.actual_finish_day is not None and self.actual_start_day is None:
            raise ValueError("actual_start_day is required when actual_finish_day is provided.")
        if self.actual_finish_day is not None and self.progress_percent < 100.0:
            raise ValueError(
                "progress_percent must be 100 when actual_finish_day is provided."
            )
        if (
            self.actual_start_day is not None
            and self.actual_finish_day is not None
            and self.actual_finish_day < self.actual_start_day
        ):
            raise ValueError("actual_finish_day must be >= actual_start_day.")
        return self


# ── Scope Progress Overview ──────────────────────────────────────────────────


class MilestoneProgressRow(BaseModel):
    """Progress summary row for a single milestone."""

    milestone_id: str
    milestone_name: str
    sequence: int
    progress_percent: Optional[float]
    actual_start_day: Optional[int]
    actual_finish_day: Optional[int]
    last_progress_update_at: Optional[datetime]


class ScopeProgressResponse(BaseModel):
    """Aggregated progress overview for a construction scope."""

    scope_id: str
    total_milestones: int
    started_milestones: int
    completed_milestones: int
    overall_completion_percent: float
    milestones: List[MilestoneProgressRow]


# ── Schedule Variance ────────────────────────────────────────────────────────


class MilestoneVarianceRow(BaseModel):
    """Schedule variance row for a single milestone."""

    milestone_id: str
    milestone_name: str
    planned_start: int
    planned_finish: int
    actual_start_day: Optional[int]
    actual_finish_day: Optional[int]
    progress_percent: Optional[float]
    schedule_variance_days: Optional[int]
    completion_variance_days: Optional[int]
    milestone_status: str
    is_critical: bool
    risk_exposed: bool


class ScopeVarianceResponse(BaseModel):
    """Full schedule variance analysis for a construction scope."""

    scope_id: str
    project_delay_days: int
    critical_path_shift: bool
    affected_milestones: List[str]
    milestones: List[MilestoneVarianceRow]


# ── Milestone Cost Update ────────────────────────────────────────────────────


class MilestoneCostUpdate(BaseModel):
    """Request body for POST /construction/milestones/{id}/cost."""

    planned_cost: Optional[Decimal] = None
    actual_cost: Optional[Decimal] = None

    @field_validator("planned_cost", "actual_cost")
    @classmethod
    def costs_non_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Cost values must be non-negative.")
        return v

    @model_validator(mode="after")
    def at_least_one_cost_provided(self) -> "MilestoneCostUpdate":
        if self.planned_cost is None and self.actual_cost is None:
            raise ValueError(
                "At least one of planned_cost or actual_cost must be provided."
            )
        return self


# ── Scope Milestone Cost Overview ────────────────────────────────────────────


class MilestoneCostRow(BaseModel):
    """Cost summary row for a single milestone."""

    milestone_id: str
    milestone_name: str
    sequence: int
    planned_cost: Optional[Decimal]
    actual_cost: Optional[Decimal]
    cost_variance: Optional[Decimal]
    cost_variance_percent: Optional[Decimal]
    cost_last_updated_at: Optional[datetime]


class ScopeMilestoneCostResponse(BaseModel):
    """Milestone-level cost variance overview for a construction scope."""

    scope_id: str
    project_budget: Decimal
    project_actual_cost: Decimal
    project_cost_variance: Decimal
    project_overrun_percent: Optional[Decimal]
    milestones: List[MilestoneCostRow]


# ── Contractor ───────────────────────────────────────────────────────────────


class ContractorCreate(BaseModel):
    contractor_code: str = Field(..., min_length=1, max_length=50)
    contractor_name: str = Field(..., min_length=1, max_length=255)
    contractor_type: ContractorType = ContractorType.MAIN_CONTRACTOR
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    status: ContractorStatus = ContractorStatus.ACTIVE
    notes: Optional[str] = None


class ContractorUpdate(BaseModel):
    contractor_name: Optional[str] = Field(None, min_length=1, max_length=255)
    contractor_type: Optional[ContractorType] = None
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    status: Optional[ContractorStatus] = None
    notes: Optional[str] = None


class ContractorResponse(BaseModel):
    id: str
    contractor_code: str
    contractor_name: str
    contractor_type: ContractorType
    contact_name: Optional[str]
    contact_email: Optional[str]
    phone: Optional[str]
    status: ContractorStatus
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContractorList(BaseModel):
    items: List[ContractorResponse]
    total: int


# ── ProcurementPackage ───────────────────────────────────────────────────────


class ProcurementPackageCreate(BaseModel):
    scope_id: str
    package_code: str = Field(..., min_length=1, max_length=50)
    package_name: str = Field(..., min_length=1, max_length=255)
    package_type: ProcurementPackageType = ProcurementPackageType.OTHER
    status: ProcurementPackageStatus = ProcurementPackageStatus.DRAFT
    planned_value: Optional[Decimal] = None
    awarded_value: Optional[Decimal] = None
    contractor_id: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("planned_value", "awarded_value")
    @classmethod
    def values_non_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Value must be non-negative.")
        return v


class ProcurementPackageUpdate(BaseModel):
    package_name: Optional[str] = Field(None, min_length=1, max_length=255)
    package_type: Optional[ProcurementPackageType] = None
    status: Optional[ProcurementPackageStatus] = None
    planned_value: Optional[Decimal] = None
    awarded_value: Optional[Decimal] = None
    notes: Optional[str] = None

    @field_validator("planned_value", "awarded_value")
    @classmethod
    def values_non_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Value must be non-negative.")
        return v


class ProcurementPackageResponse(BaseModel):
    id: str
    scope_id: str
    contractor_id: Optional[str]
    package_code: str
    package_name: str
    package_type: ProcurementPackageType
    status: ProcurementPackageStatus
    planned_value: Optional[Decimal]
    awarded_value: Optional[Decimal]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProcurementPackageList(BaseModel):
    items: List[ProcurementPackageResponse]
    total: int


# ── Procurement Assignment / Linkage ─────────────────────────────────────────


class PackageAssignContractorRequest(BaseModel):
    contractor_id: str


class PackageLinkMilestoneRequest(BaseModel):
    milestone_id: str


# ── Procurement Overview ─────────────────────────────────────────────────────


class ProcurementPackageStatusCount(BaseModel):
    status: ProcurementPackageStatus
    count: int


class ProcurementOverviewResponse(BaseModel):
    """Aggregated procurement summary for a construction scope."""

    scope_id: str
    total_packages: int
    total_planned_value: Decimal
    total_awarded_value: Decimal
    uncommitted_value: Decimal
    packages_by_status: Dict[str, int]
    packages: List[ProcurementPackageResponse]


# ── Construction Risk Alerts (PR-CONSTR-044) ─────────────────────────────────


class ConstructionRiskAlertResponse(BaseModel):
    """A single construction risk alert."""

    alert_code: str
    severity: str
    scope_id: Optional[str] = None
    contractor_id: Optional[str] = None
    package_id: Optional[str] = None
    milestone_id: Optional[str] = None
    message: str
    metric_value: Optional[float] = None
    threshold: Optional[float] = None


class ScopeRiskAlertListResponse(BaseModel):
    """Risk alert listing for a construction scope."""

    scope_id: str
    total_alerts: int
    alerts: List[ConstructionRiskAlertResponse]


# ── Contractor Performance (PR-CONSTR-044) ───────────────────────────────────


class ContractorPerformanceSummaryResponse(BaseModel):
    """Derived performance summary for a single contractor."""

    contractor_id: str
    contractor_name: str
    total_milestones: int
    delayed_milestones: int
    over_budget_milestones: int
    delay_ratio: Optional[float]
    overrun_ratio: Optional[float]
    alerts: List[ConstructionRiskAlertResponse]


# ── Procurement Risk Overview (PR-CONSTR-044) ────────────────────────────────


class ProcurementRiskOverviewResponse(BaseModel):
    """Aggregated procurement risk summary for a construction scope."""

    scope_id: str
    total_packages: int
    unawarded_packages: int
    stalled_packages: int
    cancelled_or_on_hold_packages: int
    total_planned_value: Decimal
    total_awarded_value: Decimal
    uncommitted_value: Decimal
    alerts: List[ConstructionRiskAlertResponse]


# ── Contractor Scorecard (PR-CONSTR-045) ─────────────────────────────────────


class ContractorScorecardResponse(BaseModel):
    """Derived scorecard for a single contractor."""

    contractor_id: str
    contractor_name: str
    total_milestones: int
    completed_milestones: int
    delayed_milestones: int
    on_time_milestones: int
    over_budget_milestones: int
    assessed_cost_milestones: int
    delayed_ratio: Optional[float]
    on_time_rate: Optional[float]
    overrun_ratio: Optional[float]
    avg_cost_variance_percent: Optional[float]
    active_packages: int
    completed_packages: int
    risk_signal_count: int
    schedule_score: float
    cost_score: float
    risk_score: float
    performance_score: float
    average_delay_days: Optional[float]
    median_delay_days: Optional[float]
    max_delay_days: Optional[int]
    delay_rate: Optional[float]
    total_cost_variance: Optional[Decimal]
    average_cost_variance_pct: Optional[float]
    max_cost_overrun_pct: Optional[float]
    cost_overrun_rate: Optional[float]
    reliability_index: Optional[float] = None
    reliability_band: Optional[str] = None
    reliability_confidence: Optional[str] = None
    watchlist_status: Optional[str] = None
    breach_reasons: List[str] = Field(default_factory=list)


# ── Contractor Trend (PR-CONSTR-045) ─────────────────────────────────────────


class ContractorTrendPointResponse(BaseModel):
    """Scorecard snapshot for a single calendar month period."""

    period_label: str
    total_milestones: int
    completed_milestones: int
    delayed_milestones: int
    over_budget_milestones: int
    delayed_ratio: Optional[float]
    overrun_ratio: Optional[float]
    performance_score: float
    score_delta: Optional[float]


class ContractorTrendResponse(BaseModel):
    """Trend analytics summary for a single contractor."""

    contractor_id: str
    contractor_name: str
    trend_points: List[ContractorTrendPointResponse]
    trend_direction: str
    overall_score: float
    periods_analysed: int


# ── Scope Contractor Ranking (PR-CONSTR-045) ─────────────────────────────────


class ScopeContractorRankingRowResponse(BaseModel):
    """Ranking row for a contractor within a scope."""

    contractor_rank: int
    contractor_id: str
    contractor_name: str
    performance_score: float
    schedule_score: float
    cost_score: float
    risk_score: float
    total_milestones: int
    delayed_ratio: Optional[float]
    overrun_ratio: Optional[float]


class ScopeContractorRankingResponse(BaseModel):
    """Ranked contractor list for a construction scope."""

    scope_id: str
    total_contractors: int
    contractors: List[ScopeContractorRankingRowResponse]


class ScopeContractorScorecardListResponse(BaseModel):
    """All contractor scorecards for a construction scope."""

    scope_id: str
    total_contractors: int
    contractors_on_watch: int = 0
    contractors_escalated: int = 0
    contractors_critical: int = 0
    scorecards: List[ContractorScorecardResponse]


# ── Portfolio Risk Rollup (PR-CONSTR-050) ─────────────────────────────────────


class ProjectConstructionRiskResponse(BaseModel):
    """Project-level construction risk rollup aggregated from contractor scorecards."""

    project_id: str
    contractors_total: int = Field(
        description=(
            "Total number of contractor-scope entries assessed. "
            "A contractor active in multiple scopes contributes one entry per scope."
        )
    )
    contractors_on_watch: int
    contractors_escalated: int
    contractors_critical: int
    project_risk_score: float
    top_breach_reasons: List[str] = Field(default_factory=list)
    highest_risk_contractor: Optional[str] = None


# ── Construction Executive Summary (PR-CONSTR-051) ────────────────────────────


class ProjectConstructionExecutiveSummaryResponse(BaseModel):
    """Single executive-ready construction health snapshot for a project."""

    project_id: str
    construction_health_status: str = Field(
        description="Deterministic health tier: Stable / Watch / Escalated / Critical."
    )
    project_risk_score: float
    contractors_total: int
    contractors_on_watch: int
    contractors_escalated: int
    contractors_critical: int
    top_breach_reasons: List[str] = Field(default_factory=list)
    highest_risk_contractor: Optional[str] = None
    priority_actions: List[str] = Field(default_factory=list)
    summary_generated_at: str = Field(
        description="UTC ISO-8601 timestamp when this summary was computed."
    )
