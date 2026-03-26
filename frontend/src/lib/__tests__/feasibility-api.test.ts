/**
 * Tests for feasibility-api.ts — typed wrappers around the
 * /api/v1/feasibility backend endpoints.
 *
 * Validates that each client function constructs the correct path, method,
 * and body before delegating to apiFetch.
 *
 * PR-FEAS-02
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
// Helpers
// ---------------------------------------------------------------------------

const RUN_ID = "run-abc-123";

const mockAssumptions = {
  id: "asm-1",
  run_id: RUN_ID,
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

const validCreatePayload = {
  sellable_area_sqm: 1000,
  avg_sale_price_per_sqm: 3000,
  construction_cost_per_sqm: 800,
  soft_cost_ratio: 0.1,
  finance_cost_ratio: 0.05,
  sales_cost_ratio: 0.03,
  development_period_months: 24,
  notes: null,
};

beforeEach(() => {
  jest.clearAllMocks();
  mockApiFetch.mockResolvedValue(mockAssumptions);
});

// ---------------------------------------------------------------------------
// upsertFeasibilityAssumptions — POST
// ---------------------------------------------------------------------------

describe("upsertFeasibilityAssumptions", () => {
  it("calls the correct path with POST method", async () => {
    await api.upsertFeasibilityAssumptions(RUN_ID, validCreatePayload);

    expect(mockApiFetch).toHaveBeenCalledWith(
      `/feasibility/runs/${RUN_ID}/assumptions`,
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("sends the full payload as JSON body", async () => {
    await api.upsertFeasibilityAssumptions(RUN_ID, validCreatePayload);

    const [, options] = mockApiFetch.mock.calls[0];
    expect(options.body).toBe(JSON.stringify(validCreatePayload));
    expect(options.headers).toEqual(
      expect.objectContaining({ "Content-Type": "application/json" }),
    );
  });

  it("encodes run_id in URL path", async () => {
    await api.upsertFeasibilityAssumptions("run/with/slashes", validCreatePayload);

    const [path] = mockApiFetch.mock.calls[0];
    expect(path).toContain(encodeURIComponent("run/with/slashes"));
  });

  it("returns the response from apiFetch", async () => {
    const result = await api.upsertFeasibilityAssumptions(RUN_ID, validCreatePayload);
    expect(result).toEqual(mockAssumptions);
  });
});

// ---------------------------------------------------------------------------
// patchFeasibilityAssumptions — PATCH
// ---------------------------------------------------------------------------

describe("patchFeasibilityAssumptions", () => {
  it("calls the correct path with PATCH method", async () => {
    await api.patchFeasibilityAssumptions(RUN_ID, { sellable_area_sqm: 1500 });

    expect(mockApiFetch).toHaveBeenCalledWith(
      `/feasibility/runs/${RUN_ID}/assumptions`,
      expect.objectContaining({ method: "PATCH" }),
    );
  });

  it("sends partial payload as JSON body", async () => {
    const partial = { sellable_area_sqm: 1500 };
    await api.patchFeasibilityAssumptions(RUN_ID, partial);

    const [, options] = mockApiFetch.mock.calls[0];
    expect(options.body).toBe(JSON.stringify(partial));
    expect(options.headers).toEqual(
      expect.objectContaining({ "Content-Type": "application/json" }),
    );
  });

  it("encodes run_id in URL path", async () => {
    await api.patchFeasibilityAssumptions("run/with/slashes", { notes: "updated" });

    const [path] = mockApiFetch.mock.calls[0];
    expect(path).toContain(encodeURIComponent("run/with/slashes"));
  });

  it("returns the response from apiFetch", async () => {
    const updated = { ...mockAssumptions, sellable_area_sqm: 1500 };
    mockApiFetch.mockResolvedValueOnce(updated);

    const result = await api.patchFeasibilityAssumptions(RUN_ID, { sellable_area_sqm: 1500 });
    expect(result).toEqual(updated);
  });

  it("sends only the fields provided (partial payload)", async () => {
    const partial = { development_period_months: 36 };
    await api.patchFeasibilityAssumptions(RUN_ID, partial);

    const [, options] = mockApiFetch.mock.calls[0];
    const body = JSON.parse(options.body);
    expect(body).toEqual(partial);
    expect(Object.keys(body)).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// getFeasibilityAssumptions — GET
// ---------------------------------------------------------------------------

describe("getFeasibilityAssumptions", () => {
  it("calls the correct path with GET method (no body)", async () => {
    await api.getFeasibilityAssumptions(RUN_ID);

    expect(mockApiFetch).toHaveBeenCalledWith(
      `/feasibility/runs/${RUN_ID}/assumptions`,
    );
  });

  it("returns the assumptions response", async () => {
    const result = await api.getFeasibilityAssumptions(RUN_ID);
    expect(result).toEqual(mockAssumptions);
  });
});

// ---------------------------------------------------------------------------
// POST vs PATCH path distinction
// ---------------------------------------------------------------------------

describe("POST vs PATCH path distinction", () => {
  it("upsert uses POST and patch uses PATCH — different HTTP methods for same resource", async () => {
    await api.upsertFeasibilityAssumptions(RUN_ID, validCreatePayload);
    const postOptions = mockApiFetch.mock.calls[0][1];
    expect(postOptions.method).toBe("POST");

    jest.clearAllMocks();

    await api.patchFeasibilityAssumptions(RUN_ID, { sellable_area_sqm: 500 });
    const patchOptions = mockApiFetch.mock.calls[0][1];
    expect(patchOptions.method).toBe("PATCH");
  });
});

// ---------------------------------------------------------------------------
// deleteFeasibilityRun — DELETE — PR-FEAS-04
// ---------------------------------------------------------------------------

describe("deleteFeasibilityRun", () => {
  it("calls the correct path with DELETE method", async () => {
    mockApiFetch.mockResolvedValueOnce(undefined);
    await api.deleteFeasibilityRun(RUN_ID);

    expect(mockApiFetch).toHaveBeenCalledWith(
      `/feasibility/runs/${RUN_ID}`,
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("encodes run_id in URL path", async () => {
    mockApiFetch.mockResolvedValueOnce(undefined);
    await api.deleteFeasibilityRun("run/with/slashes");

    const [path] = mockApiFetch.mock.calls[0];
    expect(path).toContain(encodeURIComponent("run/with/slashes"));
  });

  it("does not add Content-Type header (no body)", async () => {
    mockApiFetch.mockResolvedValueOnce(undefined);
    await api.deleteFeasibilityRun(RUN_ID);

    const [, options] = mockApiFetch.mock.calls[0];
    expect(options.headers).toBeUndefined();
  });

  it("resolves without a return value on success", async () => {
    mockApiFetch.mockResolvedValueOnce(undefined);
    const result = await api.deleteFeasibilityRun(RUN_ID);
    expect(result).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// listFeasibilityRuns — scenario_id filtering — PR-FEAS-05
// ---------------------------------------------------------------------------

describe("listFeasibilityRuns — scenario_id filter", () => {
  const mockRunList = { items: [], total: 0 };

  beforeEach(() => {
    mockApiFetch.mockResolvedValue(mockRunList);
  });

  it("omits scenario_id param when not provided", async () => {
    await api.listFeasibilityRuns();
    const [path] = mockApiFetch.mock.calls[0];
    expect(path).toBe("/feasibility/runs");
  });

  it("appends scenario_id query param when provided", async () => {
    await api.listFeasibilityRuns({ scenario_id: "scen-123" });
    const [path] = mockApiFetch.mock.calls[0];
    expect(path).toBe("/feasibility/runs?scenario_id=scen-123");
  });

  it("appends project_id query param when provided", async () => {
    await api.listFeasibilityRuns({ project_id: "proj-1" });
    const [path] = mockApiFetch.mock.calls[0];
    expect(path).toBe("/feasibility/runs?project_id=proj-1");
  });

  it("appends both project_id and scenario_id when both are provided", async () => {
    await api.listFeasibilityRuns({ project_id: "proj-1", scenario_id: "scen-123" });
    const [path] = mockApiFetch.mock.calls[0];
    expect(path).toContain("project_id=proj-1");
    expect(path).toContain("scenario_id=scen-123");
    expect(path).toMatch(/^\/feasibility\/runs\?/);
  });

  it("omits scenario_id when the value is an empty string", async () => {
    await api.listFeasibilityRuns({ scenario_id: "" });
    const [path] = mockApiFetch.mock.calls[0];
    expect(path).not.toContain("scenario_id");
  });

  it("includes skip and limit params alongside scenario_id", async () => {
    await api.listFeasibilityRuns({ scenario_id: "scen-abc", skip: 10, limit: 50 });
    const [path] = mockApiFetch.mock.calls[0];
    expect(path).toContain("scenario_id=scen-abc");
    expect(path).toContain("skip=10");
    expect(path).toContain("limit=50");
  });
});
