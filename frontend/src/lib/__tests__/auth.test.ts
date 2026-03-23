/**
 * Tests for auth.ts — token management helpers.
 *
 * Validates that the auth helpers correctly read/write/clear the access token
 * from localStorage and that the session bootstrap guards work as expected.
 */

import {
  clearToken,
  getToken,
  isAuthenticated,
  logout,
  requireAuth,
  setToken,
} from "../auth";

// ---------------------------------------------------------------------------
// localStorage stub
// ---------------------------------------------------------------------------

const mockStorageState: Record<string, string> = {};

beforeEach(() => {
  // Clear in-memory store and reset all mock implementations
  Object.keys(mockStorageState).forEach((k) => delete mockStorageState[k]);

  Object.defineProperty(window, "localStorage", {
    value: {
      getItem: (key: string) => mockStorageState[key] ?? null,
      setItem: (key: string, value: string) => {
        mockStorageState[key] = value;
      },
      removeItem: (key: string) => {
        delete mockStorageState[key];
      },
      clear: () => {
        Object.keys(mockStorageState).forEach((k) => delete mockStorageState[k]);
      },
    },
    writable: true,
  });
});

// ---------------------------------------------------------------------------
// setToken / getToken
// ---------------------------------------------------------------------------

describe("setToken / getToken", () => {
  it("stores a token and retrieves it", () => {
    setToken("test-token-abc");
    expect(getToken()).toBe("test-token-abc");
  });

  it("returns null when no token is stored", () => {
    expect(getToken()).toBeNull();
  });

  it("overwrites an existing token", () => {
    setToken("token-v1");
    setToken("token-v2");
    expect(getToken()).toBe("token-v2");
  });
});

// ---------------------------------------------------------------------------
// clearToken
// ---------------------------------------------------------------------------

describe("clearToken", () => {
  it("removes the stored token", () => {
    setToken("to-be-cleared");
    clearToken();
    expect(getToken()).toBeNull();
  });

  it("is safe to call when no token is stored", () => {
    expect(() => clearToken()).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// isAuthenticated
// ---------------------------------------------------------------------------

describe("isAuthenticated", () => {
  it("returns true when a token is stored", () => {
    setToken("live-token");
    expect(isAuthenticated()).toBe(true);
  });

  it("returns false when no token is stored", () => {
    expect(isAuthenticated()).toBe(false);
  });

  it("returns false after the token is cleared", () => {
    setToken("ephemeral-token");
    clearToken();
    expect(isAuthenticated()).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// logout
// ---------------------------------------------------------------------------

describe("logout", () => {
  it("clears the stored token", () => {
    setToken("session-token");
    logout();
    expect(getToken()).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// requireAuth
// ---------------------------------------------------------------------------

describe("requireAuth", () => {
  it("returns the token when one is stored", () => {
    setToken("valid-token");
    expect(requireAuth()).toBe("valid-token");
  });

  it("throws when no token is stored", () => {
    expect(() => requireAuth()).toThrow("Not authenticated");
  });
});
