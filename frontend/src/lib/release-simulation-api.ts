/**
 * release-simulation-api.ts — Typed API clients for the Release Strategy
 * Simulation Engine endpoints (PR-V7-04).
 *
 * Backend endpoints:
 *   POST /api/v1/projects/{id}/simulate-strategy
 *   POST /api/v1/projects/{id}/simulate-strategies
 *
 * Responsibility: issue typed requests and return typed responses.
 * No business logic, no metric transformation, no client-side computation.
 */

import { apiFetch } from "./api-client";
import type {
  SimulateStrategiesRequest,
  SimulateStrategiesResponse,
  SimulateStrategyRequest,
  SimulateStrategyResponse,
} from "./release-simulation-types";

/**
 * Run a single release strategy what-if simulation for a project.
 *
 * All simulation values are backend-owned — no values are recomputed here.
 * Returns HTTP 404 when the project does not exist.
 */
export async function simulateReleaseStrategy(
  projectId: string,
  request: SimulateStrategyRequest,
  signal?: AbortSignal,
): Promise<SimulateStrategyResponse> {
  return apiFetch<SimulateStrategyResponse>(
    `/projects/${encodeURIComponent(projectId)}/simulate-strategy`,
    {
      method: "POST",
      body: JSON.stringify(request),
      signal,
    },
  );
}

/**
 * Run multiple release strategy simulations and return results ranked by IRR.
 *
 * All simulation values are backend-owned — no values are recomputed here.
 * Returns HTTP 404 when the project does not exist.
 */
export async function simulateReleaseStrategies(
  projectId: string,
  request: SimulateStrategiesRequest,
  signal?: AbortSignal,
): Promise<SimulateStrategiesResponse> {
  return apiFetch<SimulateStrategiesResponse>(
    `/projects/${encodeURIComponent(projectId)}/simulate-strategies`,
    {
      method: "POST",
      body: JSON.stringify(request),
      signal,
    },
  );
}
