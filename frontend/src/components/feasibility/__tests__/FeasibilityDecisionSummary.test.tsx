/**
 * FeasibilityDecisionSummary tests
 *
 * Validates standalone component behaviour:
 *  - correct label mapping: VIABLE→Proceed, MARGINAL→Review, NOT_VIABLE→Do Not Proceed
 *  - correct viability label mapping
 *  - correct risk level label mapping (MEDIUM→Moderate)
 *  - "Decision not available" fallback when all decision fields are null
 *  - partial data: decision only (viability + risk null → "—")
 *  - accessibility: role="region" + aria-label present on both branches
 *
 * Integration coverage (decision summary rendered inside FeasibilityRunDetailView)
 * lives in FeasibilityRunDetailView.test.tsx.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import FeasibilityDecisionSummary from "@/components/feasibility/FeasibilityDecisionSummary";
import type { FeasibilityResult } from "@/lib/feasibility-types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeResult(
  overrides: Partial<
    Pick<FeasibilityResult, "decision" | "viability_status" | "risk_level">
  > = {},
): Pick<FeasibilityResult, "decision" | "viability_status" | "risk_level"> {
  return {
    decision: "VIABLE",
    viability_status: "VIABLE",
    risk_level: "LOW",
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Decision label mapping
// ---------------------------------------------------------------------------

test("renders Proceed label for VIABLE decision", () => {
  render(<FeasibilityDecisionSummary result={makeResult({ decision: "VIABLE" })} />);
  expect(screen.getByTestId("decision-value")).toHaveTextContent("Proceed");
});

test("renders Review label for MARGINAL decision", () => {
  render(<FeasibilityDecisionSummary result={makeResult({ decision: "MARGINAL" })} />);
  expect(screen.getByTestId("decision-value")).toHaveTextContent("Review");
});

test("renders Do Not Proceed label for NOT_VIABLE decision", () => {
  render(<FeasibilityDecisionSummary result={makeResult({ decision: "NOT_VIABLE" })} />);
  expect(screen.getByTestId("decision-value")).toHaveTextContent("Do Not Proceed");
});

// ---------------------------------------------------------------------------
// Viability label mapping
// ---------------------------------------------------------------------------

test("renders Viable for VIABLE viability_status", () => {
  render(<FeasibilityDecisionSummary result={makeResult({ viability_status: "VIABLE" })} />);
  expect(screen.getByTestId("viability-value")).toHaveTextContent("Viable");
});

test("renders Marginal for MARGINAL viability_status", () => {
  render(
    <FeasibilityDecisionSummary
      result={makeResult({ decision: "MARGINAL", viability_status: "MARGINAL" })}
    />,
  );
  expect(screen.getByTestId("viability-value")).toHaveTextContent("Marginal");
});

test("renders Not Viable for NOT_VIABLE viability_status", () => {
  render(
    <FeasibilityDecisionSummary
      result={makeResult({ decision: "NOT_VIABLE", viability_status: "NOT_VIABLE" })}
    />,
  );
  expect(screen.getByTestId("viability-value")).toHaveTextContent("Not Viable");
});

// ---------------------------------------------------------------------------
// Risk level label mapping
// ---------------------------------------------------------------------------

test("renders Low for LOW risk_level", () => {
  render(<FeasibilityDecisionSummary result={makeResult({ risk_level: "LOW" })} />);
  expect(screen.getByTestId("risk-value")).toHaveTextContent("Low");
});

test("renders Moderate for MEDIUM risk_level", () => {
  render(<FeasibilityDecisionSummary result={makeResult({ risk_level: "MEDIUM" })} />);
  expect(screen.getByTestId("risk-value")).toHaveTextContent("Moderate");
});

test("renders High for HIGH risk_level", () => {
  render(
    <FeasibilityDecisionSummary
      result={makeResult({ decision: "NOT_VIABLE", viability_status: "NOT_VIABLE", risk_level: "HIGH" })}
    />,
  );
  expect(screen.getByTestId("risk-value")).toHaveTextContent("High");
});

// ---------------------------------------------------------------------------
// Fallback — all null
// ---------------------------------------------------------------------------

test("renders 'Decision not available' when all fields are null", () => {
  render(
    <FeasibilityDecisionSummary
      result={{ decision: null, viability_status: null, risk_level: null }}
    />,
  );
  expect(screen.getByText(/decision not available/i)).toBeInTheDocument();
  expect(screen.queryByTestId("decision-value")).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Partial data — decision present but viability/risk null
// ---------------------------------------------------------------------------

test("renders dash placeholders when viability and risk are null", () => {
  render(
    <FeasibilityDecisionSummary
      result={{ decision: "VIABLE", viability_status: null, risk_level: null }}
    />,
  );
  expect(screen.getByTestId("decision-value")).toHaveTextContent("Proceed");
  expect(screen.getByTestId("viability-value")).toHaveTextContent("—");
  expect(screen.getByTestId("risk-value")).toHaveTextContent("—");
});

// ---------------------------------------------------------------------------
// Accessibility — aria-label
// ---------------------------------------------------------------------------

test("renders with accessible aria-label", () => {
  render(<FeasibilityDecisionSummary result={makeResult()} />);
  expect(
    screen.getByRole("region", { name: /investment decision summary/i }),
  ).toBeInTheDocument();
});

test("renders fallback with accessible aria-label", () => {
  render(
    <FeasibilityDecisionSummary
      result={{ decision: null, viability_status: null, risk_level: null }}
    />,
  );
  expect(
    screen.getByRole("region", { name: /investment decision summary/i }),
  ).toBeInTheDocument();
});

