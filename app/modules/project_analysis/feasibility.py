"""Current measured area feasibility; Decimal arithmetic and explicit missing inputs."""

import uuid
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.modules.inventory.common_areas import list_areas
from app.modules.inventory.models import Unit
from app.modules.project_analysis import schemas, service


class Measure(BaseModel):
    value: Decimal | None
    measured_count: int
    expected_count: int
    reason: str | None = None
    formula: str


class AreaGroup(BaseModel):
    unit_type: str
    bedrooms: int | None
    apartments: int
    areas: dict[str, Measure]


class Efficiency(BaseModel):
    label: str
    percentage: Decimal | None
    numerator: Decimal | None
    denominator: Decimal | None
    formula: str
    reason: str | None


class Feasibility(BaseModel):
    context: schemas.Context
    apartments: int
    other_units: int
    totals: dict[str, Measure]
    averages: dict[str, Measure]
    groups: list[AreaGroup]
    efficiencies: list[Efficiency]
    notes: list[str]


ZERO = Decimal("0")
FACTORS = {
    "sqm": Decimal("1"),
    "m2": Decimal("1"),
    "m²": Decimal("1"),
    "sqft": Decimal("0.09290304"),
    "ft2": Decimal("0.09290304"),
    "ft²": Decimal("0.09290304"),
}


