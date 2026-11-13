"""Optional, closed amenity details embedded in the audited Project Bio document."""

import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Measure = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)]
Count = Annotated[int, Field(ge=0, le=1000000)]
Status = Literal["planned", "under_construction", "available"]
Setting = Literal["indoor", "outdoor"]


class AmenityInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="after")
    def ordered_ranges(self) -> "AmenityInput":
        for minimum, maximum in (
            ("min_depth_m", "max_depth_m"),
            ("min_area_sqm", "max_area_sqm"),
            ("min_age", "max_age"),
        ):
            low, high = getattr(self, minimum, None), getattr(self, maximum, None)
            if low is not None and high is not None and low > high:
                raise ValueError(f"{minimum} must not exceed {maximum}.")
        return self


class AmenityContext(AmenityInput):
    applicability: Literal["whole_project", "selected"] | None = None
    blocks: Text = ""
    units: Text = ""
    supporting_url: HttpUrl | None = None
    status: Status | None = None


class Pool(AmenityInput):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: Text = ""
    pool_type: Literal["main", "children"] | None = None
    setting: Setting | None = None
    length_m: Measure | None = None
    width_m: Measure | None = None
    area_sqm: Measure | None = None
    min_depth_m: Measure | None = None
    max_depth_m: Measure | None = None
    location: Text = ""
    access: Text = ""
    heating: bool | None = None
    step_free_entry: bool | None = None
    shallow_area: bool | None = None
    sun_deck: bool | None = None
    status: Status | None = None


class SwimmingPools(AmenityContext):
    pools: list[Pool] = Field(default_factory=list, max_length=50)


class Gym(AmenityContext):
    area_sqm: Measure | None = None
    location: Text = ""
    equipment: Text = ""
    access: Text = ""


class Garden(AmenityContext):
    shared_garden: bool | None = None
    garden_view: bool | None = None
    area_sqm: Measure | None = None
    facilities: Text = ""
    access: Text = ""
    view_blocks: Text = ""
    view_units: Text = ""


class Energy(AmenityContext):
    features: Text = ""
    rating: Text = ""
    certificate_url: HttpUrl | None = None


class PlayArea(AmenityContext):
    area_sqm: Measure | None = None
    location: Text = ""
    setting: Setting | None = None
    min_age: Annotated[int, Field(ge=0, le=25)] | None = None
    max_age: Annotated[int, Field(ge=0, le=25)] | None = None
    equipment: Text = ""
    shade: Text = ""


class Balcony(AmenityInput):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    unit_type: Text = ""
    area_sqm: Measure | None = None
    min_area_sqm: Measure | None = None
    max_area_sqm: Measure | None = None
    overlooks: Text = ""
    blocks: Text = ""
    units: Text = ""


class Balconies(AmenityContext):
    balconies: list[Balcony] = Field(default_factory=list, max_length=100)


class Parking(AmenityContext):
    total_spaces: Count | None = None
    spaces_per_unit: Count | None = None
    covered_spaces: Count | None = None
    uncovered_spaces: Count | None = None
    visitor_spaces: Count | None = None
    ev_charging: Literal["available", "planned", "unavailable"] | None = None
    ev_notes: Text = ""


class Amenities(AmenityInput):
    swimming_pools: SwimmingPools = Field(default_factory=SwimmingPools)
    gym: Gym = Field(default_factory=Gym)
    garden: Garden = Field(default_factory=Garden)
    energy: Energy = Field(default_factory=Energy)
    play_area: PlayArea = Field(default_factory=PlayArea)
    balconies: Balconies = Field(default_factory=Balconies)
    parking: Parking = Field(default_factory=Parking)

    @model_validator(mode="after")
    def unique_entries(self) -> "Amenities":
        for rows in (self.swimming_pools.pools, self.balconies.balconies):
            if len({row.id for row in rows}) != len(rows):
                raise ValueError("Amenity entries must have distinct identifiers.")
        return self


def removed_details(before: dict, after: dict) -> bool:
    """Only explicit record removal requires a reason; ordinary field edits do not."""

    def populated(value: object) -> bool:
        if isinstance(value, dict):
            return any(populated(item) for key, item in value.items() if key != "id")
        if isinstance(value, list):
            return bool(value)
        return value is not None and value != ""

    for key, old in before.items():
        new = after.get(key, {})
        if populated(old) and not populated(new):
            return True
        child_key = (
            "pools" if key == "swimming_pools" else "balconies" if key == "balconies" else None
        )
        if child_key:
            old_ids = {item["id"] for item in old.get(child_key, [])}
            new_ids = {item["id"] for item in new.get(child_key, [])}
            if old_ids - new_ids:
                return True
    return False
