/**
 * scenario-types.ts — TypeScript types for the Scenario Engine module.
 *
 * Mirrors the Pydantic schemas in app/modules/scenario/schemas.py.
 */

// ---------------------------------------------------------------------------
// Scenario
// ---------------------------------------------------------------------------

export type ScenarioStatus = "draft" | "approved" | "archived";

export interface Scenario {
  id: string;
  name: string;
  code: string | null;
  status: ScenarioStatus;
  source_type: string;
  project_id: string | null;
  land_id: string | null;
  base_scenario_id: string | null;
  is_active: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScenarioList {
  items: Scenario[];
  total: number;
}

export interface ScenarioCreate {
  name: string;
  code?: string | null;
  source_type?: string;
  project_id?: string | null;
  land_id?: string | null;
  notes?: string | null;
}

export interface ScenarioUpdate {
  name?: string;
  code?: string | null;
  notes?: string | null;
}

export interface ScenarioDuplicateRequest {
  name: string;
  code?: string | null;
  notes?: string | null;
}

// ---------------------------------------------------------------------------
// Scenario Version
// ---------------------------------------------------------------------------

export interface ScenarioVersion {
  id: string;
  scenario_id: string;
  version_number: number;
  title: string | null;
  notes: string | null;
  assumptions_json: Record<string, unknown> | null;
  comparison_metrics_json: Record<string, unknown> | null;
  created_by: string | null;
  is_approved: boolean;
  created_at: string;
  updated_at: string;
}

export interface ScenarioVersionList {
  items: ScenarioVersion[];
  total: number;
}

// ---------------------------------------------------------------------------
// Comparison
// ---------------------------------------------------------------------------

export interface ScenarioCompareRequest {
  scenario_ids: string[];
}

export interface ScenarioCompareItem {
  scenario_id: string;
  scenario_name: string;
  status: ScenarioStatus;
  latest_version_number: number | null;
  assumptions_json: Record<string, unknown> | null;
  comparison_metrics_json: Record<string, unknown> | null;
}

export interface ScenarioCompareResponse {
  scenarios: ScenarioCompareItem[];
}

// ---------------------------------------------------------------------------
// Financial Scenario Runs
// ---------------------------------------------------------------------------

/** A persisted financial scenario run produced by the Financial Scenario Engine. */
export interface FinancialScenarioRun {
  id: string;
  scenario_id: string;
  label: string;
  notes: string | null;
  is_baseline: boolean;
  assumptions_json: Record<string, unknown> | null;
  results_json: Record<string, unknown> | null;
  irr: number | null;
  npv: number | null;
  roi: number | null;
  developer_margin: number | null;
  gross_profit: number | null;
  /** ISO 4217 currency code for monetary outputs (npv, gross_profit). */
  currency: string;
  created_at: string;
  updated_at: string;
}

export interface FinancialScenarioRunList {
  items: FinancialScenarioRun[];
  total: number;
}
