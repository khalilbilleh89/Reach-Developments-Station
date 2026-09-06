"""Public contracts for projects, land, planning, permits and documents.

Money and rates follow the PR-MVP-01 conventions unchanged: ``Decimal`` end to
end, serialised as JSON strings, and every rate named ``*_rate_fraction`` and
carrying an explicit fraction of one.

Development cost is redacted here rather than in the interface. A value the
caller may not see is absent from the response body, not hidden by CSS.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, PlainSerializer

from app.modules.projects.models import (
    PERMIT_STATUSES,
    PROJECT_STATUSES,
    LandParcel,
    Permit,
)
from app.modules.settings.models import AREA_UNITS


class StrictRequest(BaseModel):
    """A request body that refuses anything it does not declare.

    Pydantic's default is to ignore an unknown key, which means a client that
    misspells a control flag — or names a field this API deliberately does not
    accept, such as a permit ``status`` — is told the mutation succeeded when
    part of it was silently dropped. For a register of statutory and financial
    record that is the wrong default.

    Deliberately one base class with one setting, not an application framework.
    """

    model_config = ConfigDict(extra="forbid")


ProjectStatus = Literal[PROJECT_STATUSES]  # type: ignore[valid-type]
PermitStatus = Literal[PERMIT_STATUSES]  # type: ignore[valid-type]
AreaUnit = Literal[AREA_UNITS]  # type: ignore[valid-type]

#: Decimals leave the API as strings, for the same reason as in Settings: a JSON
#: number is a float, and a float is never an acceptable carrier for money.
DecimalStr = Annotated[Decimal, PlainSerializer(str, return_type=str, when_used="json")]

Money = Annotated[DecimalStr, Field(ge=0, decimal_places=2)]
RateFraction = Annotated[DecimalStr, Field(ge=0, le=1, decimal_places=6)]
Measure = Annotated[DecimalStr, Field(ge=0, decimal_places=4)]
PositiveMeasure = Annotated[DecimalStr, Field(gt=0, decimal_places=4)]
Ratio = Annotated[DecimalStr, Field(ge=0, decimal_places=4)]
#: An ownership share is a real stake: zero is not a share, it is no interest
#: at all, and the database says so too.
OwnershipShare = Annotated[DecimalStr, Field(gt=0, le=1, decimal_places=6)]
Latitude = Annotated[DecimalStr, Field(ge=-90, le=90, decimal_places=6)]
Longitude = Annotated[DecimalStr, Field(ge=-180, le=180, decimal_places=6)]

#: A project code is normalised to upper case by the service; the pattern keeps
#: whitespace and arbitrary Unicode out of an identifier people type and quote.
ProjectCode = Annotated[str, Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")]


# --------------------------------------------------------------------------- #
# Projects
# --------------------------------------------------------------------------- #


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    developer_entity: str
    country_pack_id: uuid.UUID
    city: str | None
    location: str | None
    latitude: DecimalStr | None
    longitude: DecimalStr | None
    project_type_code: str | None
    status: str
    base_currency_id: uuid.UUID
    reporting_currency_id: uuid.UUID
    fiscal_year_start_month: int
    planned_start: date | None
    planned_completion: date | None
    project_manager_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ProjectSummary(ProjectRead):
    """A project plus the small counts a register needs to be readable."""

    parcel_count: int = 0
    permit_count: int = 0
    blocking_permit_count: int = 0
    critical_path_permit_count: int = 0
    overdue_permit_count: int = 0


class ProjectDetail(ProjectSummary):
    """Detail adds the currency and country codes so a client need not re-fetch."""

    country_code: str | None = None
    base_currency_code: str | None = None
    reporting_currency_code: str | None = None
    project_manager_display_name: str | None = None
    #: Derived, never stored: a duration column would go stale the moment either
    #: planned date moved.
    planned_duration_days: int | None = None


class ProjectCreateRequest(StrictRequest):
    code: ProjectCode
    name: str = Field(min_length=1, max_length=200)
    developer_entity: str = Field(min_length=1, max_length=200)
    country_pack_id: uuid.UUID
    base_currency_id: uuid.UUID
    reporting_currency_id: uuid.UUID
    city: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=500)
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    project_type_code: str | None = Field(default=None, max_length=64)
    status: ProjectStatus = "setup"
    fiscal_year_start_month: int | None = Field(default=None, ge=1, le=12)
    planned_start: date | None = None
    planned_completion: date | None = None
    project_manager_user_id: uuid.UUID | None = None


class ProjectUpdateRequest(StrictRequest):
    """``code`` is absent: a project code is immutable once issued."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    developer_entity: str | None = Field(default=None, min_length=1, max_length=200)
    country_pack_id: uuid.UUID | None = None
    city: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=500)
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    project_type_code: str | None = Field(default=None, max_length=64)
    status: ProjectStatus | None = None
    base_currency_id: uuid.UUID | None = None
    reporting_currency_id: uuid.UUID | None = None
    fiscal_year_start_month: int | None = Field(default=None, ge=1, le=12)
    planned_start: date | None = None
    planned_completion: date | None = None
    project_manager_user_id: uuid.UUID | None = None


