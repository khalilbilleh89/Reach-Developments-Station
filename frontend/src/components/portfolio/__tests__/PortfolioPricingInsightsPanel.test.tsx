/**
 * PortfolioPricingInsightsPanel tests
 *
 * Validates:
 *  - empty portfolio renders empty state
 *  - summary KPIs render correctly
 *  - project cards render with all required fields
 *  - top opportunities section renders
 *  - pricing risk zones section renders
 *  - status badges render correctly
 *  - adjustment percentages render correctly
 *  - read-only: no mutation controls
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock CSS modules
jest.mock("@/styles/portfolio.module.css", () => ({
  summaryStrip: "summaryStrip",
  summaryCard: "summaryCard",
  summaryValue: "summaryValue",
  summaryLabel: "summaryLabel",
  varianceProjectCard: "varianceProjectCard",
  varianceCardHeader: "varianceCardHeader",
  varianceProjectList: "varianceProjectList",
  projectName: "projectName",
  projectStats: "projectStats",
  healthBadge: "healthBadge",
  badgeOverrun: "badgeOverrun",
  badgeSaving: "badgeSaving",
  badgeNeutral: "badgeNeutral",
}));

import { PortfolioPricingInsightsPanel } from "@/components/portfolio/PortfolioPricingInsightsPanel";
import type { PortfolioPricingInsightsResponse } from "@/lib/pricing-optimization-types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const makeEmptyResponse = (): PortfolioPricingInsightsResponse => ({
  summary: {
    total_projects: 0,
    projects_with_pricing_data: 0,
    avg_recommended_adjustment_pct: null,
    projects_underpriced: 0,
    projects_overpriced: 0,
    projects_balanced: 0,
  },
  projects: [],
  top_opportunities: [],
  pricing_risk_zones: [],
});

const makeUnderpricedCard = () => ({
  project_id: "proj-1",
  project_name: "Marina Tower",
  pricing_status: "underpriced" as const,
  avg_recommended_adjustment_pct: 6.5,
  recommendation_count: 2,
  high_demand_unit_types: ["studio", "one_bedroom"],
  low_demand_unit_types: [],
});

const makeOverpricedCard = () => ({
  project_id: "proj-2",
  project_name: "Palm Villa",
  pricing_status: "overpriced" as const,
  avg_recommended_adjustment_pct: -5.0,
  recommendation_count: 1,
  high_demand_unit_types: [],
  low_demand_unit_types: ["three_bedroom"],
});

const makeBalancedCard = () => ({
  project_id: "proj-3",
  project_name: "City Walk",
  pricing_status: "balanced" as const,
  avg_recommended_adjustment_pct: 0.0,
  recommendation_count: 0,
  high_demand_unit_types: [],
  low_demand_unit_types: [],
});

const makeFullResponse = (): PortfolioPricingInsightsResponse => ({
  summary: {
    total_projects: 3,
    projects_with_pricing_data: 3,
    avg_recommended_adjustment_pct: 1.5,
    projects_underpriced: 1,
    projects_overpriced: 1,
    projects_balanced: 1,
  },
  projects: [makeUnderpricedCard(), makeBalancedCard(), makeOverpricedCard()],
  top_opportunities: [makeUnderpricedCard()],
  pricing_risk_zones: [makeOverpricedCard()],
});

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

test("renders empty state when no projects", () => {
  render(<PortfolioPricingInsightsPanel data={makeEmptyResponse()} />);
  expect(screen.getByTestId("pricing-empty-state")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Panel structure
// ---------------------------------------------------------------------------

test("renders panel when projects exist", () => {
  render(<PortfolioPricingInsightsPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("portfolio-pricing-panel")).toBeInTheDocument();
});

test("renders summary KPIs", () => {
  render(<PortfolioPricingInsightsPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("pricing-total-projects")).toHaveTextContent("3");
  expect(screen.getByTestId("pricing-underpriced-count")).toHaveTextContent("1");
  expect(screen.getByTestId("pricing-overpriced-count")).toHaveTextContent("1");
  expect(screen.getByTestId("pricing-avg-adj")).toHaveTextContent("+1.5%");
});

test("renders top opportunities section when present", () => {
  render(<PortfolioPricingInsightsPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("top-opportunities")).toBeInTheDocument();
});

test("renders pricing risk zones section when present", () => {
  render(<PortfolioPricingInsightsPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("pricing-risk-zones")).toBeInTheDocument();
});

test("renders all projects section", () => {
  render(<PortfolioPricingInsightsPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("all-pricing-projects")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Project card fields
// ---------------------------------------------------------------------------

test("renders project cards with names", () => {
  render(<PortfolioPricingInsightsPanel data={makeFullResponse()} />);
  expect(screen.getAllByText("Marina Tower").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Palm Villa").length).toBeGreaterThan(0);
});

test("renders adjustment percentages with sign", () => {
  render(<PortfolioPricingInsightsPanel data={makeFullResponse()} />);
  // +6.5% for underpriced project
  expect(screen.getAllByText("+6.5% avg adj.").length).toBeGreaterThan(0);
  // -5.0% for overpriced project
  expect(screen.getAllByText("-5.0% avg adj.").length).toBeGreaterThan(0);
});

test("renders null avg adjustment as dash", () => {
  const resp: PortfolioPricingInsightsResponse = {
    ...makeEmptyResponse(),
    projects: [
      {
        project_id: "proj-null",
        project_name: "No Data Project",
        pricing_status: "no_data",
        avg_recommended_adjustment_pct: null,
        recommendation_count: 0,
        high_demand_unit_types: [],
        low_demand_unit_types: [],
      },
    ],
    summary: {
      total_projects: 1,
      projects_with_pricing_data: 0,
      avg_recommended_adjustment_pct: null,
      projects_underpriced: 0,
      projects_overpriced: 0,
      projects_balanced: 0,
    },
  };
  render(<PortfolioPricingInsightsPanel data={resp} />);
  expect(screen.getByTestId("pricing-avg-adj")).toHaveTextContent("—");
});

// ---------------------------------------------------------------------------
// Read-only
// ---------------------------------------------------------------------------

test("renders no mutation controls (read-only panel)", () => {
  const { container } = render(
    <PortfolioPricingInsightsPanel data={makeFullResponse()} />,
  );
  const buttons = container.querySelectorAll("button");
  const inputs = container.querySelectorAll("input");
  expect(buttons).toHaveLength(0);
  expect(inputs).toHaveLength(0);
});
