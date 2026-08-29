/**
 * The single place the browser talks to the API.
 *
 * Relative, same-origin URLs only: the frontend and the API are one Render
 * service, so there is no public backend base URL and no CORS to configure.
 * Components never call `fetch` directly — they go through the typed helpers in
 * this directory.
 */

const API_ROOT = "/api/v1";

/** An error carrying the status and the API's `{ detail }` message. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }

  /** The session is gone or was never established. */
  get isUnauthenticated(): boolean {
    return this.status === 401;
  }

  /** Authenticated, but not allowed to do this. */
  get isForbidden(): boolean {
    return this.status === 403;
  }

  /** Conflicts with current state or a business rule. */
  get isConflict(): boolean {
    return this.status === 409;
  }
}

type Json = Record<string, unknown> | unknown[];

/**
 * Turn a failed response into an `ApiError` with a message worth showing.
 *
 * The API answers `{ "detail": "..." }` for its own errors and FastAPI's
 * validation array for 422, so both shapes are flattened here rather than in
 * every caller.
 */
async function toApiError(response: Response): Promise<ApiError> {
  let detail = `Request failed (${response.status}).`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      detail = body.detail;
    } else if (Array.isArray(body.detail)) {
      const messages = body.detail
        .map((item) => {
          const entry = item as { loc?: unknown[]; msg?: string };
          const field = Array.isArray(entry.loc) ? entry.loc.slice(1).join(".") : "";
          return field ? `${field}: ${entry.msg ?? ""}` : (entry.msg ?? "");
        })
        .filter(Boolean);
      if (messages.length > 0) detail = messages.join("; ");
    }
  } catch {
    // A non-JSON body (a proxy error page, say) leaves the default message.
  }
  return new ApiError(response.status, detail);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    // The session is an HttpOnly cookie; it is never read by JavaScript and
    // never stored in localStorage or sessionStorage.
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });

  if (!response.ok) {
    throw await toApiError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function get<T>(path: string): Promise<T> {
  return request<T>(path, { method: "GET" });
}

export function post<T>(path: string, body?: Json): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function patch<T>(path: string, body: Json): Promise<T> {
  return request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
}

export function put<T>(path: string, body: Json): Promise<T> {
  return request<T>(path, { method: "PUT", body: JSON.stringify(body) });
}

/**
 * POST a CSV file's text as the request body.
 *
 * Raw `text/csv` rather than multipart: the browser reads the file itself with
 * `File.text()`, so there is no upload library here and no multipart parser on
 * the server — one screen does not justify a dependency on either side.
 */
export function postCsv<T>(path: string, csv: string): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: csv,
    headers: { "Content-Type": "text/csv" },
  });
}
