/**
 * Typed API operations, grouped by resource.
 *
 * Every network call the application makes goes through one of these.
 */

import { get, patch, post, postCsv, put, remove } from "./client";
import type {
  AdminUser,
  BudgetDetail,
  BudgetVersion,
  Certificate,
  CertificateDetail,
  ConstructionContract,
  ConstructionInvoice,
  ConstructionMilestone,
  ConstructionPayment,
  ConstructionReconciliation,
  ConstructionSummary,
  ContractDetail,
  CostCode,
  DeliveryResult,
  ForecastDetail,
  ForecastVersion,
  MilestoneCertified,
  MilestoneTriggerOption,
  Variation,
  VariationDetail,
  ApprovalThresholds,
  AreaSchedule,
  AreaType,
  AgingRow,
  AuditEvent,
  Building,
  CollectionAction,
  CollectionClearance,
  CollectionDispute,
  CollectionProjectSummary,
  CollectionRefund,
  CollectionRegisterRow,
  CollectionRestructure,
  CollectionSaleSummary,
  CollectionWaiver,
  CountryPack,
  Currency,
  CurrentUser,
  CustomValue,
  DocumentReference,
  EscalationActivation,
  Floor,
  ImportReport,
  LandParcel,
  MarketBenchmark,
  Page,
  PaymentPlanDetail,
  PlanRegister,
  PlanVersionDetail,
  Permit,
  PermitRegister,
  PermitStatusEvent,
  Phase,
  PhaseAccess,
  PlanningControl,
  PriceRegister,
  PriceVersion,
  Receipt,
  ReceiptAllocation as ReceiptAllocationResponse,
  RestructureApplyResult,
  RestructurePreview,
  SuggestedAllocation,
  PriceVersionDetail,
  PricingAreaRule,
  PricingConfiguration,
  PricingEscalationRule,
  PricingOverview,
  PricingPremiumRule,
  ProjectAccess,
  ProjectDetail,
  ProjectSummary,
  QuotePreview,
  ReferenceValue,
  Reservation,
  ReservationAdjustment,
  ReservationDetail,
  Role,
  SaleCancellation,
  SaleContract,
  SaleDetail,
  SalesClient,
  ClientParty,
  HandoverDetail,
  HandoverClearance,
  LegalTimeline,
  SalesPolicy,
  SalesRegister,
  InstallmentTriggerEvent,
  SeriesPreview,
  ShareReconciliation,
  SubAsset,
  TriggerRefreshResult,
  TaxRule,
  Unit,
  UnitPricing,
  UnitRegister,
  UnitStatusEvent,
  AllocationVersion,
  AllocationVersionDetail,
  CalculationPreview,
  CostPool,
  ProjectEconomics,
  UnitAllocation,
  UnitCost,
  UnitEconomics as UnitEconomicsRow,
  UnitEconomicsDetail,
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
    get<Page<AdminUser>>(
      `/admin/users?limit=200${search ? `&search=${encodeURIComponent(search)}` : ""}`,
    ),
  create: (input: {
    email: string;
    display_name: string;
    initial_password: string;
    role_keys: string[];
  }) => post<AdminUser>("/admin/users", input),
  update: (
    id: string,
    input: {
      display_name?: string;
      is_active?: boolean;
      role_keys?: string[];
      reason?: string;
    },
  ) => patch<AdminUser>(`/admin/users/${id}`, input),
  resetPassword: (id: string, newPassword: string) =>
    post<void>(`/admin/users/${id}/reset-password`, {
      new_password: newPassword,
    }),
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

  taxRules: (packId: string) =>
    get<TaxRule[]>(`/settings/country-packs/${packId}/tax-rules`),
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
    get<ApprovalThresholds>(
      `/settings/country-packs/${packId}/approval-thresholds`,
    ),
  writeApprovalThresholds: (packId: string, input: Record<string, unknown>) =>
    put<ApprovalThresholds>(
      `/settings/country-packs/${packId}/approval-thresholds`,
      input,
    ),
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
  create: (input: Record<string, unknown>) =>
    post<ProjectDetail>("/projects", input),
  update: (id: string, input: Record<string, unknown>) =>
    patch<ProjectDetail>(`/projects/${id}`, input),

  access: (id: string) => get<ProjectAccess[]>(`/projects/${id}/access`),
  grantAccess: (id: string, userId: string) =>
    put<ProjectAccess>(`/projects/${id}/access/${userId}`, {}),
  setAccess: (id: string, userId: string, isActive: boolean) =>
    patch<ProjectAccess>(`/projects/${id}/access/${userId}`, {
      is_active: isActive,
    }),

  parcels: (id: string) => get<LandParcel[]>(`/projects/${id}/parcels`),
  createParcel: (id: string, input: Record<string, unknown>) =>
    post<LandParcel>(`/projects/${id}/parcels`, input),
  updateParcel: (
    id: string,
    parcelId: string,
    input: Record<string, unknown>,
  ) => patch<LandParcel>(`/projects/${id}/parcels/${parcelId}`, input),

  planning: (id: string, parcelId: string) =>
    get<PlanningControl>(
      `/projects/${id}/parcels/${parcelId}/planning-controls`,
    ),
  writePlanning: (
    id: string,
    parcelId: string,
    input: Record<string, unknown>,
  ) =>
    put<PlanningControl>(
      `/projects/${id}/parcels/${parcelId}/planning-controls`,
      input,
    ),

  permits: (id: string, query: Record<string, string> = {}) => {
    const params = new URLSearchParams(query);
    const suffix = params.toString();
    return get<PermitRegister>(
      `/projects/${id}/permits${suffix ? `?${suffix}` : ""}`,
    );
  },
  createPermit: (id: string, input: Record<string, unknown>) =>
    post<Permit>(`/projects/${id}/permits`, input),
  updatePermit: (
    id: string,
    permitId: string,
    input: Record<string, unknown>,
  ) => patch<Permit>(`/projects/${id}/permits/${permitId}`, input),
  transitionPermit: (
    id: string,
    permitId: string,
    input: {
      to_status: string;
      effective_date: string;
      reason?: string;
      notes?: string;
    },
  ) => post<Permit>(`/projects/${id}/permits/${permitId}/transitions`, input),
  permitHistory: (id: string, permitId: string) =>
    get<PermitStatusEvent[]>(
      `/projects/${id}/permits/${permitId}/status-history`,
    ),

  documents: (id: string) =>
    get<DocumentReference[]>(`/projects/${id}/documents`),
  createDocument: (id: string, input: Record<string, unknown>) =>
    post<DocumentReference>(`/projects/${id}/documents`, input),
  updateDocument: (
    id: string,
    documentId: string,
    input: Record<string, unknown>,
  ) =>
    patch<DocumentReference>(`/projects/${id}/documents/${documentId}`, input),
};

/**
 * Inventory: the physical catalogue inside a project.
 *
 * Grouped separately from `projects` because it is a separate domain on the
 * server, and every path here is scoped to the project that owns the records.
 */
