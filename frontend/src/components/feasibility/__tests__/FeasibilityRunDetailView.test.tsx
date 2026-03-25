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
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
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
jest.mock("@/lib/format-utils", () => ({
  formatCurrency: (v: number) => `AED ${v.toLocaleString()}`,
}));

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
  calculateFeasibility: jest.fn(),
  getFeasibilityResults: jest.fn(),
  assignProjectToRun: jest.fn(),
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
  calculateFeasibility,
  getFeasibilityResults,
  assignProjectToRun,
} from "@/lib/feasibility-api";
import { listProjects } from "@/lib/projects-api";
import { ApiError } from "@/lib/api-client";
import FeasibilityRunDetailView from "@/components/feasibility/FeasibilityRunDetailView";

const mockGetRun = getFeasibilityRun as jest.Mock;
const mockGetAssumptions = getFeasibilityAssumptions as jest.Mock;
const mockUpsertAssumptions = upsertFeasibilityAssumptions as jest.Mock;
const mockCalculate = calculateFeasibility as jest.Mock;
const mockGetResults = getFeasibilityResults as jest.Mock;
const mockAssignProject = assignProjectToRun as jest.Mock;
const mockListProjects = listProjects as jest.Mock;

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
    expect(screen.getByText(/Proceed/i)).toBeInTheDocument();
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

