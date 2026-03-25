/**
 * concept-design-types.ts — TypeScript types for the Concept Design domain.
 *
 * Mirrors the backend Pydantic schemas defined in
 * app/modules/concept_design/schemas.py.
 *
 * PR-CONCEPT-055
 */

// ---------------------------------------------------------------------------
// Enums / literals
// ---------------------------------------------------------------------------

export type ConceptOptionStatus = "draft" | "active" | "archived";

// ---------------------------------------------------------------------------
// ConceptOption types
// ---------------------------------------------------------------------------

export interface ConceptOption {
  id: string;
  project_id: string | null;
  scenario_id: string | null;
  name: string;
  status: ConceptOptionStatus;
  description: string | null;
  site_area: number | null;
  gross_floor_area: number | null;
  building_count: number | null;
  floor_count: number | null;
  is_promoted: boolean;
  promoted_at: string | null;
  promoted_project_id: string | null;
  promotion_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConceptOptionListResponse {
  items: ConceptOption[];
  total: number;
}

export interface ConceptOptionCreate {
  project_id?: string | null;
  scenario_id?: string | null;
  name: string;
  status?: ConceptOptionStatus;
  description?: string | null;
  site_area?: number | null;
  gross_floor_area?: number | null;
  building_count?: number | null;
  floor_count?: number | null;
}

export interface ConceptOptionUpdate {
  name?: string;
  status?: ConceptOptionStatus;
  description?: string | null;
  site_area?: number | null;
  gross_floor_area?: number | null;
  building_count?: number | null;
  floor_count?: number | null;
}

// ---------------------------------------------------------------------------
// ConceptUnitMixLine types
// ---------------------------------------------------------------------------

export interface ConceptUnitMixLine {
  id: string;
  concept_option_id: string;
  unit_type: string;
  units_count: number;
  avg_internal_area: number | null;
  avg_sellable_area: number | null;
  mix_percentage: number | null;
  created_at: string;
  updated_at: string;
}

export interface ConceptUnitMixLineCreate {
  unit_type: string;
  units_count: number;
  avg_internal_area?: number | null;
  avg_sellable_area?: number | null;
  mix_percentage?: number | null;
}

// ---------------------------------------------------------------------------
// ConceptOptionSummary — derived metrics from the concept engine
// ---------------------------------------------------------------------------

export interface ConceptOptionSummary {
  concept_option_id: string;
  name: string;
  status: ConceptOptionStatus;
  project_id: string | null;
  scenario_id: string | null;
  site_area: number | null;
  gross_floor_area: number | null;
  building_count: number | null;
  floor_count: number | null;
  unit_count: number;
  sellable_area: number | null;
  efficiency_ratio: number | null;
  average_unit_area: number | null;
  mix_lines: ConceptUnitMixLine[];
}

// ---------------------------------------------------------------------------
// Comparison types — PR-CONCEPT-053
// ---------------------------------------------------------------------------

export interface ConceptOptionComparisonRow {
  concept_option_id: string;
  name: string;
  status: ConceptOptionStatus;
  unit_count: number;
  sellable_area: number | null;
  efficiency_ratio: number | null;
  average_unit_area: number | null;
  building_count: number | null;
  floor_count: number | null;
  sellable_area_delta_vs_best: number | null;
  efficiency_delta_vs_best: number | null;
  unit_count_delta_vs_best: number;
  is_best_sellable_area: boolean;
  is_best_efficiency: boolean;
  is_best_unit_count: boolean;
}

export interface ConceptOptionComparisonResponse {
  comparison_basis: string;
  option_count: number;
  best_sellable_area_option_id: string | null;
  best_efficiency_option_id: string | null;
  best_unit_count_option_id: string | null;
  rows: ConceptOptionComparisonRow[];
}

// ---------------------------------------------------------------------------
// Promotion types — PR-CONCEPT-054
// ---------------------------------------------------------------------------

export interface ConceptPromotionRequest {
  target_project_id?: string | null;
  phase_name?: string | null;
  promotion_notes?: string | null;
}

export interface ConceptPromotionResponse {
  concept_option_id: string;
  promoted_project_id: string;
  promoted_phase_id: string;
  promoted_phase_name: string;
  promoted_at: string;
  promotion_notes: string | null;
}
