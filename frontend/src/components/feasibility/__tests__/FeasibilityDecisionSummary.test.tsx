/**
 * FeasibilityDecisionSummary tests
 *
 * Validates:
 *  - decision block renders for a fully-populated result
 *  - correct label mapping: VIABLE→PROCEED, MARGINAL→REVIEW, NOT_VIABLE→REJECT
 *  - correct viability label mapping
 *  - correct risk level label mapping (MEDIUM→Moderate)
 *  - "Decision not available" fallback when all decision fields are null
 *  - partial data: decision only (viability + risk null → "—")
 *  - integration: FeasibilityDecisionSummary is rendered above KPI panel in
 *    FeasibilityRunDetailView when results are present
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
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

test("renders PROCEED label for VIABLE decision", () => {
  render(<FeasibilityDecisionSummary result={makeResult({ decision: "VIABLE" })} />);
  expect(screen.getByTestId("decision-value")).toHaveTextContent("PROCEED");
});

test("renders REVIEW label for MARGINAL decision", () => {
  render(<FeasibilityDecisionSummary result={makeResult({ decision: "MARGINAL" })} />);
  expect(screen.getByTestId("decision-value")).toHaveTextContent("REVIEW");
});

test("renders REJECT label for NOT_VIABLE decision", () => {
  render(<FeasibilityDecisionSummary result={makeResult({ decision: "NOT_VIABLE" })} />);
  expect(screen.getByTestId("decision-value")).toHaveTextContent("REJECT");
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
  expect(screen.getByTestId("decision-value")).toHaveTextContent("PROCEED");
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

// ---------------------------------------------------------------------------
// Integration — decision summary appears in FeasibilityRunDetailView
// ---------------------------------------------------------------------------

let mockSearchParams = new URLSearchParams("runId=run-1");
const mockRouterPush = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockRouterPush }),
  usePathname: () => "/feasibility",
  useSearchParams: () => mockSearchParams,
}));

jest.mock("next/link", () => {
  const MockLink = ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
  MockLink.displayName = "MockLink";
  return MockLink;
});

jest.mock("@/components/shell/PageContainer.module.css", () => ({}));

jest.mock("@/lib/format-utils", () => ({
  formatCurrency: (v: number) => `AED ${v.toLocaleString()}`,
}));

jest.mock("@/lib/api-client", () => ({
  apiFetch: jest.fn(),
  ApiError: class ApiError extends Error {
    constructor(
      message: string,
      public readonly status: number,
    ) {
      super(message);
      this.name = "ApiError";
    }
  },
}));

jest.mock("@/lib/feasibility-api", () => ({
  getFeasibilityRun: jest.fn(),
  getFeasibilityAssumptions: jest.fn(),
  upsertFeasibilityAssumptions: jest.fn(),
  patchFeasibilityAssumptions: jest.fn(),
  calculateFeasibility: jest.fn(),
  getFeasibilityResults: jest.fn(),
  assignProjectToRun: jest.fn(),
  getFeasibilityRunLineage: jest.fn(),
  deleteFeasibilityRun: jest.fn(),
}));

jest.mock("@/lib/concept-design-api", () => ({
  createConceptFromFeasibility: jest.fn(),
}));

jest.mock("@/lib/projects-api", () => ({
  listProjects: jest.fn(),
}));

jest.mock("@/components/shell/PageContainer", () => ({
  PageContainer: ({
    title,
    children,
  }: {
    title: string;
    children: React.ReactNode;
  }) => (
    <div>
      <h1>{title}</h1>
      {children}
    </div>
  ),
}));

import {
  getFeasibilityRun,
  getFeasibilityAssumptions,
  getFeasibilityResults,
  getFeasibilityRunLineage,
} from "@/lib/feasibility-api";
import { listProjects } from "@/lib/projects-api";
import FeasibilityRunDetailView from "@/components/feasibility/FeasibilityRunDetailView";

const mockGetRun = getFeasibilityRun as jest.Mock;
const mockGetAssumptions = getFeasibilityAssumptions as jest.Mock;
const mockGetResults = getFeasibilityResults as jest.Mock;
const mockGetLineage = getFeasibilityRunLineage as jest.Mock;
const mockListProjects = listProjects as jest.Mock;

const mockRun = {
  id: "run-1",
  project_id: null,
  project_name: null,
  scenario_id: null,
  scenario_name: "Base Case Q1",
  scenario_type: "base" as const,
  notes: null,
  source_concept_option_id: null,
  seed_source_type: null,
  status: "calculated" as const,
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

const mockAssumptions = {
  id: "asm-1",
  run_id: "run-1",
  sellable_area_sqm: 1000,
  avg_sale_price_per_sqm: 3000,
  construction_cost_per_sqm: 800,
  soft_cost_ratio: 0.1,
  finance_cost_ratio: 0.05,
  sales_cost_ratio: 0.03,
  development_period_months: 24,
  notes: null,
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

const mockResult: FeasibilityResult = {
  id: "res-1",
  run_id: "run-1",
  gdv: 3000000,
  construction_cost: 800000,
  soft_cost: 80000,
  finance_cost: 50000,
  sales_cost: 30000,
  total_cost: 960000,
  developer_profit: 2040000,
  profit_margin: 0.68,
  irr_estimate: 0.42,
  irr: 0.38,
  equity_multiple: 4.125,
  break_even_price: 960,
  break_even_units: 320,
  scenario_outputs: null,
  viability_status: "VIABLE",
  risk_level: "LOW",
  decision: "VIABLE",
  payback_period: 2.0,
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

beforeEach(() => {
  jest.clearAllMocks();
  mockSearchParams = new URLSearchParams("runId=run-1");
  mockListProjects.mockResolvedValue({ items: [], total: 0 });
  mockGetLineage.mockResolvedValue({
    record_type: "feasibility_run",
    record_id: "run-1",
    source_concept_option_id: null,
    reverse_seeded_concept_options: [],
    project_id: null,
  });
});

test("decision summary is rendered in detail view when results are present", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockResolvedValue(mockResult);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(
      screen.getByRole("region", { name: /investment decision summary/i }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("decision-value")).toHaveTextContent("PROCEED");
  });
});

test("decision summary is not rendered in detail view when no results", async () => {
  const { ApiError } = jest.requireMock("@/lib/api-client");
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockRejectedValue(new ApiError("Not Found", 404));

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByText(/no results yet/i)).toBeInTheDocument();
  });

  expect(
    screen.queryByRole("region", { name: /investment decision summary/i }),
  ).not.toBeInTheDocument();
});
