/**
 * FeasibilityRunDetailView tests
 *
 * Validates:
 *  - loading state
 *  - run detail renders correctly from query param
 *  - source summary displays run metadata
 *  - assumptions form pre-populates seeded values
 *  - calculate button is disabled when no assumptions exist
 *  - results panel renders KPIs after calculation
 *  - error state displays on backend failure
 *  - no-runId state shows a safe message
 *  - numeric validation: Infinity, pasted out-of-range ratios, decimal dev period
 *  - stale state cleared when runId changes
 */
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock Next.js navigation — useSearchParams provides ?runId=run-1
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

// Mock CSS modules
jest.mock("@/components/shell/PageContainer.module.css", () => ({}));

// Mock format-utils
jest.mock("@/lib/format-utils", () => {
  const currencyFormatter = new Intl.NumberFormat("en-US");
  return {
    formatCurrency: (v: number) => `AED ${currencyFormatter.format(v)}`,
  };
});

// Mock api-client — expose ApiError for 404 simulation
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

// Mock feasibility-api
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

// Mock concept-design-api — reverse-seeding
jest.mock("@/lib/concept-design-api", () => ({
  createConceptFromFeasibility: jest.fn(),
}));

// Mock projects-api
jest.mock("@/lib/projects-api", () => ({
  listProjects: jest.fn(),
}));

// Mock PageContainer
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
  upsertFeasibilityAssumptions,
  patchFeasibilityAssumptions,
  calculateFeasibility,
  getFeasibilityResults,
  assignProjectToRun,
  getFeasibilityRunLineage,
  deleteFeasibilityRun,
} from "@/lib/feasibility-api";
import { createConceptFromFeasibility } from "@/lib/concept-design-api";
import { listProjects } from "@/lib/projects-api";
import { ApiError } from "@/lib/api-client";
import FeasibilityRunDetailView from "@/components/feasibility/FeasibilityRunDetailView";

const mockGetRun = getFeasibilityRun as jest.Mock;
const mockGetAssumptions = getFeasibilityAssumptions as jest.Mock;
const mockUpsertAssumptions = upsertFeasibilityAssumptions as jest.Mock;
const mockPatchAssumptions = patchFeasibilityAssumptions as jest.Mock;
const mockCalculate = calculateFeasibility as jest.Mock;
const mockGetResults = getFeasibilityResults as jest.Mock;
const mockAssignProject = assignProjectToRun as jest.Mock;
const mockListProjects = listProjects as jest.Mock;
const mockCreateConcept = createConceptFromFeasibility as jest.Mock;
const mockGetLineage = getFeasibilityRunLineage as jest.Mock;
const mockDeleteRun = deleteFeasibilityRun as jest.Mock;

/** Helper to create a mocked ApiError with a given status code. */
function mockApiError(message: string, status: number): Error {
  return new (ApiError as unknown as new (msg: string, status: number) => Error)(message, status);
}

const mock404 = () => mockApiError("Not Found", 404);

const mockRun = {
  id: "run-1",
  project_id: null,
  project_name: null,
  scenario_id: null,
  scenario_name: "Base Case Q1",
  scenario_type: "base" as const,
  notes: "Test run notes",
  source_concept_option_id: null,
  seed_source_type: null,
  status: "draft" as const,
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

const mockResult = {
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
  profit_per_sqm: 2040,
  scenario_outputs: null,
  viability_status: "VIABLE" as const,
  risk_level: "LOW" as const,
  decision: "VIABLE" as const,
  payback_period: 2.0,
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

/** Reusable mock project for project-linkage tests. */
const mockProject = {
  id: "proj-1",
  name: "Harbour Tower",
  code: "HT-01",
  developer_name: null,
  location: null,
  start_date: null,
  target_end_date: null,
  status: "pipeline",
  description: null,
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

// ---------------------------------------------------------------------------
// Loading and error states
// ---------------------------------------------------------------------------

test("renders loading state initially", () => {
  mockGetRun.mockReturnValue(new Promise(() => {}));
  mockGetAssumptions.mockReturnValue(new Promise(() => {}));
  mockGetResults.mockReturnValue(new Promise(() => {}));
  mockListProjects.mockReturnValue(new Promise(() => {}));

  render(<FeasibilityRunDetailView />);
  expect(screen.getByText(/loading feasibility run/i)).toBeInTheDocument();
});

test("renders error state when run fetch fails", async () => {
  mockGetRun.mockRejectedValue(new Error("Network error"));
  mockGetAssumptions.mockRejectedValue(new Error("Network error"));
  mockGetResults.mockRejectedValue(new Error("Network error"));

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/network error/i)).toBeInTheDocument();
  });
});

test("renders safe message when no runId is provided", async () => {
  mockSearchParams = new URLSearchParams("");

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByText(/no run id provided/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Source summary
// ---------------------------------------------------------------------------

test("renders run source summary with scenario name and type", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    // "Base Case Q1" appears in both the page title and source summary
    const matches = screen.getAllByText("Base Case Q1");
    expect(matches.length).toBeGreaterThan(0);
    expect(screen.getByText("Base")).toBeInTheDocument();
  });
});

test("renders run notes in source summary", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByText("Test run notes")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Assumptions form
// ---------------------------------------------------------------------------

test("pre-populates assumptions form with existing values", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    const sellableInput = screen.getByLabelText(
      /sellable area/i,
    ) as HTMLInputElement;
    expect(sellableInput.value).toBe("1000");
  });
});

test("pre-populates avg sale price in assumptions form", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    const input = screen.getByLabelText(/avg sale price/i) as HTMLInputElement;
    expect(input.value).toBe("3000");
  });
});

// ---------------------------------------------------------------------------
// Calculate button
// ---------------------------------------------------------------------------

