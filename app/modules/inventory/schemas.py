"""Public contracts for inventory, areas, sub-assets and configurable fields.

Every request model refuses keys it does not declare. A misspelled ``bedroms``
answering 200 would tell an operator a change happened that did not, and for a
catalogue that later carries prices and contracts that is the wrong default.

Measures and factors are ``Decimal`` end to end and leave the API as JSON
strings. A weighted saleable area routed through a binary float is a number
nobody can reconcile against a drawing.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from app.modules.inventory.models import (
    AREA_ROLES,
    AREA_SCHEDULE_STATUSES,
    ASSET_CLASSES,
    COLLECTION_STATUSES,
    COMMERCIAL_STATUSES,
    CUSTOM_FIELD_DATA_TYPES,
    CUSTOM_FIELD_ENTITIES,
    CUSTOM_FIELD_SCOPES,
    DELIVERY_STATUSES,
    LEGAL_STATUSES,
    PHASE_STATUSES,
    STATUS_DIMENSIONS,
    SUB_ASSET_TYPES,
    TRANSFER_MODES,
)
from app.modules.projects.models import PHASE_SCOPES
from app.modules.projects.schemas import StrictRequest

#: Decimals leave the API as strings. A JSON number is a float, and a float is
#: never an acceptable carrier for a measured area or a weighting factor.
DecimalStr = Annotated[Decimal, PlainSerializer(str, return_type=str, when_used="json")]

Measure = Annotated[DecimalStr, Field(ge=0, decimal_places=4)]
Factor = Annotated[DecimalStr, Field(ge=0, le=1, decimal_places=6)]
Coverage = Annotated[DecimalStr, Field(ge=0, le=1, decimal_places=6)]

PhaseStatus = Literal[PHASE_STATUSES]  # type: ignore[valid-type]
PhaseScope = Literal[PHASE_SCOPES]  # type: ignore[valid-type]
AssetClass = Literal[ASSET_CLASSES]  # type: ignore[valid-type]
CommercialStatus = Literal[COMMERCIAL_STATUSES]  # type: ignore[valid-type]
LegalStatus = Literal[LEGAL_STATUSES]  # type: ignore[valid-type]
CollectionStatus = Literal[COLLECTION_STATUSES]  # type: ignore[valid-type]
DeliveryStatus = Literal[DELIVERY_STATUSES]  # type: ignore[valid-type]
StatusDimension = Literal[STATUS_DIMENSIONS]  # type: ignore[valid-type]
AreaRole = Literal[AREA_ROLES]  # type: ignore[valid-type]
AreaScheduleStatus = Literal[AREA_SCHEDULE_STATUSES]  # type: ignore[valid-type]
SubAssetType = Literal[SUB_ASSET_TYPES]  # type: ignore[valid-type]
TransferMode = Literal[TRANSFER_MODES]  # type: ignore[valid-type]
CustomFieldEntity = Literal[CUSTOM_FIELD_ENTITIES]  # type: ignore[valid-type]
CustomFieldDataType = Literal[CUSTOM_FIELD_DATA_TYPES]  # type: ignore[valid-type]
CustomFieldScope = Literal[CUSTOM_FIELD_SCOPES]  # type: ignore[valid-type]

#: A response built from an ORM row. Only requests are strict.
_READ = ConfigDict(from_attributes=True, extra="ignore")

Code = Annotated[str, Field(min_length=1, max_length=32)]
FloorCode = Annotated[str, Field(min_length=1, max_length=16)]
Name = Annotated[str, Field(min_length=1, max_length=200)]
Reference = Annotated[str, Field(min_length=1, max_length=64)]
Notes = Annotated[str, Field(max_length=2000)]


# --------------------------------------------------------------------------- #
# Phase
# --------------------------------------------------------------------------- #


class PhaseCreateRequest(StrictRequest):
    """``code`` is normalised to upper case and immutable once issued."""

    code: Code
    name: Name
    sequence: int = Field(default=0, ge=0)
    status: PhaseStatus | None = None
    planned_start: date | None = None
    planned_completion: date | None = None
    notes: Notes | None = None


class PhaseUpdateRequest(StrictRequest):
    """``code`` is absent: a phase code is immutable once issued."""

    name: Name | None = None
    sequence: int | None = Field(default=None, ge=0)
    status: PhaseStatus | None = None
    planned_start: date | None = None
    planned_completion: date | None = None
    notes: Notes | None = None
    is_active: bool | None = None


class PhaseRead(BaseModel):
    model_config = _READ

    id: uuid.UUID
    project_id: uuid.UUID
    code: str
    name: str
    sequence: int
    status: str
    planned_start: date | None
    planned_completion: date | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Building and floor
# --------------------------------------------------------------------------- #


class BuildingCreateRequest(StrictRequest):
    phase_id: uuid.UUID
    code: Code
    name: Name
    zone: str | None = Field(default=None, max_length=120)
    block: str | None = Field(default=None, max_length=120)
    entrance_wing: str | None = Field(default=None, max_length=120)
    sequence: int = Field(default=0, ge=0)


class BuildingUpdateRequest(StrictRequest):
    """``phase_id`` and ``code`` are absent: a building does not change phase."""

    name: Name | None = None
    zone: str | None = Field(default=None, max_length=120)
    block: str | None = Field(default=None, max_length=120)
    entrance_wing: str | None = Field(default=None, max_length=120)
    sequence: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class BuildingRead(BaseModel):
    model_config = _READ

    id: uuid.UUID
    project_id: uuid.UUID
    phase_id: uuid.UUID
    code: str
    name: str
    zone: str | None
    block: str | None
    entrance_wing: str | None
    sequence: int
    is_active: bool


class FloorCreateRequest(StrictRequest):
    building_id: uuid.UUID
    code: FloorCode
    label: Name
    level_number: int | None = None
    sequence: int = Field(default=0, ge=0)


class FloorUpdateRequest(StrictRequest):
    label: Name | None = None
    level_number: int | None = None
    sequence: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class FloorRead(BaseModel):
    model_config = _READ

    id: uuid.UUID
    project_id: uuid.UUID
    building_id: uuid.UUID
    code: str
    label: str
    level_number: int | None
    sequence: int
    is_active: bool


# --------------------------------------------------------------------------- #
# Unit
# --------------------------------------------------------------------------- #


class _UnitFacts(StrictRequest):
    """What a unit is, physically. Status and release controls are elsewhere."""

    unit_type_code: str | None = Field(default=None, max_length=64)
    bedrooms: int | None = Field(default=None, ge=0, le=99)
    bathrooms: int | None = Field(default=None, ge=0, le=99)
    has_maid_room: bool | None = None
    is_duplex: bool | None = None
    is_penthouse: bool | None = None
    furnishing_specification_code: str | None = Field(default=None, max_length=64)
    floor_band_code: str | None = Field(default=None, max_length=64)
    orientation_code: str | None = Field(default=None, max_length=64)
    view_class_code: str | None = Field(default=None, max_length=64)
    is_corner: bool | None = None
    pool_access: bool | None = None
    accessibility_code: str | None = Field(default=None, max_length=64)
    garden_class_code: str | None = Field(default=None, max_length=64)
    plot_coverage_fraction: Coverage | None = None


class UnitCreateRequest(_UnitFacts):
    floor_id: uuid.UUID
    unit_number: Annotated[str, Field(min_length=1, max_length=32)]
    unit_reference: Reference
    sequence: int = Field(default=0, ge=0)
    asset_class: AssetClass


class UnitUpdateRequest(_UnitFacts):
    """Status is absent by construction, and so is ``pricing_approved``.

    Status moves only through the transition endpoint, which records why. The
    release controls have their own endpoint because each of their fields has a
    different owning role. ``floor_id`` is accepted, but only while the unit is
    still unreleased.
    """

    floor_id: uuid.UUID | None = None
    unit_number: Annotated[str, Field(min_length=1, max_length=32)] | None = None
    unit_reference: Reference | None = None
    sequence: int | None = Field(default=None, ge=0)
    asset_class: AssetClass | None = None
    is_active: bool | None = None


class ReleaseControlsRequest(StrictRequest):
    """The release gates. ``pricing_approved`` is deliberately not here.

    PR-MVP-04 sets it when an approved price exists. Accepting it now would be a
    pricing approval with no price behind it, and the strict model turns any
    attempt into a 422 rather than a silent no-op.
    """

    drawings_approved: bool | None = None
    legal_sale_eligible: bool | None = None
    release_date: date | None = None
    release_batch: str | None = Field(default=None, max_length=64)
    block_reason: str | None = Field(default=None, max_length=500)


class CommercialTransitionRequest(StrictRequest):
    to_status: CommercialStatus
    effective_date: date
    reason: str | None = Field(default=None, max_length=500)
    notes: Notes | None = None


class AreaLine(BaseModel):
    """One measured area and what it contributes to the weighted total."""

    model_config = ConfigDict(extra="ignore")

    area_type_id: uuid.UUID
    code: str
    label: str
    area_role: str
    unit_of_measure: str
    raw_area: DecimalStr
    weight_factor: DecimalStr
    weighted_area: DecimalStr


class UnitSummary(BaseModel):
    """A row of the unit register: what a manager scans, and nothing more."""

    model_config = _READ

    id: uuid.UUID
    project_id: uuid.UUID
    unit_reference: str
    unit_number: str
    floor_id: uuid.UUID
    floor_code: str | None = None
    building_id: uuid.UUID | None = None
    building_code: str | None = None
    phase_id: uuid.UUID | None = None
    phase_code: str | None = None
    asset_class: str
    unit_type_code: str | None
    bedrooms: int | None
    #: The project's primary internal area from the current approved schedule.
    internal_area: DecimalStr | None = None
    weighted_saleable_area: DecimalStr | None = None
    parking_count: int = 0
    storage_count: int = 0
    commercial_status: str
    legal_status: str
    collection_status: str
    delivery_status: str
    is_complete: bool = False
    completeness_percent: int = 0
    release_eligible: bool = False
    release_blockers: list[str] = Field(default_factory=list)
    is_active: bool


class UnitDetail(UnitSummary):
    """Everything about one unit that inventory owns. Not yet Unit 360."""

    bathrooms: int | None
    has_maid_room: bool
    is_duplex: bool
    is_penthouse: bool
    furnishing_specification_code: str | None
    floor_band_code: str | None
    orientation_code: str | None
    view_class_code: str | None
    is_corner: bool
    pool_access: bool
    accessibility_code: str | None
    garden_class_code: str | None
    plot_coverage_fraction: DecimalStr | None
    sequence: int
    drawings_approved: bool
    legal_sale_eligible: bool
    pricing_approved: bool
    release_date: date | None
    release_batch: str | None
    block_reason: str | None
    missing_requirements: list[str] = Field(default_factory=list)
    area_lines: list[AreaLine] = Field(default_factory=list)
    area_schedule_id: uuid.UUID | None = None
    area_revision_code: str | None = None
    created_at: datetime
    updated_at: datetime


class UnitRegister(BaseModel):
    """A page of units, and counts describing the whole filtered set."""

    units: list[UnitSummary]
    total: int
    available_count: int
    held_count: int
    unreleased_count: int
    release_eligible_count: int


class UnitStatusEventRead(BaseModel):
    model_config = _READ

    id: uuid.UUID
    unit_id: uuid.UUID
    dimension: str
    from_status: str
    to_status: str
    effective_date: date
    reason: str | None
    notes: str | None
    changed_at: datetime


# --------------------------------------------------------------------------- #
# Sub-assets
# --------------------------------------------------------------------------- #


class SubAssetCreateRequest(StrictRequest):
    asset_reference: Reference
    asset_type: SubAssetType
    subtype_code: str | None = Field(default=None, max_length=64)
    floor_id: uuid.UUID | None = None
    linked_unit_id: uuid.UUID | None = None
    area: Measure | None = None
    transfer_mode: TransferMode = "attached"
    notes: Notes | None = None


class SubAssetUpdateRequest(StrictRequest):
    asset_reference: Reference | None = None
    subtype_code: str | None = Field(default=None, max_length=64)
    floor_id: uuid.UUID | None = None
    linked_unit_id: uuid.UUID | None = None
    area: Measure | None = None
    transfer_mode: TransferMode | None = None
    notes: Notes | None = None
    is_active: bool | None = None


class SubAssetRead(BaseModel):
    model_config = _READ

    id: uuid.UUID
    project_id: uuid.UUID
    asset_reference: str
    asset_type: str
    subtype_code: str | None
    floor_id: uuid.UUID | None
    linked_unit_id: uuid.UUID | None
    area: DecimalStr | None
    transfer_mode: str
    notes: str | None
    is_active: bool


# --------------------------------------------------------------------------- #
# Areas
# --------------------------------------------------------------------------- #


class AreaTypeCreateRequest(StrictRequest):
    code: Code
    label: Name
    area_role: AreaRole
    unit_of_measure: str = Field(default="sqm", max_length=16)
    #: An explicit fraction of one. A balcony at 0.500000 contributes half its
    #: measured area to the weighted saleable figure — and none of its raw area
    #: changes, ever.
    weight_factor: Factor
    required_for_release: bool = False
    sort_order: int = Field(default=0, ge=0)


class AreaTypeUpdateRequest(StrictRequest):
    label: Name | None = None
    area_role: AreaRole | None = None
    unit_of_measure: str | None = Field(default=None, max_length=16)
    weight_factor: Factor | None = None
    required_for_release: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class AreaTypeRead(BaseModel):
    model_config = _READ

    id: uuid.UUID
    project_id: uuid.UUID
    code: str
    label: str
    area_role: str
    unit_of_measure: str
    weight_factor: DecimalStr
    required_for_release: bool
    sort_order: int
    is_active: bool


class AreaValueWrite(StrictRequest):
    area_type_id: uuid.UUID
    raw_area: Measure


class AreaScheduleCreateRequest(StrictRequest):
    revision_code: Code
    measurement_standard: str | None = Field(default=None, max_length=120)
    plan_revision: str | None = Field(default=None, max_length=64)
    source: str | None = Field(default=None, max_length=120)
    measured_date: date | None = None
    reconciled: bool = False
    notes: Notes | None = None
    values: list[AreaValueWrite] = Field(default_factory=list, max_length=50)


class AreaScheduleUpdateRequest(StrictRequest):
    """Only a draft accepts this. An approved revision is immutable."""

    measurement_standard: str | None = Field(default=None, max_length=120)
    plan_revision: str | None = Field(default=None, max_length=64)
    source: str | None = Field(default=None, max_length=120)
    measured_date: date | None = None
    reconciled: bool | None = None
    notes: Notes | None = None
    values: list[AreaValueWrite] | None = Field(default=None, max_length=50)


class AreaScheduleRead(BaseModel):
    model_config = _READ

    id: uuid.UUID
    project_id: uuid.UUID
    unit_id: uuid.UUID
    revision_code: str
    status: str
    measurement_standard: str | None
    plan_revision: str | None
    source: str | None
    measured_date: date | None
    verified_by_user_id: uuid.UUID | None
    approved_by_user_id: uuid.UUID | None
    approved_at: datetime | None
    reconciled: bool
    notes: str | None
    lines: list[AreaLine] = Field(default_factory=list)
    weighted_saleable_area: DecimalStr | None = None


# --------------------------------------------------------------------------- #
# Phase access
# --------------------------------------------------------------------------- #


class PhaseScopeRequest(StrictRequest):
    phase_scope: PhaseScope


class PhaseAccessRequest(StrictRequest):
    is_active: bool


class PhaseAccessRead(BaseModel):
    model_config = _READ

    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    phase_id: uuid.UUID
    phase_code: str | None = None
    phase_name: str | None = None
    is_active: bool
    granted_at: datetime
    revoked_at: datetime | None


# --------------------------------------------------------------------------- #
# Configurable fields
# --------------------------------------------------------------------------- #


class CustomFieldOptionWrite(StrictRequest):
    code: Annotated[str, Field(min_length=1, max_length=64)]
    label: Name
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = True


class CustomFieldOptionRead(BaseModel):
    model_config = _READ

    id: uuid.UUID
    code: str
    label: str
    sort_order: int
    is_active: bool


class CustomFieldCreateRequest(StrictRequest):
    """A definition's identity — entity, key, type and scope — is fixed at birth.

    Changing any of them later would reinterpret every value already recorded
    against it, so the update model below simply does not accept them.
    """

    entity_type: CustomFieldEntity
    field_key: Annotated[str, Field(min_length=1, max_length=64)]
    display_label: Name
    description: str | None = Field(default=None, max_length=500)
    data_type: CustomFieldDataType
    unit_of_measure: str | None = Field(default=None, max_length=32)
    help_text: str | None = Field(default=None, max_length=500)
    required: bool = False
    required_for_release: bool = False
    minimum_value: DecimalStr | None = None
    maximum_value: DecimalStr | None = None
    regex_pattern: str | None = Field(default=None, max_length=200)
    is_unique: bool = False
    scope_type: CustomFieldScope
    country_pack_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    unit_type_code: str | None = Field(default=None, max_length=64)
    visible_role_keys: list[str] | None = Field(default=None, max_length=20)
    editable_role_keys: list[str] | None = Field(default=None, max_length=20)
    sensitive: bool = False
    approval_required: bool = False
    filterable: bool = False
    groupable: bool = False
    dashboard_visible: bool = False
    export_visible: bool = True
    valid_from: date | None = None
    valid_to: date | None = None
    options: list[CustomFieldOptionWrite] = Field(default_factory=list, max_length=100)


class CustomFieldUpdateRequest(StrictRequest):
    display_label: Name | None = None
    description: str | None = Field(default=None, max_length=500)
    unit_of_measure: str | None = Field(default=None, max_length=32)
    help_text: str | None = Field(default=None, max_length=500)
    required: bool | None = None
    required_for_release: bool | None = None
    minimum_value: DecimalStr | None = None
    maximum_value: DecimalStr | None = None
    regex_pattern: str | None = Field(default=None, max_length=200)
    visible_role_keys: list[str] | None = Field(default=None, max_length=20)
    editable_role_keys: list[str] | None = Field(default=None, max_length=20)
    sensitive: bool | None = None
    approval_required: bool | None = None
    filterable: bool | None = None
    groupable: bool | None = None
    dashboard_visible: bool | None = None
    export_visible: bool | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    is_active: bool | None = None
    change_reason: str | None = Field(default=None, max_length=500)
    options: list[CustomFieldOptionWrite] | None = Field(default=None, max_length=100)


class CustomFieldRead(BaseModel):
    model_config = _READ

    id: uuid.UUID
    entity_type: str
    field_key: str
    display_label: str
    description: str | None
    data_type: str
    unit_of_measure: str | None
    help_text: str | None
    required: bool
    required_for_release: bool
    minimum_value: DecimalStr | None
    maximum_value: DecimalStr | None
    regex_pattern: str | None
    is_unique: bool
    scope_type: str
    country_pack_id: uuid.UUID | None
    project_id: uuid.UUID | None
    unit_type_code: str | None
    visible_role_keys: list[str] | None
    editable_role_keys: list[str] | None
    sensitive: bool
    approval_required: bool
    filterable: bool
    groupable: bool
    dashboard_visible: bool
    export_visible: bool
    valid_from: date | None
    valid_to: date | None
    is_active: bool
    version: int
    options: list[CustomFieldOptionRead] = Field(default_factory=list)


class CustomValuesRequest(StrictRequest):
    """A bulk write keyed by field key. One transaction, per-field security.

    ``None`` clears a value; the row survives with a null so the audit trail can
    show both sides of the change.
    """

    values: dict[str, Any] = Field(default_factory=dict)
    change_reason: str | None = Field(default=None, max_length=500)


class CustomValueRead(BaseModel):
    """One field, its definition metadata, and this entity's value for it."""

    definition_id: uuid.UUID
    field_key: str
    display_label: str
    data_type: str
    unit_of_measure: str | None
    help_text: str | None
    required: bool
    required_for_release: bool
    is_editable: bool
    options: list[CustomFieldOptionRead] = Field(default_factory=list)
    value: Any = None


# --------------------------------------------------------------------------- #
# Bulk import
# --------------------------------------------------------------------------- #


class ImportIssue(BaseModel):
    """One problem with one cell, named precisely enough to fix in the file."""

    row: int
    column: str | None
    severity: Literal["error", "warning"]
    message: str


class ImportReport(BaseModel):
    mode: Literal["create", "upsert"]
    applied: bool
    total_rows: int
    create_count: int
    update_count: int
    valid_rows: int
    invalid_rows: int
    error_count: int
    warning_count: int
    issues: list[ImportIssue]
    #: True when ``issues`` was capped; ``error_count`` still counts them all.
    issues_truncated: bool = False
