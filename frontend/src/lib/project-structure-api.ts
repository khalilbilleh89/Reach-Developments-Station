/**
 * project-structure-api.ts — typed API client for the Project Structure Viewer.
 *
 * Calls:
 *   GET /api/v1/projects/{projectId}/structure
 *
 * No response transforms beyond safe typing.
 */

import { apiFetch } from "@/lib/api-client";
import type { ProjectStructureResponse } from "@/lib/project-structure-types";

export async function getProjectStructure(
  projectId: string,
): Promise<ProjectStructureResponse> {
  return apiFetch<ProjectStructureResponse>(`/projects/${projectId}/structure`);
}
