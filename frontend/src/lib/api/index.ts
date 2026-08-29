/**
 * Typed API operations, grouped by resource.
 *
 * Every network call the application makes goes through one of these.
 */

import { get, patch, post, postCsv, put } from "./client";
import type {
  AdminUser,
  ApprovalThresholds,
  AreaSchedule,
  AreaType,
  AuditEvent,
  Building,
  CountryPack,
  Currency,
  CurrentUser,
  CustomValue,
  DocumentReference,
  Floor,
  ImportReport,
  LandParcel,
  Page,
  Permit,
  PermitRegister,
  PermitStatusEvent,
  Phase,
  PhaseAccess,
  PlanningControl,
  ProjectAccess,
  ProjectDetail,
  ProjectSummary,
  ReferenceValue,
  Role,
  SubAsset,
  TaxRule,
  Unit,
  UnitRegister,
  UnitStatusEvent,
} from "./types";

export { ApiError } from "./client";
export type * from "./types";

export const auth = {
  me: () => get<CurrentUser>("/auth/me"),
  login: (email: string, password: string) =>
    post<CurrentUser>("/auth/login", { email, password }),
  logout: () => post<void>("/auth/logout"),
  changePassword: (newPassword: string, currentPassword?: string) =>
    post<void>("/auth/change-password", {
      new_password: newPassword,
      ...(currentPassword ? { current_password: currentPassword } : {}),
    }),
};

export const users = {
  list: (search?: string) =>
    get<Page<AdminUser>>(`/admin/users?limit=200${search ? `&search=${encodeURIComponent(search)}` : ""}`),
  create: (input: {
    email: string;
    display_name: string;
    initial_password: string;
    role_keys: string[];
  }) => post<AdminUser>("/admin/users", input),
  update: (
    id: string,
    input: { display_name?: string; is_active?: boolean; role_keys?: string[]; reason?: string },
  ) => patch<AdminUser>(`/admin/users/${id}`, input),
  resetPassword: (id: string, newPassword: string) =>
    post<void>(`/admin/users/${id}/reset-password`, { new_password: newPassword }),
  roles: () => get<Role[]>("/admin/roles"),
};

export const settings = {
  currencies: () => get<Currency[]>("/settings/currencies"),
  createCurrency: (input: {
    code: string;
    name: string;
    symbol?: string | null;
    minor_units: number;
  }) => post<Currency>("/settings/currencies", input),

  countryPacks: () => get<CountryPack[]>("/settings/country-packs"),
  createCountryPack: (input: {
    country_code: string;
    name: string;
    locale: string;
    timezone: string;
    default_currency_id: string;
    area_unit: string;
    fiscal_year_start_month: number;
  }) => post<CountryPack>("/settings/country-packs", input),
  updateCountryPack: (id: string, input: Record<string, unknown>) =>
    patch<CountryPack>(`/settings/country-packs/${id}`, input),

  taxRules: (packId: string) => get<TaxRule[]>(`/settings/country-packs/${packId}/tax-rules`),
  createTaxRule: (
    packId: string,
    input: {
      tax_code: string;
      label: string;
      applies_to: string;
      calculation_basis: string;
      rate_fraction: string;
      valid_from: string;
      valid_to?: string | null;
    },
  ) => post<TaxRule>(`/settings/country-packs/${packId}/tax-rules`, input),
  updateTaxRule: (id: string, input: Record<string, unknown>) =>
    patch<TaxRule>(`/settings/tax-rules/${id}`, input),

  referenceValues: () => get<ReferenceValue[]>("/settings/reference-values"),
  createReferenceValue: (input: {
    country_pack_id?: string | null;
    category: string;
    code: string;
    label: string;
    description?: string | null;
    sort_order: number;
  }) => post<ReferenceValue>("/settings/reference-values", input),
  updateReferenceValue: (id: string, input: Record<string, unknown>) =>
    patch<ReferenceValue>(`/settings/reference-values/${id}`, input),

  approvalThresholds: (packId: string) =>
    get<ApprovalThresholds>(`/settings/country-packs/${packId}/approval-thresholds`),
  writeApprovalThresholds: (packId: string, input: Record<string, unknown>) =>
    put<ApprovalThresholds>(`/settings/country-packs/${packId}/approval-thresholds`, input),
};

export const audit = {
  list: (limit = 100) => get<Page<AuditEvent>>(`/audit-events?limit=${limit}`),
};

/**
 * Project workspace operations.
 *
 * Every path is project-scoped. The API establishes the security boundary for
 * itself on each request; these helpers just describe the shape of the call.
 */
