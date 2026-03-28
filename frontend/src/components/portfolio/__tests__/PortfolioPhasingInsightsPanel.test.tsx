/**
 * PortfolioPhasingInsightsPanel tests (PR-V7-03)
 *
 * Validates:
 *  - empty portfolio renders empty state
 *  - summary KPI strip renders correctly
 *  - project cards render with all required fields
 *  - top phase opportunities section renders
 *  - top release risks section renders
 *  - current-phase recommendation badge color mapping is correct
 *  - next-phase recommendation badge renders correctly
 *  - sell-through % renders
 *  - read-only: no mutation controls
 */
import React from "react";
import { render, screen, within } from "@testing-library/react";
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

import { PortfolioPhasingInsightsPanel } from "@/components/portfolio/PortfolioPhasingInsightsPanel";
import type { PortfolioPhasingInsightsResponse } from "@/lib/phasing-optimization-types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const makeEmptyResponse = (): PortfolioPhasingInsightsResponse => ({
  summary: {
    total_projects: 0,
    projects_prepare_next_phase_count: 0,
    projects_hold_inventory_count: 0,
    projects_delay_release_count: 0,
    projects_insufficient_data_count: 0,
  },
  projects: [],
  top_phase_opportunities: [],
  top_release_risks: [],
});

const makeHighDemandCard = () => ({
  project_id: "proj-1",
  project_name: "Marina Tower",
  current_phase_recommendation: "release_more_inventory" as const,
  next_phase_recommendation: "prepare_next_phase" as const,
  release_urgency: "high" as const,
  confidence: "high" as const,
  sell_through_pct: 90.0,
  absorption_status: "high_demand" as const,
  has_next_phase: true,
});

const makeLowDemandCard = () => ({
  project_id: "proj-2",
  project_name: "Palm Villa",
  current_phase_recommendation: "delay_further_release" as const,
  next_phase_recommendation: "defer_next_phase" as const,
  release_urgency: "low" as const,
  confidence: "high" as const,
  sell_through_pct: 20.0,
  absorption_status: "low_demand" as const,
  has_next_phase: true,
});

const makeBalancedCard = () => ({
  project_id: "proj-3",
  project_name: "City Walk",
  current_phase_recommendation: "maintain_current_release" as const,
  next_phase_recommendation: "do_not_open_next_phase" as const,
  release_urgency: "low" as const,
  confidence: "high" as const,
  sell_through_pct: 50.0,
  absorption_status: "balanced" as const,
  has_next_phase: false,
});

const makeFullResponse = (): PortfolioPhasingInsightsResponse => ({
  summary: {
    total_projects: 3,
    projects_prepare_next_phase_count: 1,
    projects_hold_inventory_count: 0,
    projects_delay_release_count: 1,
    projects_insufficient_data_count: 0,
  },
  projects: [makeHighDemandCard(), makeBalancedCard(), makeLowDemandCard()],
  top_phase_opportunities: [makeHighDemandCard()],
  top_release_risks: [makeLowDemandCard()],
});

// ---------------------------------------------------------------------------
// Empty portfolio
// ---------------------------------------------------------------------------

test("renders empty state for empty portfolio", () => {
  render(<PortfolioPhasingInsightsPanel data={makeEmptyResponse()} />);
  expect(screen.getByTestId("phasing-empty-state")).toBeInTheDocument();
  expect(screen.getByTestId("portfolio-phasing-panel")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Summary KPI strip
// ---------------------------------------------------------------------------

test("renders summary KPI strip with correct counts", () => {
  render(<PortfolioPhasingInsightsPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("phasing-total-projects")).toHaveTextContent("3");
  expect(screen.getByTestId("phasing-prepare-count")).toHaveTextContent("1");
  expect(screen.getByTestId("phasing-delay-count")).toHaveTextContent("1");
  expect(screen.getByTestId("phasing-hold-count")).toHaveTextContent("0");
  expect(screen.getByTestId("phasing-insufficient-count")).toHaveTextContent("0");
});

// ---------------------------------------------------------------------------
// Project cards
// ---------------------------------------------------------------------------

test("renders project cards for all projects", () => {
  render(<PortfolioPhasingInsightsPanel data={makeFullResponse()} />);
  // Cards appear in multiple sections; check "all-phasing-projects" section
  const allSection = screen.getByTestId("all-phasing-projects");
  expect(within(allSection).getByTestId("phasing-card-proj-1")).toBeInTheDocument();
  expect(within(allSection).getByTestId("phasing-card-proj-2")).toBeInTheDocument();
  expect(within(allSection).getByTestId("phasing-card-proj-3")).toBeInTheDocument();
});

test("renders current-phase recommendation badge on cards", () => {
  render(<PortfolioPhasingInsightsPanel data={makeFullResponse()} />);
  const allSection = screen.getByTestId("all-phasing-projects");
  expect(within(allSection).getByTestId("current-rec-badge-proj-1")).toHaveTextContent("Release More");
  // proj-2 = Palm Villa (low demand) → Delay Release
  expect(within(allSection).getByTestId("current-rec-badge-proj-2")).toHaveTextContent("Delay Release");
  // proj-3 = City Walk (balanced) → Maintain
  expect(within(allSection).getByTestId("current-rec-badge-proj-3")).toHaveTextContent("Maintain");
});

test("renders next-phase recommendation badge on cards", () => {
  render(<PortfolioPhasingInsightsPanel data={makeFullResponse()} />);
  const allSection = screen.getByTestId("all-phasing-projects");
  expect(within(allSection).getByTestId("next-rec-badge-proj-1")).toHaveTextContent("Prepare Next Phase");
  // proj-2 = Palm Villa (low demand) → Defer Next Phase
  expect(within(allSection).getByTestId("next-rec-badge-proj-2")).toHaveTextContent("Defer Next Phase");
});

// ---------------------------------------------------------------------------
// Top phase opportunities section
// ---------------------------------------------------------------------------

test("renders top phase opportunities section", () => {
  render(<PortfolioPhasingInsightsPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("top-phase-opportunities")).toBeInTheDocument();
  expect(screen.getByTestId("top-phase-opportunities")).toHaveTextContent("Marina Tower");
});

// ---------------------------------------------------------------------------
// Top release risks section
// ---------------------------------------------------------------------------

test("renders top release risks section", () => {
  render(<PortfolioPhasingInsightsPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("top-release-risks")).toBeInTheDocument();
  expect(screen.getByTestId("top-release-risks")).toHaveTextContent("Palm Villa");
});

// ---------------------------------------------------------------------------
// All projects section
// ---------------------------------------------------------------------------

test("renders all projects section", () => {
  render(<PortfolioPhasingInsightsPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("all-phasing-projects")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Sell-through % renders
// ---------------------------------------------------------------------------

test("renders sell-through percentage on project cards", () => {
  render(<PortfolioPhasingInsightsPanel data={makeFullResponse()} />);
  const allSection = screen.getByTestId("all-phasing-projects");
  const card = within(allSection).getByTestId("phasing-card-proj-1");
  expect(card).toHaveTextContent("90.0%");
});

// ---------------------------------------------------------------------------
// Read-only: no mutation controls
// ---------------------------------------------------------------------------

test("does not render any mutation controls", () => {
  render(<PortfolioPhasingInsightsPanel data={makeFullResponse()} />);
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  expect(screen.queryByRole("form")).not.toBeInTheDocument();
});
