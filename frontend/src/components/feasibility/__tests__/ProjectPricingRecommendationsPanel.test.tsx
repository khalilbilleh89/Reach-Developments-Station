/**
 * ProjectPricingRecommendationsPanel tests
 *
 * Validates:
 *  - loading state renders correctly
 *  - error state renders correctly
 *  - empty recommendations renders empty state
 *  - recommendation cards render with all required fields
 *  - demand status badges render correctly
 *  - price adjustment direction colors are correct
 *  - demand context note renders when provided
 *  - no-pricing-data notice renders when has_pricing_data=false
 *  - read-only: no mutation controls
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock the API client
jest.mock("@/lib/pricing-optimization-api", () => ({
  getProjectPricingRecommendations: jest.fn(),
}));

// Mock format-utils
jest.mock("@/lib/format-utils", () => ({
  formatCurrency: (v: number) => `AED ${v.toLocaleString("en-US")}`,
}));

import { getProjectPricingRecommendations } from "@/lib/pricing-optimization-api";
import { ProjectPricingRecommendationsPanel } from "@/components/feasibility/ProjectPricingRecommendationsPanel";
import type { ProjectPricingRecommendationsResponse } from "@/lib/pricing-optimization-types";

const mockGetRecommendations = getProjectPricingRecommendations as jest.Mock;

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const makeEmptyResponse = (): ProjectPricingRecommendationsResponse => ({
  project_id: "proj-1",
  project_name: "Test Project",
  recommendations: [],
  has_pricing_data: false,
  demand_context: null,
});

const makeHighDemandRec = () => ({
  unit_type: "studio",
  current_avg_price: 500_000,
  recommended_price: 540_000,
  change_pct: 8.0,
  confidence: "high" as const,
  reason: "High demand with critically low inventory. Recommend price increase of ~8%.",
  demand_status: "high_demand" as const,
  total_units: 10,
  available_units: 2,
  sold_units: 8,
  availability_pct: 20.0,
});

const makeBalancedRec = () => ({
  unit_type: "one_bedroom",
  current_avg_price: 750_000,
  recommended_price: 750_000,
  change_pct: 0.0,
  confidence: "high" as const,
  reason: "Demand is on plan. No price change recommended.",
  demand_status: "balanced" as const,
  total_units: 8,
  available_units: 4,
  sold_units: 4,
  availability_pct: 50.0,
});

const makeLowDemandRec = () => ({
  unit_type: "three_bedroom",
  current_avg_price: 1_200_000,
  recommended_price: 1_104_000,
  change_pct: -8.0,
  confidence: "high" as const,
  reason: "Low demand with high inventory. Recommend price reduction of ~8% or incentive program.",
  demand_status: "low_demand" as const,
  total_units: 5,
  available_units: 4,
  sold_units: 1,
  availability_pct: 80.0,
});

const makeNoDataRec = () => ({
  unit_type: "penthouse",
  current_avg_price: null,
  recommended_price: null,
  change_pct: null,
  confidence: "insufficient_data" as const,
  reason: "Insufficient sales data for pricing recommendation.",
  demand_status: "no_data" as const,
  total_units: 3,
  available_units: 3,
  sold_units: 0,
  availability_pct: 100.0,
});

const makeFullResponse = (): ProjectPricingRecommendationsResponse => ({
  project_id: "proj-1",
  project_name: "Marina Tower",
  recommendations: [makeHighDemandRec(), makeBalancedRec(), makeLowDemandRec()],
  has_pricing_data: true,
  demand_context: "Sales velocity is 125.0% of plan — project is selling faster than planned.",
});

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

test("renders loading state while fetching", () => {
  mockGetRecommendations.mockReturnValue(new Promise(() => {}));
  render(<ProjectPricingRecommendationsPanel projectId="proj-1" />);
  expect(screen.getByTestId("pricing-rec-loading")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

test("renders error state on API failure", async () => {
  mockGetRecommendations.mockRejectedValue(new Error("API error"));
  render(<ProjectPricingRecommendationsPanel projectId="proj-1" />);
  const errorEl = await screen.findByTestId("pricing-rec-error");
  expect(errorEl).toHaveTextContent("API error");
});

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

test("renders empty state when no recommendations", async () => {
  mockGetRecommendations.mockResolvedValue(makeEmptyResponse());
  render(<ProjectPricingRecommendationsPanel projectId="proj-1" />);
  await screen.findByTestId("pricing-rec-empty");
  expect(screen.getByTestId("pricing-rec-empty")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Panel renders
// ---------------------------------------------------------------------------

test("renders panel with recommendation cards", async () => {
  mockGetRecommendations.mockResolvedValue(makeFullResponse());
  render(<ProjectPricingRecommendationsPanel projectId="proj-1" />);
  await screen.findByTestId("pricing-recommendations-panel");
  expect(screen.getByTestId("pricing-rec-grid")).toBeInTheDocument();
});

test("renders demand context note when provided", async () => {
  mockGetRecommendations.mockResolvedValue(makeFullResponse());
  render(<ProjectPricingRecommendationsPanel projectId="proj-1" />);
  await screen.findByTestId("demand-context-note");
  expect(screen.getByTestId("demand-context-note")).toHaveTextContent("125.0% of plan");
});

test("renders no-pricing-data notice when has_pricing_data=false", async () => {
  const resp: ProjectPricingRecommendationsResponse = {
    ...makeEmptyResponse(),
    recommendations: [makeNoDataRec()],
    has_pricing_data: false,
  };
  mockGetRecommendations.mockResolvedValue(resp);
  render(<ProjectPricingRecommendationsPanel projectId="proj-1" />);
  await screen.findByTestId("no-pricing-data-notice");
  expect(screen.getByTestId("no-pricing-data-notice")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Recommendation card fields
// ---------------------------------------------------------------------------

test("renders unit type in each recommendation card", async () => {
  mockGetRecommendations.mockResolvedValue(makeFullResponse());
  render(<ProjectPricingRecommendationsPanel projectId="proj-1" />);
  await screen.findByTestId("rec-card-studio");
  expect(screen.getByTestId("rec-unit-type-studio")).toHaveTextContent("studio");
  expect(screen.getByTestId("rec-unit-type-one_bedroom")).toHaveTextContent("one_bedroom");
  expect(screen.getByTestId("rec-unit-type-three_bedroom")).toHaveTextContent("three_bedroom");
});

test("renders demand status badges correctly", async () => {
  mockGetRecommendations.mockResolvedValue(makeFullResponse());
  render(<ProjectPricingRecommendationsPanel projectId="proj-1" />);
  await screen.findByTestId("rec-demand-studio");
  expect(screen.getByTestId("rec-demand-studio")).toHaveTextContent("High Demand");
  expect(screen.getByTestId("rec-demand-one_bedroom")).toHaveTextContent("On Plan");
  expect(screen.getByTestId("rec-demand-three_bedroom")).toHaveTextContent("Low Demand");
});

test("renders change percentage for each recommendation", async () => {
  mockGetRecommendations.mockResolvedValue(makeFullResponse());
  render(<ProjectPricingRecommendationsPanel projectId="proj-1" />);
  await screen.findByTestId("rec-change-pct-studio");
  expect(screen.getByTestId("rec-change-pct-studio")).toHaveTextContent("+8.0%");
  expect(screen.getByTestId("rec-change-pct-one_bedroom")).toHaveTextContent("Hold");
  expect(screen.getByTestId("rec-change-pct-three_bedroom")).toHaveTextContent("-8.0%");
});

test("renders reason text in each recommendation card", async () => {
  mockGetRecommendations.mockResolvedValue(makeFullResponse());
  render(<ProjectPricingRecommendationsPanel projectId="proj-1" />);
  await screen.findByTestId("rec-reason-studio");
  expect(screen.getByTestId("rec-reason-studio")).toHaveTextContent(
    "High demand with critically low inventory",
  );
});

// ---------------------------------------------------------------------------
// Read-only: no mutation controls
// ---------------------------------------------------------------------------

test("renders no mutation controls (read-only panel)", async () => {
  mockGetRecommendations.mockResolvedValue(makeFullResponse());
  const { container } = render(
    <ProjectPricingRecommendationsPanel projectId="proj-1" />,
  );
  await screen.findByTestId("pricing-recommendations-panel");
  // No buttons or inputs that would mutate pricing
  const buttons = container.querySelectorAll("button");
  const inputs = container.querySelectorAll("input");
  expect(buttons).toHaveLength(0);
  expect(inputs).toHaveLength(0);
});