export const projects = {
  list: (query: { search?: string; status?: string } = {}) => {
    const params = new URLSearchParams({ limit: "100" });
    if (query.search) params.set("search", query.search);
    if (query.status) params.set("status", query.status);
    return get<ProjectSummary[]>(`/projects?${params.toString()}`);
  },
  read: (id: string) => get<ProjectDetail>(`/projects/${id}`),
  create: (input: Record<string, unknown>) => post<ProjectDetail>("/projects", input),
  update: (id: string, input: Record<string, unknown>) =>
    patch<ProjectDetail>(`/projects/${id}`, input),

  access: (id: string) => get<ProjectAccess[]>(`/projects/${id}/access`),
  grantAccess: (id: string, userId: string) =>
    put<ProjectAccess>(`/projects/${id}/access/${userId}`, {}),
  setAccess: (id: string, userId: string, isActive: boolean) =>
    patch<ProjectAccess>(`/projects/${id}/access/${userId}`, { is_active: isActive }),

  parcels: (id: string) => get<LandParcel[]>(`/projects/${id}/parcels`),
  createParcel: (id: string, input: Record<string, unknown>) =>
    post<LandParcel>(`/projects/${id}/parcels`, input),
  updateParcel: (id: string, parcelId: string, input: Record<string, unknown>) =>
    patch<LandParcel>(`/projects/${id}/parcels/${parcelId}`, input),

  planning: (id: string, parcelId: string) =>
    get<PlanningControl>(`/projects/${id}/parcels/${parcelId}/planning-controls`),
  writePlanning: (id: string, parcelId: string, input: Record<string, unknown>) =>
    put<PlanningControl>(`/projects/${id}/parcels/${parcelId}/planning-controls`, input),

  permits: (id: string, query: Record<string, string> = {}) => {
    const params = new URLSearchParams(query);
    const suffix = params.toString();
    return get<PermitRegister>(`/projects/${id}/permits${suffix ? `?${suffix}` : ""}`);
  },
  createPermit: (id: string, input: Record<string, unknown>) =>
    post<Permit>(`/projects/${id}/permits`, input),
  updatePermit: (id: string, permitId: string, input: Record<string, unknown>) =>
    patch<Permit>(`/projects/${id}/permits/${permitId}`, input),
  transitionPermit: (
    id: string,
    permitId: string,
    input: { to_status: string; effective_date: string; reason?: string; notes?: string },
  ) => post<Permit>(`/projects/${id}/permits/${permitId}/transitions`, input),
  permitHistory: (id: string, permitId: string) =>
    get<PermitStatusEvent[]>(`/projects/${id}/permits/${permitId}/status-history`),

  documents: (id: string) => get<DocumentReference[]>(`/projects/${id}/documents`),
  createDocument: (id: string, input: Record<string, unknown>) =>
    post<DocumentReference>(`/projects/${id}/documents`, input),
  updateDocument: (id: string, documentId: string, input: Record<string, unknown>) =>
    patch<DocumentReference>(`/projects/${id}/documents/${documentId}`, input),
};

/**
 * Inventory: the physical catalogue inside a project.
 *
 * Grouped separately from `projects` because it is a separate domain on the
 * server, and every path here is scoped to the project that owns the records.
 */
