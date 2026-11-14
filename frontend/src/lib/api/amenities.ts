export type AmenityContext = {
  applicability?: "whole_project" | "selected" | null;
  blocks?: string; units?: string; supporting_url?: string | null;
  status?: "planned" | "under_construction" | "available" | null;
};
export type PoolEntry = {
  id: string; name?: string; pool_type?: "main" | "children" | null;
  setting?: "indoor" | "outdoor" | null;
  length_m?: string | null; width_m?: string | null; area_sqm?: string | null;
  min_depth_m?: string | null; max_depth_m?: string | null;
  location?: string; access?: string; heating?: boolean | null;
  step_free_entry?: boolean | null; shallow_area?: boolean | null; sun_deck?: boolean | null;
  status?: AmenityContext["status"];
};
export type BalconyEntry = {
  id: string; unit_type?: string; area_sqm?: string | null;
  min_area_sqm?: string | null; max_area_sqm?: string | null;
  overlooks?: string; blocks?: string; units?: string;
};
export type AmenityDetails = {
  swimming_pools?: AmenityContext & { pools?: PoolEntry[] };
  gym?: AmenityContext & { area_sqm?: string | null; location?: string; equipment?: string; access?: string };
  garden?: AmenityContext & { shared_garden?: boolean | null; garden_view?: boolean | null; area_sqm?: string | null; facilities?: string; access?: string; view_blocks?: string; view_units?: string };
  energy?: AmenityContext & { features?: string; rating?: string; certificate_url?: string | null };
  play_area?: AmenityContext & { area_sqm?: string | null; location?: string; setting?: "indoor" | "outdoor" | null; min_age?: number | null; max_age?: number | null; equipment?: string; shade?: string };
  balconies?: AmenityContext & { balconies?: BalconyEntry[] };
  parking?: AmenityContext & { total_spaces?: number | null; spaces_per_unit?: number | null; covered_spaces?: number | null; uncovered_spaces?: number | null; visitor_spaces?: number | null; ev_charging?: "available" | "planned" | "unavailable" | null; ev_notes?: string };
};
export type AmenityKey = keyof AmenityDetails;
