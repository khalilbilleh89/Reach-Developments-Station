import type { AmenityKey } from "@/lib/api/amenities";

export const AMENITIES: { key: AmenityKey; name: string }[] = [
  { key: "swimming_pools", name: "Swimming Pools" },
  { key: "gym", name: "Garden View Gym" },
  { key: "garden", name: "Tropical Garden View" },
  { key: "energy", name: "Energy-Efficient Project" },
  { key: "play_area", name: "Kid's Play Area" },
  { key: "balconies", name: "Balconies With Premium View" },
  { key: "parking", name: "Dedicated Parking Lots" },
];
export type AmenityField = { key: string; label: string; kind?: "decimal" | "count" | "choice" | "boolean" | "url"; options?: { value: string; label: string }[]; when?: string };
const choice = (key: string, label: string, options: string[][]): AmenityField => ({ key, label, kind: "choice", options: options.map(([value, label]) => ({ value, label })) });
const measure = (key: string, label: string): AmenityField => ({ key, label, kind: "decimal" });
const setting = choice("setting", "Setting", [["indoor", "Indoor"], ["outdoor", "Outdoor"]]);
export const STATUS = choice("status", "Facility status", [["planned", "Planned"], ["under_construction", "Under construction"], ["available", "Available for use"]]);
export const COMMON: AmenityField[] = [
  choice("applicability", "Applies to", [["whole_project", "Whole project"], ["selected", "Selected blocks or units"]]),
  { key: "blocks", label: "Selected blocks", when: "selected" },
  { key: "units", label: "Selected units", when: "selected" },
  { key: "supporting_url", label: "Supporting drawing or document link", kind: "url" },
];
export const POOL_FIELDS: AmenityField[] = [
  { key: "name", label: "Pool name" }, choice("pool_type", "Pool type", [["main", "Main"], ["children", "Children’s"]]), setting,
  measure("length_m", "Length (m)"), measure("width_m", "Width (m)"), measure("area_sqm", "Surface area (m²)"),
  measure("min_depth_m", "Minimum depth (m)"), measure("max_depth_m", "Maximum depth (m)"),
  { key: "location", label: "Location" }, { key: "access", label: "Who can use it" },
  ...[["heating", "Heating"], ["step_free_entry", "Step-free entry"], ["shallow_area", "Shallow area"], ["sun_deck", "Sun deck"]].map(([key, label]): AmenityField => ({ key, label, kind: "boolean" })), STATUS,
];
export const BALCONY_FIELDS: AmenityField[] = [
  { key: "unit_type", label: "Unit type or entry name" }, measure("area_sqm", "Balcony size (m²)"),
  measure("min_area_sqm", "Minimum balcony size (m²)"), measure("max_area_sqm", "Maximum balcony size (m²)"),
  { key: "overlooks", label: "What it overlooks" }, { key: "blocks", label: "Blocks with this view" }, { key: "units", label: "Units with this view" },
];
export const FIELDS: Record<AmenityKey, AmenityField[]> = {
  swimming_pools: [],
  gym: [measure("area_sqm", "Floor area (m²)"), { key: "location", label: "Location" }, { key: "equipment", label: "Available equipment" }, { key: "access", label: "Who can use it" }],
  garden: [
    { key: "shared_garden", label: "Shared garden", kind: "boolean" }, { key: "garden_view", label: "Garden view from selected units", kind: "boolean" },
    { ...measure("area_sqm", "Shared garden area (m²)"), when: "shared_garden" },
    { key: "facilities", label: "Shared garden facilities", when: "shared_garden" }, { key: "access", label: "Who can use the shared garden", when: "shared_garden" },
    { key: "view_blocks", label: "Blocks with a garden view", when: "garden_view" }, { key: "view_units", label: "Units with a garden view", when: "garden_view" },
  ],
  energy: [{ key: "features", label: "Energy-saving features" }, { key: "rating", label: "Documented energy rating" }, { key: "certificate_url", label: "Supporting certificate or specification link", kind: "url" }],
  play_area: [measure("area_sqm", "Area (m²)"), { key: "location", label: "Location" }, setting, { key: "min_age", label: "Minimum age (years)", kind: "count" }, { key: "max_age", label: "Maximum age (years)", kind: "count" }, { key: "equipment", label: "Play equipment" }, { key: "shade", label: "Shade" }],
  balconies: [],
  parking: [
    ...[["total_spaces", "Total parking spaces"], ["spaces_per_unit", "Spaces allocated per unit"], ["covered_spaces", "Covered spaces"], ["uncovered_spaces", "Uncovered spaces"], ["visitor_spaces", "Visitor spaces"]].map(([key, label]): AmenityField => ({ key, label, kind: "count" })),
    choice("ev_charging", "EV charging availability", [["available", "Available"], ["planned", "Planned"], ["unavailable", "Unavailable"]]), { key: "ev_notes", label: "EV charging details" },
  ],
};
export function visible(field: AmenityField, record: Record<string, unknown>) {
  return !field.when || (field.when === "selected" ? record.applicability === "selected" : record[field.when] === true);
}
export function recorded(value: unknown) { return value !== null && value !== undefined && value !== ""; }
export function fieldText(field: AmenityField, value: unknown): string {
  if (!recorded(value)) return "Not recorded";
  if (field.kind === "boolean") return value ? "Yes" : "No";
  return field.options?.find(option => option.value === value)?.label ?? String(value);
}