def rounded(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def measure(values: list[Decimal | None], formula: str, reason: str | None = None) -> Measure:
    known = [value for value in values if value is not None]
    complete = bool(values) and len(known) == len(values) and reason is None
    return Measure(
        value=sum(known, ZERO) if complete else None,
        measured_count=len(known),
        expected_count=len(values),
        formula=formula,
        reason=None
        if complete
        else reason
        or "Complete measurements are not recorded; enter explicit zero where not applicable.",
    )


def combine(*parts: Measure, formula: str) -> Measure:
    return measure([part.value for part in parts], formula)


def component(lines: list[dict], key: str) -> Decimal | None:
    found = [line for line in lines if line["physical_component"] == key]
    if len(found) != 1:
        return None
    line = found[0]
    factor = FACTORS.get(line["unit_of_measure"].strip().lower())
    return line["raw_area"] * factor if factor is not None else None


def sum_components(lines: list[dict], keys: tuple[str, ...]) -> Decimal | None:
    values = [component(lines, key) for key in keys]
    return sum(values, ZERO) if all(value is not None for value in values) else None


def apartment_areas(
    population: list[Unit],
    lines: dict[uuid.UUID, list[dict]],
    allocations: dict[uuid.UUID, Decimal],
    common_complete: bool,
) -> dict[str, Measure]:
    result = {}
    for key, components in {
        "covered": ("internal", "balcony"),
        "internal": ("internal",),
        "balcony": ("balcony",),
        "terrace": ("terrace",),
    }.items():
        result[key] = measure(
            [sum_components(lines.get(unit.id, []), components) for unit in population],
            "Approved apartment schedules: " + " + ".join(components),
        )
    result["common"] = measure(
        [allocations.get(unit.id, ZERO) if common_complete else None for unit in population],
        "Common Areas allocated to these apartments",
    )
    result["total"] = combine(
        result["covered"],
        result["terrace"],
        result["common"],
        formula=(
            "Apartment covered (including balcony) + terrace + allocated common "
            "area; excludes other private outdoors and garages"
        ),
    )
    return result


def read(session: Session, ctx: schemas.Context) -> Feasibility:
    population = [unit for unit in service.units(session, ctx) if unit.is_active]
    apartments = [unit for unit in population if unit.asset_class == "apartment"]
    lines = service.area_lines(session, [unit.id for unit in population])
    shared = list_areas(session, ctx.project_id)
    scoped = bool(ctx.filters["phase_id"] or ctx.filters["building_id"])
    allocations: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    apartment_ids = {unit.id for unit in apartments}
    for row in shared:
        if row.category == "common" and row.apartment_id is not None:
            allocations[row.apartment_id] += row.area_sqm
    common_rows = [row for row in shared if row.category == "common"]
    common_complete = bool(common_rows) and not any(
        row.area_sqm > 0 and row.apartment_id not in apartment_ids for row in common_rows
    )
    areas = apartment_areas(apartments, lines, allocations, common_complete)
    totals = {key: value for key, value in areas.items() if key != "total"}
    for category in ("common", "garage", "community", "roads_pavements"):
        totals[category] = measure(
            [row.area_sqm for row in shared if row.category == category],
            f"Sum of Inventory Common Areas: {category}; each physical area recorded once",
            "Project-level common areas cannot be allocated to a phase/building filter."
            if scoped
            else None,
        )
    totals["buildable"] = combine(
        totals["internal"],
        totals["common"],
        formula=(
            "Apartment internal covered area + common area; excludes balconies and all open areas"
        ),
    )
    all_covered = measure(
        [sum_components(lines.get(unit.id, []), ("internal", "balcony")) for unit in population],
        "Covered area of all active inventory units, including non-apartments",
    )
    totals["building"] = combine(
        all_covered,
        totals["common"],
        totals["garage"],
        formula=(
            "All active unit covered areas + common area + garage; excludes open "
            "terraces and outdoor site areas"
        ),
    )
    outdoor = measure(
        [
            sum_components(
                lines.get(unit.id, []), ("terrace", "roof_garden", "front_garden", "porches")
            )
            for unit in population
        ],
        "All active units: terrace + roof garden + front garden + porches",
    )
    totals["grand"] = combine(
        totals["building"],
        outdoor,
        totals["community"],
        totals["roads_pavements"],
        formula=(
            "Building area + all private outdoor areas + community area + "
            "roads/pavements; disjoint area components, not land footprint"
        ),
    )
    averages = {}
    average_sources = dict(areas)
    if len(population) == len(apartments) and not scoped:
        average_sources["common"] = totals["common"]
        average_sources["total"] = combine(
            totals["covered"],
            totals["terrace"],
            totals["common"],
            formula="Apartment covered + terrace + project common area (mean, not unit allocation)",
        )
    for key, value in average_sources.items():
        averages[key] = Measure(
            value=value.value / len(apartments) if apartments and value.value is not None else None,
            measured_count=value.measured_count,
            expected_count=value.expected_count,
            reason=value.reason or ("No active apartments." if not apartments else None),
            formula=f"{value.formula}; divided by {len(apartments)} active apartments",
        )
    grouped: dict[tuple[str, int | None], list[Unit]] = defaultdict(list)
    for unit in apartments:
        grouped[(unit.unit_type_code or "Not assigned", unit.bedrooms)].append(unit)
    groups = [
        AreaGroup(
            unit_type=key[0],
            bedrooms=key[1],
            apartments=len(cohort),
            areas=apartment_areas(cohort, lines, allocations, common_complete),
        )
        for key, cohort in sorted(
            grouped.items(), key=lambda item: (item[0][0], -1 if item[0][1] is None else item[0][1])
        )
    ]
    efficiencies = []
    for label, numerator, denominator, formula in (
        (
            "Internal / buildable efficiency",
            totals["internal"],
            totals["buildable"],
            "Apartment internal / (apartment internal + common) * 100",
        ),
        (
            "Covered / buildable ratio",
            totals["covered"],
            totals["buildable"],
            "Apartment covered including balcony / buildable * 100; may exceed 100%",
        ),
        (
            "Covered / building efficiency",
            totals["covered"],
            totals["building"],
            "Apartment covered including balcony / total building * 100",
        ),
        ("Common-area share", totals["common"], totals["buildable"], "Common / buildable * 100"),
        (
            "Balcony share of covered area",
            totals["balcony"],
            totals["covered"],
            "Apartment balcony / apartment covered * 100",
        ),
    ):
        n, d = numerator.value, denominator.value
        efficiencies.append(
            Efficiency(
                label=label,
                numerator=n,
                denominator=d,
                percentage=(n / d * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if n is not None and d is not None and d > 0
                else None,
                formula=formula,
                reason=None
                if n is not None and d is not None and d > 0
                else "Complete numerator and positive denominator are required.",
            )
        )
    notes = [
        (
            "Current active inventory, including unreleased and sold units; "
            "inactive units excluded. Historical observation dates do not "
            "reconstruct area schedules."
        ),
        (
            "All areas shown in m². Supported square-foot measurements convert "
            "at 0.09290304 m²/ft². Missing, duplicate, or unsupported "
            "measurements remain unavailable."
        ),
        (
            "Covered area is a physical sellable-area basis, not a statement of "
            "legal sale eligibility or remaining unsold stock."
        ),
        (
            "Apartment total = covered + terrace + allocated common. It differs "
            "from Inventory Gross, which also includes roof/front gardens and "
            "porches but excludes common areas."
        ),
        (
            "Common Areas must contain disjoint measured areas; do not enter a "
            "project total in addition to its component or apartment allocation "
            "rows. Record zero for a category that does not apply."
        ),
    ]
    if not common_complete:
        notes.append(
            "Allocate all common area to active apartments to enable bedroom breakdowns. "
            "Project averages use common area / apartment count; this does not assign "
            "that average to individual apartments."
        )
    if len(population) != len(apartments):
        totals["buildable"].value = None
        totals[
            "buildable"
        ].reason = (
            "Mixed property classes: project common area is not exclusively apartment common area."
        )
        for ratio in efficiencies[:2] + efficiencies[3:4]:
            ratio.percentage = None
            ratio.denominator = None
            ratio.reason = totals["buildable"].reason
        notes.append(
            "Apartment totals exclude other property classes; building/grand "
            "include every active unit. Apartment buildable efficiency is "
            "unavailable for mixed classes."
        )
    for value in (
        list(totals.values())
        + list(averages.values())
        + [v for group in groups for v in group.areas.values()]
    ):
        if value.value is not None:
            value.value = rounded(value.value)
    return Feasibility(
        context=ctx.model_copy(
            update={
                "source_basis": (
                    "Current approved apartment schedules and Inventory Common Areas measurements"
                )
            }
        ),
        apartments=len(apartments),
        other_units=len(population) - len(apartments),
        totals=totals,
        averages=averages,
        groups=groups,
        efficiencies=efficiencies,
        notes=notes,
    )
