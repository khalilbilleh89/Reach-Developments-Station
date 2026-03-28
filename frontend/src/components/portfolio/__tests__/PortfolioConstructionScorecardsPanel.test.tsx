/**
 * PortfolioConstructionScorecardsPanel tests — validates rendering across
 * empty state, count summary, top-risk projects, and missing-baseline lists.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock CSS modules
jest.mock("@/styles/portfolio.module.css", () => ({
  panelCard: "panelCard",
  panelTitle: "panelTitle",
  panelEmpty: "panelEmpty",
  metricsRow: "metricsRow",
  metricItem: "metricItem",
  metricLabel: "metricLabel",
  metricValue: "metricValue",
  statItem: "statItem",
  statLabel: "statLabel",
  statValue: "statValue",
  healthBadge: "healthBadge",
  varianceCardHeader: "varianceCardHeader",
  projectName: "projectName",
  varianceSection: "varianceSection",
  varianceSectionTitle: "varianceSectionTitle",
  varianceCardGrid: "varianceCardGrid",
  varianceProjectCard: "varianceProjectCard",
  varianceOverrun: "varianceOverrun",
  varianceSaving: "varianceSaving",
  varianceNeutral: "varianceNeutral",
  badgeOverrun: "badgeOverrun",
  badgeSaving: "badgeSaving",
  badgeNeutral: "badgeNeutral",
  riskFlagList: "riskFlagList",
  riskFlagItem: "riskFlagItem",
  riskSeverityBadge: "riskSeverityBadge",
  riskFlagBody: "riskFlagBody",
  riskFlagDescription: "riskFlagDescription",
  riskFlagProject: "riskFlagProject",
  severityCritical: "severityCritical",
  severityWarning: "severityWarning",
}));

import { PortfolioConstructionScorecardsPanel } from "@/components/portfolio/PortfolioConstructionScorecardsPanel";
import type {
  ConstructionPortfolioScorecardItem,
  ConstructionPortfolioScorecardsResponse,
} from "@/lib/construction-scorecard-types";

// ---------------------------------------------------------------------------
// Factory helpers
// ---------------------------------------------------------------------------

const makeEmptyResponse = (): ConstructionPortfolioScorecardsResponse => ({
  summary: {
    total_projects_scored: 0,
    healthy_count: 0,
    warning_count: 0,
    critical_count: 0,
    incomplete_count: 0,
    projects_missing_baseline: 0,
  },
  projects: [],
  top_risk_projects: [],
  missing_baseline_projects: [],
});

const makeItem = (
  overrides: Partial<ConstructionPortfolioScorecardItem> = {},
): ConstructionPortfolioScorecardItem => ({
  project_id: "proj-1",
  project_name: "Marina Tower",
  has_approved_baseline: true,
  approved_baseline_amount: "1000000.00",
  current_forecast_amount: "1100000.00",
  cost_variance_amount: "100000.00",
  cost_variance_pct: "10.00",
  contingency_amount: "50000.00",
  contingency_pressure_pct: "5.00",
  overall_health_status: "warning",
  ...overrides,
});

const makeResponse = (
  overrides: Partial<ConstructionPortfolioScorecardsResponse> = {},
): ConstructionPortfolioScorecardsResponse => ({
  summary: {
    total_projects_scored: 2,
    healthy_count: 1,
    warning_count: 1,
    critical_count: 0,
    incomplete_count: 0,
    projects_missing_baseline: 0,
  },
  projects: [
    makeItem({ project_name: "Warning Project", overall_health_status: "warning" }),
    makeItem({ project_id: "proj-2", project_name: "Healthy Project", overall_health_status: "healthy" }),
  ],
  top_risk_projects: [
    makeItem({ project_name: "Warning Project", overall_health_status: "warning" }),
  ],
  missing_baseline_projects: [],
  ...overrides,
});

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

test("renders empty state when no projects", () => {
  render(<PortfolioConstructionScorecardsPanel data={makeEmptyResponse()} />);
  expect(screen.getByText(/no projects found/i)).toBeInTheDocument();
});

test("renders panel title in empty state", () => {
  render(<PortfolioConstructionScorecardsPanel data={makeEmptyResponse()} />);
  expect(screen.getByText("Construction Health")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Summary counts
// ---------------------------------------------------------------------------

test("renders total projects count", () => {
  render(<PortfolioConstructionScorecardsPanel data={makeResponse()} />);
  expect(screen.getByText("Total Projects")).toBeInTheDocument();
  expect(screen.getByText("2")).toBeInTheDocument();
});

test("renders healthy count", () => {
  render(<PortfolioConstructionScorecardsPanel data={makeResponse()} />);
  // "Healthy" appears as metric label and as project badge — use getAllByText
  const healthyEls = screen.getAllByText("Healthy");
  expect(healthyEls.length).toBeGreaterThan(0);
  // healthy_count = 1 — verify the count value appears in summary
  const metricValues = screen.getAllByText("1");
  expect(metricValues.length).toBeGreaterThan(0);
});

test("renders warning count", () => {
  render(<PortfolioConstructionScorecardsPanel data={makeResponse()} />);
  // "Warning" appears as metric label and as project badge — use getAllByText
  const warningEls = screen.getAllByText("Warning");
  expect(warningEls.length).toBeGreaterThan(0);
});

test("renders critical count", () => {
  const data = makeResponse({
    summary: {
      total_projects_scored: 1,
      healthy_count: 0,
      warning_count: 0,
      critical_count: 1,
      incomplete_count: 0,
      projects_missing_baseline: 0,
    },
  });
  render(<PortfolioConstructionScorecardsPanel data={data} />);
  expect(screen.getByText("Critical")).toBeInTheDocument();
});

test("renders panel title", () => {
  render(<PortfolioConstructionScorecardsPanel data={makeResponse()} />);
  expect(screen.getByText("Construction Health")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Top-risk projects
// ---------------------------------------------------------------------------

test("renders top-risk section when projects exist", () => {
  render(<PortfolioConstructionScorecardsPanel data={makeResponse()} />);
  expect(screen.getByText("Projects Requiring Attention")).toBeInTheDocument();
});

test("renders top-risk project name", () => {
  render(<PortfolioConstructionScorecardsPanel data={makeResponse()} />);
  expect(screen.getByText("Warning Project")).toBeInTheDocument();
});

test("does not render top-risk section when no risk projects", () => {
  const data = makeResponse({ top_risk_projects: [] });
  render(<PortfolioConstructionScorecardsPanel data={data} />);
  expect(
    screen.queryByText("Projects Requiring Attention"),
  ).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Missing baseline projects
// ---------------------------------------------------------------------------

test("renders missing baseline section when projects exist", () => {
  const data = makeResponse({
    missing_baseline_projects: [
      makeItem({
        project_id: "proj-m",
        project_name: "Missing Baseline Project",
        has_approved_baseline: false,
        approved_baseline_amount: null,
        cost_variance_amount: null,
        cost_variance_pct: null,
        contingency_pressure_pct: null,
        overall_health_status: "incomplete",
      }),
    ],
  });
  render(<PortfolioConstructionScorecardsPanel data={data} />);
  expect(screen.getByText("Missing Approved Baseline")).toBeInTheDocument();
  expect(screen.getByText("Missing Baseline Project")).toBeInTheDocument();
});

test("does not render missing baseline section when empty", () => {
  const data = makeResponse({ missing_baseline_projects: [] });
  render(<PortfolioConstructionScorecardsPanel data={data} />);
  expect(
    screen.queryByText("Missing Approved Baseline"),
  ).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Variance amounts
// ---------------------------------------------------------------------------

test("renders variance amount for top-risk project card", () => {
  render(<PortfolioConstructionScorecardsPanel data={makeResponse()} />);
  // cost_variance_amount = "100000.00" → "+100,000.00"
  expect(screen.getByText("+100,000.00")).toBeInTheDocument();
});
