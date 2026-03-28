/**
 * absorption-api.ts — Typed API client for the Project Absorption Metrics
 * endpoint (PR-V7-01).
 *
 * Responsibility: issue the GET /projects/{id}/absorption-metrics request
 * and return a typed response. No business logic, no metric transformation,
 * and no client-side recomputation of absorption values.
 *
 * Backend endpoint:
 *   GET /api/v1/projects/{project_id}/absorption-metrics
 */

import { apiFetch } from "./api-client";
import type { ProjectAbsorptionMetrics } from "./absorption-types";

/**
 * Fetch the read-only absorption metrics for a single project.
 *
 * All metrics are backend-owned — no values are recomputed or transformed here.
 * Returns HTTP 404 when the project does not exist.
 */
export async function getProjectAbsorptionMetrics(
  projectId: string,
  signal?: AbortSignal,
): Promise<ProjectAbsorptionMetrics> {
  return apiFetch<ProjectAbsorptionMetrics>(
    `/projects/${encodeURIComponent(projectId)}/absorption-metrics`,
    { signal },
  );
}