export const inventory = {
  phases: (projectId: string) =>
    get<Phase[]>(`/projects/${projectId}/inventory/phases`),
  createPhase: (projectId: string, input: Record<string, unknown>) =>
    post<Phase>(`/projects/${projectId}/inventory/phases`, input),
  updatePhase: (
    projectId: string,
    phaseId: string,
    input: Record<string, unknown>,
  ) =>
    patch<Phase>(`/projects/${projectId}/inventory/phases/${phaseId}`, input),

  buildings: (projectId: string, phaseId?: string) =>
    get<Building[]>(
      `/projects/${projectId}/inventory/buildings${phaseId ? `?phase_id=${phaseId}` : ""}`,
    ),
  createBuilding: (projectId: string, input: Record<string, unknown>) =>
    post<Building>(`/projects/${projectId}/inventory/buildings`, input),

  floors: (
    projectId: string,
    query: { building_id?: string; phase_id?: string } = {},
  ) => {
    const params = new URLSearchParams(query as Record<string, string>);
    const suffix = params.toString();
    return get<Floor[]>(
      `/projects/${projectId}/inventory/floors${suffix ? `?${suffix}` : ""}`,
    );
  },
  createFloor: (projectId: string, input: Record<string, unknown>) =>
    post<Floor>(`/projects/${projectId}/inventory/floors`, input),

  units: (projectId: string, query: Record<string, string> = {}) => {
    const params = new URLSearchParams(query);
    const suffix = params.toString();
    return get<UnitRegister>(
      `/projects/${projectId}/inventory/units${suffix ? `?${suffix}` : ""}`,
    );
  },
  unit: (projectId: string, unitId: string) =>
    get<Unit>(`/projects/${projectId}/inventory/units/${unitId}`),
  createUnit: (projectId: string, input: Record<string, unknown>) =>
    post<Unit>(`/projects/${projectId}/inventory/units`, input),
  updateUnit: (
    projectId: string,
    unitId: string,
    input: Record<string, unknown>,
  ) => patch<Unit>(`/projects/${projectId}/inventory/units/${unitId}`, input),
  releaseControls: (
    projectId: string,
    unitId: string,
    input: Record<string, unknown>,
  ) =>
    patch<Unit>(
      `/projects/${projectId}/inventory/units/${unitId}/release-controls`,
      input,
    ),
  transitionUnit: (
    projectId: string,
    unitId: string,
    input: {
      to_status: string;
      effective_date: string;
      reason?: string;
      notes?: string;
    },
  ) =>
    post<Unit>(
      `/projects/${projectId}/inventory/units/${unitId}/commercial-transitions`,
      input,
    ),
  unitHistory: (projectId: string, unitId: string) =>
    get<UnitStatusEvent[]>(
      `/projects/${projectId}/inventory/units/${unitId}/status-history`,
    ),

  areaTypes: (projectId: string) =>
    get<AreaType[]>(`/projects/${projectId}/inventory/area-types`),
  createAreaType: (projectId: string, input: Record<string, unknown>) =>
    post<AreaType>(`/projects/${projectId}/inventory/area-types`, input),
  updateAreaType: (
    projectId: string,
    areaTypeId: string,
    input: Record<string, unknown>,
  ) =>
    patch<AreaType>(
      `/projects/${projectId}/inventory/area-types/${areaTypeId}`,
      input,
    ),

  areaSchedules: (projectId: string, unitId: string) =>
    get<AreaSchedule[]>(
      `/projects/${projectId}/inventory/units/${unitId}/area-schedules`,
    ),
  createAreaSchedule: (
    projectId: string,
    unitId: string,
    input: Record<string, unknown>,
  ) =>
    post<AreaSchedule>(
      `/projects/${projectId}/inventory/units/${unitId}/area-schedules`,
      input,
    ),
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
  approveAreaSchedule: (
    projectId: string,
    unitId: string,
    scheduleId: string,
  ) =>
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
  updateSubAsset: (
    projectId: string,
    assetId: string,
    input: Record<string, unknown>,
  ) =>
    patch<SubAsset>(
      `/projects/${projectId}/inventory/sub-assets/${assetId}`,
      input,
    ),

  unitValues: (projectId: string, unitId: string) =>
    get<CustomValue[]>(
      `/projects/${projectId}/inventory/units/${unitId}/custom-values`,
    ),
  writeUnitValues: (
    projectId: string,
    unitId: string,
    values: Record<string, unknown>,
    changeReason?: string,
  ) =>
    put<CustomValue[]>(
      `/projects/${projectId}/inventory/units/${unitId}/custom-values`,
      {
        values,
        ...(changeReason ? { change_reason: changeReason } : {}),
      },
    ),

  phaseScope: (projectId: string, userId: string, scope: "all" | "selected") =>
    patch<{ phase_scope: string }>(
      `/projects/${projectId}/access/${userId}/phase-scope`,
      {
        phase_scope: scope,
      },
    ),
  phaseAccess: (projectId: string, userId: string) =>
    get<PhaseAccess[]>(`/projects/${projectId}/access/${userId}/phases`),
  setPhaseAccess: (
    projectId: string,
    userId: string,
    phaseId: string,
    isActive: boolean,
  ) =>
    patch<PhaseAccess>(
      `/projects/${projectId}/access/${userId}/phases/${phaseId}`,
      {
        is_active: isActive,
      },
    ),
  grantPhaseAccess: (projectId: string, userId: string, phaseId: string) =>
    put<PhaseAccess>(
      `/projects/${projectId}/access/${userId}/phases/${phaseId}`,
      {},
    ),

  importTemplate: (projectId: string) =>
    get<{ filename: string; content: string }>(
      `/projects/${projectId}/inventory/import/template`,
    ),
  validateImport: (
    projectId: string,
    csv: string,
    query: Record<string, string>,
  ) =>
    postCsv<ImportReport>(
      `/projects/${projectId}/inventory/import/validate?${new URLSearchParams(query)}`,
      csv,
    ),
  applyImport: (
    projectId: string,
    csv: string,
    query: Record<string, string>,
  ) =>
    postCsv<ImportReport>(
      `/projects/${projectId}/inventory/import/apply?${new URLSearchParams(query)}`,
      csv,
    ),
};

/**
 * Pricing.
 *
 * The browser sends inputs and renders what comes back. Every figure on a
 * pricing screen — a premium, a cap, a deviation, a quote waterfall — is
 * computed by the backend, because two implementations of one formula is one
 * implementation that eventually disagrees with the register.
 */