test("calculate button is disabled when no assumptions exist", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    const calcBtn = screen.getByRole("button", { name: /calculate/i });
    expect(calcBtn).toBeDisabled();
  });
});

test("calculate button is enabled when assumptions exist", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    const calcBtn = screen.getByRole("button", { name: /calculate/i });
    expect(calcBtn).not.toBeDisabled();
  });
});

// ---------------------------------------------------------------------------
// Results panel
// ---------------------------------------------------------------------------

test("renders results panel with KPIs when results exist", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockResolvedValue(mockResult);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByText("VIABLE")).toBeInTheDocument();
    expect(screen.getAllByText(/Proceed/i).length).toBeGreaterThan(0);
  });
});

test("renders 'no results' placeholder when results not calculated", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByText(/no results yet/i)).toBeInTheDocument();
  });
});

test("renders calculation results after calculate button click", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockRejectedValue(mock404());
  mockCalculate.mockResolvedValue(mockResult);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    const calcBtn = screen.getByRole("button", { name: /calculate/i });
    expect(calcBtn).not.toBeDisabled();
  });

  fireEvent.click(screen.getByRole("button", { name: /calculate/i }));

  await waitFor(() => {
    expect(mockCalculate).toHaveBeenCalledWith("run-1");
    expect(screen.getByText("VIABLE")).toBeInTheDocument();
  });
});

test("shows calculation error inline when calculate fails", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockRejectedValue(mock404());
  mockCalculate.mockRejectedValue(new Error("Calculation failed: missing field"));

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    const calcBtn = screen.getByRole("button", { name: /calculate/i });
    expect(calcBtn).not.toBeDisabled();
  });

  fireEvent.click(screen.getByRole("button", { name: /calculate/i }));

  await waitFor(() => {
    expect(screen.getByText(/calculation failed: missing field/i)).toBeInTheDocument();
  });
});

test("renders unit economics panel with price/sqm, cost/sqm, and profit/sqm after calculation", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockResolvedValue(mockResult);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    const panel = screen.getByTestId("unit-economics-panel");
    expect(panel).toBeInTheDocument();
    // Panel heading
    expect(panel).toHaveTextContent(/unit economics/i);
    // Labels
    expect(panel).toHaveTextContent(/Sale Price \/ sqm/i);
    expect(panel).toHaveTextContent(/Construction Cost \/ sqm/i);
    expect(panel).toHaveTextContent(/Profit \/ sqm/i);
    expect(panel).toHaveTextContent(/Break-even Price \/ sqm/i);
  });
});

// ---------------------------------------------------------------------------
// Assumptions save
// ---------------------------------------------------------------------------

test("save assumptions button calls upsertFeasibilityAssumptions", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());
  mockUpsertAssumptions.mockResolvedValue(mockAssumptions);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByLabelText(/sellable area/i)).toBeInTheDocument();
  });

  fireEvent.change(screen.getByLabelText(/sellable area/i), { target: { value: "1500" } });
  fireEvent.change(screen.getByLabelText(/avg sale price/i), { target: { value: "3500" } });
  fireEvent.change(screen.getByLabelText(/construction cost/i), { target: { value: "900" } });
  fireEvent.change(screen.getByLabelText(/soft cost ratio/i), { target: { value: "10" } });
  fireEvent.change(screen.getByLabelText(/finance cost ratio/i), { target: { value: "5" } });
  fireEvent.change(screen.getByLabelText(/sales cost ratio/i), { target: { value: "3" } });
  fireEvent.change(screen.getByLabelText(/development period/i), { target: { value: "24" } });

  fireEvent.click(screen.getByRole("button", { name: /save assumptions/i }));

  await waitFor(() => {
    expect(mockUpsertAssumptions).toHaveBeenCalledWith(
      "run-1",
      expect.objectContaining({
        sellable_area_sqm: 1500,
        avg_sale_price_per_sqm: 3500,
        development_period_months: 24,
      }),
    );
  });
});

// ---------------------------------------------------------------------------
// Numeric validation — non-finite and out-of-range values
// ---------------------------------------------------------------------------

test("rejects negative value in sellable area field", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);
  await waitFor(() => expect(screen.getByLabelText(/sellable area/i)).toBeInTheDocument());

  // Negative values must be rejected (sellable area must be > 0)
  fireEvent.change(screen.getByLabelText(/sellable area/i), { target: { value: "-500" } });
  fireEvent.change(screen.getByLabelText(/avg sale price/i), { target: { value: "3000" } });
  fireEvent.change(screen.getByLabelText(/construction cost/i), { target: { value: "800" } });
  fireEvent.change(screen.getByLabelText(/soft cost ratio/i), { target: { value: "10" } });
  fireEvent.change(screen.getByLabelText(/finance cost ratio/i), { target: { value: "5" } });
  fireEvent.change(screen.getByLabelText(/sales cost ratio/i), { target: { value: "3" } });
  fireEvent.change(screen.getByLabelText(/development period/i), { target: { value: "24" } });

  fireEvent.click(screen.getByRole("button", { name: /save assumptions/i }));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toHaveTextContent(/invalid value for sellable area/i);
    expect(mockUpsertAssumptions).not.toHaveBeenCalled();
  });
});

