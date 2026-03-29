/**
 * portfolio-auto-strategy-types.ts — TypeScript types for the Portfolio
 * Auto-Strategy & Intervention Prioritization endpoints (PR-V7-06).
 *
 * Backend endpoint:
 *   GET /api/v1/portfolio/auto-strategy
 */

// ---------------------------------------------------------------------------
// Intervention classification literals
// ---------------------------------------------------------------------------

export type InterventionPriority =
  | "urgent_intervention"
  | "recommended_intervention"
  | "monitor_closely"
  | "stable"
  | "insufficient_data";

export type InterventionType =
  | "pricing_intervention"
  | "phasing_intervention"
  | "mixed_intervention"
  | "monitor_only"
  | "insufficient_data";

// ---------------------------------------------------------------------------
// Per-project intervention card
// ---------------------------------------------------------------------------

export interface PortfolioInterventionProjectCard {
  project_id: string;
  project_name: string;
  has_feasibility_baseline: boolean;
  recommended_strategy: "hold" | "maintain" | "accelerate" | null;
  best_irr: number | null;
  irr_delta: number | null;
  risk_score: "low" | "medium" | "high" | null;
  intervention_priority: InterventionPriority;
  intervention_type: InterventionType;
  urgency_score: number;
  reason: string;
}

// ---------------------------------------------------------------------------
// Top-action item (lightweight)
// ---------------------------------------------------------------------------

export interface PortfolioTopActionItem {
  project_id: string;
  project_name: string;
  intervention_priority: InterventionPriority;
  intervention_type: InterventionType;
  urgency_score: number;
  reason: string;
}

// ---------------------------------------------------------------------------
// Portfolio summary KPIs
// ---------------------------------------------------------------------------

export interface PortfolioInterventionSummary {
  total_projects: number;
  analyzed_projects: number;
  projects_with_baseline: number;
  urgent_intervention_count: number;
  monitor_only_count: number;
  no_data_count: number;
}

// ---------------------------------------------------------------------------
// Canonical response envelope
// ---------------------------------------------------------------------------

export interface PortfolioAutoStrategyResponse {
  summary: PortfolioInterventionSummary;
  top_actions: PortfolioTopActionItem[];
  top_risk_projects: PortfolioInterventionProjectCard[];
  top_upside_projects: PortfolioInterventionProjectCard[];
  project_cards: PortfolioInterventionProjectCard[];
}
