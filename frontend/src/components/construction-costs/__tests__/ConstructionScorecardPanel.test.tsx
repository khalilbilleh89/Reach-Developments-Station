/**
 * ConstructionScorecardPanel tests — validates rendering across loading,
 * error, incomplete-state, and full-scorecard scenarios.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock CSS modules
jest.mock("@/styles/construction.module.css", () => ({
  summaryEmpty: "summaryEmpty",
  loadingState: "loadingState",
  errorState: "errorState",
}));

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
  varianceOverrun: "varianceOverrun",
  varianceSaving: "varianceSaving",
  varianceNeutral: "varianceNeutral",
  badgeOverrun: "badgeOverrun",
  badgeSaving: "badgeSaving",
  badgeNeutral: "badgeNeutral",
  riskSeverityBadge: "riskSeverityBadge",
  severityCritical: "severityCritical",
  severityWarning: "severityWarning",
}));

jest.mock("@/lib/construction-scorecard-api", () => ({
  getProjectConstructionScorecard: jest.fn(),
}));

import { getProjectConstructionScorecard } from "@/lib/construction-scorecard-api";
import { ConstructionScorecardPanel } from "@/components/construction-costs/ConstructionScorecardPanel";
import type { ConstructionProjectScorecard } from "@/lib/construction-scorecard-types";

const mockGet = getProjectConstructionScorecard as jest.Mock;

// ---------- Factory helpers -----------------------------------------------

const makeIncompleteScorecard = (): ConstructionProjectScorecard => ({
  project_id: "proj-1",
  project_name: "Test Project",
  has_approved_baseline: false,
  approved_baseline_set_id: null,
  approved_baseline_amount: null,
  approved_at: null,
  current_forecast_amount: "500000.00",
  cost_variance_amount: null,
  cost_variance_pct: null,
  cost_status: "incomplete",
  contingency_amount: "50000.00",
  contingency_pressure_pct: null,
  contingency_status: "incomplete",
  overall_health_status: "incomplete",
  last_updated_at: null,
});

const makeHealthyScorecard = (): ConstructionProjectScorecard => ({
  project_id: "proj-1",
  project_name: "Test Project",
  has_approved_baseline: true,
  approved_baseline_set_id: "set-1",
  approved_baseline_amount: "1000000.00",
  approved_at: "2024-01-15T10:00:00Z",
  current_forecast_amount: "1030000.00",
  cost_variance_amount: "30000.00",
  cost_variance_pct: "3.00",
  cost_status: "healthy",
  contingency_amount: "50000.00",
  contingency_pressure_pct: "5.00",
  contingency_status: "healthy",
  overall_health_status: "healthy",
  last_updated_at: "2024-01-20T10:00:00Z",
});

const makeWarningScorecard = (): ConstructionProjectScorecard => ({
  ...makeHealthyScorecard(),
  current_forecast_amount: "1100000.00",
  cost_variance_amount: "100000.00",
  cost_variance_pct: "10.00",
  cost_status: "warning",
  overall_health_status: "warning",
});

const makeCriticalScorecard = (): ConstructionProjectScorecard => ({
  ...makeHealthyScorecard(),
  current_forecast_amount: "1250000.00",
  cost_variance_amount: "250000.00",
  cost_variance_pct: "25.00",
  cost_status: "critical",
  overall_health_status: "critical",
});

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

test("renders loading state initially", () => {
  mockGet.mockReturnValue(new Promise(() => {})); // never resolves
  render(<ConstructionScorecardPanel projectId="proj-1" />);
  expect(screen.getByText(/loading scorecard/i)).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

test("renders error state on fetch failure", async () => {
  mockGet.mockRejectedValue(new Error("Network failure"));
  render(<ConstructionScorecardPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByText(/network failure/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Incomplete state (no approved baseline)
// ---------------------------------------------------------------------------

test("renders incomplete state when no approved baseline", async () => {
  mockGet.mockResolvedValue(makeIncompleteScorecard());
  render(<ConstructionScorecardPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("scorecard-incomplete")).toBeInTheDocument();
  });
  expect(screen.getByText(/no approved baseline/i)).toBeInTheDocument();
});

test("incomplete state still shows current forecast amount", async () => {
  mockGet.mockResolvedValue(makeIncompleteScorecard());
  render(<ConstructionScorecardPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("scorecard-incomplete")).toBeInTheDocument();
  });
  // current_forecast_amount = 500000.00 → rendered as 500,000.00
  expect(screen.getByText("500,000.00")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Full scorecard — healthy
// ---------------------------------------------------------------------------

test("renders full scorecard when baseline exists", async () => {
  mockGet.mockResolvedValue(makeHealthyScorecard());
  render(<ConstructionScorecardPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("scorecard-full")).toBeInTheDocument();
  });
});

test("healthy badge renders correctly", async () => {
  mockGet.mockResolvedValue(makeHealthyScorecard());
  render(<ConstructionScorecardPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("scorecard-full")).toBeInTheDocument();
  });
  // Should have "Healthy" text at least once (overall badge)
  const healthyEls = screen.getAllByText("Healthy");
  expect(healthyEls.length).toBeGreaterThan(0);
});

test("renders approved baseline amount", async () => {
  mockGet.mockResolvedValue(makeHealthyScorecard());
  render(<ConstructionScorecardPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("scorecard-full")).toBeInTheDocument();
  });
  // 1,000,000.00
  expect(screen.getByText("1,000,000.00")).toBeInTheDocument();
});

test("renders cost variance amount and pct", async () => {
  mockGet.mockResolvedValue(makeHealthyScorecard());
  render(<ConstructionScorecardPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("scorecard-full")).toBeInTheDocument();
  });
  // variance amount = 30,000.00 (positive so +30,000.00)
  expect(screen.getByText("+30,000.00")).toBeInTheDocument();
  // variance pct = +3.00%
  expect(screen.getByText("+3.00%")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Warning badge
// ---------------------------------------------------------------------------

test("warning badge renders for warning scorecard", async () => {
  mockGet.mockResolvedValue(makeWarningScorecard());
  render(<ConstructionScorecardPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("scorecard-full")).toBeInTheDocument();
  });
  const warningEls = screen.getAllByText("Warning");
  expect(warningEls.length).toBeGreaterThan(0);
});

// ---------------------------------------------------------------------------
// Critical badge
// ---------------------------------------------------------------------------

test("critical badge renders for critical scorecard", async () => {
  mockGet.mockResolvedValue(makeCriticalScorecard());
  render(<ConstructionScorecardPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("scorecard-full")).toBeInTheDocument();
  });
  const criticalEls = screen.getAllByText("Critical");
  expect(criticalEls.length).toBeGreaterThan(0);
});

// ---------------------------------------------------------------------------
// Scorecard panel renders title
// ---------------------------------------------------------------------------

test("renders Construction Health Scorecard title", async () => {
  mockGet.mockResolvedValue(makeHealthyScorecard());
  render(<ConstructionScorecardPanel projectId="proj-1" />);
  expect(
    screen.getByText("Construction Health Scorecard"),
  ).toBeInTheDocument();
});