test("rejects ratio value greater than 100", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);
  await waitFor(() => expect(screen.getByLabelText(/soft cost ratio/i)).toBeInTheDocument());

  fireEvent.change(screen.getByLabelText(/sellable area/i), { target: { value: "1000" } });
  fireEvent.change(screen.getByLabelText(/avg sale price/i), { target: { value: "3000" } });
  fireEvent.change(screen.getByLabelText(/construction cost/i), { target: { value: "800" } });
  // 150 is > 100 — should be rejected
  fireEvent.change(screen.getByLabelText(/soft cost ratio/i), { target: { value: "150" } });
  fireEvent.change(screen.getByLabelText(/finance cost ratio/i), { target: { value: "5" } });
  fireEvent.change(screen.getByLabelText(/sales cost ratio/i), { target: { value: "3" } });
  fireEvent.change(screen.getByLabelText(/development period/i), { target: { value: "24" } });

  fireEvent.click(screen.getByRole("button", { name: /save assumptions/i }));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toHaveTextContent(/soft cost ratio must be between 0 and 100/i);
    expect(mockUpsertAssumptions).not.toHaveBeenCalled();
  });
});

test("rejects decimal development period (12.9 is not an integer)", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);
  await waitFor(() => expect(screen.getByLabelText(/development period/i)).toBeInTheDocument());

  fireEvent.change(screen.getByLabelText(/sellable area/i), { target: { value: "1000" } });
  fireEvent.change(screen.getByLabelText(/avg sale price/i), { target: { value: "3000" } });
  fireEvent.change(screen.getByLabelText(/construction cost/i), { target: { value: "800" } });
  fireEvent.change(screen.getByLabelText(/soft cost ratio/i), { target: { value: "10" } });
  fireEvent.change(screen.getByLabelText(/finance cost ratio/i), { target: { value: "5" } });
  fireEvent.change(screen.getByLabelText(/sales cost ratio/i), { target: { value: "3" } });
  // 12.9 is not an integer — should be rejected
  fireEvent.change(screen.getByLabelText(/development period/i), { target: { value: "12.9" } });

  fireEvent.click(screen.getByRole("button", { name: /save assumptions/i }));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toHaveTextContent(/whole number of months/i);
    expect(mockUpsertAssumptions).not.toHaveBeenCalled();
  });
});

test("rejects zero value for avg sale price", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);
  await waitFor(() => expect(screen.getByLabelText(/avg sale price/i)).toBeInTheDocument());

  fireEvent.change(screen.getByLabelText(/sellable area/i), { target: { value: "1000" } });
  fireEvent.change(screen.getByLabelText(/avg sale price/i), { target: { value: "0" } });
  fireEvent.change(screen.getByLabelText(/construction cost/i), { target: { value: "800" } });
  fireEvent.change(screen.getByLabelText(/soft cost ratio/i), { target: { value: "10" } });
  fireEvent.change(screen.getByLabelText(/finance cost ratio/i), { target: { value: "5" } });
  fireEvent.change(screen.getByLabelText(/sales cost ratio/i), { target: { value: "3" } });
  fireEvent.change(screen.getByLabelText(/development period/i), { target: { value: "24" } });

  fireEvent.click(screen.getByRole("button", { name: /save assumptions/i }));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toHaveTextContent(/invalid value for avg sale price/i);
    expect(mockUpsertAssumptions).not.toHaveBeenCalled();
  });
});

test("rejects zero value for construction cost", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);
  await waitFor(() => expect(screen.getByLabelText(/construction cost/i)).toBeInTheDocument());

  fireEvent.change(screen.getByLabelText(/sellable area/i), { target: { value: "1000" } });
  fireEvent.change(screen.getByLabelText(/avg sale price/i), { target: { value: "3000" } });
  fireEvent.change(screen.getByLabelText(/construction cost/i), { target: { value: "0" } });
  fireEvent.change(screen.getByLabelText(/soft cost ratio/i), { target: { value: "10" } });
  fireEvent.change(screen.getByLabelText(/finance cost ratio/i), { target: { value: "5" } });
  fireEvent.change(screen.getByLabelText(/sales cost ratio/i), { target: { value: "3" } });
  fireEvent.change(screen.getByLabelText(/development period/i), { target: { value: "24" } });

  fireEvent.click(screen.getByRole("button", { name: /save assumptions/i }));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toHaveTextContent(/invalid value for construction cost/i);
    expect(mockUpsertAssumptions).not.toHaveBeenCalled();
  });
});

test("rejects negative finance cost ratio", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);
  await waitFor(() => expect(screen.getByLabelText(/finance cost ratio/i)).toBeInTheDocument());

  fireEvent.change(screen.getByLabelText(/sellable area/i), { target: { value: "1000" } });
  fireEvent.change(screen.getByLabelText(/avg sale price/i), { target: { value: "3000" } });
  fireEvent.change(screen.getByLabelText(/construction cost/i), { target: { value: "800" } });
  fireEvent.change(screen.getByLabelText(/soft cost ratio/i), { target: { value: "10" } });
  fireEvent.change(screen.getByLabelText(/finance cost ratio/i), { target: { value: "-5" } });
  fireEvent.change(screen.getByLabelText(/sales cost ratio/i), { target: { value: "3" } });
  fireEvent.change(screen.getByLabelText(/development period/i), { target: { value: "24" } });

  fireEvent.click(screen.getByRole("button", { name: /save assumptions/i }));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toHaveTextContent(/finance cost ratio must be between 0 and 100/i);
    expect(mockUpsertAssumptions).not.toHaveBeenCalled();
  });
});

test("rejects sales cost ratio above 100", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);
  await waitFor(() => expect(screen.getByLabelText(/sales cost ratio/i)).toBeInTheDocument());

  fireEvent.change(screen.getByLabelText(/sellable area/i), { target: { value: "1000" } });
  fireEvent.change(screen.getByLabelText(/avg sale price/i), { target: { value: "3000" } });
  fireEvent.change(screen.getByLabelText(/construction cost/i), { target: { value: "800" } });
  fireEvent.change(screen.getByLabelText(/soft cost ratio/i), { target: { value: "10" } });
  fireEvent.change(screen.getByLabelText(/finance cost ratio/i), { target: { value: "5" } });
  fireEvent.change(screen.getByLabelText(/sales cost ratio/i), { target: { value: "200" } });
  fireEvent.change(screen.getByLabelText(/development period/i), { target: { value: "24" } });

  fireEvent.click(screen.getByRole("button", { name: /save assumptions/i }));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toHaveTextContent(/sales cost ratio must be between 0 and 100/i);
    expect(mockUpsertAssumptions).not.toHaveBeenCalled();
  });
});

