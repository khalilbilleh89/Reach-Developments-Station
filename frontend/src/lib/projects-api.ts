/**
 * projects-api.ts — API wrapper for the Projects domain.
 *
 * All project data fetching is centralised here.
 *
 * Paths are relative to the API prefix already embedded in BASE_URL
 * (e.g. /api/v1) — do NOT include /api/v1 here.
 *
 * Backend endpoints used:
 *   GET    /projects                   → list projects
 *   POST   /projects                   → create project
 *   GET    /projects/{id}              → get project by id
 *   PATCH  /projects/{id}              → update project
 *   DELETE /projects/{id}              → delete project
 *   POST   /projects/{id}/archive      → archive project
 *   GET    /projects/{id}/summary      → get project KPI summary
 */

import { apiFetch } from "./api-client";
import type {
  Project,
  ProjectCreate,
  ProjectListResponse,
  ProjectStatus,
  ProjectSummary,
  ProjectUpdate,
} from "./projects-types";

export async function listProjects(params?: {
  status?: ProjectStatus;
  search?: string;
  skip?: number;
  limit?: number;
}): Promise<ProjectListResponse> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.search) query.set("search", params.search);
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiFetch<ProjectListResponse>(`/projects${qs ? `?${qs}` : ""}`);
}

export async function getProject(id: string): Promise<Project> {
  return apiFetch<Project>(`/projects/${id}`);
}

export async function createProject(data: ProjectCreate): Promise<Project> {
  return apiFetch<Project>("/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateProject(
  id: string,
  data: ProjectUpdate
): Promise<Project> {
  return apiFetch<Project>(`/projects/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function archiveProject(id: string): Promise<Project> {
  return apiFetch<Project>(`/projects/${id}/archive`, {
    method: "POST",
  });
}

export async function deleteProject(id: string): Promise<void> {
  await apiFetch<void>(`/projects/${id}`, {
    method: "DELETE",
  });
}

export async function getProjectSummary(id: string): Promise<ProjectSummary> {
  return apiFetch<ProjectSummary>(`/projects/${id}/summary`);
}