# --------------------------------------------------------------------------- #
# Project access
# --------------------------------------------------------------------------- #


class ProjectAccessRead(BaseModel):
    """A membership row plus the identity an administration screen needs.

    Carries no password, hash or session information: this describes who may
    open a project, and nothing about how they authenticate.
    """

    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    display_name: str
    role_keys: list[str]
    is_active: bool
    phase_scope: str
    granted_at: datetime
    revoked_at: datetime | None


class ProjectAccessUpdateRequest(StrictRequest):
    is_active: bool


# --------------------------------------------------------------------------- #
# Land parcels
# --------------------------------------------------------------------------- #


class _ParcelFacts(StrictRequest):
    """Everything about a parcel that is not commercially sensitive."""

    title_deed_number: str | None = Field(default=None, max_length=120)
    cadastral_reference: str | None = Field(default=None, max_length=120)
    #: Free text since PR-V2-01: the wording on the title and planning record,
    #: not a code from a dictionary. Suggestions are offered by the interface;
    #: nothing here refuses a value for being unfamiliar.
    ownership_type: str | None = Field(default=None, max_length=500)
    ownership_share_fraction: OwnershipShare | None = None
    acquisition_date: date | None = None
    seller: str | None = Field(default=None, max_length=200)
    title_status: str | None = Field(default=None, max_length=500)
    zoning: str | None = Field(default=None, max_length=500)
    frontage: Measure | None = None
    road_access: str | None = Field(default=None, max_length=500)
    topography: str | None = Field(default=None, max_length=500)
    geotechnical_status: str | None = Field(default=None, max_length=500)
    contamination_status: str | None = Field(default=None, max_length=500)
    flood_drainage_status: str | None = Field(default=None, max_length=500)
    archaeology_heritage_status: str | None = Field(default=None, max_length=500)
    power_available: bool | None = None
    water_available: bool | None = None
    sewer_available: bool | None = None
    stormwater_available: bool | None = None
    telecom_available: bool | None = None
    utility_notes: str | None = Field(default=None, max_length=2000)
    easements: str | None = Field(default=None, max_length=2000)
    encroachments: str | None = Field(default=None, max_length=2000)
    constraints_notes: str | None = Field(default=None, max_length=2000)


