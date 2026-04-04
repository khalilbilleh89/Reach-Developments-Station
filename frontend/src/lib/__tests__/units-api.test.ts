/**
 * Tests for units-api.ts — getUnitPricing error handling.
 *
 * Validates that:
 *   - a 404 response returns null (unit not priced yet)
 *   - a 422 response returns null (pricing engine rejected due to incomplete data)
 *   - a 500 response re-throws the ApiError
 *   - a successful response returns the pricing data
 */

import { ApiError } from "../api-client";
import { getUnitPricing } from "../units-api";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

jest.mock("../api-client", () => {
  const original = jest.requireActual("../api-client");
  return {
    ...original,
    apiFetch: jest.fn(),
  };
});

jest.mock("../auth", () => ({
  getToken: jest.fn().mockReturnValue(null),
  clearToken: jest.fn(),
}));

import { apiFetch } from "../api-client";
const mockApiFetch = apiFetch as jest.Mock;

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  jest.clearAllMocks();
});

describe("getUnitPricing", () => {
  it("returns the pricing data on success", async () => {
    const mockPrice = { unit_id: "abc", final_unit_price: 500_000 };
    mockApiFetch.mockResolvedValue(mockPrice);

    const result = await getUnitPricing("abc");

    expect(result).toEqual(mockPrice);
  });

  it("returns null when the unit has no pricing yet (404)", async () => {
    mockApiFetch.mockRejectedValue(new ApiError("Not Found", 404));

    const result = await getUnitPricing("abc");

    expect(result).toBeNull();
  });

  it("returns null when the pricing engine rejects due to incomplete data (422)", async () => {
    mockApiFetch.mockRejectedValue(
      new ApiError("Unprocessable Content", 422),
    );

    const result = await getUnitPricing("abc");

    expect(result).toBeNull();
  });

  it("re-throws on server errors (500)", async () => {
    const err = new ApiError("Internal Server Error", 500);
    mockApiFetch.mockRejectedValue(err);

    await expect(getUnitPricing("abc")).rejects.toThrow(err);
  });

  it("re-throws on auth errors (401)", async () => {
    const err = new ApiError("Unauthorized", 401);
    mockApiFetch.mockRejectedValue(err);

    await expect(getUnitPricing("abc")).rejects.toThrow(err);
  });
});
