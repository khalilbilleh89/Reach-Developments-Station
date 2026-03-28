/**
 * StrategyPanel tests (PR-V7-05)
 *
 * Validates:
 *  - panel renders without crashing
 *  - loading state renders
 *  - error state renders
 *  - best strategy card renders with all required fields
 *  - price adjustment displays correctly
 *  - phase delay displays correctly
 *  - release strategy displays correctly
 *  - IRR displays correctly
 *  - risk score badge renders
 *  - reason text renders
 *  - top strategies list renders
 *  - no-baseline notice renders when has_feasibility_baseline is false
 *  - no-strategy-available renders when best_strategy is null
 *  - scenario count renders
 */
import React from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock API client
jest.mock("@/lib/strategy-api", () => ({
  getRecommendedStrategy: jest.fn(),
}));

// Mock format-utils
jest.mock("@/lib/format-utils", () => ({
  formatCurrency: (v: number) => `AED ${v.toLocaleString("en-US")}`,
}));

import { getRecommendedStrategy } from "@/lib/strategy-api";
import { StrategyPanel } from "@/components/strategy/StrategyPanel";
import type {
  RecommendedStrategyResponse,
} from "@/lib/strategy-types";
import type { SimulationResult } from "@/lib/release-simulation-types";

const mockGetStrategy = getRecommendedStrategy as jest.Mock;

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeResult(overrides: Partial<SimulationResult> = {}): SimulationResult {
  return {
    label: "+8% / 0mo / accelerate",
    price_adjustment_pct: 8,
    phase_delay_months: 0,
    release_strategy: "accelerate",
    simulated_gdv: 3240000,
    simulated_dev_period_months: 22,
    irr: 0.21,
    irr_delta: 0.05,
    npv: 1400000,
    cashflow_delay_months: -2,
    risk_score: "low",
    baseline_gdv: 3000000,
    baseline_irr: 0.16,
    baseline_dev_period_months: 24,
    baseline_total_cost: 2400000,
    ...overrides,
  };
}

function makeResponse(
  overrides: Partial<RecommendedStrategyResponse> = {},
): RecommendedStrategyResponse {
  const best = makeResult();
  return {
    project_id: "proj-1",
    project_name: "Test Project",
    has_feasibility_baseline: true,
    best_strategy: best,
    top_strategies: [best, makeResult({ irr: 0.19, risk_score: "medium" })],
    reason: "Best strategy: accelerate release with +8% price adjustment.",
    generated_scenario_count: 20,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Initial render
// ---------------------------------------------------------------------------

test("renders the panel without crashing", async () => {
  mockGetStrategy.mockResolvedValueOnce(makeResponse());
  await act(async () => {
    render(<StrategyPanel projectId="proj-1" />);
  });
  expect(screen.getByTestId("strategy-panel")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

test("renders loading state initially", () => {
  mockGetStrategy.mockReturnValue(new Promise(() => {}));
  render(<StrategyPanel projectId="proj-1" />);
  expect(screen.getByTestId("strategy-loading")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

test("renders error state on API failure", async () => {
  mockGetStrategy.mockRejectedValueOnce(new Error("Network error"));
  render(<StrategyPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("strategy-error")).toBeInTheDocument();
  });
  expect(screen.getByTestId("strategy-error")).toHaveTextContent("Network error");
});

// ---------------------------------------------------------------------------
// Best strategy card
// ---------------------------------------------------------------------------

test("renders best strategy card with required fields", async () => {
  mockGetStrategy.mockResolvedValueOnce(makeResponse());
  render(<StrategyPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("best-strategy-card")).toBeInTheDocument();
  });

  const card = screen.getByTestId("best-strategy-card");
  expect(card).toBeInTheDocument();
});

test("renders price adjustment in best strategy", async () => {
  mockGetStrategy.mockResolvedValueOnce(makeResponse());
  render(<StrategyPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("best-strategy-card")).toBeInTheDocument();
  });
  const card = screen.getByTestId("best-strategy-card");
  expect(card.querySelector("[data-testid='price-adjustment']")).toBeInTheDocument();
});

test("renders phase delay in best strategy", async () => {
  mockGetStrategy.mockResolvedValueOnce(makeResponse());
  render(<StrategyPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("best-strategy-card")).toBeInTheDocument();
  });
  const card = screen.getByTestId("best-strategy-card");
  expect(card.querySelector("[data-testid='phase-delay']")).toBeInTheDocument();
});