test("save is not called when development period is zero", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);
  await waitFor(() => expect(screen.getByLabelText(/development period/i)).toBeInTheDocument());

  fireEvent.change(screen.getByLabelText(/sellable area/i), { target: { value: "1000" } });
  fireEvent.change(screen.getByLabelText(/avg sale price/i), { target: { value: "3000" } });
  fireEvent.change(screen.getByLabelText(/construction cost/i), { target: { value: "800" } });
  fireEvent.change(screen.getByLabelText(/soft cost ratio/i), { target: { value: "10" } });
  fireEvent.change(screen.getByLabelText(/finance cost ratio/i), { target: { value: "5" } });
  fireEvent.change(screen.getByLabelText(/sales cost ratio/i), { target: { value: "3" } });
  // 0 is not a valid development period (must be ≥ 1)
  fireEvent.change(screen.getByLabelText(/development period/i), { target: { value: "0" } });

  fireEvent.click(screen.getByRole("button", { name: /save assumptions/i }));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toHaveTextContent(/whole number of months/i);
    expect(mockUpsertAssumptions).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// State reset on runId change
// ---------------------------------------------------------------------------

test("switches runId and clears stale calcError and result", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockResolvedValue(mockResult);
  mockCalculate.mockRejectedValue(new Error("Stale calculation error"));

  const { rerender } = render(<FeasibilityRunDetailView />);

  await waitFor(() => expect(screen.getByText("VIABLE")).toBeInTheDocument());

  fireEvent.click(screen.getByRole("button", { name: /calculate/i }));
  await waitFor(() => expect(screen.getByText(/stale calculation error/i)).toBeInTheDocument());

  mockSearchParams = new URLSearchParams("runId=run-2");
  const run2 = { ...mockRun, id: "run-2", scenario_name: "Run Two" };
  mockGetRun.mockResolvedValue(run2);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  rerender(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.queryByText(/stale calculation error/i)).not.toBeInTheDocument();
    expect(screen.queryByText("VIABLE")).not.toBeInTheDocument();
    expect(screen.getByText(/no results yet/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Project linkage context (PR-W5.3)
// ---------------------------------------------------------------------------

test("shows Unlinked state when run has no project", async () => {
  mockGetRun.mockResolvedValue({ ...mockRun, project_id: null, project_name: null });
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByText(/this run is not linked to a project/i)).toBeInTheDocument();
  });
});

test("shows project name when run is linked to a project", async () => {
  mockGetRun.mockResolvedValue({
    ...mockRun,
    project_id: "proj-1",
    project_name: "Harbour Tower",
  });
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("linked-project-name")).toHaveTextContent("Harbour Tower");
  });
});

test("shows Assign Project button when projects are available and run is unlinked", async () => {
  mockGetRun.mockResolvedValue({ ...mockRun, project_id: null, project_name: null });
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());
  mockListProjects.mockResolvedValue({ items: [mockProject], total: 1 });

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByRole("button", { name: /assign project/i })).toBeInTheDocument();
  });
});

test("calls assignProjectToRun when Assign Project is clicked", async () => {
  const runWithoutProject = { ...mockRun, project_id: null, project_name: null };
  const runWithProject = { ...mockRun, project_id: "proj-1", project_name: "Harbour Tower" };

  mockGetRun.mockResolvedValue(runWithoutProject);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());
  mockListProjects.mockResolvedValue({ items: [mockProject], total: 1 });
  mockAssignProject.mockResolvedValue(runWithProject);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByLabelText(/select project to assign/i)).toBeInTheDocument();
  });

  fireEvent.change(screen.getByLabelText(/select project to assign/i), { target: { value: "proj-1" } });
  fireEvent.click(screen.getByRole("button", { name: /assign project/i }));

  await waitFor(() => {
    expect(mockAssignProject).toHaveBeenCalledWith("run-1", "proj-1");
  });
});

test("shows Unlink Project button when run is linked to a project", async () => {
  mockGetRun.mockResolvedValue({
    ...mockRun,
    project_id: "proj-1",
    project_name: "Harbour Tower",
  });
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByRole("button", { name: /unlink project/i })).toBeInTheDocument();
  });
});

test("calls assignProjectToRun with null when Unlink Project is clicked", async () => {
  const runWithProject = { ...mockRun, project_id: "proj-1", project_name: "Harbour Tower" };
  const runWithoutProject = { ...mockRun, project_id: null, project_name: null };

  mockGetRun.mockResolvedValue(runWithProject);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());
  mockAssignProject.mockResolvedValue(runWithoutProject);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByRole("button", { name: /unlink project/i })).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: /unlink project/i }));

  await waitFor(() => {
    expect(mockAssignProject).toHaveBeenCalledWith("run-1", null);
  });
});


// ---------------------------------------------------------------------------
// Create Concept Option button — PR-CONCEPT-064
// ---------------------------------------------------------------------------

test("renders Create Concept Option button when run is loaded", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("create-concept-btn")).toBeInTheDocument();
  });
  expect(screen.getByTestId("create-concept-btn")).toHaveTextContent("Create Concept Option");
});