export const pricing = {
  overview: (projectId: string) =>
    get<PricingOverview>(`/projects/${projectId}/pricing/overview`),
  register: (projectId: string, query: Record<string, string> = {}) =>
    get<PriceRegister>(
      `/projects/${projectId}/pricing/register?${new URLSearchParams(query)}`,
    ),

  configurations: (projectId: string) =>
    get<PricingConfiguration[]>(
      `/projects/${projectId}/pricing/configurations`,
    ),
  createConfiguration: (projectId: string, body: Record<string, unknown>) =>
    post<PricingConfiguration>(
      `/projects/${projectId}/pricing/configurations`,
      body,
    ),
  updateConfiguration: (
    projectId: string,
    id: string,
    body: Record<string, unknown>,
  ) =>
    patch<PricingConfiguration>(
      `/projects/${projectId}/pricing/configurations/${id}`,
      body,
    ),
  submitConfiguration: (projectId: string, id: string, reason?: string) =>
    post<PricingConfiguration>(
      `/projects/${projectId}/pricing/configurations/${id}/submit`,
      {
        ...(reason ? { reason } : {}),
      },
    ),
  approveConfiguration: (projectId: string, id: string, reason: string) =>
    post<PricingConfiguration>(
      `/projects/${projectId}/pricing/configurations/${id}/approve`,
      {
        reason,
      },
    ),
  returnConfiguration: (projectId: string, id: string, reason: string) =>
    post<PricingConfiguration>(
      `/projects/${projectId}/pricing/configurations/${id}/return`,
      {
        reason,
      },
    ),
  activateConfiguration: (projectId: string, id: string) =>
    post<PricingConfiguration>(
      `/projects/${projectId}/pricing/configurations/${id}/activate`,
    ),

  areaRules: (projectId: string, configurationId: string) =>
    get<PricingAreaRule[]>(
      `/projects/${projectId}/pricing/configurations/${configurationId}/area-rules`,
    ),
  createAreaRule: (
    projectId: string,
    configurationId: string,
    body: Record<string, unknown>,
  ) =>
    post<PricingAreaRule>(
      `/projects/${projectId}/pricing/configurations/${configurationId}/area-rules`,
      body,
    ),
  premiumRules: (projectId: string, configurationId: string) =>
    get<PricingPremiumRule[]>(
      `/projects/${projectId}/pricing/configurations/${configurationId}/premium-rules`,
    ),
  createPremiumRule: (
    projectId: string,
    configurationId: string,
    body: Record<string, unknown>,
  ) =>
    post<PricingPremiumRule>(
      `/projects/${projectId}/pricing/configurations/${configurationId}/premium-rules`,
      body,
    ),

  escalationRules: (projectId: string) =>
    get<PricingEscalationRule[]>(
      `/projects/${projectId}/pricing/escalation-rules`,
    ),
  createEscalationRule: (
    projectId: string,
    configurationId: string,
    body: Record<string, unknown>,
  ) =>
    post<PricingEscalationRule>(
      `/projects/${projectId}/pricing/configurations/${configurationId}/escalation-rules`,
      body,
    ),
  activations: (projectId: string) =>
    get<EscalationActivation[]>(
      `/projects/${projectId}/pricing/escalation-activations`,
    ),
  activateEscalation: (
    projectId: string,
    ruleId: string,
    body: Record<string, unknown>,
  ) =>
    post<EscalationActivation>(
      `/projects/${projectId}/pricing/escalation-rules/${ruleId}/activate`,
      body,
    ),
  reverseActivation: (
    projectId: string,
    activationId: string,
    reason: string,
  ) =>
    post<EscalationActivation>(
      `/projects/${projectId}/pricing/escalation-activations/${activationId}/reverse`,
      { reason },
    ),

  benchmarks: (projectId: string) =>
    get<MarketBenchmark[]>(`/projects/${projectId}/pricing/market-benchmarks`),
  createBenchmark: (projectId: string, body: Record<string, unknown>) =>
    post<MarketBenchmark>(
      `/projects/${projectId}/pricing/market-benchmarks`,
      body,
    ),

  unit: (projectId: string, unitId: string) =>
    get<UnitPricing>(`/projects/${projectId}/pricing/units/${unitId}`),
  createPriceVersion: (
    projectId: string,
    unitId: string,
    body: Record<string, unknown> = {},
  ) =>
    post<PriceVersionDetail>(
      `/projects/${projectId}/pricing/units/${unitId}/price-versions`,
      body,
    ),
  priceVersion: (projectId: string, versionId: string) =>
    get<PriceVersionDetail>(
      `/projects/${projectId}/pricing/price-versions/${versionId}`,
    ),
  submitPriceVersion: (projectId: string, versionId: string, reason?: string) =>
    post<PriceVersion>(
      `/projects/${projectId}/pricing/price-versions/${versionId}/submit`,
      {
        ...(reason ? { reason } : {}),
      },
    ),
  approvePriceVersion: (projectId: string, versionId: string, reason: string) =>
    post<PriceVersion>(
      `/projects/${projectId}/pricing/price-versions/${versionId}/approve`,
      {
        reason,
      },
    ),
  activatePriceVersion: (projectId: string, versionId: string) =>
    post<PriceVersion>(
      `/projects/${projectId}/pricing/price-versions/${versionId}/activate`,
    ),

  generatePrices: (projectId: string, body: Record<string, unknown>) =>
    post<PriceVersion[]>(
      `/projects/${projectId}/pricing/price-versions/generate`,
      body,
    ),
  bulkSubmit: (projectId: string, versionIds: string[]) =>
    post<PriceVersion[]>(
      `/projects/${projectId}/pricing/price-versions/submit`,
      {
        version_ids: versionIds,
      },
    ),
  bulkApprove: (projectId: string, versionIds: string[], reason: string) =>
    post<PriceVersion[]>(
      `/projects/${projectId}/pricing/price-versions/approve`,
      {
        version_ids: versionIds,
        reason,
      },
    ),
  bulkActivate: (projectId: string, versionIds: string[]) =>
    post<PriceVersion[]>(
      `/projects/${projectId}/pricing/price-versions/activate`,
      {
        version_ids: versionIds,
      },
    ),

  quotePreview: (
    projectId: string,
    unitId: string,
    body: Record<string, unknown>,
  ) =>
    post<QuotePreview>(
      `/projects/${projectId}/pricing/units/${unitId}/quote-preview`,
      body,
    ),
};

/**
 * Sales and legal.
 *
 * Every transition is its own named call. There is no `setStatus` here and no
 * generic transition helper, because the server has no route that would answer
 * one: activating a reservation, submitting a contract, recording a
 * registration and completing a handover are four different acts with four
 * different rights and four different sets of preconditions.
 *
 * Nothing in this file calculates. Discounts, tax, contract price, effective
 * net revenue and approval thresholds are the server's answers; the browser
 * sends inputs and displays what comes back.
 */
