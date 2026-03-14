/**
 * api-client.ts — thin wrapper around fetch for backend API calls.
 *
 * All requests attach the stored access token as a Bearer header.
 * The base URL is read from NEXT_PUBLIC_API_URL (defaults to localhost).
 */

import { getToken } from "./auth";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

function authHeaders(): HeadersInit {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

export async function apiFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "GET",
    headers: authHeaders(),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ?? `API error: ${response.status}`,
    );
  }

  return response.json() as Promise<T>;
}
