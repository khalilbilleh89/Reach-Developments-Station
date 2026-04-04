/**
 * PortfolioAutoStrategyPanel tests (PR-V7-06)
 *
 * Validates:
 *  - empty portfolio renders empty state
 *  - summary KPIs render correctly
 *  - project intervention cards render with all required fields
 *  - top actions section renders
 *  - top risk section renders
 *  - top upside section renders
 *  - intervention priority badges render correctly
 *  - urgency score renders on cards
 *  - reason text renders on cards
 *  - best IRR renders on cards
 *  - read-only: no mutation controls
 *  - all-projects section renders
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
  badgeNeedsAttention: "badgeNeedsAttention",
}));

import { PortfolioAutoStrategyPanel } from "@/components/portfolio/PortfolioAutoStrategyPanel";
import type { PortfolioAutoStrategyResponse } from "@/lib/portfolio-auto-strategy-types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const makeEmptyResponse = (): PortfolioAutoStrategyResponse => ({
  summary: {
    total_projects: 0,
    analyzed_projects: 0,
    projects_with_baseline: 0,
    urgent_intervention_count: 0,
    monitor_only_count: 0,
    no_data_count: 0,
  },
  top_actions: [],
  top_risk_projects: [],
  top_upside_projects: [],
  project_cards: [],
});

const makeUrgentCard = () => ({
  project_id: "proj-1",
  project_name: "Marina Tower",
  has_feasibility_baseline: false,
  recommended_strategy: "hold" as const,
  best_irr: 0.11,
  irr_delta: null,
  risk_score: "high" as const,
  intervention_priority: "urgent_intervention" as const,
  intervention_type: "pricing_intervention" as const,
  urgency_score: 75,
  reason: "Urgent intervention for Marina Tower. Intervention type: Pricing intervention.",
});

const makeStableCard = () => ({
  project_id: "proj-2",
  project_name: "Palm Villa",
  has_feasibility_baseline: true,
  recommended_strategy: "accelerate" as const,
  best_irr: 0.22,
  irr_delta: null,
  risk_score: "low" as const,
  intervention_priority: "stable" as const,
  intervention_type: "monitor_only" as const,
  urgency_score: 10,
  reason: "Stable for Palm Villa. No immediate action required.",
});

const makeNoDataCard = () => ({
  project_id: "proj-3",
  project_name: "City Walk",
  has_feasibility_baseline: false,
  recommended_strategy: null,
  best_irr: null,
  irr_delta: null,
  risk_score: null,
  intervention_priority: "insufficient_data" as const,
  intervention_type: "insufficient_data" as const,
  urgency_score: 0,
  reason: "Insufficient data for City Walk.",
});

const makeRecommendedCard = () => ({
  project_id: "proj-4",
  project_name: "Downtown Hub",
  has_feasibility_baseline: true,
  recommended_strategy: "maintain" as const,
  best_irr: 0.18,
  irr_delta: null,
  risk_score: "medium" as const,
  intervention_priority: "recommended_intervention" as const,
  intervention_type: "phasing_intervention" as const,
  urgency_score: 45,
  reason: "Recommended intervention for Downtown Hub.",
});

const makeFullResponse = (): PortfolioAutoStrategyResponse => ({
  summary: {
    total_projects: 3,
    analyzed_projects: 2,
    projects_with_baseline: 1,
    urgent_intervention_count: 1,
    monitor_only_count: 1,
    no_data_count: 1,
  },
  top_actions: [
    {
      project_id: "proj-1",
      project_name: "Marina Tower",
      intervention_priority: "urgent_intervention",
      intervention_type: "pricing_intervention",
      urgency_score: 75,
      reason: "Urgent intervention for Marina Tower.",
    },
  ],
  top_risk_projects: [makeUrgentCard()],
  top_upside_projects: [makeStableCard()],
  project_cards: [makeUrgentCard(), makeStableCard(), makeNoDataCard()],
});

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

test("renders empty state when no projects", () => {
  render(<PortfolioAutoStrategyPanel data={makeEmptyResponse()} />);
  expect(screen.getByTestId("portfolio-auto-strategy-panel")).toBeInTheDocument();
  expect(screen.getByTestId("auto-strategy-empty-state")).toBeInTheDocument();
});

test("does not render summary strip when empty", () => {
  render(<PortfolioAutoStrategyPanel data={makeEmptyResponse()} />);
  expect(screen.queryByTestId("auto-strategy-summary-strip")).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Summary KPIs
// ---------------------------------------------------------------------------

test("renders summary KPI strip with correct values", () => {
  render(<PortfolioAutoStrategyPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("auto-strategy-summary-strip")).toBeInTheDocument();
  expect(screen.getByTestId("auto-strategy-total-projects")).toHaveTextContent("3");
  expect(screen.getByTestId("auto-strategy-analyzed")).toHaveTextContent("2");
  expect(screen.getByTestId("auto-strategy-urgent")).toHaveTextContent("1");
  expect(screen.getByTestId("auto-strategy-monitor")).toHaveTextContent("1");
  expect(screen.getByTestId("auto-strategy-no-data")).toHaveTextContent("1");
});

// ---------------------------------------------------------------------------
// Project cards
// ---------------------------------------------------------------------------

test("renders project cards for all projects", () => {
  render(<PortfolioAutoStrategyPanel data={makeFullResponse()} />);
  expect(screen.getAllByTestId("auto-strategy-card-proj-1").length).toBeGreaterThanOrEqual(1);
  expect(screen.getAllByTestId("auto-strategy-card-proj-2").length).toBeGreaterThanOrEqual(1);
  expect(screen.getAllByTestId("auto-strategy-card-proj-3").length).toBeGreaterThanOrEqual(1);
});

test("renders best IRR on project card", () => {
  render(<PortfolioAutoStrategyPanel data={makeFullResponse()} />);
  const irrElements = screen.getAllByTestId("auto-strategy-irr-proj-1");
  expect(irrElements.length).toBeGreaterThanOrEqual(1);
  expect(irrElements[0]).toHaveTextContent("11.00%");
});

test("renders dash for null IRR on no-data card", () => {
  render(<PortfolioAutoStrategyPanel data={makeFullResponse()} />);
  const irrElements = screen.getAllByTestId("auto-strategy-irr-proj-3");
  expect(irrElements.length).toBeGreaterThanOrEqual(1);
  expect(irrElements[0]).toHaveTextContent("—");
});

test("renders urgency score on project card", () => {
  render(<PortfolioAutoStrategyPanel data={makeFullResponse()} />);
  const urgencyElements = screen.getAllByTestId("urgency-score-proj-1");
  expect(urgencyElements[0]).toHaveTextContent("75");
});

test("renders reason text on project card", () => {
  render(<PortfolioAutoStrategyPanel data={makeFullResponse()} />);
  const reasonElements = screen.getAllByTestId("auto-strategy-reason-proj-1");
  expect(reasonElements.length).toBeGreaterThanOrEqual(1);
  expect(reasonElements[0]).toHaveTextContent("Urgent intervention for Marina Tower");
});

// ---------------------------------------------------------------------------
// Priority badges
// ---------------------------------------------------------------------------

test("renders urgent priority badge", () => {
  render(<PortfolioAutoStrategyPanel data={makeFullResponse()} />);
  const badges = screen.getAllByTestId("priority-badge-proj-1");
  expect(badges[0]).toHaveTextContent("Urgent");
});

test("renders stable priority badge", () => {
  render(<PortfolioAutoStrategyPanel data={makeFullResponse()} />);
  const badges = screen.getAllByTestId("priority-badge-proj-2");
  expect(badges[0]).toHaveTextContent("Stable");
});

test("renders no-data priority badge", () => {
  render(<PortfolioAutoStrategyPanel data={makeFullResponse()} />);
  const badges = screen.getAllByTestId("priority-badge-proj-3");
  expect(badges[0]).toHaveTextContent("No Data");
});

test("recommended_intervention badge uses badgeNeedsAttention class (not neutral)", () => {
  const data: PortfolioAutoStrategyResponse = {
    ...makeFullResponse(),
    project_cards: [makeRecommendedCard()],
    top_actions: [],
    top_risk_projects: [makeRecommendedCard()],
    top_upside_projects: [],
  };
  render(<PortfolioAutoStrategyPanel data={data} />);
  const badges = screen.getAllByTestId("priority-badge-proj-4");
  expect(badges[0]).toHaveTextContent("Recommended");
  // Must use the caution/needs-attention class, not the neutral fallback
  expect(badges[0]).toHaveClass("badgeNeedsAttention");
  expect(badges[0]).not.toHaveClass("badgeNeutral");
});

// ---------------------------------------------------------------------------
// Top actions section
// ---------------------------------------------------------------------------

test("renders top actions section when non-empty", () => {
  render(<PortfolioAutoStrategyPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("top-actions-section")).toBeInTheDocument();
});

test("renders top action row with correct content", () => {
  render(<PortfolioAutoStrategyPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("top-action-proj-1")).toBeInTheDocument();
  expect(screen.getByTestId("top-action-proj-1")).toHaveTextContent("Marina Tower");
});

test("does not render top actions section when empty", () => {
  const data = { ...makeFullResponse(), top_actions: [] };
  render(<PortfolioAutoStrategyPanel data={data} />);
  expect(screen.queryByTestId("top-actions-section")).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Top risk section
// ---------------------------------------------------------------------------

test("renders top risk section when non-empty", () => {
  render(<PortfolioAutoStrategyPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("top-risk-section")).toBeInTheDocument();
});

test("does not render top risk section when empty", () => {
  const data = { ...makeFullResponse(), top_risk_projects: [] };
  render(<PortfolioAutoStrategyPanel data={data} />);
  expect(screen.queryByTestId("top-risk-section")).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Top upside section
// ---------------------------------------------------------------------------

test("renders top upside section when non-empty", () => {
  render(<PortfolioAutoStrategyPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("top-upside-section")).toBeInTheDocument();
});

test("does not render top upside section when empty", () => {
  const data = { ...makeFullResponse(), top_upside_projects: [] };
  render(<PortfolioAutoStrategyPanel data={data} />);
  expect(screen.queryByTestId("top-upside-section")).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// All projects section
// ---------------------------------------------------------------------------

test("renders all projects section", () => {
  render(<PortfolioAutoStrategyPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("all-auto-strategy-projects")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Read-only: no mutation controls
// ---------------------------------------------------------------------------

test("renders no buttons that would mutate data", () => {
  render(<PortfolioAutoStrategyPanel data={makeFullResponse()} />);
  const buttons = screen.queryAllByRole("button");
  expect(buttons.length).toBe(0);
});