export const sales = {
  policy: (projectId: string) =>
    get<SalesPolicy>(`/projects/${projectId}/sales/policy`),
  writePolicy: (projectId: string, body: Record<string, unknown>) =>
    put<SalesPolicy>(`/projects/${projectId}/sales/policy`, body),

  register: (projectId: string, query: Record<string, string> = {}) =>
    get<SalesRegister>(
      `/projects/${projectId}/sales/register?${new URLSearchParams(query).toString()}`,
    ),

  clients: (projectId: string, query: Record<string, string> = {}) =>
    get<SalesClient[]>(
      `/projects/${projectId}/sales/clients?${new URLSearchParams(query).toString()}`,
    ),
  client: (projectId: string, clientId: string) =>
    get<SalesClient>(`/projects/${projectId}/sales/clients/${clientId}`),
  createClient: (projectId: string, body: Record<string, unknown>) =>
    post<SalesClient>(`/projects/${projectId}/sales/clients`, body),
  updateClient: (
    projectId: string,
    clientId: string,
    body: Record<string, unknown>,
  ) =>
    patch<SalesClient>(
      `/projects/${projectId}/sales/clients/${clientId}`,
      body,
    ),

  parties: (projectId: string, clientId: string) =>
    get<ClientParty[]>(
      `/projects/${projectId}/sales/clients/${clientId}/parties`,
    ),
  shareReconciliation: (projectId: string, clientId: string) =>
    get<ShareReconciliation>(
      `/projects/${projectId}/sales/clients/${clientId}/share-reconciliation`,
    ),
  createParty: (
    projectId: string,
    clientId: string,
    body: Record<string, unknown>,
  ) =>
    post<ClientParty>(
      `/projects/${projectId}/sales/clients/${clientId}/parties`,
      body,
    ),
  updateParty: (
    projectId: string,
    partyId: string,
    body: Record<string, unknown>,
  ) =>
    patch<ClientParty>(
      `/projects/${projectId}/sales/client-parties/${partyId}`,
      body,
    ),

  reservations: (projectId: string, query: Record<string, string> = {}) =>
    get<Reservation[]>(
      `/projects/${projectId}/sales/reservations?${new URLSearchParams(query).toString()}`,
    ),
  reservation: (projectId: string, reservationId: string) =>
    get<ReservationDetail>(
      `/projects/${projectId}/sales/reservations/${reservationId}`,
    ),
  createReservation: (projectId: string, body: Record<string, unknown>) =>
    post<ReservationDetail>(`/projects/${projectId}/sales/reservations`, body),
  updateReservation: (
    projectId: string,
    reservationId: string,
    body: Record<string, unknown>,
  ) =>
    patch<ReservationDetail>(
      `/projects/${projectId}/sales/reservations/${reservationId}`,
      body,
    ),
  recalculateReservation: (
    projectId: string,
    reservationId: string,
    body: Record<string, unknown> = {},
  ) =>
    post<ReservationDetail>(
      `/projects/${projectId}/sales/reservations/${reservationId}/recalculate`,
      body,
    ),
  addAdjustment: (
    projectId: string,
    reservationId: string,
    body: Record<string, unknown>,
  ) =>
    post<ReservationDetail>(
      `/projects/${projectId}/sales/reservations/${reservationId}/adjustments`,
      body,
    ),
  updateAdjustment: (
    projectId: string,
    adjustmentId: string,
    body: Record<string, unknown>,
  ) =>
    patch<ReservationAdjustment>(
      `/projects/${projectId}/sales/reservation-adjustments/${adjustmentId}`,
      body,
    ),
  submitException: (projectId: string, reservationId: string, reason: string) =>
    post<ReservationDetail>(
      `/projects/${projectId}/sales/reservations/${reservationId}/submit-exception`,
      { reason },
    ),
  decideException: (
    projectId: string,
    reservationId: string,
    approved: boolean,
    reason: string,
  ) =>
    post<ReservationDetail>(
      `/projects/${projectId}/sales/reservations/${reservationId}/approve-exception`,
      { approved, reason },
    ),
  confirmDeposit: (
    projectId: string,
    reservationId: string,
    evidenceReference: string,
  ) =>
    post<ReservationDetail>(
      `/projects/${projectId}/sales/reservations/${reservationId}/confirm-deposit`,
      { evidence_reference: evidenceReference },
    ),
  waiveDeposit: (projectId: string, reservationId: string, reason: string) =>
    post<ReservationDetail>(
      `/projects/${projectId}/sales/reservations/${reservationId}/waive-deposit`,
      { reason },
    ),
  requoteReservation: (
    projectId: string,
    reservationId: string,
    reason: string,
  ) =>
    post<ReservationDetail>(
      `/projects/${projectId}/sales/reservations/${reservationId}/requote`,
      { reason },
    ),
  activateReservation: (projectId: string, reservationId: string) =>
    post<ReservationDetail>(
      `/projects/${projectId}/sales/reservations/${reservationId}/activate`,
      {},
    ),
  extendReservation: (
    projectId: string,
    reservationId: string,
    body: Record<string, unknown>,
  ) =>
    post<ReservationDetail>(
      `/projects/${projectId}/sales/reservations/${reservationId}/extend`,
      body,
    ),
  expireReservation: (projectId: string, reservationId: string) =>
    post<ReservationDetail>(
      `/projects/${projectId}/sales/reservations/${reservationId}/expire`,
      {},
    ),
  cancelReservation: (
    projectId: string,
    reservationId: string,
    reason: string,
  ) =>
    post<ReservationDetail>(
      `/projects/${projectId}/sales/reservations/${reservationId}/cancel`,
      { reason },
    ),

  contracts: (projectId: string, query: Record<string, string> = {}) =>
    get<SaleContract[]>(
      `/projects/${projectId}/sales/contracts?${new URLSearchParams(query).toString()}`,
    ),
  contract: (projectId: string, saleId: string) =>
    get<SaleDetail>(`/projects/${projectId}/sales/contracts/${saleId}`),
  createContract: (projectId: string, body: Record<string, unknown>) =>
    post<SaleDetail>(`/projects/${projectId}/sales/contracts`, body),
  updateContract: (
    projectId: string,
    saleId: string,
    body: Record<string, unknown>,
  ) =>
    patch<SaleDetail>(`/projects/${projectId}/sales/contracts/${saleId}`, body),
  submitContract: (
    projectId: string,
    saleId: string,
    body: Record<string, unknown> = {},
  ) =>
    post<SaleDetail>(
      `/projects/${projectId}/sales/contracts/${saleId}/submit`,
      body,
    ),
  confirmFirstPayment: (
    projectId: string,
    saleId: string,
    evidenceReference: string,
  ) =>
    post<SaleDetail>(
      `/projects/${projectId}/sales/contracts/${saleId}/confirm-first-payment`,
      {
        evidence_reference: evidenceReference,
      },
    ),
  waiveFirstPayment: (projectId: string, saleId: string, reason: string) =>
    post<SaleDetail>(
      `/projects/${projectId}/sales/contracts/${saleId}/waive-first-payment`,
      {
        reason,
      },
    ),
  activateContract: (projectId: string, saleId: string) =>
    post<SaleDetail>(
      `/projects/${projectId}/sales/contracts/${saleId}/activate`,
      {},
    ),

  legalEvents: (projectId: string, saleId: string) =>
    get<LegalTimeline>(
      `/projects/${projectId}/sales/contracts/${saleId}/legal-events`,
    ),
  recordLegalEvent: (
    projectId: string,
    saleId: string,
    body: Record<string, unknown>,
  ) =>
    post<LegalTimeline>(
      `/projects/${projectId}/sales/contracts/${saleId}/legal-events`,
      body,
    ),
  reverseLegalEvent: (projectId: string, eventId: string, reason: string) =>
    post<LegalTimeline>(
      `/projects/${projectId}/sales/legal-events/${eventId}/reverse`,
      {
        reason,
      },
    ),

  cancellation: (projectId: string, saleId: string) =>
    get<SaleCancellation | null>(
      `/projects/${projectId}/sales/contracts/${saleId}/cancellation`,
    ),
  startCancellation: (
    projectId: string,
    saleId: string,
    body: Record<string, unknown>,
  ) =>
    post<SaleCancellation>(
      `/projects/${projectId}/sales/contracts/${saleId}/cancellation`,
      body,
    ),
  approveCancellationTerms: (
    projectId: string,
    cancellationId: string,
    reason: string,
  ) =>
    post<SaleCancellation>(
      `/projects/${projectId}/sales/cancellations/${cancellationId}/approve-financial-terms`,
      { reason },
    ),
  advanceCancellation: (
    projectId: string,
    cancellationId: string,
    body: Record<string, unknown>,
  ) =>
    post<SaleCancellation>(
      `/projects/${projectId}/sales/cancellations/${cancellationId}/advance`,
      body,
    ),
  completeCancellation: (
    projectId: string,
    cancellationId: string,
    body: Record<string, unknown> = {},
  ) =>
    post<SaleCancellation>(
      `/projects/${projectId}/sales/cancellations/${cancellationId}/complete`,
      body,
    ),

  handover: (projectId: string, saleId: string) =>
    get<HandoverDetail | null>(
      `/projects/${projectId}/sales/contracts/${saleId}/handover`,
    ),
  createHandover: (
    projectId: string,
    saleId: string,
    body: Record<string, unknown> = {},
  ) =>
    post<HandoverDetail>(
      `/projects/${projectId}/sales/contracts/${saleId}/handover`,
      body,
    ),
  updateHandover: (
    projectId: string,
    handoverId: string,
    body: Record<string, unknown>,
  ) =>
    patch<HandoverDetail>(
      `/projects/${projectId}/sales/handovers/${handoverId}`,
      body,
    ),
  grantClearance: (
    projectId: string,
    handoverId: string,
    clearanceType: string,
    evidenceReference: string,
  ) =>
    post<HandoverClearance>(
      `/projects/${projectId}/sales/handovers/${handoverId}/clearances/${clearanceType}`,
      { evidence_reference: evidenceReference },
    ),
  revokeClearance: (
    projectId: string,
    handoverId: string,
    clearanceType: string,
    reason: string,
  ) =>
    post<HandoverClearance>(
      `/projects/${projectId}/sales/handovers/${handoverId}/clearances/${clearanceType}/revoke`,
      { reason },
    ),
  completeHandover: (
    projectId: string,
    handoverId: string,
    body: Record<string, unknown>,
  ) =>
    post<HandoverDetail>(
      `/projects/${projectId}/sales/handovers/${handoverId}/complete`,
      body,
    ),
};

/**
 * Payment plans: the contractual schedule behind a sale.
 *
 * Every figure these return was computed by the server. The builder sends
 * inputs and renders the reconciliation that comes back; it never totals a
 * column, derives an amount from a percentage, or decides whether a schedule
 * adds up.
 */
