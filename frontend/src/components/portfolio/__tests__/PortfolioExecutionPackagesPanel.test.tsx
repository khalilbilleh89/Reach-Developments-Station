/**
 * PortfolioExecutionPackagesPanel tests (PR-V7-07)
 *
 * Validates:
 *  - empty portfolio renders empty state
 *  - summary KPIs render correctly
 *  - project execution package cards render with all required fields
 *  - top-ready-actions section renders
 *  - top-caution section renders
 *  - top-blocked section renders
 *  - all-projects section renders
 *  - readiness badges render correctly
 *  - urgency score renders on cards
 *  - next-best-action renders on cards
 *  - blockers render on blocked cards
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
  badgeNeedsAttention: "badgeNeedsAttention",
}));

import { PortfolioExecutionPackagesPanel } from "@/components/portfolio/PortfolioExecutionPackagesPanel";
import type { PortfolioExecutionPackageResponse } from "@/lib/strategy-execution-package-types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const makeEmptyResponse = (): PortfolioExecutionPackageResponse => ({
  summary: {
    total_projects: 0,
    ready_for_review_count: 0,
    blocked_count: 0,
    caution_required_count: 0,
    insufficient_data_count: 0,
  },
  top_ready_actions: [],
  top_blocked_actions: [],
  top_high_risk_packages: [],
  packages: [],
});

const makeReadyCard = () => ({
  project_id: "proj-1",
  project_name: "Marina Tower",
  recommended_strategy: "maintain" as const,
  intervention_priority: "recommended_intervention",
  intervention_type: "pricing_intervention",
  execution_readiness: "ready_for_review" as const,
  has_feasibility_baseline: true,
  requires_manual_review: true,
  next_best_action: "Review Simulation Evidence",
  blockers: [],
  urgency_score: 45,
  expected_impact: "Projected IRR: 15.00% (medium risk).",
});

const makeBlockedCard = () => ({
  project_id: "proj-2",
  project_name: "Palm Villa",
  recommended_strategy: null,
  intervention_priority: "insufficient_data",
  intervention_type: "insufficient_data",
  execution_readiness: "blocked_by_dependency" as const,
  has_feasibility_baseline: false,
  requires_manual_review: true,
  next_best_action: "Establish Feasibility Baseline",
  blockers: ["Feasibility Baseline"],
  urgency_score: 15,
  expected_impact: "Unable to estimate — no baseline.",
});

const makeCautionCard = () => ({
  project_id: "proj-3",
  project_name: "City Walk",
  recommended_strategy: "hold" as const,
  intervention_priority: "urgent_intervention",
  intervention_type: "mixed_intervention",
  execution_readiness: "caution_required" as const,
  has_feasibility_baseline: true,
  requires_manual_review: true,
  next_best_action: "Route for Executive Sign-Off",
  blockers: [],
  urgency_score: 80,
  expected_impact: "Projected IRR: 9.00% (high risk).",
});

const makeNoDataCard = () => ({
  project_id: "proj-4",
  project_name: "Downtown Hub",
  recommended_strategy: null,
  intervention_priority: "insufficient_data",
  intervention_type: "insufficient_data",
  execution_readiness: "insufficient_data" as const,
  has_feasibility_baseline: false,
  requires_manual_review: true,
  next_best_action: "Resolve Insufficient Strategy Data",
  blockers: ["Strategy Data", "Feasibility Baseline"],
  urgency_score: 0,
  expected_impact: "Unable to estimate — no strategy data.",
});

const makeFullResponse = (): PortfolioExecutionPackageResponse => ({
  summary: {
    total_projects: 4,
    ready_for_review_count: 1,
    blocked_count: 1,
    caution_required_count: 1,
    insufficient_data_count: 1,
  },
  top_ready_actions: [makeReadyCard()],
  top_blocked_actions: [makeBlockedCard()],
  top_high_risk_packages: [makeCautionCard()],
  packages: [makeReadyCard(), makeCautionCard(), makeBlockedCard(), makeNoDataCard()],
});

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

test("renders empty state when no projects", () => {
  render(<PortfolioExecutionPackagesPanel data={makeEmptyResponse()} />);
  expect(
    screen.getByTestId("portfolio-execution-packages-panel"),
  ).toBeInTheDocument();
  expect(screen.getByTestId("exec-pkg-empty-state")).toBeInTheDocument();
});

test("does not render summary strip when empty", () => {
  render(<PortfolioExecutionPackagesPanel data={makeEmptyResponse()} />);
  expect(screen.queryByTestId("exec-pkg-summary-strip")).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Summary KPIs
// ---------------------------------------------------------------------------

test("renders summary KPI strip with correct values", () => {
  render(<PortfolioExecutionPackagesPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("exec-pkg-summary-strip")).toBeInTheDocument();
  expect(screen.getByTestId("exec-pkg-total")).toHaveTextContent("4");
  expect(screen.getByTestId("exec-pkg-ready")).toHaveTextContent("1");
  expect(screen.getByTestId("exec-pkg-blocked")).toHaveTextContent("1");
  expect(screen.getByTestId("exec-pkg-caution")).toHaveTextContent("1");
  expect(screen.getByTestId("exec-pkg-no-data")).toHaveTextContent("1");
});

// ---------------------------------------------------------------------------
// Package cards
// ---------------------------------------------------------------------------

test("renders all project cards", () => {
  render(<PortfolioExecutionPackagesPanel data={makeFullResponse()} />);
  expect(
    screen.getAllByTestId("exec-pkg-card-proj-1").length,
  ).toBeGreaterThanOrEqual(1);
  expect(
    screen.getAllByTestId("exec-pkg-card-proj-2").length,
  ).toBeGreaterThanOrEqual(1);
  expect(
    screen.getAllByTestId("exec-pkg-card-proj-3").length,
  ).toBeGreaterThanOrEqual(1);
});

test("renders urgency score on project card", () => {
  render(<PortfolioExecutionPackagesPanel data={makeFullResponse()} />);
  const urgencyElements = screen.getAllByTestId("exec-pkg-urgency-proj-1");
  expect(urgencyElements[0]).toHaveTextContent("45");
});

test("renders next-best-action on card", () => {
  render(<PortfolioExecutionPackagesPanel data={makeFullResponse()} />);
  const nextActionElements = screen.getAllByTestId(
    "exec-pkg-next-action-proj-1",
  );
  expect(nextActionElements[0]).toHaveTextContent("Review Simulation Evidence");
});

test("renders blockers on blocked card", () => {
  render(<PortfolioExecutionPackagesPanel data={makeFullResponse()} />);
  const blockersElements = screen.getAllByTestId("exec-pkg-blockers-proj-2");
  expect(blockersElements[0]).toHaveTextContent("Feasibility Baseline");
});

test("does not render blockers on non-blocked card", () => {
  render(<PortfolioExecutionPackagesPanel data={makeFullResponse()} />);
  expect(screen.queryByTestId("exec-pkg-blockers-proj-1")).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Readiness badges
// ---------------------------------------------------------------------------

test("renders ready readiness badge", () => {
  render(<PortfolioExecutionPackagesPanel data={makeFullResponse()} />);
  const badges = screen.getAllByTestId("exec-pkg-readiness-badge-proj-1");
  expect(badges[0]).toHaveTextContent("Ready");
});

test("renders blocked readiness badge", () => {
  render(<PortfolioExecutionPackagesPanel data={makeFullResponse()} />);
  const badges = screen.getAllByTestId("exec-pkg-readiness-badge-proj-2");
  expect(badges[0]).toHaveTextContent("Blocked");
});

test("renders caution readiness badge", () => {
  render(<PortfolioExecutionPackagesPanel data={makeFullResponse()} />);
  const badges = screen.getAllByTestId("exec-pkg-readiness-badge-proj-3");
  expect(badges[0]).toHaveTextContent("Caution");
});

test("renders no-data readiness badge", () => {
  render(<PortfolioExecutionPackagesPanel data={makeFullResponse()} />);
  const badges = screen.getAllByTestId("exec-pkg-readiness-badge-proj-4");
  expect(badges[0]).toHaveTextContent("No Data");
});

// ---------------------------------------------------------------------------
// Section visibility
// ---------------------------------------------------------------------------

test("renders top-ready section when non-empty", () => {
  render(<PortfolioExecutionPackagesPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("exec-pkg-top-ready-section")).toBeInTheDocument();
});

test("renders top-caution section when non-empty", () => {
  render(<PortfolioExecutionPackagesPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("exec-pkg-top-caution-section")).toBeInTheDocument();
});

test("renders top-blocked section when non-empty", () => {
  render(<PortfolioExecutionPackagesPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("exec-pkg-top-blocked-section")).toBeInTheDocument();
});

test("renders all-projects section", () => {
  render(<PortfolioExecutionPackagesPanel data={makeFullResponse()} />);
  expect(screen.getByTestId("exec-pkg-all-projects")).toBeInTheDocument();
});

test("does not render top-ready section when empty", () => {
  const data = { ...makeFullResponse(), top_ready_actions: [] };
  render(<PortfolioExecutionPackagesPanel data={data} />);
  expect(
    screen.queryByTestId("exec-pkg-top-ready-section"),
  ).not.toBeInTheDocument();
});

test("does not render top-caution section when empty", () => {
  const data = { ...makeFullResponse(), top_high_risk_packages: [] };
  render(<PortfolioExecutionPackagesPanel data={data} />);
  expect(
    screen.queryByTestId("exec-pkg-top-caution-section"),
  ).not.toBeInTheDocument();
});

test("does not render top-blocked section when empty", () => {
  const data = { ...makeFullResponse(), top_blocked_actions: [] };
  render(<PortfolioExecutionPackagesPanel data={data} />);
  expect(
    screen.queryByTestId("exec-pkg-top-blocked-section"),
  ).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Read-only: no mutation controls
// ---------------------------------------------------------------------------

test("renders no buttons that would mutate data", () => {
  render(<PortfolioExecutionPackagesPanel data={makeFullResponse()} />);
  const buttons = screen.queryAllByRole("button");
  expect(buttons.length).toBe(0);
});