test("calls createConceptFromFeasibility with runId when button is clicked", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());
  mockCreateConcept.mockResolvedValue({
    concept_option_id: "concept-new-1",
    source_feasibility_run_id: "run-1",
    scenario_id: null,
    project_id: null,
    seed_source_type: "feasibility_run",
  });

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("create-concept-btn")).toBeInTheDocument();
  });

  fireEvent.click(screen.getByTestId("create-concept-btn"));

  await waitFor(() => {
    expect(mockCreateConcept).toHaveBeenCalledWith("run-1");
  });
});

test("navigates to concept-design page after successful concept creation", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());
  mockCreateConcept.mockResolvedValue({
    concept_option_id: "concept-new-1",
    source_feasibility_run_id: "run-1",
    scenario_id: null,
    project_id: null,
    seed_source_type: "feasibility_run",
  });

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("create-concept-btn")).toBeInTheDocument();
  });

  fireEvent.click(screen.getByTestId("create-concept-btn"));

  await waitFor(() => {
    expect(mockRouterPush).toHaveBeenCalledWith(
      "/concept-design?concept_option_id=concept-new-1",
    );
  });
});

test("shows error when concept creation fails", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());
  mockCreateConcept.mockRejectedValue(new Error("Concept creation failed"));

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("create-concept-btn")).toBeInTheDocument();
  });

  fireEvent.click(screen.getByTestId("create-concept-btn"));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toHaveTextContent("Concept creation failed");
  });
  expect(mockRouterPush).not.toHaveBeenCalled();
});


// ---------------------------------------------------------------------------
// Lifecycle lineage panel — PR-CONCEPT-065
// ---------------------------------------------------------------------------

test("renders lifecycle lineage panel when run is loaded", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());
  mockGetLineage.mockResolvedValue({
    record_type: "feasibility_run",
    record_id: "run-1",
    source_concept_option_id: null,
    reverse_seeded_concept_options: [],
    project_id: null,
  });

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("feasibility-lineage-panel")).toBeInTheDocument();
  });
});

test("lineage panel shows loading state before lineage fetch resolves", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());
  // lineage never resolves during this test — simulates in-flight state
  mockGetLineage.mockReturnValue(new Promise(() => {}));

  render(<FeasibilityRunDetailView />);

  // Core run data has loaded but lineage is still loading
  await waitFor(() => {
    const matches = screen.getAllByText(mockRun.scenario_name);
    expect(matches.length).toBeGreaterThan(0);
  });

  expect(screen.getByText(/loading lineage data/i)).toBeInTheDocument();
});

test("lineage panel shows source concept when seeded from a concept", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());
  mockGetLineage.mockResolvedValue({
    record_type: "feasibility_run",
    record_id: "run-1",
    source_concept_option_id: "concept-source-abc",
    reverse_seeded_concept_options: [],
    project_id: null,
  });

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("lineage-source-concept")).toBeInTheDocument();
  });
});

test("lineage panel shows reverse-seeded concept options list", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());
  mockGetLineage.mockResolvedValue({
    record_type: "feasibility_run",
    record_id: "run-1",
    source_concept_option_id: null,
    reverse_seeded_concept_options: ["concept-1", "concept-2"],
    project_id: null,
  });

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("lineage-reverse-seeded-list")).toBeInTheDocument();
  });
});

test("lineage panel shows unavailable message when lineage fetch fails", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());
  mockGetLineage.mockRejectedValue(new Error("Lineage unavailable"));

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByText(/lineage data unavailable/i)).toBeInTheDocument();
  });
});

test("lineage panel shows project ID when run is linked to a project", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());
  mockGetLineage.mockResolvedValue({
    record_type: "feasibility_run",
    record_id: "run-1",
    source_concept_option_id: null,
    reverse_seeded_concept_options: [],
    project_id: "project-xyz-123",
  });

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("lineage-project-id")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Seed-source metadata in source summary — PR-FEAS-01
// ---------------------------------------------------------------------------

test("source summary shows 'Manual' seed type for manual run (null seed fields)", async () => {
  mockGetRun.mockResolvedValue({ ...mockRun, source_concept_option_id: null, seed_source_type: null });
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("run-seed-source-type")).toHaveTextContent("Manual");
    expect(screen.queryByTestId("run-source-concept-option-id")).not.toBeInTheDocument();
  });
});

test("source summary shows 'Concept Option' seed type for concept-seeded run", async () => {
  mockGetRun.mockResolvedValue({
    ...mockRun,
    source_concept_option_id: "concept-abc-123",
    seed_source_type: "concept_option" as const,
  });
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("run-seed-source-type")).toHaveTextContent("Concept Option");
    expect(screen.getByTestId("run-source-concept-option-id")).toBeInTheDocument();
    expect(screen.getByTestId("run-source-concept-option-id")).toHaveTextContent("concept-abc-");
  });
});

test("source summary shows source concept option ID truncated for concept-seeded run", async () => {
  mockGetRun.mockResolvedValue({
    ...mockRun,
    source_concept_option_id: "concept-full-id-xyz",
    seed_source_type: "concept_option" as const,
  });
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    const el = screen.getByTestId("run-source-concept-option-id");
    const text = el.textContent ?? "";
    expect(text).toContain("concept-full");
    expect(text).not.toContain("concept-full-id-xyz");
    expect(text).toContain("…");
  });
});

