/**
 * ConstructionCostContextPanel tests
 *
 * Validates:
 *  - loading state renders
 *  - error state renders
 *  - null context renders fallback error state
 *  - no-project state: note shown, no variance
 *  - no-cost-records state: note shown, assumed cost shown, no variance
 *  - both sides present: variance rendered correctly
 *  - negative variance renders
 *  - zero variance renders
 *  - by-category breakdown renders
 *  - by-stage breakdown renders
 *  - assumed_construction_cost=null renders "Assumptions not yet defined"
 *  - read-only: no buttons or mutation controls
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock format-utils
jest.mock("@/lib/format-utils", () => ({
  formatCurrency: (v: number) => `AED ${v.toLocaleString("en-US")}`,
}));

import ConstructionCostContextPanel from "@/components/feasibility/ConstructionCostContextPanel";
import type { FeasibilityConstructionCostContext } from "@/lib/feasibility-types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const noProjectContext: FeasibilityConstructionCostContext = {
  feasibility_run_id: "run-1",
  project_id: null,
  has_cost_records: false,
  active_record_count: 0,
  recorded_construction_cost_total: null,
  by_category: null,
  by_stage: null,
  assumed_construction_cost: null,
  variance_amount: null,
  variance_pct: null,
  note: "No project linked to this feasibility run.",
};

const noRecordsContext: FeasibilityConstructionCostContext = {
  feasibility_run_id: "run-1",
  project_id: "proj-1",
  has_cost_records: false,
  active_record_count: 0,
  recorded_construction_cost_total: null,
  by_category: null,
  by_stage: null,
  assumed_construction_cost: 800000,
  variance_amount: null,
  variance_pct: null,
  note: "No construction cost records for this project yet.",
};

const noAssumptionsContext: FeasibilityConstructionCostContext = {
  feasibility_run_id: "run-1",
  project_id: "proj-1",
  has_cost_records: true,
  active_record_count: 2,
  recorded_construction_cost_total: "900000.00",
  by_category: { hard_cost: "900000.00" },
  by_stage: { construction: "900000.00" },
  assumed_construction_cost: null,
  variance_amount: null,
  variance_pct: null,
  note: "Construction cost records exist but the feasibility-side cost basis is unavailable.",
};

const fullContext: FeasibilityConstructionCostContext = {
  feasibility_run_id: "run-1",
  project_id: "proj-1",
  has_cost_records: true,
  active_record_count: 3,
  recorded_construction_cost_total: "900000.00",
  by_category: { hard_cost: "700000.00", soft_cost: "200000.00" },
  by_stage: { construction: "600000.00", pre_construction: "300000.00" },
  assumed_construction_cost: 800000,
  variance_amount: "100000.00",
  variance_pct: 0.125,
  note: "Variance shown: recorded construction cost total vs. feasibility-side assumed construction cost.",
};

const negativeVarianceContext: FeasibilityConstructionCostContext = {
  ...fullContext,
  recorded_construction_cost_total: "600000.00",
  variance_amount: "-200000.00",
  variance_pct: -0.25,
};

const zeroVarianceContext: FeasibilityConstructionCostContext = {
  ...fullContext,
  recorded_construction_cost_total: "800000.00",
  variance_amount: "0.00",
  variance_pct: 0,
};

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

test("renders loading state when loading=true", () => {
  render(<ConstructionCostContextPanel context={undefined} loading={true} />);
  expect(
    screen.getByTestId("construction-cost-context-loading"),
  ).toBeInTheDocument();
  expect(screen.getByText(/loading construction cost context/i)).toBeInTheDocument();
});

test("renders loading state when context=undefined", () => {
  render(<ConstructionCostContextPanel context={undefined} />);
  expect(
    screen.getByTestId("construction-cost-context-loading"),
  ).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

test("renders error state when error prop provided", () => {
  render(
    <ConstructionCostContextPanel
      context={noProjectContext}
      error="Failed to load context."
    />,
  );
  expect(
    screen.getByTestId("construction-cost-context-error"),
  ).toBeInTheDocument();
  expect(screen.getByText(/failed to load context/i)).toBeInTheDocument();
});

test("renders error state when context=null", () => {
  render(<ConstructionCostContextPanel context={null} />);
  expect(
    screen.getByTestId("construction-cost-context-error"),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/construction cost context is currently unavailable/i),
  ).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// No-project state
// ---------------------------------------------------------------------------

test("renders panel with note when no project linked", () => {
  render(<ConstructionCostContextPanel context={noProjectContext} />);
  expect(
    screen.getByTestId("construction-cost-context-panel"),
  ).toBeInTheDocument();
  expect(
    screen.getByTestId("construction-cost-context-note"),
  ).toHaveTextContent("No project linked to this feasibility run.");
  // No variance rows
  expect(screen.queryByTestId("variance-amount")).not.toBeInTheDocument();
  expect(screen.queryByTestId("variance-pct")).not.toBeInTheDocument();
  // Active record count shows 0
  expect(screen.getByTestId("active-record-count")).toHaveTextContent("0");
});

// ---------------------------------------------------------------------------
// No-records state
// ---------------------------------------------------------------------------

test("renders assumed cost and note when no cost records but assumptions exist", () => {
  render(<ConstructionCostContextPanel context={noRecordsContext} />);
  expect(
    screen.getByTestId("construction-cost-context-note"),
  ).toHaveTextContent("No construction cost records for this project yet.");
  expect(screen.getByTestId("assumed-construction-cost")).toHaveTextContent(
    "800,000",
  );
  // No variance
  expect(screen.queryByTestId("variance-amount")).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// No-assumptions state
// ---------------------------------------------------------------------------

test("renders 'Assumptions not yet defined' when assumed_construction_cost is null", () => {
  render(<ConstructionCostContextPanel context={noAssumptionsContext} />);
  expect(screen.getByTestId("assumed-construction-cost")).toHaveTextContent(
    "Assumptions not yet defined",
  );
  expect(screen.getByTestId("active-record-count")).toHaveTextContent("2");
  // No variance
  expect(screen.queryByTestId("variance-amount")).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Full context — variance displayed
// ---------------------------------------------------------------------------

test("renders full context with variance when both sides present", () => {
  render(<ConstructionCostContextPanel context={fullContext} />);

  expect(screen.getByTestId("recorded-construction-cost")).toBeInTheDocument();
  expect(screen.getByTestId("assumed-construction-cost")).toHaveTextContent(
    "800,000",
  );
  expect(screen.getByTestId("variance-amount")).toBeInTheDocument();
  expect(screen.getByTestId("variance-pct")).toHaveTextContent("+12.50%");
});

test("renders negative variance correctly", () => {
  render(<ConstructionCostContextPanel context={negativeVarianceContext} />);
  expect(screen.getByTestId("variance-pct")).toHaveTextContent("-25.00%");
});

test("renders zero variance correctly", () => {
  render(<ConstructionCostContextPanel context={zeroVarianceContext} />);
  expect(screen.getByTestId("variance-pct")).toHaveTextContent("+0.00%");
});

// ---------------------------------------------------------------------------
// Grouped breakdowns
// ---------------------------------------------------------------------------

test("renders by-category breakdown when has_cost_records=true", () => {
  render(<ConstructionCostContextPanel context={fullContext} />);
  expect(screen.getByTestId("by-category-breakdown")).toBeInTheDocument();
  // Check category names rendered (underscores replaced with spaces)
  expect(screen.getByText("hard cost")).toBeInTheDocument();
  expect(screen.getByText("soft cost")).toBeInTheDocument();
});

test("renders by-stage breakdown when has_cost_records=true", () => {
  render(<ConstructionCostContextPanel context={fullContext} />);
  expect(screen.getByTestId("by-stage-breakdown")).toBeInTheDocument();
  expect(screen.getByText("construction")).toBeInTheDocument();
  expect(screen.getByText("pre construction")).toBeInTheDocument();
});

test("does not render by-category breakdown when has_cost_records=false", () => {
  render(<ConstructionCostContextPanel context={noRecordsContext} />);
  expect(screen.queryByTestId("by-category-breakdown")).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Read-only: no mutation controls
// ---------------------------------------------------------------------------

test("panel contains no form inputs or submit buttons", () => {
  render(<ConstructionCostContextPanel context={fullContext} />);
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(screen.queryByRole("form")).not.toBeInTheDocument();
});
