/**
 * Tests for feasibility-api.ts — typed wrappers around the
 * /api/v1/feasibility backend endpoints.
 *
 * Validates that each client function constructs the correct path, method,
 * and body before delegating to apiFetch.
 *
 * PR-W5.2
 */

import * as api from "../feasibility-api";
import * as apiClient from "../api-client";

// ---------------------------------------------------------------------------
// Mock apiFetch
// ---------------------------------------------------------------------------

jest.mock("../api-client", () => ({
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

const mockApiFetch = apiClient.apiFetch as jest.Mock;

// ---------------------------------------------------------------------------
// Fixture data
// ---------------------------------------------------------------------------

const RUN_ID = "run-abc-123";

const mockRun = {
  id: RUN_ID,
  project_id: null,
  scenario_id: null,
  scenario_name: "Base Case",
  scenario_type: "base",
  notes: null,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const mockRunList = { items: [mockRun], total: 1 };

const mockAssumptions = {
  id: "asm-001",
  run_id: RUN_ID,
  sellable_area_sqm: 1000,
  avg_sale_price_per_sqm: 3000,
  construction_cost_per_sqm: 800,
  soft_cost_ratio: 0.1,
  finance_cost_ratio: 0.05,
  sales_cost_ratio: 0.03,
  development_period_months: 24,
  notes: null,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const mockResult = {
  id: "res-001",
  run_id: RUN_ID,
  gdv: 3000000,
  construction_cost: 800000,
  soft_cost: 80000,
  finance_cost: 40000,
  sales_cost: 24000,
  total_cost: 944000,
  developer_profit: 2056000,
  profit_margin: 0.685,
  irr_estimate: 0.45,
  irr: null,
  equity_multiple: null,
  break_even_price: null,
  break_even_units: null,
  scenario_outputs: null,
  viability_status: "viable",
  risk_level: "low",
  decision: "proceed",
  payback_period: null,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

beforeEach(() => {
  jest.clearAllMocks();
  mockApiFetch.mockResolvedValue(mockRun);
});

// ---------------------------------------------------------------------------
// listFeasibilityRuns
// ---------------------------------------------------------------------------

describe("listFeasibilityRuns", () => {
  it("calls GET /feasibility/runs with no query string when no params", async () => {
    mockApiFetch.mockResolvedValue(mockRunList);
    const result = await api.listFeasibilityRuns();
    expect(mockApiFetch).toHaveBeenCalledWith("/feasibility/runs");
    expect(result).toBe(mockRunList);
  });

  it("appends project_id query param when provided", async () => {
    mockApiFetch.mockResolvedValue(mockRunList);
    await api.listFeasibilityRuns({ project_id: "proj-1" });
    expect(mockApiFetch).toHaveBeenCalledWith(
      expect.stringContaining("project_id=proj-1"),
    );
  });

  it("appends skip and limit query params", async () => {
    mockApiFetch.mockResolvedValue(mockRunList);
    await api.listFeasibilityRuns({ skip: 10, limit: 50 });
    const url = (mockApiFetch.mock.calls[0] as [string])[0];
    expect(url).toContain("skip=10");
    expect(url).toContain("limit=50");
  });
});

// ---------------------------------------------------------------------------
// getFeasibilityRun
// ---------------------------------------------------------------------------

describe("getFeasibilityRun", () => {
  it("calls GET /feasibility/runs/{runId}", async () => {
    await api.getFeasibilityRun(RUN_ID);
    expect(mockApiFetch).toHaveBeenCalledWith(`/feasibility/runs/${RUN_ID}`);
  });

  it("encodes special characters in the run ID", async () => {
    await api.getFeasibilityRun("run/with spaces");
    expect(mockApiFetch).toHaveBeenCalledWith(
      "/feasibility/runs/run%2Fwith%20spaces",
    );
  });
});

// ---------------------------------------------------------------------------
// createFeasibilityRun
// ---------------------------------------------------------------------------

describe("createFeasibilityRun", () => {
  it("calls POST /feasibility/runs with the correct body", async () => {
    const payload = { scenario_name: "Test Run", scenario_type: "base" as const };
    await api.createFeasibilityRun(payload);
    expect(mockApiFetch).toHaveBeenCalledWith(
      "/feasibility/runs",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(payload),
      }),
    );
  });
});

// ---------------------------------------------------------------------------
// updateFeasibilityRun
// ---------------------------------------------------------------------------

describe("updateFeasibilityRun", () => {
  it("calls PATCH /feasibility/runs/{runId} with the correct body", async () => {
    const patch = { scenario_name: "Updated" };
    await api.updateFeasibilityRun(RUN_ID, patch);
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/feasibility/runs/${RUN_ID}`,
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify(patch),
      }),
    );
  });
});

// ---------------------------------------------------------------------------
// upsertFeasibilityAssumptions
// ---------------------------------------------------------------------------

describe("upsertFeasibilityAssumptions", () => {
  it("calls POST /feasibility/runs/{runId}/assumptions with the correct body", async () => {
    mockApiFetch.mockResolvedValue(mockAssumptions);
    const payload = {
      sellable_area_sqm: 1000,
      avg_sale_price_per_sqm: 3000,
      construction_cost_per_sqm: 800,
      soft_cost_ratio: 0.1,
      finance_cost_ratio: 0.05,
      sales_cost_ratio: 0.03,
      development_period_months: 24,
    };
    const result = await api.upsertFeasibilityAssumptions(RUN_ID, payload);
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/feasibility/runs/${RUN_ID}/assumptions`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(payload),
      }),
    );
    expect(result).toBe(mockAssumptions);
  });
});

// ---------------------------------------------------------------------------
// getFeasibilityAssumptions
// ---------------------------------------------------------------------------

describe("getFeasibilityAssumptions", () => {
  it("calls GET /feasibility/runs/{runId}/assumptions", async () => {
    mockApiFetch.mockResolvedValue(mockAssumptions);
    await api.getFeasibilityAssumptions(RUN_ID);
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/feasibility/runs/${RUN_ID}/assumptions`,
    );
  });
});

// ---------------------------------------------------------------------------
// calculateFeasibility
// ---------------------------------------------------------------------------

describe("calculateFeasibility", () => {
  it("calls POST /feasibility/runs/{runId}/calculate with no body", async () => {
    mockApiFetch.mockResolvedValue(mockResult);
    const result = await api.calculateFeasibility(RUN_ID);
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/feasibility/runs/${RUN_ID}/calculate`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(result).toBe(mockResult);
  });
});

// ---------------------------------------------------------------------------
// getFeasibilityResults
// ---------------------------------------------------------------------------

describe("getFeasibilityResults", () => {
  it("calls GET /feasibility/runs/{runId}/results", async () => {
    mockApiFetch.mockResolvedValue(mockResult);
    const result = await api.getFeasibilityResults(RUN_ID);
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/feasibility/runs/${RUN_ID}/results`,
    );
    expect(result).toBe(mockResult);
  });
});
