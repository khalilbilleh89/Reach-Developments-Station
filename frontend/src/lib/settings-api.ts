/**
 * settings-api.ts — API wrapper for the Settings domain.
 *
 * All settings data fetching and mutation is centralised here.
 *
 * Paths are relative to the API prefix already embedded in BASE_URL
 * (e.g. /api/v1) — do NOT include /api/v1 here.
 *
 * Backend endpoints used:
 *
 * PricingPolicy:
 *   POST   /settings/pricing-policies               → create pricing policy
 *   GET    /settings/pricing-policies               → list pricing policies
 *   GET    /settings/pricing-policies/{id}          → get pricing policy by id
 *   PATCH  /settings/pricing-policies/{id}          → update pricing policy
 *   DELETE /settings/pricing-policies/{id}          → delete pricing policy
 *
 * CommissionPolicy:
 *   POST   /settings/commission-policies            → create commission policy
 *   GET    /settings/commission-policies            → list commission policies
 *   GET    /settings/commission-policies/{id}       → get commission policy by id
 *   PATCH  /settings/commission-policies/{id}       → update commission policy
 *   DELETE /settings/commission-policies/{id}       → delete commission policy
 *
 * ProjectTemplate:
 *   POST   /settings/project-templates              → create project template
 *   GET    /settings/project-templates              → list project templates
 *   GET    /settings/project-templates/{id}         → get project template by id
 *   PATCH  /settings/project-templates/{id}         → update project template
 *   DELETE /settings/project-templates/{id}         → delete project template
 */

import { apiFetch } from "./api-client";
import type {
  CommissionPolicy,
  CommissionPolicyCreate,
  CommissionPolicyList,
  CommissionPolicyUpdate,
  PricingPolicy,
  PricingPolicyCreate,
  PricingPolicyList,
  PricingPolicyUpdate,
  ProjectTemplate,
  ProjectTemplateCreate,
  ProjectTemplateList,
  ProjectTemplateUpdate,
} from "./settings-types";

// ---------------------------------------------------------------------------
// PricingPolicy endpoints
// ---------------------------------------------------------------------------

export async function listPricingPolicies(params?: {
  is_active?: boolean;
  skip?: number;
  limit?: number;
}): Promise<PricingPolicyList> {
  const query = new URLSearchParams();
  if (params?.is_active !== undefined)
    query.set("is_active", String(params.is_active));
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiFetch<PricingPolicyList>(
    `/settings/pricing-policies${qs ? `?${qs}` : ""}`,
  );
}

export async function getPricingPolicy(id: string): Promise<PricingPolicy> {
  return apiFetch<PricingPolicy>(
    `/settings/pricing-policies/${encodeURIComponent(id)}`,
  );
}

export async function createPricingPolicy(
  data: PricingPolicyCreate,
): Promise<PricingPolicy> {
  return apiFetch<PricingPolicy>("/settings/pricing-policies", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updatePricingPolicy(
  id: string,
  data: PricingPolicyUpdate,
): Promise<PricingPolicy> {
  return apiFetch<PricingPolicy>(
    `/settings/pricing-policies/${encodeURIComponent(id)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}

export async function makeDefaultPricingPolicy(id: string): Promise<PricingPolicy> {
  return apiFetch<PricingPolicy>(
    `/settings/pricing-policies/${encodeURIComponent(id)}/make-default`,
    { method: "POST" },
  );
}

export async function deletePricingPolicy(id: string): Promise<void> {
  return apiFetch<void>(
    `/settings/pricing-policies/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  );
}

// ---------------------------------------------------------------------------
// CommissionPolicy endpoints
// ---------------------------------------------------------------------------

export async function listCommissionPolicies(params?: {
  is_active?: boolean;
  skip?: number;
  limit?: number;
}): Promise<CommissionPolicyList> {
  const query = new URLSearchParams();
  if (params?.is_active !== undefined)
    query.set("is_active", String(params.is_active));
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiFetch<CommissionPolicyList>(
    `/settings/commission-policies${qs ? `?${qs}` : ""}`,
  );
}

export async function getCommissionPolicy(
  id: string,
): Promise<CommissionPolicy> {
  return apiFetch<CommissionPolicy>(
    `/settings/commission-policies/${encodeURIComponent(id)}`,
  );
}

export async function createCommissionPolicy(
  data: CommissionPolicyCreate,
): Promise<CommissionPolicy> {
  return apiFetch<CommissionPolicy>("/settings/commission-policies", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateCommissionPolicy(
  id: string,
  data: CommissionPolicyUpdate,
): Promise<CommissionPolicy> {
  return apiFetch<CommissionPolicy>(
    `/settings/commission-policies/${encodeURIComponent(id)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}

export async function makeDefaultCommissionPolicy(
  id: string,
): Promise<CommissionPolicy> {
  return apiFetch<CommissionPolicy>(
    `/settings/commission-policies/${encodeURIComponent(id)}/make-default`,
    { method: "POST" },
  );
}

export async function deleteCommissionPolicy(id: string): Promise<void> {
  return apiFetch<void>(
    `/settings/commission-policies/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  );
}

// ---------------------------------------------------------------------------
// ProjectTemplate endpoints
// ---------------------------------------------------------------------------

export async function listProjectTemplates(params?: {
  is_active?: boolean;
  skip?: number;
  limit?: number;
}): Promise<ProjectTemplateList> {
  const query = new URLSearchParams();
  if (params?.is_active !== undefined)
    query.set("is_active", String(params.is_active));
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiFetch<ProjectTemplateList>(
    `/settings/project-templates${qs ? `?${qs}` : ""}`,
  );
}

export async function getProjectTemplate(
  id: string,
): Promise<ProjectTemplate> {
  return apiFetch<ProjectTemplate>(
    `/settings/project-templates/${encodeURIComponent(id)}`,
  );
}

export async function createProjectTemplate(
  data: ProjectTemplateCreate,
): Promise<ProjectTemplate> {
  return apiFetch<ProjectTemplate>("/settings/project-templates", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateProjectTemplate(
  id: string,
  data: ProjectTemplateUpdate,
): Promise<ProjectTemplate> {
  return apiFetch<ProjectTemplate>(
    `/settings/project-templates/${encodeURIComponent(id)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
}

export async function deleteProjectTemplate(id: string): Promise<void> {
  return apiFetch<void>(
    `/settings/project-templates/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  );
}
