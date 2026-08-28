/**
 * Typed API operations, grouped by resource.
 *
 * Every network call the application makes goes through one of these.
 */

import { get, patch, post, put } from "./client";
import type {
  AdminUser,
  ApprovalThresholds,
  AuditEvent,
  CountryPack,
  Currency,
  CurrentUser,
  Page,
  ReferenceValue,
  Role,
  TaxRule,
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