export const inventory = {
  phases: (projectId: string) => get<Phase[]>(`/projects/${projectId}/inventory/phases`),
  createPhase: (projectId: string, input: Record<string, unknown>) =>
    post<Phase>(`/projects/${projectId}/inventory/phases`, input),
  updatePhase: (projectId: string, phaseId: string, input: Record<string, unknown>) =>
    patch<Phase>(`/projects/${projectId}/inventory/phases/${phaseId}`, input),

  buildings: (projectId: string, phaseId?: string) =>
    get<Building[]>(
      `/projects/${projectId}/inventory/buildings${phaseId ? `?phase_id=${phaseId}` : ""}`,
    ),
  createBuilding: (projectId: string, input: Record<string, unknown>) =>
    post<Building>(`/projects/${projectId}/inventory/buildings`, input),

  floors: (projectId: string, query: { building_id?: string; phase_id?: string } = {}) => {
    const params = new URLSearchParams(query as Record<string, string>);
    const suffix = params.toString();
    return get<Floor[]>(`/projects/${projectId}/inventory/floors${suffix ? `?${suffix}` : ""}`);
  },
  createFloor: (projectId: string, input: Record<string, unknown>) =>
    post<Floor>(`/projects/${projectId}/inventory/floors`, input),

  units: (projectId: string, query: Record<string, string> = {}) => {
    const params = new URLSearchParams(query);
    const suffix = params.toString();
    return get<UnitRegister>(`/projects/${projectId}/inventory/units${suffix ? `?${suffix}` : ""}`);
  },
  unit: (projectId: string, unitId: string) =>
    get<Unit>(`/projects/${projectId}/inventory/units/${unitId}`),
  createUnit: (projectId: string, input: Record<string, unknown>) =>
    post<Unit>(`/projects/${projectId}/inventory/units`, input),
  updateUnit: (projectId: string, unitId: string, input: Record<string, unknown>) =>
    patch<Unit>(`/projects/${projectId}/inventory/units/${unitId}`, input),
  releaseControls: (projectId: string, unitId: string, input: Record<string, unknown>) =>
    patch<Unit>(`/projects/${projectId}/inventory/units/${unitId}/release-controls`, input),
  transitionUnit: (
    projectId: string,
    unitId: string,
    input: { to_status: string; effective_date: string; reason?: string; notes?: string },
  ) => post<Unit>(`/projects/${projectId}/inventory/units/${unitId}/commercial-transitions`, input),
  unitHistory: (projectId: string, unitId: string) =>
    get<UnitStatusEvent[]>(`/projects/${projectId}/inventory/units/${unitId}/status-history`),

  areaTypes: (projectId: string) =>
    get<AreaType[]>(`/projects/${projectId}/inventory/area-types`),
  createAreaType: (projectId: string, input: Record<string, unknown>) =>
    post<AreaType>(`/projects/${projectId}/inventory/area-types`, input),
  updateAreaType: (projectId: string, areaTypeId: string, input: Record<string, unknown>) =>
    patch<AreaType>(`/projects/${projectId}/inventory/area-types/${areaTypeId}`, input),

  areaSchedules: (projectId: string, unitId: string) =>
    get<AreaSchedule[]>(`/projects/${projectId}/inventory/units/${unitId}/area-schedules`),
  createAreaSchedule: (projectId: string, unitId: string, input: Record<string, unknown>) =>
    post<AreaSchedule>(`/projects/${projectId}/inventory/units/${unitId}/area-schedules`, input),
  updateAreaSchedule: (
    projectId: string,
    unitId: string,
    scheduleId: string,
    input: Record<string, unknown>,
  ) =>
    patch<AreaSchedule>(
      `/projects/${projectId}/inventory/units/${unitId}/area-schedules/${scheduleId}`,
      input,
    ),
  approveAreaSchedule: (projectId: string, unitId: string, scheduleId: string) =>
    post<AreaSchedule>(
      `/projects/${projectId}/inventory/units/${unitId}/area-schedules/${scheduleId}/approve`,
    ),

  subAssets: (projectId: string, query: Record<string, string> = {}) => {
    const params = new URLSearchParams(query);
    const suffix = params.toString();
    return get<SubAsset[]>(
      `/projects/${projectId}/inventory/sub-assets${suffix ? `?${suffix}` : ""}`,
    );
  },
  createSubAsset: (projectId: string, input: Record<string, unknown>) =>
    post<SubAsset>(`/projects/${projectId}/inventory/sub-assets`, input),
  updateSubAsset: (projectId: string, assetId: string, input: Record<string, unknown>) =>
    patch<SubAsset>(`/projects/${projectId}/inventory/sub-assets/${assetId}`, input),

  unitValues: (projectId: string, unitId: string) =>
    get<CustomValue[]>(`/projects/${projectId}/inventory/units/${unitId}/custom-values`),
  writeUnitValues: (
    projectId: string,
    unitId: string,
    values: Record<string, unknown>,
    changeReason?: string,
  ) =>
    put<CustomValue[]>(`/projects/${projectId}/inventory/units/${unitId}/custom-values`, {
      values,
      ...(changeReason ? { change_reason: changeReason } : {}),
    }),

  phaseScope: (projectId: string, userId: string, scope: "all" | "selected") =>
    patch<{ phase_scope: string }>(`/projects/${projectId}/access/${userId}/phase-scope`, {
      phase_scope: scope,
    }),
  phaseAccess: (projectId: string, userId: string) =>
    get<PhaseAccess[]>(`/projects/${projectId}/access/${userId}/phases`),
  setPhaseAccess: (projectId: string, userId: string, phaseId: string, isActive: boolean) =>
    patch<PhaseAccess>(`/projects/${projectId}/access/${userId}/phases/${phaseId}`, {
      is_active: isActive,
    }),
  grantPhaseAccess: (projectId: string, userId: string, phaseId: string) =>
    put<PhaseAccess>(`/projects/${projectId}/access/${userId}/phases/${phaseId}`, {}),

  importTemplate: (projectId: string) =>
    get<{ filename: string; content: string }>(
      `/projects/${projectId}/inventory/import/template`,
    ),
  validateImport: (projectId: string, csv: string, query: Record<string, string>) =>
    postCsv<ImportReport>(
      `/projects/${projectId}/inventory/import/validate?${new URLSearchParams(query)}`,
      csv,
    ),
  applyImport: (projectId: string, csv: string, query: Record<string, string>) =>
    postCsv<ImportReport>(
      `/projects/${projectId}/inventory/import/apply?${new URLSearchParams(query)}`,
      csv,
    ),
};
