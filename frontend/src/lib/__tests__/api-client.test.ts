/**
 * Tests for api-client.ts — apiFetch and global 401 recovery.
 *
 * Validates that:
 *   - the Authorization header is attached when a token is present
 *   - no Authorization header is sent when no token is stored
 *   - non-2xx responses throw a typed ApiError
 *   - a 401 response clears the stored token and redirects to /login
 *   - a 204 response resolves to undefined
 *   - a successful JSON response is returned
 */

import { ApiError, apiFetch } from "../api-client";
import * as auth from "../auth";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

jest.mock("../auth", () => ({
  getToken: jest.fn(),
  clearToken: jest.fn(),
}));

const mockGetToken = auth.getToken as jest.Mock;
const mockClearToken = auth.clearToken as jest.Mock;

// ---------------------------------------------------------------------------
// Global browser object setup / teardown
// ---------------------------------------------------------------------------

// Capture and restore global.fetch so the override does not leak into other
// test files running in the same Jest worker.
const originalFetch = global.fetch;
const mockFetch = jest.fn();

// Capture and restore window.location so the override does not leak.  Save
// the original descriptor so it can be re-applied verbatim in afterAll.
const originalLocationDescriptor = Object.getOwnPropertyDescriptor(
  window,
  "location",
);
const mockLocationReplace = jest.fn();

beforeAll(() => {
  global.fetch = mockFetch;
  Object.defineProperty(window, "location", {
    value: { replace: mockLocationReplace },
    writable: true,
    configurable: true,
  });
});

afterAll(() => {
  global.fetch = originalFetch;
  if (originalLocationDescriptor) {
    Object.defineProperty(window, "location", originalLocationDescriptor);
  }
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  jest.clearAllMocks();
  mockGetToken.mockReturnValue(null);
});

describe("apiFetch — authorization header", () => {
  it("attaches Bearer token when one is stored", async () => {
    mockGetToken.mockReturnValue("my-token");
    mockFetch.mockResolvedValue(makeResponse(200, { id: 1 }));

    await apiFetch("/test");

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer my-token");
  });

  it("omits the Authorization header when no token is stored", async () => {
    mockGetToken.mockReturnValue(null);
    mockFetch.mockResolvedValue(makeResponse(200, { id: 2 }));

    await apiFetch("/test");

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Headers;
    expect(headers.get("Authorization")).toBeNull();
  });
});

describe("apiFetch — successful responses", () => {
  it("returns parsed JSON on 200", async () => {
    mockFetch.mockResolvedValue(makeResponse(200, { value: 42 }));
    const result = await apiFetch<{ value: number }>("/data");
    expect(result).toEqual({ value: 42 });
  });

  it("returns undefined on 204 No Content", async () => {
    mockFetch.mockResolvedValue(makeResponse(204, null));
    const result = await apiFetch("/no-content");
    expect(result).toBeUndefined();
  });
});

describe("apiFetch — error responses", () => {
  it("throws ApiError with status and detail message on 400", async () => {
    mockFetch.mockResolvedValue(
      makeResponse(400, { detail: "Bad input" }),
    );

    await expect(apiFetch("/bad")).rejects.toMatchObject({
      name: "ApiError",
      status: 400,
      message: "Bad input",
    });
  });

  it("throws ApiError with fallback message when body has no detail", async () => {
    mockFetch.mockResolvedValue(makeResponse(500, {}));

    await expect(apiFetch("/error")).rejects.toMatchObject({
      name: "ApiError",
      status: 500,
      message: "API error: 500",
    });
  });

  it("throws ApiError even when json parsing fails", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 503,
      json: () => Promise.reject(new Error("not json")),
    } as unknown as Response);

    await expect(apiFetch("/broken")).rejects.toMatchObject({
      name: "ApiError",
      status: 503,
    });
  });
});

describe("apiFetch — 401 global recovery", () => {
  it("clears the stored token on a 401 response", async () => {
    mockGetToken.mockReturnValue("stale-token");
    mockFetch.mockResolvedValue(
      makeResponse(401, { detail: "Not authenticated" }),
    );

    await expect(apiFetch("/protected")).rejects.toMatchObject({
      status: 401,
    });

    expect(mockClearToken).toHaveBeenCalledTimes(1);
  });

  it("redirects to /login on a 401 response", async () => {
    mockGetToken.mockReturnValue("stale-token");
    mockFetch.mockResolvedValue(
      makeResponse(401, { detail: "Not authenticated" }),
    );

    await expect(apiFetch("/protected")).rejects.toMatchObject({
      status: 401,
    });

    expect(mockLocationReplace).toHaveBeenCalledWith("/login");
  });

  it("still throws ApiError after 401 recovery so callers can react", async () => {
    mockFetch.mockResolvedValue(
      makeResponse(401, { detail: "Unauthorized" }),
    );

    const err = await apiFetch("/protected").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(401);
  });

  it("does not clear token or redirect on a 403 response", async () => {
    mockFetch.mockResolvedValue(
      makeResponse(403, { detail: "Forbidden" }),
    );

    await expect(apiFetch("/forbidden")).rejects.toMatchObject({ status: 403 });

    expect(mockClearToken).not.toHaveBeenCalled();
    expect(mockLocationReplace).not.toHaveBeenCalled();
  });

  it("does not clear token or redirect on a 404 response", async () => {
    mockFetch.mockResolvedValue(
      makeResponse(404, { detail: "Not found" }),
    );

    await expect(apiFetch("/missing")).rejects.toMatchObject({ status: 404 });

    expect(mockClearToken).not.toHaveBeenCalled();
    expect(mockLocationReplace).not.toHaveBeenCalled();
  });
});