class LandParcelRead(_ParcelFacts):
    # A response is built from an ORM row, so it stays permissive; only the
    # request models are strict.
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID
    project_id: uuid.UUID
    plot_number: str
    land_area: DecimalStr
    area_unit: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    #: Null for a caller not cleared to see development cost. Null means "not
    #: exposed" — never a zero, which would read as a real figure of zero.
    purchase_price: DecimalStr | None = None
    acquisition_fees: DecimalStr | None = None
    financials_visible: bool = False
    #: The currency the amounts above are in, so no client has to assume.
    base_currency_code: str | None = None

    @classmethod
    def build(
        cls,
        parcel: LandParcel,
        *,
        include_financials: bool,
        base_currency_code: str | None,
    ) -> LandParcelRead:
        """Assemble a response, dropping cost entirely when it may not be shown."""
        read = cls.model_validate(parcel)
        if include_financials:
            read.purchase_price = parcel.purchase_price
            read.acquisition_fees = parcel.acquisition_fees
            read.financials_visible = True
            read.base_currency_code = base_currency_code
        else:
            read.purchase_price = None
            read.acquisition_fees = None
            read.financials_visible = False
            read.base_currency_code = None
        return read


class LandParcelCreateRequest(_ParcelFacts):
    plot_number: str = Field(min_length=1, max_length=64)
    land_area: PositiveMeasure
    #: Defaults from the country pack when omitted.
    area_unit: AreaUnit | None = None
    purchase_price: Money | None = None
    acquisition_fees: Money | None = None


class LandParcelUpdateRequest(_ParcelFacts):
    plot_number: str | None = Field(default=None, min_length=1, max_length=64)
    land_area: PositiveMeasure | None = None
    area_unit: AreaUnit | None = None
    purchase_price: Money | None = None
    acquisition_fees: Money | None = None
    is_active: bool | None = None


# --------------------------------------------------------------------------- #
# Planning controls
# --------------------------------------------------------------------------- #


class PlanningControlWriteRequest(StrictRequest):
    """The complete current planning envelope for a parcel.

    A full replacement rather than a patch: these controls are issued and read
    as one set, and a half-updated envelope would describe a planning position
    that no authority granted.
    """

    permitted_uses: str | None = Field(default=None, max_length=2000)
    site_coverage_rate_fraction: RateFraction | None = None
    far_ratio: Ratio | None = None
    maximum_gfa: Measure | None = None
    maximum_floors: int | None = Field(default=None, gt=0)
    maximum_height: Measure | None = None
    front_setback: Measure | None = None
    side_setback: Measure | None = None
    rear_setback: Measure | None = None
    parking_requirement: str | None = Field(default=None, max_length=500)
    minimum_plot_area: Measure | None = None
    minimum_frontage: Measure | None = None
    density: Measure | None = None
    exclusions: str | None = Field(default=None, max_length=2000)
    variance_required: bool = False
    variance_notes: str | None = Field(default=None, max_length=2000)


class PlanningControlRead(PlanningControlWriteRequest):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID
    project_id: uuid.UUID
    parcel_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Permits
# --------------------------------------------------------------------------- #