test("source summary does not show source concept option ID for manual run", async () => {
  mockGetRun.mockResolvedValue({
    ...mockRun,
    source_concept_option_id: null,
    seed_source_type: "manual" as const,
  });
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("run-seed-source-type")).toHaveTextContent("Manual");
    expect(screen.queryByTestId("run-source-concept-option-id")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// POST vs PATCH save-path branching — PR-FEAS-02
// ---------------------------------------------------------------------------

test("uses POST (upsert) when no assumptions exist on first save", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());
  mockUpsertAssumptions.mockResolvedValue(mockAssumptions);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => expect(screen.getByLabelText(/sellable area/i)).toBeInTheDocument());

  fireEvent.change(screen.getByLabelText(/sellable area/i), { target: { value: "1000" } });
  fireEvent.change(screen.getByLabelText(/avg sale price/i), { target: { value: "3000" } });
  fireEvent.change(screen.getByLabelText(/construction cost/i), { target: { value: "800" } });
  fireEvent.change(screen.getByLabelText(/soft cost ratio/i), { target: { value: "10" } });
  fireEvent.change(screen.getByLabelText(/finance cost ratio/i), { target: { value: "5" } });
  fireEvent.change(screen.getByLabelText(/sales cost ratio/i), { target: { value: "3" } });
  fireEvent.change(screen.getByLabelText(/development period/i), { target: { value: "24" } });

  fireEvent.click(screen.getByRole("button", { name: /save assumptions/i }));

  await waitFor(() => {
    expect(mockUpsertAssumptions).toHaveBeenCalledWith("run-1", expect.any(Object));
    expect(mockPatchAssumptions).not.toHaveBeenCalled();
  });
});

test("uses PATCH when assumptions already exist on subsequent save", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockRejectedValue(mock404());
  mockPatchAssumptions.mockResolvedValue({ ...mockAssumptions, sellable_area_sqm: 1500 });

  render(<FeasibilityRunDetailView />);

  await waitFor(() => expect(screen.getByLabelText(/sellable area/i)).toBeInTheDocument());

  // Change one field and save
  fireEvent.change(screen.getByLabelText(/sellable area/i), { target: { value: "1500" } });

  fireEvent.click(screen.getByRole("button", { name: /save assumptions/i }));

  await waitFor(() => {
    expect(mockPatchAssumptions).toHaveBeenCalledWith("run-1", expect.any(Object));
    expect(mockUpsertAssumptions).not.toHaveBeenCalled();
  });
});

test("PATCH sends only the changed field, omitting unchanged fields", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockRejectedValue(mock404());
  mockPatchAssumptions.mockResolvedValue({ ...mockAssumptions, sellable_area_sqm: 1500 });

  render(<FeasibilityRunDetailView />);

  await waitFor(() => expect(screen.getByLabelText(/sellable area/i)).toBeInTheDocument());

  // Change only sellable area
  fireEvent.change(screen.getByLabelText(/sellable area/i), { target: { value: "1500" } });

  fireEvent.click(screen.getByRole("button", { name: /save assumptions/i }));

  await waitFor(() => {
    expect(mockPatchAssumptions).toHaveBeenCalled();
    const [, patchBody] = mockPatchAssumptions.mock.calls[0];
    // Only the changed field should be present
    expect(patchBody).toEqual({ sellable_area_sqm: 1500 });
    // Unchanged fields must not be included
    expect(patchBody).not.toHaveProperty("avg_sale_price_per_sqm");
    expect(patchBody).not.toHaveProperty("construction_cost_per_sqm");
    expect(patchBody).not.toHaveProperty("soft_cost_ratio");
    expect(patchBody).not.toHaveProperty("finance_cost_ratio");
    expect(patchBody).not.toHaveProperty("sales_cost_ratio");
    expect(patchBody).not.toHaveProperty("development_period_months");
  });
});

test("no PATCH request sent when no fields changed (no-op guard)", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => expect(screen.getByLabelText(/sellable area/i)).toBeInTheDocument());

  // Click save without changing any fields — all form values match existing assumptions
  fireEvent.click(screen.getByRole("button", { name: /save assumptions/i }));

  // Allow microtasks to settle
  await waitFor(() => {
    expect(mockPatchAssumptions).not.toHaveBeenCalled();
    expect(mockUpsertAssumptions).not.toHaveBeenCalled();
  });
});

test("surfaces PATCH error message when patch save fails", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockRejectedValue(mock404());
  mockPatchAssumptions.mockRejectedValue(new Error("Patch save failed"));

  render(<FeasibilityRunDetailView />);

  await waitFor(() => expect(screen.getByLabelText(/sellable area/i)).toBeInTheDocument());

  // Change a field so PATCH is triggered
  fireEvent.change(screen.getByLabelText(/sellable area/i), { target: { value: "1500" } });

  fireEvent.click(screen.getByRole("button", { name: /save assumptions/i }));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toHaveTextContent(/patch save failed/i);
  });
});

test("does not call calculate after a PATCH save — calculation remains explicit", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockRejectedValue(mock404());
  mockPatchAssumptions.mockResolvedValue(mockAssumptions);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => expect(screen.getByLabelText(/sellable area/i)).toBeInTheDocument());

  // Change a field so PATCH is triggered
  fireEvent.change(screen.getByLabelText(/sellable area/i), { target: { value: "1500" } });

  fireEvent.click(screen.getByRole("button", { name: /save assumptions/i }));

  await waitFor(() => {
    expect(mockPatchAssumptions).toHaveBeenCalled();
  });

  expect(mockCalculate).not.toHaveBeenCalled();
});

// ---------------------------------------------------------------------------
// Lifecycle status badge — PR-FEAS-03
// ---------------------------------------------------------------------------

test("shows 'Draft' lifecycle badge for a run with status 'draft'", async () => {
  mockGetRun.mockResolvedValue({ ...mockRun, status: "draft" as const });
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("run-lifecycle-status")).toHaveTextContent("Draft");
  });
});

test("shows 'Ready for Calculation' lifecycle badge for 'assumptions_defined' status", async () => {
  mockGetRun.mockResolvedValue({ ...mockRun, status: "assumptions_defined" as const });
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("run-lifecycle-status")).toHaveTextContent("Ready for Calculation");
  });
});