export const paymentPlans = {
  register: (projectId: string) =>
    get<PlanRegister>(`/projects/${projectId}/payment-plans`),
  read: (projectId: string, planId: string) =>
    get<PaymentPlanDetail>(`/projects/${projectId}/payment-plans/${planId}`),
  /** The plan governing one sale, or null when it has not been scheduled yet. */
  forSale: (projectId: string, saleId: string) =>
    get<PaymentPlanDetail | null>(
      `/projects/${projectId}/payment-plans/for-sale/${saleId}`,
    ),
  create: (projectId: string, body: Record<string, unknown>) =>
    post<PaymentPlanDetail>(`/projects/${projectId}/payment-plans`, body),
  createVersion: (
    projectId: string,
    planId: string,
    body: Record<string, unknown>,
  ) =>
    post<PlanVersionDetail>(
      `/projects/${projectId}/payment-plans/${planId}/versions`,
      body,
    ),
  version: (projectId: string, planId: string, versionId: string) =>
    get<PlanVersionDetail>(
      `/projects/${projectId}/payment-plans/${planId}/versions/${versionId}`,
    ),
  writeSchedule: (
    projectId: string,
    planId: string,
    versionId: string,
    body: Record<string, unknown>,
  ) =>
    put<PlanVersionDetail>(
      `/projects/${projectId}/payment-plans/${planId}/versions/${versionId}/installments`,
      body,
    ),
  submitVersion: (projectId: string, planId: string, versionId: string) =>
    post<PlanVersionDetail>(
      `/projects/${projectId}/payment-plans/${planId}/versions/${versionId}/submit`,
      {},
    ),
  approveVersion: (
    projectId: string,
    planId: string,
    versionId: string,
    reason: string,
  ) =>
    post<PlanVersionDetail>(
      `/projects/${projectId}/payment-plans/${planId}/versions/${versionId}/approve`,
      { reason },
    ),
  rejectVersion: (
    projectId: string,
    planId: string,
    versionId: string,
    reason: string,
  ) =>
    post<PlanVersionDetail>(
      `/projects/${projectId}/payment-plans/${planId}/versions/${versionId}/reject`,
      { reason },
    ),
  activateVersion: (projectId: string, planId: string, versionId: string) =>
    post<PlanVersionDetail>(
      `/projects/${projectId}/payment-plans/${planId}/versions/${versionId}/activate`,
      {},
    ),
  seriesPreview: (projectId: string, body: Record<string, unknown>) =>
    post<SeriesPreview>(
      `/projects/${projectId}/payment-plans/series-preview`,
      body,
    ),
  refreshTriggers: (projectId: string, planId: string) =>
    post<TriggerRefreshResult>(
      `/projects/${projectId}/payment-plans/${planId}/refresh-triggers`,
      {},
    ),
  setForecast: (
    projectId: string,
    planId: string,
    installmentId: string,
    body: Record<string, unknown>,
  ) =>
    patch<unknown>(
      `/projects/${projectId}/payment-plans/${planId}/installments/${installmentId}/forecast`,
      body,
    ),
  setOwner: (
    projectId: string,
    planId: string,
    installmentId: string,
    ownerUserId: string | null,
  ) =>
    patch<unknown>(
      `/projects/${projectId}/payment-plans/${planId}/installments/${installmentId}/owner`,
      { owner_user_id: ownerUserId },
    ),
  triggerEvents: (projectId: string, planId: string, installmentId: string) =>
    get<InstallmentTriggerEvent[]>(
      `/projects/${projectId}/payment-plans/${planId}/installments/${installmentId}/trigger-events`,
    ),
  submitManualTrigger: (
    projectId: string,
    planId: string,
    installmentId: string,
    body: Record<string, unknown>,
  ) =>
    post<InstallmentTriggerEvent>(
      `/projects/${projectId}/payment-plans/${planId}/installments/${installmentId}/manual-trigger`,
      body,
    ),
  approveManualTrigger: (projectId: string, planId: string, eventId: string) =>
    post<InstallmentTriggerEvent>(
      `/projects/${projectId}/payment-plans/${planId}/trigger-events/${eventId}/approve`,
      {},
    ),
  reverseManualTrigger: (
    projectId: string,
    planId: string,
    eventId: string,
    reason: string,
  ) =>
    post<InstallmentTriggerEvent>(
      `/projects/${projectId}/payment-plans/${planId}/trigger-events/${eventId}/reverse`,
      { reason },
    ),
};

/**
 * Collections — the ledger of what actually arrived.
 *
 * Every figure these return is derived on the server. Nothing in the browser
 * works out an outstanding balance, a day count, an aging bucket or whether an
 * account may be cleared: those are financial truths, and two implementations
 * of a financial truth is one implementation too many.
 */
