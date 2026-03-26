/**
 * feasibility-scenario-outputs.ts — normalizer for the scenario_outputs field
 * returned by the backend FeasibilityResult.
 *
 * Converts the raw backend JSON blob to the typed FeasibilityScenarioOutputs
 * display model safely, handling null, missing scenarios, and missing metrics
 * without throwing.
 *
 * PR-FEAS-07 — Feasibility Scenario Outputs Typed Display
 */

import type {
  FeasibilityScenarioMetrics,
  FeasibilityScenarioOutputs,
} from "@/lib/feasibility-types";

/** Scenario names produced by the backend scenario runner. */
const SCENARIO_KEYS = ["base", "upside", "downside", "investor"] as const;

/** Metric field names produced by `_outputs_to_dict` in scenario_runner.py. */
const METRIC_KEYS: (keyof FeasibilityScenarioMetrics)[] = [
  "gdv",
  "construction_cost",
  "soft_cost",
  "finance_cost",
  "sales_cost",
  "total_cost",
  "developer_profit",
  "profit_margin",
  "irr_estimate",
];

/**
 * Safely coerce a value to `number | null`.
 * Returns null for anything that is not a finite number.
 */
function toNumberOrNull(value: unknown): number | null {
  if (typeof value === "number" && isFinite(value)) return value;
  return null;
}

/**
 * Normalize a single scenario blob into a typed FeasibilityScenarioMetrics.
 * Always returns a valid object — missing or non-numeric fields become null.
 */
function normalizeMetrics(raw: unknown): FeasibilityScenarioMetrics {
  const src = raw != null && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const result = {} as FeasibilityScenarioMetrics;
  for (const key of METRIC_KEYS) {
    result[key] = toNumberOrNull(src[key]);
  }
  return result;
}

/**
 * Normalize the raw `scenario_outputs` payload from the backend into a typed
 * `FeasibilityScenarioOutputs` object.
 *
 * @param raw - The raw `scenario_outputs` value from FeasibilityResult.
 * @returns A typed object containing only recognized scenarios present in the
 *          payload, where each included scenario has missing or non-numeric
 *          metric fields coerced to null; returns null when the payload is
 *          itself null, non-object, an array, or when no recognized scenarios
 *          are found.
 */
export function normalizeFeasibilityScenarioOutputs(
  raw: unknown,
): FeasibilityScenarioOutputs | null {
  if (raw == null || typeof raw !== "object" || Array.isArray(raw)) {
    return null;
  }

  const src = raw as Record<string, unknown>;
  const result: FeasibilityScenarioOutputs = {};

  for (const key of SCENARIO_KEYS) {
    if (Object.prototype.hasOwnProperty.call(src, key)) {
      result[key] = normalizeMetrics(src[key]);
    }
  }

  // Return null if no known scenario keys were found at all
  if (Object.keys(result).length === 0) {
    return null;
  }

  return result;
}