test("shows 'Calculated' lifecycle badge for 'calculated' status", async () => {
  mockGetRun.mockResolvedValue({ ...mockRun, status: "calculated" as const });
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockResolvedValue(mockResult);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("run-lifecycle-status")).toHaveTextContent("Calculated");
  });
});

test("calculate button is disabled when no assumptions exist (draft state)", async () => {
  mockGetRun.mockResolvedValue({ ...mockRun, status: "draft" as const });
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByRole("button", { name: /calculate/i })).toBeDisabled();
  });
});

test("calculate button is enabled when assumptions exist (assumptions_defined state)", async () => {
  mockGetRun.mockResolvedValue({ ...mockRun, status: "assumptions_defined" as const });
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByRole("button", { name: /calculate/i })).not.toBeDisabled();
  });
});

test("lifecycle status updates to 'Calculated' after calculation", async () => {
  const calculatedRun = { ...mockRun, status: "calculated" as const };
  // First call returns 'assumptions_defined', subsequent calls return 'calculated'.
  mockGetRun
    .mockResolvedValueOnce({ ...mockRun, status: "assumptions_defined" as const })
    .mockResolvedValue(calculatedRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockResolvedValue(mockResult);
  mockCalculate.mockResolvedValue(mockResult);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("run-lifecycle-status")).toHaveTextContent("Ready for Calculation");
  });

  fireEvent.click(screen.getByRole("button", { name: /calculate/i }));

  await waitFor(() => {
    expect(screen.getByTestId("run-lifecycle-status")).toHaveTextContent("Calculated");
  });
});

// ---------------------------------------------------------------------------
// Delete run — PR-FEAS-04
// ---------------------------------------------------------------------------

test("renders delete run button in detail view", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("delete-run-btn")).toBeInTheDocument();
  });
});

test("shows confirmation dialog before deleting", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());
  mockDeleteRun.mockResolvedValue(undefined);

  const confirmSpy = jest.spyOn(window, "confirm").mockReturnValue(false);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("delete-run-btn")).toBeInTheDocument();
  });

  fireEvent.click(screen.getByTestId("delete-run-btn"));

  expect(confirmSpy).toHaveBeenCalledWith(
    expect.stringContaining("Base Case Q1"),
  );
  expect(mockDeleteRun).not.toHaveBeenCalled();

  confirmSpy.mockRestore();
});

test("calls deleteFeasibilityRun and navigates to list on confirmation", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());
  mockDeleteRun.mockResolvedValue(undefined);

  jest.spyOn(window, "confirm").mockReturnValue(true);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("delete-run-btn")).toBeInTheDocument();
  });

  fireEvent.click(screen.getByTestId("delete-run-btn"));

  await waitFor(() => {
    expect(mockDeleteRun).toHaveBeenCalledWith("run-1");
    expect(mockRouterPush).toHaveBeenCalledWith("/feasibility");
  });

  (window.confirm as jest.Mock).mockRestore();
});

test("surfaces error when delete API call fails", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());
  mockDeleteRun.mockRejectedValue(new Error("Delete failed"));

  jest.spyOn(window, "confirm").mockReturnValue(true);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("delete-run-btn")).toBeInTheDocument();
  });

  fireEvent.click(screen.getByTestId("delete-run-btn"));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/delete failed/i)).toBeInTheDocument();
  });

  (window.confirm as jest.Mock).mockRestore();
});

test("does not navigate when confirmation is cancelled", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockRejectedValue(mock404());
  mockGetResults.mockRejectedValue(mock404());

  jest.spyOn(window, "confirm").mockReturnValue(false);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("delete-run-btn")).toBeInTheDocument();
  });

  fireEvent.click(screen.getByTestId("delete-run-btn"));

  expect(mockRouterPush).not.toHaveBeenCalled();

  (window.confirm as jest.Mock).mockRestore();
});

// ---------------------------------------------------------------------------
// Path-based (deep-link) route context tests — PR-FEAS-05
// ---------------------------------------------------------------------------

