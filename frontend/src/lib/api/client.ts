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
export type FieldError = { path: (string | number)[]; message: string };

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string, readonly fieldErrors: FieldError[] = []) {
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
  const fieldErrors: FieldError[] = [];
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      detail = body.detail;
    } else if (Array.isArray(body.detail)) {
      const messages = body.detail
        .map((item) => {
          const entry = item as { loc?: unknown[]; msg?: string };
          const path = Array.isArray(entry.loc) ? entry.loc.filter((part): part is string | number => typeof part === "string" || typeof part === "number") : [];
          if (["body", "query", "path"].includes(String(path[0]))) path.shift();
          fieldErrors.push({ path, message: entry.msg ?? "Invalid value." });
          const field = path.join(".");
          return field ? `${field}: ${entry.msg ?? ""}` : (entry.msg ?? "");
        })
        .filter(Boolean);
      if (messages.length > 0) detail = messages.join("; ");
    }
  } catch {
    // A non-JSON body (a proxy error page, say) leaves the default message.
  }
  return new ApiError(response.status, detail, fieldErrors);
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
 * DELETE a resource that has one.
 *
 * Rare on purpose: financial and legal records are reversed, superseded or
 * withdrawn, and every one of those keeps what was previously believed on the
 * record. The only route that answers this verb removes a cost pool from an
 * unsubmitted draft, which nobody has approved and nothing has been sold
 * against.
 */
export function remove(path: string): Promise<void> {
  return request<void>(path, { method: "DELETE" });
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

/**
 * POST raw bytes as the request body.
 *
 * The workbook equivalent of `postCsv`, and raw for the same reason: the
 * browser already holds the bytes, so multipart would be a parser on both
 * sides carried for one screen.
 */
export function postBinary<T>(path: string, bytes: ArrayBuffer): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: bytes,
    headers: { "Content-Type": "application/octet-stream" },
  });
}

/**
 * Fetch a file and hand it to the browser to save.
 *
 * Through `fetch` rather than a plain link because the session is an HttpOnly
 * cookie on a same-origin API call, and because a link cannot report a 403 as
 * anything other than a broken download. The server names the file; the
 * fallback is only used when it does not.
 */
export async function download(path: string, fallbackName: string): Promise<void> {
  const response = await fetch(`${API_ROOT}${path}`, {
    method: "GET",
    credentials: "include",
  });
  if (!response.ok) {
    throw await toApiError(response);
  }
  const disposition = response.headers.get("content-disposition") ?? "";
  const named = /filename="?([^"';]+)"?/.exec(disposition);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = named ? named[1] : fallbackName;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    // Revoked on the next tick: Safari has not necessarily started reading the
    // blob by the time click() returns.
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
}
