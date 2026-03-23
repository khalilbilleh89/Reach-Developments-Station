/**
 * api-client.ts — thin wrapper around fetch for backend API calls.
 *
 * All requests attach the stored access token as a Bearer header.
 * The base URL is read from NEXT_PUBLIC_API_URL (defaults to localhost).
 * A global 401 interceptor clears the stored session and redirects to /login
 * so that every protected page recovers deterministically when the backend
 * reports the token is invalid or expired.
 */

import { clearToken, getToken } from "./auth";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

/**
 * ApiError — structured error thrown by apiFetch when the server returns a
 * non-2xx response. Carries the HTTP status code for precise discrimination
 * (e.g. 404 "not found" vs 500 "server error") by callers.
 */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function authHeaders(extra?: HeadersInit): Headers {
  const token = getToken();
  const headers = new Headers(extra);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

/**
 * Handle a definitive 401 Unauthorized response from the backend.
 *
 * Clears the stored access token so stale auth state cannot persist, then
 * navigates to /login.  Using window.location.replace avoids adding the
 * current (now-unauthenticated) page to the browser history.
 */
function handleUnauthorized(): void {
  clearToken();
  if (typeof window !== "undefined") {
    window.location.replace("/login");
  }
}

export async function apiFetch<T>(
  path: string,
  init?: Omit<RequestInit, "headers"> & { headers?: HeadersInit },
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "GET",
    ...init,
    headers: authHeaders(init?.headers),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = new ApiError(
      (body as { detail?: string }).detail ?? `API error: ${response.status}`,
      response.status,
    );

    // Global 401 recovery — clear stale session and redirect to login.
    if (response.status === 401) {
      handleUnauthorized();
    }

    throw error;
  }

  // 204 No Content — return undefined cast to T (callers that expect void use this)
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}