class PermitTypeRead(BaseModel):
    """One permit type available to a project, as the workspace needs it.

    Deliberately narrower than ``ReferenceValueRead``: this answers "what may I
    file here, and what is it called", not "how is the system's reference data
    configured". ``is_active`` is present because a selector must offer only
    what may still be assigned while a historical permit must still render its
    label.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    label: str
    description: str | None
    is_active: bool


class PermitTypeCreateRequest(StrictRequest):
    """The whole contract for adding a permit type from the permit workspace.

    Three fields, and no way to say which category or which jurisdiction: the
    route's project decides both. Strict, so a body naming ``category`` or
    ``country_pack_id`` is refused rather than quietly ignored — the difference
    matters when the field a caller is reaching for would turn this endpoint
    into a general-purpose Settings write.
    """

    code: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)


class _PermitFacts(StrictRequest):
    parcel_id: uuid.UUID | None = None
    authority_reference: str | None = Field(default=None, max_length=120)
    prerequisite_permit_id: uuid.UUID | None = None
    owner_user_id: uuid.UUID | None = None
    consultant: str | None = Field(default=None, max_length=200)
    planned_submission_date: date | None = None
    forecast_submission_date: date | None = None
    actual_submission_date: date | None = None
    accepted_for_review_date: date | None = None
    comments_received_date: date | None = None
    resubmission_date: date | None = None
    planned_issue_date: date | None = None
    forecast_issue_date: date | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    renewal_date: date | None = None
    statutory_sla_days: int | None = Field(default=None, gt=0)
    conditions: str | None = Field(default=None, max_length=4000)
    is_blocking: bool = False
    is_critical_path: bool = False
    next_action: str | None = Field(default=None, max_length=500)
    escalation_owner_user_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=4000)


class PermitRead(_PermitFacts):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID
    project_id: uuid.UUID
    permit_code: str
    permit_type_code: str
    authority: str
    status: str
    status_effective_date: date
    created_at: datetime
    updated_at: datetime

    #: Derived at read time; see ``service.derive_permit_metrics``.
    days_in_stage: int = 0
    sla_days_remaining: int | None = None
    sla_overdue: bool = False
    submission_variance_days: int | None = None
    issue_variance_days: int | None = None
    prerequisite_satisfied: bool = True
    expired_flag: bool = False

    #: Redacted for callers not cleared to see development cost, exactly as
    #: land acquisition cost is.
    fee_amount: DecimalStr | None = None
    financials_visible: bool = False
    base_currency_code: str | None = None

    @classmethod
    def build(
        cls,
        permit: Permit,
        *,
        metrics: dict[str, Any],
        include_financials: bool,
        base_currency_code: str | None,
    ) -> PermitRead:
        read = cls.model_validate(permit)
        for key, value in metrics.items():
            setattr(read, key, value)
        if include_financials:
            read.fee_amount = permit.fee_amount
            read.financials_visible = True
            read.base_currency_code = base_currency_code
        else:
            read.fee_amount = None
            read.financials_visible = False
            read.base_currency_code = None
        return read


class PermitCreateRequest(_PermitFacts):
    permit_code: str = Field(min_length=1, max_length=64)
    permit_type_code: str = Field(min_length=1, max_length=64)
    authority: str = Field(min_length=1, max_length=200)
    status_effective_date: date | None = None
    fee_amount: Money | None = None


class PermitUpdateRequest(_PermitFacts):
    """``status`` is absent on purpose.

    Status moves only through the transition endpoint, so an ordinary update
    cannot overwrite the register's history by setting a column.
    """

    permit_type_code: str | None = Field(default=None, min_length=1, max_length=64)
    authority: str | None = Field(default=None, min_length=1, max_length=200)
    is_blocking: bool | None = None
    is_critical_path: bool | None = None
    fee_amount: Money | None = None


class PermitTransitionRequest(StrictRequest):
    to_status: PermitStatus
    effective_date: date
    reason: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class PermitStatusEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    permit_id: uuid.UUID
    from_status: str
    to_status: str
    effective_date: date
    reason: str | None
    notes: str | None
    changed_by_user_id: uuid.UUID
    changed_at: datetime


class PermitRegister(BaseModel):
    """A permit list plus the counts that make it actionable at a glance."""

    permits: list[PermitRead]
    total: int
    blocking_count: int
    critical_path_count: int
    sla_overdue_count: int


# --------------------------------------------------------------------------- #
# Document references
# --------------------------------------------------------------------------- #


class DocumentReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    parcel_id: uuid.UUID | None
    permit_id: uuid.UUID | None
    title: str
    document_type_code: str
    reference_number: str | None
    external_url: str
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DocumentReferenceCreateRequest(StrictRequest):
    title: str = Field(min_length=1, max_length=200)
    document_type_code: str = Field(min_length=1, max_length=64)
    #: Validated as a URL, then stored as text. This records where a document
    #: lives; it does not fetch, upload, sign or store one.
    external_url: AnyHttpUrl
    parcel_id: uuid.UUID | None = None
    permit_id: uuid.UUID | None = None
    reference_number: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)


class DocumentReferenceUpdateRequest(StrictRequest):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    document_type_code: str | None = Field(default=None, min_length=1, max_length=64)
    external_url: AnyHttpUrl | None = None
    reference_number: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None
