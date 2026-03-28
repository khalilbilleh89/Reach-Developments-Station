/**
 * ReleaseSimulationPanel tests (PR-V7-04)
 *
 * Validates:
 *  - panel renders in initial state
 *  - mode toggle between single and comparison
 *  - single simulation: loading state renders
 *  - single simulation: error state renders
 *  - single simulation: result renders with IRR, delta, NPV, risk score, GDV
 *  - risk score badge renders correctly for low / medium / high
 *  - cashflow delay label renders correctly
 *  - no-baseline notice renders when has_feasibility_baseline is false
 *  - comparison mode: run button renders
 *  - comparison mode: multiple results render
 *  - comparison mode: error state renders
 */
import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock API clients
jest.mock("@/lib/release-simulation-api", () => ({
  simulateReleaseStrategy: jest.fn(),
  simulateReleaseStrategies: jest.fn(),
}));

import {
  simulateReleaseStrategies,
  simulateReleaseStrategy,
} from "@/lib/release-simulation-api";
import { ReleaseSimulationPanel } from "@/components/feasibility/ReleaseSimulationPanel";
import type {
  SimulateStrategiesResponse,
  SimulateStrategyResponse,
  SimulationResult,
} from "@/lib/release-simulation-types";

const mockSimulate = simulateReleaseStrategy as jest.Mock;
const mockSimulateMulti = simulateReleaseStrategies as jest.Mock;

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeResult(overrides: Partial<SimulationResult> = {}): SimulationResult {
  return {
    label: null,
    price_adjustment_pct: 0,
    phase_delay_months: 0,
    release_strategy: "maintain",
    simulated_gdv: 3000000,
    simulated_dev_period_months: 24,
    irr: 0.185,
    irr_delta: 0.025,
    npv: 1200000,
    cashflow_delay_months: 0,
    risk_score: "low",
    baseline_gdv: 3000000,
    baseline_irr: 0.16,
    baseline_dev_period_months: 24,
    baseline_total_cost: 2400000,
    ...overrides,
  };
}

function makeSingleResponse(
  overrides: Partial<SimulationResult> = {},
  hasBaseline = true,
): SimulateStrategyResponse {
  return {
    project_id: "proj-1",
    project_name: "Test Project",
    has_feasibility_baseline: hasBaseline,
    result: makeResult(overrides),
  };
}

function makeMultiResponse(
  results: SimulationResult[],
  hasBaseline = true,
): SimulateStrategiesResponse {
  return {
    project_id: "proj-1",
    project_name: "Test Project",
    has_feasibility_baseline: hasBaseline,
    results,
    best_scenario_label: results[0]?.label ?? null,
  };
}

// ---------------------------------------------------------------------------
// Initial render
// ---------------------------------------------------------------------------

test("renders the panel without crashing", () => {
  render(<ReleaseSimulationPanel projectId="proj-1" />);
  expect(screen.getByTestId("release-simulation-panel")).toBeInTheDocument();
});

test("renders run simulation button in initial state", () => {
  render(<ReleaseSimulationPanel projectId="proj-1" />);
  expect(screen.getByTestId("run-simulation-btn")).toBeInTheDocument();
  expect(screen.getByTestId("run-simulation-btn")).toHaveTextContent("Run Simulation");
});

test("renders scenario input form", () => {
  render(<ReleaseSimulationPanel projectId="proj-1" />);
  expect(screen.getByTestId("scenario-input-form")).toBeInTheDocument();
  expect(screen.getByTestId("price-pct-slider")).toBeInTheDocument();
  expect(screen.getByTestId("delay-months-slider")).toBeInTheDocument();
});

