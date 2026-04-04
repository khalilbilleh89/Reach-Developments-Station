/**
 * strategy-execution-package-api.ts — Typed API clients for the Strategy
 * Execution Package Generator endpoints (PR-V7-07).
 *
 * Backend endpoints:
 *   GET /api/v1/projects/{id}/strategy-execution-package
 *   GET /api/v1/portfolio/execution-packages
 *
 * Responsibility: issue typed requests and return typed responses.
 * No business logic, no metric transformation, no client-side computation.
 */

import { apiFetch } from "./api-client";
import type {
  PortfolioExecutionPackageResponse,
  ProjectStrategyExecutionPackageResponse,
} from "./strategy-execution-package-types";

/**
 * Fetch the strategy execution package for a single project.
 *
 * All execution package values are backend-owned — no values are recomputed here.
 * Returns HTTP 404 when the project does not exist.
 */
export async function getProjectStrategyExecutionPackage(
  projectId: string,
  signal?: AbortSignal,
): Promise<ProjectStrategyExecutionPackageResponse> {
  return apiFetch<ProjectStrategyExecutionPackageResponse>(
    `/projects/${encodeURIComponent(projectId)}/strategy-execution-package`,
    { signal },
  );
}

/**
 * Fetch portfolio-level execution packages for all projects.
 *
 * All values are backend-owned — no values are recomputed here.
 * Read-only — no records are mutated.
 */
export async function getPortfolioExecutionPackages(
  signal?: AbortSignal,
): Promise<PortfolioExecutionPackageResponse> {
  return apiFetch<PortfolioExecutionPackageResponse>(
    "/portfolio/execution-packages",
    { signal },
  );
}