export const collections = {
  summary: (projectId: string, asOf?: string) =>
    get<CollectionProjectSummary>(
      `/projects/${projectId}/collections/summary${asOf ? `?as_of=${asOf}` : ""}`,
    ),
  receivables: (projectId: string, asOf?: string) =>
    get<CollectionRegisterRow[]>(
      `/projects/${projectId}/collections/receivables${asOf ? `?as_of=${asOf}` : ""}`,
    ),
  aging: (
    projectId: string,
    params: { asOf?: string; overdueOnly?: boolean } = {},
  ) => {
    const query = new URLSearchParams();
    if (params.asOf) query.set("as_of", params.asOf);
    if (params.overdueOnly) query.set("overdue_only", "true");
    const suffix = query.toString();
    return get<AgingRow[]>(
      `/projects/${projectId}/collections/aging${suffix ? `?${suffix}` : ""}`,
    );
  },

  account: (projectId: string, saleId: string, asOf?: string) =>
    get<CollectionSaleSummary>(
      `/projects/${projectId}/collections/sales/${saleId}${asOf ? `?as_of=${asOf}` : ""}`,
    ),
  receipts: (projectId: string, saleId: string) =>
    get<Receipt[]>(
      `/projects/${projectId}/collections/sales/${saleId}/receipts`,
    ),
  actions: (projectId: string, saleId: string) =>
    get<CollectionAction[]>(
      `/projects/${projectId}/collections/sales/${saleId}/actions`,
    ),
  disputes: (projectId: string, saleId: string) =>
    get<CollectionDispute[]>(
      `/projects/${projectId}/collections/sales/${saleId}/disputes`,
    ),
  waivers: (projectId: string, saleId: string) =>
    get<CollectionWaiver[]>(
      `/projects/${projectId}/collections/sales/${saleId}/waivers`,
    ),
  restructures: (projectId: string, saleId: string) =>
    get<CollectionRestructure[]>(
      `/projects/${projectId}/collections/sales/${saleId}/restructures`,
    ),
  refunds: (projectId: string, saleId: string) =>
    get<CollectionRefund[]>(
      `/projects/${projectId}/collections/sales/${saleId}/refunds`,
    ),
  clearance: (projectId: string, saleId: string) =>
    get<CollectionClearance>(
      `/projects/${projectId}/collections/sales/${saleId}/collection-clearance`,
    ),

  recordReceipt: (
    projectId: string,
    saleId: string,
    body: Record<string, unknown>,
  ) =>
    post<Receipt>(
      `/projects/${projectId}/collections/sales/${saleId}/receipts`,
      body,
    ),
  receipt: (projectId: string, receiptId: string) =>
    get<Receipt>(`/projects/${projectId}/collections/receipts/${receiptId}`),
  suggestions: (projectId: string, receiptId: string) =>
    get<SuggestedAllocation[]>(
      `/projects/${projectId}/collections/receipts/${receiptId}/suggested-allocations`,
    ),
  confirmReceipt: (projectId: string, receiptId: string) =>
    post<Receipt>(
      `/projects/${projectId}/collections/receipts/${receiptId}/confirm`,
      {},
    ),
  reverseReceipt: (projectId: string, receiptId: string, reason: string) =>
    post<Receipt>(
      `/projects/${projectId}/collections/receipts/${receiptId}/reverse`,
      {
        reason,
      },
    ),

  allocate: (
    projectId: string,
    receiptId: string,
    body: Record<string, unknown>,
  ) =>
    post<ReceiptAllocationResponse>(
      `/projects/${projectId}/collections/receipts/${receiptId}/allocations`,
      body,
    ),
  reverseAllocation: (
    projectId: string,
    allocationId: string,
    reason: string,
  ) =>
    post<ReceiptAllocationResponse>(
      `/projects/${projectId}/collections/allocations/${allocationId}/reverse`,
      { reason },
    ),

  recordAction: (
    projectId: string,
    saleId: string,
    body: Record<string, unknown>,
  ) =>
    post<CollectionAction>(
      `/projects/${projectId}/collections/sales/${saleId}/actions`,
      body,
    ),

  openDispute: (projectId: string, installmentId: string, reason: string) =>
    post<CollectionDispute>(
      `/projects/${projectId}/collections/installments/${installmentId}/disputes`,
      { reason },
    ),
  resolveDispute: (projectId: string, disputeId: string, resolution: string) =>
    post<CollectionDispute>(
      `/projects/${projectId}/collections/disputes/${disputeId}/resolve`,
      { resolution },
    ),
  withdrawDispute: (projectId: string, disputeId: string, resolution: string) =>
    post<CollectionDispute>(
      `/projects/${projectId}/collections/disputes/${disputeId}/withdraw`,
      { resolution },
    ),

  submitWaiver: (
    projectId: string,
    installmentId: string,
    body: Record<string, unknown>,
  ) =>
    post<CollectionWaiver>(
      `/projects/${projectId}/collections/installments/${installmentId}/waivers`,
      body,
    ),
  approveWaiver: (projectId: string, waiverId: string) =>
    post<CollectionWaiver>(
      `/projects/${projectId}/collections/waivers/${waiverId}/approve`,
      {},
    ),
  rejectWaiver: (projectId: string, waiverId: string, reason: string) =>
    post<CollectionWaiver>(
      `/projects/${projectId}/collections/waivers/${waiverId}/reject`,
      {
        reason,
      },
    ),
  revokeWaiver: (projectId: string, waiverId: string, reason: string) =>
    post<CollectionWaiver>(
      `/projects/${projectId}/collections/waivers/${waiverId}/revoke`,
      {
        reason,
      },
    ),

  createRestructure: (
    projectId: string,
    saleId: string,
    body: Record<string, unknown>,
  ) =>
    post<CollectionRestructure>(
      `/projects/${projectId}/collections/sales/${saleId}/restructures`,
      body,
    ),
  previewRestructure: (projectId: string, restructureId: string) =>
    get<RestructurePreview>(
      `/projects/${projectId}/collections/restructures/${restructureId}/preview`,
    ),
  applyRestructure: (projectId: string, restructureId: string) =>
    post<RestructureApplyResult>(
      `/projects/${projectId}/collections/restructures/${restructureId}/apply`,
      {},
    ),
  abandonRestructure: (
    projectId: string,
    restructureId: string,
    reason: string,
  ) =>
    post<CollectionRestructure>(
      `/projects/${projectId}/collections/restructures/${restructureId}/abandon`,
      { reason },
    ),

  recordRefund: (
    projectId: string,
    saleId: string,
    body: Record<string, unknown>,
  ) =>
    post<CollectionRefund>(
      `/projects/${projectId}/collections/sales/${saleId}/refunds`,
      body,
    ),
  confirmRefund: (projectId: string, refundId: string) =>
    post<CollectionRefund>(
      `/projects/${projectId}/collections/refunds/${refundId}/confirm`,
      {},
    ),
  reverseRefund: (projectId: string, refundId: string, reason: string) =>
    post<CollectionRefund>(
      `/projects/${projectId}/collections/refunds/${refundId}/reverse`,
      {
        reason,
      },
    ),

  grantClearance: (
    projectId: string,
    saleId: string,
    evidenceReference: string,
  ) =>
    post<CollectionClearance>(
      `/projects/${projectId}/collections/sales/${saleId}/collection-clearance`,
      { evidence_reference: evidenceReference },
    ),
};

/**
 * Unit economics: what a unit costs, and the governed basis that decided it.
 *
 * Every figure these calls return is computed server-side. Nothing here is
 * recomputed in the browser — not an allocation, not a reconciliation, not a
 * margin — because the backend is the one place the arithmetic is tested.
 */
export const unitEconomics = {
  summary: (projectId: string) =>
    get<ProjectEconomics>(`/projects/${projectId}/unit-economics/summary`),
  units: (projectId: string) =>
    get<UnitEconomicsRow[]>(`/projects/${projectId}/unit-economics/units`),
  unit: (projectId: string, unitId: string) =>
    get<UnitEconomicsDetail>(
      `/projects/${projectId}/unit-economics/units/${unitId}`,
    ),
  sale: (projectId: string, saleId: string) =>
    get<UnitEconomicsDetail>(
      `/projects/${projectId}/unit-economics/sales/${saleId}`,
    ),
  unitCosts: (projectId: string, unitId?: string) =>
    get<UnitCost[]>(
      `/projects/${projectId}/unit-economics/unit-costs${unitId ? `?unit_id=${unitId}` : ""}`,
    ),

  versions: (projectId: string) =>
    get<AllocationVersion[]>(
      `/projects/${projectId}/unit-economics/allocation-versions`,
    ),
  version: (projectId: string, versionId: string) =>
    get<AllocationVersionDetail>(
      `/projects/${projectId}/unit-economics/allocation-versions/${versionId}`,
    ),
  allocations: (projectId: string, versionId: string, poolId?: string) =>
    get<UnitAllocation[]>(
      `/projects/${projectId}/unit-economics/allocation-versions/${versionId}/allocations` +
        (poolId ? `?pool_id=${poolId}` : ""),
    ),

  createVersion: (projectId: string, body: Record<string, unknown>) =>
    post<AllocationVersion>(
      `/projects/${projectId}/unit-economics/allocation-versions`,
      body,
    ),
  cloneVersion: (
    projectId: string,
    versionId: string,
    body: Record<string, unknown>,
  ) =>
    post<AllocationVersion>(
      `/projects/${projectId}/unit-economics/allocation-versions/${versionId}/clone`,
      body,
    ),

  addPool: (
    projectId: string,
    versionId: string,
    body: Record<string, unknown>,
  ) =>
    post<CostPool>(
      `/projects/${projectId}/unit-economics/allocation-versions/${versionId}/pools`,
      body,
    ),
  updatePool: (
    projectId: string,
    versionId: string,
    poolId: string,
    body: Record<string, unknown>,
  ) =>
    patch<CostPool>(
      `/projects/${projectId}/unit-economics/allocation-versions/${versionId}/pools/${poolId}`,
      body,
    ),
  removePool: (projectId: string, versionId: string, poolId: string) =>
    remove(
      `/projects/${projectId}/unit-economics/allocation-versions/${versionId}/pools/${poolId}`,
    ),
  setDrivers: (
    projectId: string,
    versionId: string,
    poolId: string,
    drivers: { unit_id: string; driver_value: string }[],
  ) =>
    put<CostPool>(
      `/projects/${projectId}/unit-economics/allocation-versions/` +
        `${versionId}/pools/${poolId}/drivers`,
      { drivers },
    ),

  calculate: (projectId: string, versionId: string) =>
    post<CalculationPreview>(
      `/projects/${projectId}/unit-economics/allocation-versions/${versionId}/calculate`,
      {},
    ),
  submitVersion: (projectId: string, versionId: string) =>
    post<AllocationVersion>(
      `/projects/${projectId}/unit-economics/allocation-versions/${versionId}/submit`,
      {},
    ),
  approveVersion: (projectId: string, versionId: string, reason?: string) =>
    post<AllocationVersion>(
      `/projects/${projectId}/unit-economics/allocation-versions/${versionId}/approve`,
      { reason: reason ?? null },
    ),
  rejectVersion: (projectId: string, versionId: string, reason: string) =>
    post<AllocationVersion>(
      `/projects/${projectId}/unit-economics/allocation-versions/${versionId}/reject`,
      { reason },
    ),
  activateVersion: (projectId: string, versionId: string) =>
    post<AllocationVersion>(
      `/projects/${projectId}/unit-economics/allocation-versions/${versionId}/activate`,
      {},
    ),

  recordUnitCost: (
    projectId: string,
    unitId: string,
    body: Record<string, unknown>,
  ) =>
    post<UnitCost>(
      `/projects/${projectId}/unit-economics/units/${unitId}/costs`,
      body,
    ),
  reverseUnitCost: (projectId: string, costId: string, reason: string) =>
    post<UnitCost>(
      `/projects/${projectId}/unit-economics/unit-costs/${costId}/reverse`,
      {
        reason,
      },
    ),
};

