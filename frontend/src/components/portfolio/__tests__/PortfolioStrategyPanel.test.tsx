/**
 * PortfolioStrategyPanel tests (PR-V7-05)
 *
 * Validates:
 *  - empty portfolio renders empty state
 *  - summary KPIs render correctly
 *  - project cards render with all required fields
 *  - top strategies section renders
 *  - intervention required section renders
 *  - risk score badges render correctly for low / medium / high
 *  - best IRR renders for each card
 *  - reason text renders on cards
 *  - read-only: no mutation controls
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock CSS modules
jest.mock("@/styles/portfolio.module.css", () => ({
  summaryStrip: "summaryStrip",
  kpiCard: "kpiCard",
  kpiValue: "kpiValue",
  kpiLabel: "kpiLabel",
  varianceProjectCard: "varianceProjectCard",
  varianceCardHeader: "varianceCardHeader",
  varianceCardGrid: "varianceCardGrid",
  projectName: "projectName",
  projectStats: "projectStats",
  healthBadge: "healthBadge",
  badgeOverrun: "badgeOverrun",
  badgeSaving: "badgeSaving",
  badgeNeutral: "badgeNeutral",
}));

import { PortfolioStrategyPanel } from "@/components/portfolio/PortfolioStrategyPanel";
import type { PortfolioStrategyInsightsResponse } from "@/lib/strategy-types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const makeEmptyResponse = (): PortfolioStrategyInsightsResponse => ({
  summary: {
    total_projects: 0,
    projects_with_baseline: 0,
    projects_high_risk: 0,
    projects_low_risk: 0,
  },
  projects: [],
  top_strategies: [],
  intervention_required: [],
});

const makeLowRiskCard = () => ({
  project_id: "proj-1",
  project_name: "Marina Tower",
  has_feasibility_baseline: true,
  best_irr: 0.21,
  best_risk_score: "low" as const,
  best_release_strategy: "accelerate" as const,
  best_price_adjustment_pct: 8.0,
  best_phase_delay_months: 0,
  reason: "Best strategy: accelerate release with +8% price.",
});

const makeHighRiskCard = () => ({
  project_id: "proj-2",
  project_name: "Palm Villa",
  has_feasibility_baseline: true,
  best_irr: 0.12,
  best_risk_score: "high" as const,
  best_release_strategy: "hold" as const,
  best_price_adjustment_pct: -5.0,
  best_phase_delay_months: 6,
  reason: "Best strategy: hold release with -5% price.",
});

const makeMediumRiskCard = () => ({
  project_id: "proj-3",
  project_name: "City Walk",
  has_feasibility_baseline: false,
  best_irr: 0.16,
  best_risk_score: "medium" as const,
  best_release_strategy: "maintain" as const,
  best_price_adjustment_pct: 0.0,
  best_phase_delay_months: 0,
  reason: "Best strategy: maintain release with no price change.",
});

const makeFullResponse = (): PortfolioStrategyInsightsResponse => ({
  summary: {
    total_projects: 3,
    projects_with_baseline: 2,
    projects_high_risk: 1,
    projects_low_risk: 1,
  },
  projects: [makeLowRiskCard(), makeMediumRiskCard(), makeHighRiskCard()],
  top_strategies: [makeLowRiskCard()],
  intervention_required: [makeHighRiskCard()],
});

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

test("renders empty state when no projects", () => {
  render(<PortfolioStrategyPanel data={makeEmptyResponse()} />);
  expect(screen.getByTestId("portfolio-strategy-panel")).toBeInTheDocument();
  expect(screen.getByTestId("strategy-empty-state")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Summary KPIs
// ---------------------------------------------------------------------------

test("renders summary KPI strip with correct values", () => {
  render(<PortfolioStrategyPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("strategy-summary-strip")).toBeInTheDocument();
  expect(screen.getByTestId("strategy-total-projects")).toHaveTextContent("3");
  expect(screen.getByTestId("strategy-with-baseline")).toHaveTextContent("2");
  expect(screen.getByTestId("strategy-high-risk")).toHaveTextContent("1");
  expect(screen.getByTestId("strategy-low-risk")).toHaveTextContent("1");
});

// ---------------------------------------------------------------------------
// Project cards
// ---------------------------------------------------------------------------

test("renders project cards for all projects", () => {
  render(<PortfolioStrategyPanel data={makeFullResponse()} />);
  expect(screen.getAllByTestId("strategy-card-proj-1").length).toBeGreaterThanOrEqual(1);
  expect(screen.getAllByTestId("strategy-card-proj-2").length).toBeGreaterThanOrEqual(1);
  expect(screen.getAllByTestId("strategy-card-proj-3").length).toBeGreaterThanOrEqual(1);
});

test("renders best IRR on project card", () => {
  render(<PortfolioStrategyPanel data={makeFullResponse()} />);
  const irrElements = screen.getAllByTestId("best-irr-proj-1");
  expect(irrElements.length).toBeGreaterThanOrEqual(1);
  expect(irrElements[0]).toHaveTextContent("21.00%");
});

test("renders risk badge on project card", () => {
  render(<PortfolioStrategyPanel data={makeFullResponse()} />);
  const lowBadges = screen.getAllByTestId("risk-badge-proj-1");
  expect(lowBadges[0]).toHaveTextContent("Low Risk");
  const highBadges = screen.getAllByTestId("risk-badge-proj-2");
  expect(highBadges[0]).toHaveTextContent("High Risk");
  const medBadges = screen.getAllByTestId("risk-badge-proj-3");
  expect(medBadges[0]).toHaveTextContent("Medium Risk");
});

test("renders reason text on project card", () => {
  render(<PortfolioStrategyPanel data={makeFullResponse()} />);
  const reasonElements = screen.getAllByTestId("strategy-reason-proj-1");
  expect(reasonElements.length).toBeGreaterThanOrEqual(1);
  expect(reasonElements[0]).toHaveTextContent(
    "Best strategy: accelerate release with +8% price.",
  );
});

// ---------------------------------------------------------------------------
// Top strategies section
// ---------------------------------------------------------------------------

test("renders top strategies section when top_strategies is non-empty", () => {
  render(<PortfolioStrategyPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("top-strategies-section")).toBeInTheDocument();
});

test("does not render top strategies section when empty", () => {
  const data = { ...makeFullResponse(), top_strategies: [] };
  render(<PortfolioStrategyPanel data={data} />);
  expect(screen.queryByTestId("top-strategies-section")).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Intervention required section
// ---------------------------------------------------------------------------

test("renders intervention required section when non-empty", () => {
  render(<PortfolioStrategyPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("intervention-required-section")).toBeInTheDocument();
});

test("does not render intervention required section when empty", () => {
  const data = { ...makeFullResponse(), intervention_required: [] };
  render(<PortfolioStrategyPanel data={data} />);
  expect(
    screen.queryByTestId("intervention-required-section"),
  ).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// All projects section
// ---------------------------------------------------------------------------

test("renders all projects section", () => {
  render(<PortfolioStrategyPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("all-strategy-projects")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Read-only: no mutation controls
// ---------------------------------------------------------------------------

test("renders no buttons that would mutate data", () => {
  render(<PortfolioStrategyPanel data={makeFullResponse()} />);
  // Ensure no submit/save/apply buttons exist
  const buttons = screen.queryAllByRole("button");
  expect(buttons.length).toBe(0);
});
