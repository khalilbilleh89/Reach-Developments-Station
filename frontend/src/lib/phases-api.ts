/**
 * phases-api.ts — API wrapper for the Phases domain.
 *
 * All phase data fetching and mutation is centralised here.
 *
 * Backend endpoints used:
 *   GET    /api/v1/projects/{projectId}/phases        → list phases for project
 *   POST   /api/v1/projects/{projectId}/phases        → create phase in project
 *   GET    /api/v1/phases/{phaseId}                   → get phase by id
 *   PATCH  /api/v1/phases/{phaseId}                   → update phase
 *   DELETE /api/v1/phases/{phaseId}                   → delete phase
 */

import { apiFetch } from "./api-client";
import type { Phase, PhaseCreate, PhaseListResponse, PhaseUpdate } from "./phases-types";

export async function listPhases(projectId: string): Promise<PhaseListResponse> {
  return apiFetch<PhaseListResponse>(`/api/v1/projects/${projectId}/phases`);
}

export async function getPhase(phaseId: string): Promise<Phase> {
  return apiFetch<Phase>(`/api/v1/phases/${phaseId}`);
}

export async function createPhase(
  projectId: string,
  data: PhaseCreate,
): Promise<Phase> {
  return apiFetch<Phase>(`/api/v1/projects/${projectId}/phases`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updatePhase(
  phaseId: string,
  data: PhaseUpdate,
): Promise<Phase> {
  return apiFetch<Phase>(`/api/v1/phases/${phaseId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deletePhase(phaseId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/phases/${phaseId}`, {
    method: "DELETE",
  });
}