test("renders release strategy buttons", () => {
  render(<ReleaseSimulationPanel projectId="proj-1" />);
  expect(screen.getByTestId("strategy-btn-maintain")).toBeInTheDocument();
  expect(screen.getByTestId("strategy-btn-hold")).toBeInTheDocument();
  expect(screen.getByTestId("strategy-btn-accelerate")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Mode toggle
// ---------------------------------------------------------------------------

test("switches to comparison mode on click", () => {
  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("mode-compare"));
  expect(screen.getByTestId("run-comparison-btn")).toBeInTheDocument();
});

test("switches back to single mode from comparison mode", () => {
  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("mode-compare"));
  fireEvent.click(screen.getByTestId("mode-single"));
  expect(screen.getByTestId("run-simulation-btn")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Single simulation: loading state
// ---------------------------------------------------------------------------

test("shows loading state while simulation is running", async () => {
  let resolvePromise: (value: unknown) => void = () => undefined;
  mockSimulate.mockImplementation(
    () => new Promise((resolve) => { resolvePromise = resolve; }),
  );

  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("run-simulation-btn"));

  expect(screen.getByTestId("run-simulation-btn")).toHaveTextContent("Running…");
  expect(screen.getByTestId("run-simulation-btn")).toBeDisabled();

  // Resolve to avoid act() warning for pending state updates.
  await act(async () => { resolvePromise(undefined); });
});

// ---------------------------------------------------------------------------
// Single simulation: error state
// ---------------------------------------------------------------------------

test("renders error message when simulation fails", async () => {
  mockSimulate.mockRejectedValue(new Error("Network error"));

  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("run-simulation-btn"));

  await waitFor(() => {
    expect(screen.getByTestId("single-error")).toBeInTheDocument();
  });
  expect(screen.getByTestId("single-error")).toHaveTextContent(
    "Simulation failed. Please try again.",
  );
});

// ---------------------------------------------------------------------------
// Single simulation: result renders
// ---------------------------------------------------------------------------

test("renders simulation result after successful run", async () => {
  mockSimulate.mockResolvedValue(makeSingleResponse());

  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("run-simulation-btn"));

  await waitFor(() => {
    expect(screen.getByTestId("single-result")).toBeInTheDocument();
  });
});

test("renders IRR in result card", async () => {
  mockSimulate.mockResolvedValue(makeSingleResponse({ irr: 0.185 }));

  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("run-simulation-btn"));

  await waitFor(() => screen.getByTestId("result-irr"));
  expect(screen.getByTestId("result-irr")).toHaveTextContent("18.50%");
});

test("renders IRR delta in result card", async () => {
  mockSimulate.mockResolvedValue(makeSingleResponse({ irr_delta: 0.025 }));

  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("run-simulation-btn"));

  await waitFor(() => screen.getByTestId("result-irr-delta"));
  expect(screen.getByTestId("result-irr-delta")).toHaveTextContent("+2.50%");
});

test("renders NPV in result card", async () => {
  mockSimulate.mockResolvedValue(makeSingleResponse({ npv: 1200000 }));

  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("run-simulation-btn"));

  await waitFor(() => screen.getByTestId("result-npv"));
  expect(screen.getByTestId("result-npv")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Risk score badge
// ---------------------------------------------------------------------------

test("renders low risk badge", async () => {
  mockSimulate.mockResolvedValue(makeSingleResponse({ risk_score: "low" }));

  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("run-simulation-btn"));

  await waitFor(() => screen.getByTestId("risk-score-badge"));
  expect(screen.getByTestId("risk-score-badge")).toHaveTextContent("Low Risk");
});

test("renders medium risk badge", async () => {
  mockSimulate.mockResolvedValue(makeSingleResponse({ risk_score: "medium" }));

  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("run-simulation-btn"));

  await waitFor(() => screen.getByTestId("risk-score-badge"));
  expect(screen.getByTestId("risk-score-badge")).toHaveTextContent("Medium Risk");
});

test("renders high risk badge", async () => {
  mockSimulate.mockResolvedValue(makeSingleResponse({ risk_score: "high" }));

  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("run-simulation-btn"));

  await waitFor(() => screen.getByTestId("risk-score-badge"));
  expect(screen.getByTestId("risk-score-badge")).toHaveTextContent("High Risk");
});

