/**
 * project-phases-api.ts — API wrapper for the Project Lifecycle & Phase Management Engine.
 *
 * All lifecycle phase data fetching and mutation is centralised here.
 *
 * Paths are relative to the API prefix already embedded in BASE_URL
 * (e.g. /api/v1) — do NOT include /api/v1 here.
 *
 * Backend endpoints used:
 *   GET    /projects/{projectId}/phases        → list phases for project
 *   POST   /projects/{projectId}/phases        → create phase in project
 *   GET    /projects/{projectId}/lifecycle     → get project lifecycle view
 *   PATCH  /phases/{phaseId}                   → update phase
 *   POST   /phases/{phaseId}/advance           → advance phase (mark completed, activate next)
 *   POST   /phases/{phaseId}/reopen            → reopen a completed phase
 */

import { apiFetch } from "./api-client";
import type {
  ProjectLifecycle,
  ProjectPhase,
  ProjectPhaseCreate,
  ProjectPhaseListResponse,
  ProjectPhaseUpdate,
} from "./project-phases-types";

export async function listProjectPhases(projectId: string): Promise<ProjectPhaseListResponse> {
  return apiFetch<ProjectPhaseListResponse>(
    `/projects/${encodeURIComponent(projectId)}/phases`,
  );
}

export async function createProjectPhase(
  projectId: string,
  data: ProjectPhaseCreate,
): Promise<ProjectPhase> {
  return apiFetch<ProjectPhase>(
    `/projects/${encodeURIComponent(projectId)}/phases`,
    {
      method: "POST",
      body: JSON.stringify(data),
    },
  );
}

export async function updateProjectPhase(
  phaseId: string,
  data: ProjectPhaseUpdate,
): Promise<ProjectPhase> {
  return apiFetch<ProjectPhase>(`/phases/${encodeURIComponent(phaseId)}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function getProjectLifecycle(projectId: string): Promise<ProjectLifecycle> {
  return apiFetch<ProjectLifecycle>(
    `/projects/${encodeURIComponent(projectId)}/lifecycle`,
  );
}

export async function advanceProjectPhase(phaseId: string): Promise<ProjectPhase> {
  return apiFetch<ProjectPhase>(
    `/phases/${encodeURIComponent(phaseId)}/advance`,
    { method: "POST" },
  );
}

export async function reopenProjectPhase(phaseId: string): Promise<ProjectPhase> {
  return apiFetch<ProjectPhase>(
    `/phases/${encodeURIComponent(phaseId)}/reopen`,
    { method: "POST" },
  );
}
