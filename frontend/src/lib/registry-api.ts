/**
 * registry-api.ts — API wrapper for the Registry/Conveyancing domain.
 *
 * All registry data fetching and mutation is centralised here.
 *
 * Paths are relative to the API prefix already embedded in BASE_URL
 * (e.g. /api/v1) — do NOT include /api/v1 here.
 *
 * Backend endpoints used:
 *   POST   /registry/cases                                    → open a new case
 *   GET    /registry/cases/{case_id}                          → get case by id
 *   GET    /registry/cases/by-sale/{sale_contract_id}         → get case by sales contract
 *   PATCH  /registry/cases/{case_id}                          → update case
 *   GET    /registry/projects/{project_id}/cases              → list cases for project
 *   GET    /registry/projects/{project_id}/summary            → project registry summary
 *   GET    /registry/cases/{case_id}/milestones               → list milestones for case
 *   PATCH  /registry/cases/{case_id}/milestones/{milestone_id}→ update milestone
 *   GET    /registry/cases/{case_id}/documents                → list documents for case
 *   PATCH  /registry/cases/{case_id}/documents/{document_id}  → update document
 *
 * Note: The legacy /registration/* aliases exist on the backend for
 * backward compatibility but are not used here. All calls use the
 * canonical /registry/* routes.
 */

import { apiFetch } from "./api-client";
import type {
  RegistrationCase,
  RegistrationCaseCreate,
  RegistrationCaseListResponse,
  RegistrationCaseUpdate,
  RegistrationDocument,
  RegistrationDocumentUpdate,
  RegistrationMilestone,
  RegistrationMilestoneUpdate,
  RegistrationSummaryResponse,
} from "./registry-types";

// ---------------------------------------------------------------------------
// Case endpoints
// ---------------------------------------------------------------------------

export async function createCase(
  data: RegistrationCaseCreate,
): Promise<RegistrationCase> {
  return apiFetch<RegistrationCase>("/registry/cases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function getCase(caseId: string): Promise<RegistrationCase> {
  return apiFetch<RegistrationCase>(
    `/registry/cases/${encodeURIComponent(caseId)}`,
  );
}

export async function getCaseBySaleContract(
  saleContractId: string,
): Promise<RegistrationCase> {
  return apiFetch<RegistrationCase>(
    `/registry/cases/by-sale/${encodeURIComponent(saleContractId)}`,
  );
}

export async function updateCase(
  caseId: string,
  data: RegistrationCaseUpdate,
): Promise<RegistrationCase> {
  return apiFetch<RegistrationCase>(
    `/registry/cases/${encodeURIComponent(caseId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}

// ---------------------------------------------------------------------------
// Project-scoped endpoints
// ---------------------------------------------------------------------------

export async function listProjectCases(
  projectId: string,
  params?: { skip?: number; limit?: number },
): Promise<RegistrationCaseListResponse> {
  const query = new URLSearchParams();
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiFetch<RegistrationCaseListResponse>(
    `/registry/projects/${encodeURIComponent(projectId)}/cases${qs ? `?${qs}` : ""}`,
  );
}

export async function getProjectSummary(
  projectId: string,
): Promise<RegistrationSummaryResponse> {
  return apiFetch<RegistrationSummaryResponse>(
    `/registry/projects/${encodeURIComponent(projectId)}/summary`,
  );
}

// ---------------------------------------------------------------------------
// Milestone endpoints
// ---------------------------------------------------------------------------

export async function listMilestones(
  caseId: string,
): Promise<RegistrationMilestone[]> {
  return apiFetch<RegistrationMilestone[]>(
    `/registry/cases/${encodeURIComponent(caseId)}/milestones`,
  );
}

export async function updateMilestone(
  caseId: string,
  milestoneId: string,
  data: RegistrationMilestoneUpdate,
): Promise<RegistrationMilestone> {
  return apiFetch<RegistrationMilestone>(
    `/registry/cases/${encodeURIComponent(caseId)}/milestones/${encodeURIComponent(milestoneId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}

// ---------------------------------------------------------------------------
// Document endpoints
// ---------------------------------------------------------------------------

export async function listDocuments(
  caseId: string,
): Promise<RegistrationDocument[]> {
  return apiFetch<RegistrationDocument[]>(
    `/registry/cases/${encodeURIComponent(caseId)}/documents`,
  );
}

export async function updateDocument(
  caseId: string,
  documentId: string,
  data: RegistrationDocumentUpdate,
): Promise<RegistrationDocument> {
  return apiFetch<RegistrationDocument>(
    `/registry/cases/${encodeURIComponent(caseId)}/documents/${encodeURIComponent(documentId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}
