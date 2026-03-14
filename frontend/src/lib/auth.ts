/**
 * auth.ts — token management helpers.
 *
 * Thin wrappers around localStorage so all auth state reads/writes
 * go through a single import, making it easy to mock in tests.
 */

const TOKEN_KEY = "reach_access_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return Boolean(getToken());
}

/** Alias kept for backward compatibility with existing mocks. */
export function logout(): void {
  clearToken();
}

/** Throws if no token is present (useful for SSR guard). */
export function requireAuth(): string {
  const token = getToken();
  if (!token) {
    throw new Error("Not authenticated");
  }
  return token;
}
