/**
 * feasibility-decision-display.ts
 *
 * Shared display-mapping helpers for feasibility decision fields.
 *
 * Centralizes the human-readable labels used by:
 *  - FeasibilityDecisionSummary (investment decision block)
 *  - FeasibilityRunDetailView results banner
 *
 * All functions are pure — no side-effects, no React imports.
 *
 * PR-FEAS-08
 */

import type {
  FeasibilityDecision,
  FeasibilityRiskLevel,
  FeasibilityViabilityStatus,
} from "@/lib/feasibility-types";

/**
 * Maps a backend FeasibilityDecision value to its human-readable action label.
 *
 * Canonical labels:
 *  VIABLE      → "Proceed"
 *  MARGINAL    → "Review"
 *  NOT_VIABLE  → "Do Not Proceed"
 *  null        → "—"
 */
export function decisionLabel(decision: FeasibilityDecision | null): string {
  if (decision === "VIABLE") return "Proceed";
  if (decision === "MARGINAL") return "Review";
  if (decision === "NOT_VIABLE") return "Do Not Proceed";
  return "—";
}

/**
 * Maps a backend FeasibilityViabilityStatus value to its display label.
 *
 * VIABLE      → "Viable"
 * MARGINAL    → "Marginal"
 * NOT_VIABLE  → "Not Viable"
 * null        → "—"
 */
export function viabilityLabel(
  status: FeasibilityViabilityStatus | null,
): string {
  if (status === "VIABLE") return "Viable";
  if (status === "MARGINAL") return "Marginal";
  if (status === "NOT_VIABLE") return "Not Viable";
  return "—";
}

/**
 * Maps a backend FeasibilityRiskLevel value to its display label.
 *
 * LOW    → "Low"
 * MEDIUM → "Moderate"
 * HIGH   → "High"
 * null   → "—"
 */
export function riskLabel(risk: FeasibilityRiskLevel | null): string {
  if (risk === "LOW") return "Low";
  if (risk === "MEDIUM") return "Moderate";
  if (risk === "HIGH") return "High";
  return "—";
}
