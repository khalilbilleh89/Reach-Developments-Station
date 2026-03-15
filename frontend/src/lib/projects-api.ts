/**
 * projects-api.ts — API wrapper for the Projects domain.
 *
 * All project data fetching is centralised here.
 *
 * Backend endpoints used:
 *   GET  /api/v1/projects                   → list projects
 *   POST /api/v1/projects                   → create project
 *   GET  /api/v1/projects/{id}              → get project by id
 *   PATCH /api/v1/projects/{id}             → update project
 *   POST /api/v1/projects/{id}/archive      → archive project
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
  return apiFetch<ProjectListResponse>(`/api/v1/projects${qs ? `?${qs}` : ""}`);
}

export async function getProject(id: string): Promise<Project> {
  return apiFetch<Project>(`/api/v1/projects/${id}`);
}

export async function createProject(data: ProjectCreate): Promise<Project> {
  return apiFetch<Project>("/api/v1/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateProject(
  id: string,
  data: ProjectUpdate
): Promise<Project> {
  return apiFetch<Project>(`/api/v1/projects/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function archiveProject(id: string): Promise<Project> {
  return apiFetch<Project>(`/api/v1/projects/${id}/archive`, {
    method: "POST",
  });
}

export async function getProjectSummary(id: string): Promise<ProjectSummary> {
  return apiFetch<ProjectSummary>(`/api/v1/projects/${id}/summary`);
}