/**
 * Construction control (PR-MVP-09).
 *
 * One namespace per governed record, addressed exactly as the server addresses
 * it. Nothing here derives a total: the summary's two positions, the
 * certificate waterfall, the variance sign and the escalation threshold all
 * arrive computed, because a figure recomputed in the browser is a figure that
 * can disagree with the one the server will enforce.
 */
export const construction = {
  summary: (projectId: string) =>
    get<ConstructionSummary>(`/projects/${projectId}/construction/summary`),
  reconciliation: (projectId: string) =>
    get<ConstructionReconciliation>(
      `/projects/${projectId}/construction/reconciliation`,
    ),

  costCodes: (projectId: string) =>
    get<CostCode[]>(`/projects/${projectId}/construction/cost-codes`),
  createCostCode: (projectId: string, body: Record<string, unknown>) =>
    post<CostCode>(`/projects/${projectId}/construction/cost-codes`, body),
  updateCostCode: (
    projectId: string,
    costCodeId: string,
    body: Record<string, unknown>,
  ) =>
    patch<CostCode>(
      `/projects/${projectId}/construction/cost-codes/${costCodeId}`,
      body,
    ),
  retireCostCode: (projectId: string, costCodeId: string, reason: string) =>
    post<CostCode>(
      `/projects/${projectId}/construction/cost-codes/${costCodeId}/retire`,
      {
        reason,
      },
    ),

  budgets: (projectId: string) =>
    get<BudgetVersion[]>(`/projects/${projectId}/construction/budgets`),
  budget: (projectId: string, versionId: string) =>
    get<BudgetDetail>(
      `/projects/${projectId}/construction/budgets/${versionId}`,
    ),
  createBudget: (projectId: string, body: Record<string, unknown>) =>
    post<BudgetDetail>(`/projects/${projectId}/construction/budgets`, body),
  writeBudgetLine: (
    projectId: string,
    versionId: string,
    body: Record<string, unknown>,
  ) =>
    put<BudgetDetail>(
      `/projects/${projectId}/construction/budgets/${versionId}/lines`,
      body,
    ),
  submitBudget: (projectId: string, versionId: string) =>
    post<BudgetDetail>(
      `/projects/${projectId}/construction/budgets/${versionId}/submit`,
      {},
    ),
  approveBudget: (projectId: string, versionId: string, reason?: string) =>
    post<BudgetDetail>(
      `/projects/${projectId}/construction/budgets/${versionId}/approve`,
      {
        reason: reason ?? null,
      },
    ),
  rejectBudget: (projectId: string, versionId: string, reason: string) =>
    post<BudgetDetail>(
      `/projects/${projectId}/construction/budgets/${versionId}/reject`,
      {
        reason,
      },
    ),
  activateBudget: (projectId: string, versionId: string) =>
    post<BudgetDetail>(
      `/projects/${projectId}/construction/budgets/${versionId}/activate`,
      {},
    ),

  contracts: (projectId: string) =>
    get<ConstructionContract[]>(
      `/projects/${projectId}/construction/contracts`,
    ),
  contract: (projectId: string, contractId: string) =>
    get<ContractDetail>(
      `/projects/${projectId}/construction/contracts/${contractId}`,
    ),
  createContract: (projectId: string, body: Record<string, unknown>) =>
    post<ContractDetail>(`/projects/${projectId}/construction/contracts`, body),
  writeContractLine: (
    projectId: string,
    contractId: string,
    body: Record<string, unknown>,
  ) =>
    put<ContractDetail>(
      `/projects/${projectId}/construction/contracts/${contractId}/lines`,
      body,
    ),
  submitContract: (projectId: string, contractId: string) =>
    post<ContractDetail>(
      `/projects/${projectId}/construction/contracts/${contractId}/submit`,
      {},
    ),
  activateContract: (projectId: string, contractId: string) =>
    post<ContractDetail>(
      `/projects/${projectId}/construction/contracts/${contractId}/activate`,
      {},
    ),
  completeContract: (projectId: string, contractId: string) =>
    post<ContractDetail>(
      `/projects/${projectId}/construction/contracts/${contractId}/complete`,
      {},
    ),
  terminateContract: (projectId: string, contractId: string, reason: string) =>
    post<ContractDetail>(
      `/projects/${projectId}/construction/contracts/${contractId}/terminate`,
      { reason },
    ),
  cancelContract: (projectId: string, contractId: string, reason: string) =>
    post<ContractDetail>(
      `/projects/${projectId}/construction/contracts/${contractId}/cancel`,
      {
        reason,
      },
    ),

  variations: (projectId: string, contractId?: string) =>
    get<Variation[]>(
      `/projects/${projectId}/construction/variations${
        contractId ? `?contract_id=${contractId}` : ""
      }`,
    ),
  variation: (projectId: string, variationId: string) =>
    get<VariationDetail>(
      `/projects/${projectId}/construction/variations/${variationId}`,
    ),
  createVariation: (
    projectId: string,
    contractId: string,
    body: Record<string, unknown>,
  ) =>
    post<VariationDetail>(
      `/projects/${projectId}/construction/contracts/${contractId}/variations`,
      body,
    ),
  writeVariationLine: (
    projectId: string,
    variationId: string,
    body: Record<string, unknown>,
  ) =>
    put<VariationDetail>(
      `/projects/${projectId}/construction/variations/${variationId}/lines`,
      body,
    ),
  submitVariation: (projectId: string, variationId: string) =>
    post<VariationDetail>(
      `/projects/${projectId}/construction/variations/${variationId}/submit`,
      {},
    ),
  approveVariation: (projectId: string, variationId: string) =>
    post<VariationDetail>(
      `/projects/${projectId}/construction/variations/${variationId}/approve`,
      {},
    ),
  rejectVariation: (projectId: string, variationId: string, reason: string) =>
    post<VariationDetail>(
      `/projects/${projectId}/construction/variations/${variationId}/reject`,
      { reason },
    ),
  withdrawVariation: (projectId: string, variationId: string, reason: string) =>
    post<VariationDetail>(
      `/projects/${projectId}/construction/variations/${variationId}/withdraw`,
      { reason },
    ),

  certificates: (projectId: string, contractId?: string) =>
    get<Certificate[]>(
      `/projects/${projectId}/construction/certificates${
        contractId ? `?contract_id=${contractId}` : ""
      }`,
    ),
  certificate: (projectId: string, certificateId: string) =>
    get<CertificateDetail>(
      `/projects/${projectId}/construction/certificates/${certificateId}`,
    ),
  createCertificate: (
    projectId: string,
    contractId: string,
    body: Record<string, unknown>,
  ) =>
    post<CertificateDetail>(
      `/projects/${projectId}/construction/contracts/${contractId}/certificates`,
      body,
    ),
  writeCertificateLine: (
    projectId: string,
    certificateId: string,
    body: Record<string, unknown>,
  ) =>
    put<CertificateDetail>(
      `/projects/${projectId}/construction/certificates/${certificateId}/lines`,
      body,
    ),
  submitCertificate: (projectId: string, certificateId: string) =>
    post<CertificateDetail>(
      `/projects/${projectId}/construction/certificates/${certificateId}/submit`,
      {},
    ),
  certifyCertificate: (projectId: string, certificateId: string) =>
    post<CertificateDetail>(
      `/projects/${projectId}/construction/certificates/${certificateId}/certify`,
      {},
    ),
  rejectCertificate: (
    projectId: string,
    certificateId: string,
    reason: string,
  ) =>
    post<CertificateDetail>(
      `/projects/${projectId}/construction/certificates/${certificateId}/reject`,
      { reason },
    ),
  reverseCertificate: (
    projectId: string,
    certificateId: string,
    reason: string,
  ) =>
    post<CertificateDetail>(
      `/projects/${projectId}/construction/certificates/${certificateId}/reverse`,
      { reason },
    ),

  invoices: (projectId: string, contractId?: string) =>
    get<ConstructionInvoice[]>(
      `/projects/${projectId}/construction/invoices${
        contractId ? `?contract_id=${contractId}` : ""
      }`,
    ),
  recordInvoice: (
    projectId: string,
    contractId: string,
    body: Record<string, unknown>,
  ) =>
    post<ConstructionInvoice>(
      `/projects/${projectId}/construction/contracts/${contractId}/invoices`,
      body,
    ),
  approveInvoice: (projectId: string, invoiceId: string) =>
    post<ConstructionInvoice>(
      `/projects/${projectId}/construction/invoices/${invoiceId}/approve`,
      {},
    ),
  disputeInvoice: (projectId: string, invoiceId: string, reason: string) =>
    post<ConstructionInvoice>(
      `/projects/${projectId}/construction/invoices/${invoiceId}/dispute`,
      {
        reason,
      },
    ),
  resolveInvoice: (projectId: string, invoiceId: string, reason: string) =>
    post<ConstructionInvoice>(
      `/projects/${projectId}/construction/invoices/${invoiceId}/resolve`,
      {
        reason,
      },
    ),
  voidInvoice: (projectId: string, invoiceId: string, reason: string) =>
    post<ConstructionInvoice>(
      `/projects/${projectId}/construction/invoices/${invoiceId}/void`,
      {
        reason,
      },
    ),

  payments: (projectId: string, contractId?: string) =>
    get<ConstructionPayment[]>(
      `/projects/${projectId}/construction/payments${
        contractId ? `?contract_id=${contractId}` : ""
      }`,
    ),
  recordPayment: (
    projectId: string,
    contractId: string,
    body: Record<string, unknown>,
  ) =>
    post<ConstructionPayment>(
      `/projects/${projectId}/construction/contracts/${contractId}/payments`,
      body,
    ),
  allocatePayment: (
    projectId: string,
    paymentId: string,
    body: Record<string, unknown>,
  ) =>
    put<ConstructionPayment>(
      `/projects/${projectId}/construction/payments/${paymentId}/allocations`,
      body,
    ),
  confirmPayment: (projectId: string, paymentId: string) =>
    post<ConstructionPayment>(
      `/projects/${projectId}/construction/payments/${paymentId}/confirm`,
      {},
    ),
  reversePayment: (projectId: string, paymentId: string, reason: string) =>
    post<ConstructionPayment>(
      `/projects/${projectId}/construction/payments/${paymentId}/reverse`,
      {
        reason,
      },
    ),

  milestones: (projectId: string) =>
    get<ConstructionMilestone[]>(
      `/projects/${projectId}/construction/milestones`,
    ),
  createMilestone: (projectId: string, body: Record<string, unknown>) =>
    post<ConstructionMilestone>(
      `/projects/${projectId}/construction/milestones`,
      body,
    ),
  updateMilestone: (
    projectId: string,
    milestoneId: string,
    body: Record<string, unknown>,
  ) =>
    patch<ConstructionMilestone>(
      `/projects/${projectId}/construction/milestones/${milestoneId}`,
      body,
    ),
  achieveMilestone: (
    projectId: string,
    milestoneId: string,
    body: Record<string, unknown>,
  ) =>
    post<ConstructionMilestone>(
      `/projects/${projectId}/construction/milestones/${milestoneId}/achieve`,
      body,
    ),
  certifyMilestone: (
    projectId: string,
    milestoneId: string,
    body: Record<string, unknown>,
  ) =>
    post<MilestoneCertified>(
      `/projects/${projectId}/construction/milestones/${milestoneId}/certify`,
      body,
    ),
  cancelMilestone: (projectId: string, milestoneId: string, reason: string) =>
    post<ConstructionMilestone>(
      `/projects/${projectId}/construction/milestones/${milestoneId}/cancel`,
      { reason },
    ),
  addMilestoneDependency: (
    projectId: string,
    milestoneId: string,
    dependsOn: string,
  ) =>
    put<ConstructionMilestone>(
      `/projects/${projectId}/construction/milestones/${milestoneId}/dependencies`,
      { depends_on_milestone_id: dependsOn },
    ),
  /** What a payment plan's `construction_milestone` trigger may point at. */
  milestoneTriggerOptions: (projectId: string) =>
    get<MilestoneTriggerOption[]>(
      `/projects/${projectId}/construction/milestone-trigger-options`,
    ),

  forecasts: (projectId: string) =>
    get<ForecastVersion[]>(`/projects/${projectId}/construction/forecasts`),
  forecast: (projectId: string, versionId: string) =>
    get<ForecastDetail>(
      `/projects/${projectId}/construction/forecasts/${versionId}`,
    ),
  createForecast: (projectId: string, body: Record<string, unknown>) =>
    post<ForecastDetail>(`/projects/${projectId}/construction/forecasts`, body),
  writeForecastLine: (
    projectId: string,
    versionId: string,
    body: Record<string, unknown>,
  ) =>
    put<ForecastDetail>(
      `/projects/${projectId}/construction/forecasts/${versionId}/lines`,
      body,
    ),
  submitForecast: (projectId: string, versionId: string) =>
    post<ForecastDetail>(
      `/projects/${projectId}/construction/forecasts/${versionId}/submit`,
      {},
    ),
  approveForecast: (projectId: string, versionId: string, reason?: string) =>
    post<ForecastDetail>(
      `/projects/${projectId}/construction/forecasts/${versionId}/approve`,
      {
        reason: reason ?? null,
      },
    ),
  rejectForecast: (projectId: string, versionId: string, reason: string) =>
    post<ForecastDetail>(
      `/projects/${projectId}/construction/forecasts/${versionId}/reject`,
      {
        reason,
      },
    ),
  activateForecast: (projectId: string, versionId: string) =>
    post<ForecastDetail>(
      `/projects/${projectId}/construction/forecasts/${versionId}/activate`,
      {},
    ),

  startConstruction: (projectId: string, body: Record<string, unknown>) =>
    post<DeliveryResult>(
      `/projects/${projectId}/construction/delivery/start`,
      body,
    ),
  markReady: (projectId: string, body: Record<string, unknown>) =>
    post<DeliveryResult>(
      `/projects/${projectId}/construction/delivery/ready`,
      body,
    ),
  revokeReady: (projectId: string, body: Record<string, unknown>) =>
    post<DeliveryResult>(
      `/projects/${projectId}/construction/delivery/revoke-ready`,
      body,
    ),
};
