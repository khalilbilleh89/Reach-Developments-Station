/**
 * ProjectPhasingRecommendationsPanel tests (PR-V7-03)
 *
 * Validates:
 *  - loading state renders correctly
 *  - error state renders correctly
 *  - insufficient-data state renders correctly
 *  - current-phase recommendation badge renders correctly
 *  - next-phase recommendation badge renders correctly
 *  - urgency badge renders correctly
 *  - inventory stats (sold / available / sell-through) render correctly
 *  - reason text renders
 *  - confidence renders
 *  - no-mutation controls (read-only)
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock the API client
jest.mock("@/lib/phasing-optimization-api", () => ({
  getProjectPhasingRecommendations: jest.fn(),
}));

import { getProjectPhasingRecommendations } from "@/lib/phasing-optimization-api";
import { ProjectPhasingRecommendationsPanel } from "@/components/feasibility/ProjectPhasingRecommendationsPanel";
import type { ProjectPhasingRecommendationResponse } from "@/lib/phasing-optimization-types";

const mockGetRecommendations = getProjectPhasingRecommendations as jest.Mock;

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const makeInsufficient = (): ProjectPhasingRecommendationResponse => ({
  project_id: "proj-1",
  project_name: "Test Project",
  current_phase_id: null,
  current_phase_name: null,
  current_phase_recommendation: "insufficient_data",
  next_phase_recommendation: "insufficient_data",
  release_urgency: "none",
  confidence: "low",
  reason: "No phase inventory found for this project.",
  sold_units: 0,
  available_units: 0,
  sell_through_pct: null,
  absorption_status: "no_data",
  has_next_phase: false,
  next_phase_id: null,
  next_phase_name: null,
});

const makeHighDemandRelease = (): ProjectPhasingRecommendationResponse => ({
  project_id: "proj-2",
  project_name: "Marina Tower",
  current_phase_id: "phase-1",
  current_phase_name: "Phase 1",
  current_phase_recommendation: "release_more_inventory",
  next_phase_recommendation: "prepare_next_phase",
  release_urgency: "high",
  confidence: "high",
  reason:
    "High demand with critically low phase inventory (10% available). Release more units immediately. Strong indicators for next phase preparation.",
  sold_units: 9,
  available_units: 1,
  sell_through_pct: 90.0,
  absorption_status: "high_demand",
  has_next_phase: true,
  next_phase_id: "phase-2",
  next_phase_name: "Phase 2",
});

const makeBalanced = (): ProjectPhasingRecommendationResponse => ({
  project_id: "proj-3",
  project_name: "Palm Villa",
  current_phase_id: "phase-1",
  current_phase_name: "Block A",
  current_phase_recommendation: "maintain_current_release",
  next_phase_recommendation: "do_not_open_next_phase",
  release_urgency: "low",
  confidence: "high",
  reason: "Sales demand is balanced with 50% phase inventory available. Maintain current release pace.",
  sold_units: 5,
  available_units: 5,
  sell_through_pct: 50.0,
  absorption_status: "balanced",
  has_next_phase: false,
  next_phase_id: null,
  next_phase_name: null,
});

const makeLowDemandDelay = (): ProjectPhasingRecommendationResponse => ({
  project_id: "proj-4",
  project_name: "City Heights",
  current_phase_id: "phase-1",
  current_phase_name: "Phase 1",
  current_phase_recommendation: "delay_further_release",
  next_phase_recommendation: "defer_next_phase",
  release_urgency: "low",
  confidence: "high",
  reason: "Low demand with high available inventory (80% available). Delay further releases until absorption improves.",
  sold_units: 2,
  available_units: 8,
  sell_through_pct: 20.0,
  absorption_status: "low_demand",
  has_next_phase: true,
  next_phase_id: "phase-2",
  next_phase_name: "Phase 2",
});

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

test("renders loading state while fetching", () => {
  mockGetRecommendations.mockReturnValue(new Promise(() => {}));
  render(<ProjectPhasingRecommendationsPanel projectId="proj-1" />);
  expect(screen.getByTestId("phasing-rec-loading")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

test("renders error state on API failure", async () => {
  mockGetRecommendations.mockRejectedValue(new Error("API error"));
  render(<ProjectPhasingRecommendationsPanel projectId="proj-1" />);
  const errorEl = await screen.findByTestId("phasing-rec-error");
  expect(errorEl).toHaveTextContent("API error");
});

// ---------------------------------------------------------------------------
// Insufficient data state
// ---------------------------------------------------------------------------

test("renders insufficient data state when no phase inventory", async () => {
  mockGetRecommendations.mockResolvedValue(makeInsufficient());
  render(<ProjectPhasingRecommendationsPanel projectId="proj-1" />);
  const el = await screen.findByTestId("phasing-rec-insufficient");
  expect(el).toBeInTheDocument();
  expect(el).toHaveTextContent("No phase inventory found");
});

// ---------------------------------------------------------------------------
// Panel renders with full data
// ---------------------------------------------------------------------------

test("renders panel with current-phase badge and next-phase badge", async () => {
  mockGetRecommendations.mockResolvedValue(makeHighDemandRelease());
  render(<ProjectPhasingRecommendationsPanel projectId="proj-2" />);
  await screen.findByTestId("phasing-recommendations-panel");

  expect(screen.getByTestId("current-phase-badge")).toHaveTextContent(
    "Release More Inventory"
  );
  expect(screen.getByTestId("next-phase-badge")).toHaveTextContent(
    "Prepare Next Phase"
  );
  expect(screen.getByTestId("urgency-badge")).toHaveTextContent("High Urgency");
});

// ---------------------------------------------------------------------------
// Current phase context
// ---------------------------------------------------------------------------

test("renders current phase name when provided", async () => {
  mockGetRecommendations.mockResolvedValue(makeHighDemandRelease());
  render(<ProjectPhasingRecommendationsPanel projectId="proj-2" />);
  await screen.findByTestId("current-phase-context");
  expect(screen.getByTestId("current-phase-context")).toHaveTextContent(
    "Phase 1"
  );
});

// ---------------------------------------------------------------------------
// Inventory stats
// ---------------------------------------------------------------------------

test("renders sold units, available units and sell-through", async () => {
  mockGetRecommendations.mockResolvedValue(makeHighDemandRelease());
  render(<ProjectPhasingRecommendationsPanel projectId="proj-2" />);
  const stats = await screen.findByTestId("inventory-stats");
  expect(stats).toHaveTextContent("9 sold");
  expect(stats).toHaveTextContent("1 available");
  expect(stats).toHaveTextContent("90.0%");
});

// ---------------------------------------------------------------------------
// Reason text
// ---------------------------------------------------------------------------

test("renders reason text", async () => {
  mockGetRecommendations.mockResolvedValue(makeBalanced());
  render(<ProjectPhasingRecommendationsPanel projectId="proj-3" />);
  const reason = await screen.findByTestId("phasing-reason");
  expect(reason).toHaveTextContent("balanced");
});

// ---------------------------------------------------------------------------
// Balanced demand
// ---------------------------------------------------------------------------

test("renders maintain badge for balanced demand", async () => {
  mockGetRecommendations.mockResolvedValue(makeBalanced());
  render(<ProjectPhasingRecommendationsPanel projectId="proj-3" />);
  await screen.findByTestId("phasing-recommendations-panel");
  expect(screen.getByTestId("current-phase-badge")).toHaveTextContent(
    "Maintain Current Release"
  );
});

// ---------------------------------------------------------------------------
// Low demand delay / defer
// ---------------------------------------------------------------------------

test("renders delay and defer badges for low demand", async () => {
  mockGetRecommendations.mockResolvedValue(makeLowDemandDelay());
  render(<ProjectPhasingRecommendationsPanel projectId="proj-4" />);
  await screen.findByTestId("phasing-recommendations-panel");
  expect(screen.getByTestId("current-phase-badge")).toHaveTextContent("Delay Further Release");
  expect(screen.getByTestId("next-phase-badge")).toHaveTextContent("Defer Next Phase");
});

// ---------------------------------------------------------------------------
// No next-phase: not_applicable
// ---------------------------------------------------------------------------

test("renders not applicable when no next phase", async () => {
  mockGetRecommendations.mockResolvedValue(makeBalanced());
  render(<ProjectPhasingRecommendationsPanel projectId="proj-3" />);
  await screen.findByTestId("phasing-recommendations-panel");
  expect(screen.getByTestId("next-phase-card")).toHaveTextContent(
    "No next phase in project structure"
  );
});

// ---------------------------------------------------------------------------
// Read-only: no mutation controls
// ---------------------------------------------------------------------------

test("does not render any mutation controls", async () => {
  mockGetRecommendations.mockResolvedValue(makeHighDemandRelease());
  render(<ProjectPhasingRecommendationsPanel projectId="proj-2" />);
  await screen.findByTestId("phasing-recommendations-panel");
  // No buttons or form elements for releasing/holding/creating phases
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  expect(screen.queryByRole("form")).not.toBeInTheDocument();
});
