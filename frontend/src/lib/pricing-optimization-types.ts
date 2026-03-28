/**
 * pricing-optimization-types.ts — TypeScript types for the Pricing
 * Optimization Engine endpoints (PR-V7-02).
 *
 * Backend endpoints:
 *   GET /api/v1/projects/{id}/pricing-recommendations
 *   GET /api/v1/portfolio/pricing-insights
 */

// ---------------------------------------------------------------------------
// Project-level pricing recommendations
// ---------------------------------------------------------------------------

export interface UnitTypePricingRecommendation {
  unit_type: string;
  current_avg_price: number | null;
  recommended_price: number | null;
  change_pct: number | null;
  confidence: "high" | "medium" | "low" | "insufficient_data";
  reason: string;
  demand_status: "high_demand" | "balanced" | "low_demand" | "no_data";
  total_units: number;
  available_units: number;
  sold_units: number;
  availability_pct: number | null;
}

export interface ProjectPricingRecommendationsResponse {
  project_id: string;
  project_name: string;
  recommendations: UnitTypePricingRecommendation[];
  has_pricing_data: boolean;
  demand_context: string | null;
}

// ---------------------------------------------------------------------------
// Portfolio pricing insights
// ---------------------------------------------------------------------------

export interface PortfolioPricingProjectCard {
  project_id: string;
  project_name: string;
  pricing_status: "underpriced" | "overpriced" | "balanced" | "no_data";
  avg_recommended_adjustment_pct: number | null;
  recommendation_count: number;
  high_demand_unit_types: string[];
  low_demand_unit_types: string[];
}

export interface PortfolioPricingInsightsSummary {
  total_projects: number;
  projects_with_pricing_data: number;
  avg_recommended_adjustment_pct: number | null;
  projects_underpriced: number;
  projects_overpriced: number;
  projects_balanced: number;
}

export interface PortfolioPricingInsightsResponse {
  summary: PortfolioPricingInsightsSummary;
  projects: PortfolioPricingProjectCard[];
  top_opportunities: PortfolioPricingProjectCard[];
  pricing_risk_zones: PortfolioPricingProjectCard[];
}