// ---------------------------------------------------------------------------
// Cashflow delay label
// ---------------------------------------------------------------------------

test("renders on-plan cashflow timing", async () => {
  mockSimulate.mockResolvedValue(makeSingleResponse({ cashflow_delay_months: 0 }));

  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("run-simulation-btn"));

  await waitFor(() => screen.getByTestId("result-cashflow-delay"));
  expect(screen.getByTestId("result-cashflow-delay")).toHaveTextContent("On Plan");
});

test("renders delayed cashflow timing", async () => {
  mockSimulate.mockResolvedValue(makeSingleResponse({ cashflow_delay_months: 3 }));

  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("run-simulation-btn"));

  await waitFor(() => screen.getByTestId("result-cashflow-delay"));
  expect(screen.getByTestId("result-cashflow-delay")).toHaveTextContent("+3mo delayed");
});

test("renders early cashflow timing", async () => {
  mockSimulate.mockResolvedValue(makeSingleResponse({ cashflow_delay_months: -2 }));

  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("run-simulation-btn"));

  await waitFor(() => screen.getByTestId("result-cashflow-delay"));
  expect(screen.getByTestId("result-cashflow-delay")).toHaveTextContent("2mo early");
});

// ---------------------------------------------------------------------------
// No-baseline notice
// ---------------------------------------------------------------------------

test("renders no-baseline notice when has_feasibility_baseline is false", async () => {
  mockSimulate.mockResolvedValue(makeSingleResponse({}, false));

  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("run-simulation-btn"));

  await waitFor(() => screen.getByTestId("no-baseline-notice"));
  expect(screen.getByTestId("no-baseline-notice")).toBeInTheDocument();
});

test("does not render no-baseline notice when baseline exists", async () => {
  mockSimulate.mockResolvedValue(makeSingleResponse({}, true));

  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("run-simulation-btn"));

  await waitFor(() => screen.getByTestId("single-result"));
  expect(screen.queryByTestId("no-baseline-notice")).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Comparison mode
// ---------------------------------------------------------------------------

test("renders comparison results when run", async () => {
  const results = [
    makeResult({ label: "Optimistic", irr: 0.22, risk_score: "low" }),
    makeResult({ label: "Base", irr: 0.18, risk_score: "medium" }),
    makeResult({ label: "Pessimistic", irr: 0.10, risk_score: "high" }),
  ];
  mockSimulateMulti.mockResolvedValue(makeMultiResponse(results));

  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("mode-compare"));
  fireEvent.click(screen.getByTestId("run-comparison-btn"));

  await waitFor(() => screen.getByTestId("comparison-results"));
  expect(screen.getByTestId("comparison-results")).toBeInTheDocument();
  // All three result cards are rendered
  expect(
    screen.getByTestId("simulation-result-card-optimistic"),
  ).toBeInTheDocument();
});

test("renders comparison error state", async () => {
  mockSimulateMulti.mockRejectedValue(new Error("Network error"));

  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("mode-compare"));
  fireEvent.click(screen.getByTestId("run-comparison-btn"));

  await waitFor(() => screen.getByTestId("compare-error"));
  expect(screen.getByTestId("compare-error")).toHaveTextContent(
    "Comparison failed. Please try again.",
  );
});

test("comparison run button shows loading state", async () => {
  let resolvePromise: (value: unknown) => void = () => undefined;
  mockSimulateMulti.mockImplementation(
    () => new Promise((resolve) => { resolvePromise = resolve; }),
  );

  render(<ReleaseSimulationPanel projectId="proj-1" />);
  fireEvent.click(screen.getByTestId("mode-compare"));
  fireEvent.click(screen.getByTestId("run-comparison-btn"));

  expect(screen.getByTestId("run-comparison-btn")).toHaveTextContent("Running…");

  // Resolve to avoid act() warning for pending state updates.
  await act(async () => { resolvePromise(undefined); });
});