describe("FeasibilityRunDetailView — path-based runId prop (deep-link route)", () => {
  const pathRunId = "run-path-abc";

  beforeEach(() => {
    // Override search params to return no runId (simulates direct route without query param).
    mockSearchParams = new URLSearchParams("");
    mockGetRun.mockResolvedValue({ ...mockRun, id: pathRunId });
    mockGetAssumptions.mockRejectedValue(mock404());
    mockGetResults.mockRejectedValue(mock404());
    mockGetLineage.mockResolvedValue({
      record_type: "feasibility_run",
      record_id: pathRunId,
      source_concept_option_id: null,
      reverse_seeded_concept_options: [],
      project_id: null,
    });
    mockListProjects.mockResolvedValue({ items: [], total: 0 });
  });

  afterEach(() => {
    // Restore default search params for other test suites.
    mockSearchParams = new URLSearchParams("runId=run-1");
    jest.clearAllMocks();
  });

  it("loads the run using the runId prop when no query param is present", async () => {
    render(<FeasibilityRunDetailView runId={pathRunId} />);

    await waitFor(() => {
      expect(mockGetRun).toHaveBeenCalledWith(pathRunId);
    });
  });

  it("renders the source summary with the correct run data from the path-based runId", async () => {
    render(<FeasibilityRunDetailView runId={pathRunId} />);

    await waitFor(() => {
      expect(screen.getAllByText("Base Case Q1").length).toBeGreaterThan(0);
    });
  });

  it("falls back to query param runId when no prop is given", async () => {
    // Restore query param for this specific test.
    mockSearchParams = new URLSearchParams("runId=run-1");
    mockGetRun.mockResolvedValue(mockRun);

    render(<FeasibilityRunDetailView />);

    await waitFor(() => {
      expect(mockGetRun).toHaveBeenCalledWith("run-1");
    });
  });

  it("renders safe placeholder when runId prop is the placeholder value '_'", async () => {
    render(<FeasibilityRunDetailView runId="_" />);

    await waitFor(() => {
      expect(screen.getByText(/no run id provided/i)).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Scenario outputs table — PR-FEAS-07
// ---------------------------------------------------------------------------

const mockScenarioOutputs = {
  base: {
    gdv: 3_000_000,
    construction_cost: 800_000,
    soft_cost: 80_000,
    finance_cost: 50_000,
    sales_cost: 30_000,
    total_cost: 960_000,
    developer_profit: 2_040_000,
    profit_margin: 0.68,
    irr_estimate: 0.42,
  },
  upside: {
    gdv: 3_300_000,
    construction_cost: 760_000,
    soft_cost: 76_000,
    finance_cost: 47_500,
    sales_cost: 28_500,
    total_cost: 912_000,
    developer_profit: 2_388_000,
    profit_margin: 0.724,
    irr_estimate: 0.48,
  },
  downside: {
    gdv: 2_700_000,
    construction_cost: 880_000,
    soft_cost: 88_000,
    finance_cost: 55_000,
    sales_cost: 33_000,
    total_cost: 1_056_000,
    developer_profit: 1_644_000,
    profit_margin: 0.609,
    irr_estimate: 0.35,
  },
  investor: {
    gdv: 3_150_000,
    construction_cost: 840_000,
    soft_cost: 84_000,
    finance_cost: 52_500,
    sales_cost: 31_500,
    total_cost: 1_008_000,
    developer_profit: 2_142_000,
    profit_margin: 0.68,
    irr_estimate: 0.44,
  },
};

const mockResultWithScenarios = {
  ...mockResult,
  scenario_outputs: mockScenarioOutputs,
};

test("renders scenario analysis table when result has scenario_outputs", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockResolvedValue(mockResultWithScenarios);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("scenario-outputs-table")).toBeInTheDocument();
  });
});

test("scenario table shows Base, Upside, Downside column headers", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockResolvedValue(mockResultWithScenarios);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("scenario-col-base")).toBeInTheDocument();
    expect(screen.getByTestId("scenario-col-upside")).toBeInTheDocument();
    expect(screen.getByTestId("scenario-col-downside")).toBeInTheDocument();
  });
});

test("scenario table shows Investor column header when investor data is present", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockResolvedValue(mockResultWithScenarios);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("scenario-col-investor")).toBeInTheDocument();
  });
});

test("scenario table renders base GDV cell", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockResolvedValue(mockResultWithScenarios);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("scenario-base-gdv")).toBeInTheDocument();
  });
});

test("scenario table renders upside developer_profit cell", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockResolvedValue(mockResultWithScenarios);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("scenario-upside-developer_profit")).toBeInTheDocument();
  });
});

test("scenario table renders downside profit_margin cell", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockResolvedValue(mockResultWithScenarios);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("scenario-downside-profit_margin")).toBeInTheDocument();
  });
});

test("scenario table shows safe empty state when scenario_outputs is null", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockResolvedValue({ ...mockResult, scenario_outputs: null });

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("scenario-outputs-table")).toBeInTheDocument();
    expect(screen.getByText(/no scenario analysis data available/i)).toBeInTheDocument();
  });
});

test("scenario table is not rendered when result is absent", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByText(/no results yet/i)).toBeInTheDocument();
  });

  expect(screen.queryByTestId("scenario-outputs-table")).not.toBeInTheDocument();
});

test("page does not crash when scenario_outputs contains partial scenario data", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockResolvedValue({
    ...mockResult,
    scenario_outputs: { base: mockScenarioOutputs.base }, // only base, no upside/downside
  });

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("scenario-outputs-table")).toBeInTheDocument();
  });
  // Upside column should not appear
  expect(screen.queryByTestId("scenario-col-upside")).not.toBeInTheDocument();
  // Base column should appear
  expect(screen.getByTestId("scenario-col-base")).toBeInTheDocument();
});

test("page does not crash when scenario_outputs is a malformed value", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockResolvedValue({
    ...mockResult,
    scenario_outputs: "not-an-object" as unknown as null,
  });

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByTestId("scenario-outputs-table")).toBeInTheDocument();
    expect(screen.getByText(/no scenario analysis data available/i)).toBeInTheDocument();
  });
});

test("existing main results panel still renders alongside scenario table", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockResolvedValue(mockResultWithScenarios);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    // Main results panel
    expect(screen.getByText("VIABLE")).toBeInTheDocument();
    // Scenario outputs table
    expect(screen.getByTestId("scenario-outputs-table")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Decision summary integration — PR-FEAS-08
// ---------------------------------------------------------------------------

test("decision summary is rendered above KPI panel when results are present", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockResolvedValue(mockResult);

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(
      screen.getByRole("region", { name: /investment decision summary/i }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("decision-value")).toHaveTextContent("Proceed");
  });
});

test("decision summary is not rendered when no results exist", async () => {
  mockGetRun.mockResolvedValue(mockRun);
  mockGetAssumptions.mockResolvedValue(mockAssumptions);
  mockGetResults.mockRejectedValue(mock404());

  render(<FeasibilityRunDetailView />);

  await waitFor(() => {
    expect(screen.getByText(/no results yet/i)).toBeInTheDocument();
  });

  expect(
    screen.queryByRole("region", { name: /investment decision summary/i }),
  ).not.toBeInTheDocument();
});
