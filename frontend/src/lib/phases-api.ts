/**
 * phases-api.ts — API wrapper for the Phases domain.
 *
 * All phase data fetching and mutation is centralised here.
 *
 * Paths are relative to the API prefix already embedded in BASE_URL
 * (e.g. /api/v1) — do NOT include /api/v1 here.
 *
 * Backend endpoints used:
 *   GET    /projects/{projectId}/phases        → list phases for project
 *   POST   /projects/{projectId}/phases        → create phase in project
 *   GET    /phases/{phaseId}                   → get phase by id
 *   PATCH  /phases/{phaseId}                   → update phase
 *   DELETE /phases/{phaseId}                   → delete phase
 */

import { apiFetch } from "./api-client";
import type { Phase, PhaseCreate, PhaseListResponse, PhaseUpdate } from "./phases-types";

export async function listPhases(projectId: string): Promise<PhaseListResponse> {
  return apiFetch<PhaseListResponse>(`/projects/${encodeURIComponent(projectId)}/phases`);
}

export async function getPhase(phaseId: string): Promise<Phase> {
  return apiFetch<Phase>(`/phases/${encodeURIComponent(phaseId)}`);
}

export async function createPhase(
  projectId: string,
  data: PhaseCreate,
): Promise<Phase> {
  return apiFetch<Phase>(`/projects/${encodeURIComponent(projectId)}/phases`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updatePhase(
  phaseId: string,
  data: PhaseUpdate,
): Promise<Phase> {
  return apiFetch<Phase>(`/phases/${encodeURIComponent(phaseId)}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deletePhase(phaseId: string): Promise<void> {
  return apiFetch<void>(`/phases/${encodeURIComponent(phaseId)}`, {
    method: "DELETE",
  });
}
