/**
 * Tests for concept-design-api.ts — typed wrappers around the
 * /api/v1/concept-options backend endpoints.
 *
 * Validates that each client function constructs the correct path, method,
 * and body before delegating to apiFetch.
 *
 * PR-CONCEPT-055
 */

import * as api from "../concept-design-api";
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

const OPTION_ID = "opt-abc-123";

const mockOption = {
  id: OPTION_ID,
  project_id: null,
  scenario_id: null,
  name: "Option A",
  status: "draft",
  description: null,
  site_area: null,
  gross_floor_area: null,
  building_count: null,
  floor_count: null,
  is_promoted: false,
  promoted_at: null,
  promoted_project_id: null,
  promotion_notes: null,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

beforeEach(() => {
  jest.clearAllMocks();
  mockApiFetch.mockResolvedValue(mockOption);
});

// ---------------------------------------------------------------------------
// listConceptOptions
// ---------------------------------------------------------------------------

describe("listConceptOptions", () => {
  it("calls /concept-options without query string when no params supplied", async () => {
    mockApiFetch.mockResolvedValue({ items: [mockOption], total: 1 });
    await api.listConceptOptions();
    expect(mockApiFetch).toHaveBeenCalledWith("/concept-options");
  });

  it("appends project_id query param when supplied", async () => {
    mockApiFetch.mockResolvedValue({ items: [], total: 0 });
    await api.listConceptOptions({ project_id: "proj-1" });
    expect(mockApiFetch).toHaveBeenCalledWith(
      "/concept-options?project_id=proj-1",
    );
  });

  it("appends scenario_id query param when supplied", async () => {
    mockApiFetch.mockResolvedValue({ items: [], total: 0 });
    await api.listConceptOptions({ scenario_id: "scen-1" });
    expect(mockApiFetch).toHaveBeenCalledWith(
      "/concept-options?scenario_id=scen-1",
    );
  });

  it("appends skip and limit when both supplied", async () => {
    mockApiFetch.mockResolvedValue({ items: [], total: 0 });
    await api.listConceptOptions({ skip: 10, limit: 50 });
    expect(mockApiFetch).toHaveBeenCalledWith(
      "/concept-options?skip=10&limit=50",
    );
  });
});

// ---------------------------------------------------------------------------
// getConceptOption
// ---------------------------------------------------------------------------

describe("getConceptOption", () => {
  it("calls /concept-options/{id}", async () => {
    await api.getConceptOption(OPTION_ID);
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/concept-options/${encodeURIComponent(OPTION_ID)}`,
    );
  });
});

// ---------------------------------------------------------------------------
// createConceptOption
// ---------------------------------------------------------------------------

describe("createConceptOption", () => {
  it("calls POST /concept-options with JSON body", async () => {
    const payload = { name: "Option B", status: "draft" as const };
    await api.createConceptOption(payload);
    expect(mockApiFetch).toHaveBeenCalledWith("/concept-options", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  });
});

// ---------------------------------------------------------------------------
// updateConceptOption
// ---------------------------------------------------------------------------

describe("updateConceptOption", () => {
  it("calls PATCH /concept-options/{id} with JSON body", async () => {
    const patch = { name: "Updated" };
    await api.updateConceptOption(OPTION_ID, patch);
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/concept-options/${encodeURIComponent(OPTION_ID)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      },
    );
  });
});

// ---------------------------------------------------------------------------
// addConceptUnitMixLine
// ---------------------------------------------------------------------------

describe("addConceptUnitMixLine", () => {
  it("calls POST /concept-options/{id}/unit-mix with JSON body", async () => {
    const line = { unit_type: "1BR", units_count: 10 };
    mockApiFetch.mockResolvedValue({ id: "line-1", ...line });
    await api.addConceptUnitMixLine(OPTION_ID, line);
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/concept-options/${encodeURIComponent(OPTION_ID)}/unit-mix`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(line),
      },
    );
  });
});

// ---------------------------------------------------------------------------
// getConceptOptionSummary
// ---------------------------------------------------------------------------

describe("getConceptOptionSummary", () => {
  it("calls GET /concept-options/{id}/summary", async () => {
    const summary = {
      concept_option_id: OPTION_ID,
      name: "Option A",
      status: "draft",
      project_id: null,
      scenario_id: null,
      site_area: null,
      gross_floor_area: null,
      building_count: null,
      floor_count: null,
      unit_count: 0,
      sellable_area: null,
      efficiency_ratio: null,
      average_unit_area: null,
      mix_lines: [],
    };
    mockApiFetch.mockResolvedValue(summary);
    const result = await api.getConceptOptionSummary(OPTION_ID);
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/concept-options/${encodeURIComponent(OPTION_ID)}/summary`,
    );
    expect(result).toEqual(summary);
  });
});

// ---------------------------------------------------------------------------
// compareConceptOptions
// ---------------------------------------------------------------------------

describe("compareConceptOptions", () => {
  it("calls /concept-options/compare with project_id param", async () => {
    const comparison = { comparison_basis: "project", option_count: 2, rows: [] };
    mockApiFetch.mockResolvedValue(comparison);
    await api.compareConceptOptions({ project_id: "proj-1" });
    expect(mockApiFetch).toHaveBeenCalledWith(
      "/concept-options/compare?project_id=proj-1",
    );
  });

  it("calls /concept-options/compare with scenario_id param", async () => {
    mockApiFetch.mockResolvedValue({ comparison_basis: "scenario", option_count: 0, rows: [] });
    await api.compareConceptOptions({ scenario_id: "scen-1" });
    expect(mockApiFetch).toHaveBeenCalledWith(
      "/concept-options/compare?scenario_id=scen-1",
    );
  });

  it("calls /concept-options/compare without params when neither supplied", async () => {
    mockApiFetch.mockResolvedValue({ comparison_basis: "none", option_count: 0, rows: [] });
    await api.compareConceptOptions({});
    expect(mockApiFetch).toHaveBeenCalledWith("/concept-options/compare");
  });
});

// ---------------------------------------------------------------------------
// promoteConceptOption
// ---------------------------------------------------------------------------

describe("promoteConceptOption", () => {
  it("calls POST /concept-options/{id}/promote with payload", async () => {
    const promoReq = { target_project_id: "proj-2", phase_name: "Phase 1" };
    const promoResp = {
      concept_option_id: OPTION_ID,
      promoted_project_id: "proj-2",
      promoted_phase_id: "phase-1",
      promoted_phase_name: "Phase 1",
      promoted_at: "2024-06-01T00:00:00Z",
      promotion_notes: null,
    };
    mockApiFetch.mockResolvedValue(promoResp);
    const result = await api.promoteConceptOption(OPTION_ID, promoReq);
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/concept-options/${encodeURIComponent(OPTION_ID)}/promote`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(promoReq),
      },
    );
    expect(result).toEqual(promoResp);
  });

  it("sends empty object body when no payload supplied", async () => {
    mockApiFetch.mockResolvedValue({
      concept_option_id: OPTION_ID,
      promoted_project_id: "proj-3",
      promoted_phase_id: "ph-2",
      promoted_phase_name: "Phase 2",
      promoted_at: "2024-06-02T00:00:00Z",
      promotion_notes: null,
    });
    await api.promoteConceptOption(OPTION_ID);
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/concept-options/${encodeURIComponent(OPTION_ID)}/promote`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      },
    );
  });
});