test("renders release strategy in best strategy", async () => {
  mockGetStrategy.mockResolvedValueOnce(makeResponse());
  render(<StrategyPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("best-strategy-card")).toBeInTheDocument();
  });
  const card = screen.getByTestId("best-strategy-card");
  const strategyEl = card.querySelector("[data-testid='release-strategy']");
  expect(strategyEl).toBeInTheDocument();
  expect(strategyEl).toHaveTextContent("Accelerate");
});

test("renders simulated IRR in best strategy", async () => {
  mockGetStrategy.mockResolvedValueOnce(makeResponse());
  render(<StrategyPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("best-strategy-card")).toBeInTheDocument();
  });
  const card = screen.getByTestId("best-strategy-card");
  const irrEl = card.querySelector("[data-testid='simulated-irr']");
  expect(irrEl).toBeInTheDocument();
  expect(irrEl).toHaveTextContent("21.00%");
});

test("renders risk score badge in best strategy", async () => {
  mockGetStrategy.mockResolvedValueOnce(makeResponse());
  render(<StrategyPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("best-strategy-card")).toBeInTheDocument();
  });
  const card = screen.getByTestId("best-strategy-card");
  const riskEl = card.querySelector("[data-testid='risk-score']");
  expect(riskEl).toBeInTheDocument();
  expect(riskEl).toHaveTextContent("Low Risk");
});

// ---------------------------------------------------------------------------
// Reason text
// ---------------------------------------------------------------------------

test("renders reason text", async () => {
  mockGetStrategy.mockResolvedValueOnce(makeResponse());
  render(<StrategyPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("strategy-reason")).toBeInTheDocument();
  });
  expect(screen.getByTestId("strategy-reason")).toHaveTextContent(
    "Best strategy: accelerate release with +8% price adjustment.",
  );
});

// ---------------------------------------------------------------------------
// Top strategies list
// ---------------------------------------------------------------------------

test("renders top strategies list", async () => {
  mockGetStrategy.mockResolvedValueOnce(makeResponse());
  render(<StrategyPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("top-strategies-list")).toBeInTheDocument();
  });
  const list = screen.getByTestId("top-strategies-list");
  expect(list.children.length).toBeGreaterThanOrEqual(1);
});

// ---------------------------------------------------------------------------
// No-baseline notice
// ---------------------------------------------------------------------------

test("renders no-baseline notice when has_feasibility_baseline is false", async () => {
  mockGetStrategy.mockResolvedValueOnce(
    makeResponse({ has_feasibility_baseline: false }),
  );
  render(<StrategyPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("no-baseline-notice")).toBeInTheDocument();
  });
});

test("does not render no-baseline notice when baseline exists", async () => {
  mockGetStrategy.mockResolvedValueOnce(makeResponse({ has_feasibility_baseline: true }));
  render(<StrategyPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("best-strategy-card")).toBeInTheDocument();
  });
  expect(screen.queryByTestId("no-baseline-notice")).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// No strategy available state
// ---------------------------------------------------------------------------

test("renders no-strategy-available when best_strategy is null", async () => {
  mockGetStrategy.mockResolvedValueOnce(
    makeResponse({ best_strategy: null, top_strategies: [] }),
  );
  render(<StrategyPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("no-strategy-available")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Scenario count
// ---------------------------------------------------------------------------

test("renders generated scenario count", async () => {
  mockGetStrategy.mockResolvedValueOnce(makeResponse({ generated_scenario_count: 20 }));
  render(<StrategyPanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByText("20 scenarios evaluated")).toBeInTheDocument();
  });
});
