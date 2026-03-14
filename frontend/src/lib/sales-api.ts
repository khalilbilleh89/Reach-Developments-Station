/**
 * sales-api.ts — centralized API wrapper for the sales workflow UI.
 *
 * This module is the normalization boundary between the backend API contract
 * and the frontend UI model. Raw backend responses are composed and normalized
 * here so that components can rely on stable, UI-friendly types.
 *
 * No business logic calculations are performed here — all financial values
 * are sourced directly from the backend.
 *
 * Backend endpoints used:
 *   GET /projects                                        → project list
 *   GET /units/{unitId}                                  → unit detail
 *   GET /pricing/unit/{unitId}                           → unit price
 *   GET /sales-exceptions/projects/{projectId}           → exceptions list
 *   GET /sales/contracts?unit_id={unitId}                → contract list
 *   GET /payment-plans/contracts/{contractId}/schedule   → payment schedule
 */

import { apiFetch, ApiError } from "./api-client";
import {
  getProjects as getProjectsFromUnitsApi,
  getUnitsByProject,
  getUnitById,
  getUnitPricing,
} from "./units-api";
import type {
  UnitListItem,
  UnitPrice,
  Project,
} from "./units-types";
import type {
  SalesCandidate,
  SalesWorkflowDetail,
  SalesFiltersState,
  ApprovedSalesException,
  ContractActionState,
  ContractStatus,
  PaymentPlanPreview,
  SalesReadinessStatus,
} from "./sales-types";

// ---------- Re-export project/unit helpers for page convenience ----------

export { getProjectsFromUnitsApi as getProjects };

// ---------- Raw backend response types (internal) ------------------------

interface SalesExceptionItem {
  id: string;
  project_id: string;
  unit_id: string;
  sale_contract_id: string | null;
  exception_type: string;
  base_price: number;
  requested_price: number;
  discount_amount: number;
  discount_percentage: number;
  incentive_value: number | null;
  incentive_description: string | null;
  approval_status: string;
  requested_by: string | null;
  approved_by: string | null;
  approved_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

interface SalesExceptionListResponse {
  total: number;
  items: SalesExceptionItem[];
}

interface ContractItem {
  id: string;
  unit_id: string;
  buyer_id: string;
  reservation_id: string | null;
  contract_number: string;
  contract_date: string;
  contract_price: number;
  status: ContractStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

interface ContractListResponse {
  total: number;
  items: ContractItem[];
}

interface PaymentScheduleItem {
  id: string;
  contract_id: string;
  due_date: string;
  amount: number;
  status: string;
}

interface PaymentScheduleListResponse {
  total: number;
  items: PaymentScheduleItem[];
}

// ---------- Error discrimination -----------------------------------------

function isNotFoundError(err: unknown): boolean {
  return err instanceof ApiError && err.status === 404;
}

// ---------- Internal helpers ---------------------------------------------

/**
 * Fetch approved sales exceptions for a specific unit within a project.
 * Returns all exceptions for the project filtered to the given unit ID.
 * Returns [] when none exist.
 */
async function fetchUnitExceptions(
  projectId: string,
  unitId: string,
): Promise<ApprovedSalesException[]> {
  try {
    const data = await apiFetch<SalesExceptionListResponse>(
      `/sales-exceptions/projects/${projectId}?limit=500`,
    );
    return data.items
      .filter((ex) => ex.unit_id === unitId)
      .map((ex) => ({
        id: ex.id,
        exception_type: ex.exception_type,
        approval_status: ex.approval_status,
        base_price: ex.base_price,
        requested_price: ex.requested_price,
        discount_amount: ex.discount_amount,
        discount_percentage: ex.discount_percentage,
        incentive_value: ex.incentive_value,
        incentive_description: ex.incentive_description,
        requested_by: ex.requested_by,
        approved_by: ex.approved_by,
      }));
  } catch (err: unknown) {
    if (isNotFoundError(err)) return [];
    throw err;
  }
}

/**
 * Fetch the active or most-recent contract for a unit.
 * Returns null when no contract exists.
 */
async function fetchUnitContract(unitId: string): Promise<ContractItem | null> {
  try {
    const data = await apiFetch<ContractListResponse>(
      `/sales/contracts?unit_id=${unitId}&limit=500`,
    );
    if (data.items.length === 0) return null;
    // Prefer active contracts; fall back to most recently created
    const active = data.items.find((c) => c.status === "active");
    if (active) return active;
    const sorted = [...data.items].sort((a, b) =>
      b.created_at.localeCompare(a.created_at),
    );
    return sorted[0];
  } catch (err: unknown) {
    if (isNotFoundError(err)) return null;
    throw err;
  }
}

/**
 * Fetch payment schedule for a contract and return a lightweight preview.
 * Returns null when no schedule exists.
 */
async function fetchPaymentPlanPreview(
  contractId: string,
): Promise<PaymentPlanPreview | null> {
  try {
    const data = await apiFetch<PaymentScheduleListResponse>(
      `/payment-plans/contracts/${contractId}/schedule`,
    );
    if (data.items.length === 0) return null;

    const totalDue = data.items.reduce((sum, item) => sum + item.amount, 0);
    const pending = data.items
      .filter((item) => item.status === "pending")
      .sort((a, b) => a.due_date.localeCompare(b.due_date));
    const next = pending[0] ?? null;

    return {
      contractId,
      totalInstallments: data.items.length,
      totalDue,
      nextDueDate: next ? next.due_date : null,
      nextDueAmount: next ? next.amount : null,
    };
  } catch (err: unknown) {
    if (isNotFoundError(err)) return null;
    throw err;
  }
}

/**
 * Derive the commercial readiness status from available backend data.
 * All values come from the backend — no business logic is added here.
 */
function deriveReadiness(
  unit: UnitListItem,
  pricing: UnitPrice | null,
  hasApprovedException: boolean,
  contractStatus: ContractStatus | null,
): SalesReadinessStatus {
  if (unit.status === "under_contract" || contractStatus === "active") {
    return "under_contract";
  }
  if (unit.status === "registered") {
    return "blocked";
  }
  if (!pricing) {
    return "missing_pricing";
  }
  if (hasApprovedException) {
    // A resolved approved exception is informational — unit can still proceed
    return "ready";
  }
  if (unit.status === "available" || unit.status === "reserved") {
    return "ready";
  }
  return "blocked";
}

/**
 * Derive the contract action state for the detail page.
 */
function deriveContractAction(
  unit: UnitListItem,
  contract: ContractItem | null,
): ContractActionState {
  if (contract) {
    const kind =
      contract.status === "active"
        ? "already_active"
        : contract.status === "draft"
          ? "already_draft"
          : "unavailable";
    return {
      kind,
      contractId: contract.id,
      contractNumber: contract.contract_number,
      contractStatus: contract.status,
    };
  }
  if (unit.status === "available" || unit.status === "reserved") {
    return { kind: "available", contractId: null, contractNumber: null, contractStatus: null };
  }
  return { kind: "unavailable", contractId: null, contractNumber: null, contractStatus: null };
}

// ---------- Public query functions ---------------------------------------

/**
 * Fetch a project's unit list enriched with sales-relevant data, suitable
 * for rendering the sales candidates queue.
 *
 * Enrichment is done in parallel per unit. Individual pricing/exception
 * failures for "not found" are tolerated; unexpected errors propagate.
 */
export async function getSalesCandidates(
  projectId: string,
): Promise<SalesCandidate[]> {
  const units = await getUnitsByProject(projectId);
  if (units.length === 0) return [];

  // Fetch pricing and contracts for all units in parallel
  const enriched = await Promise.all(
    units.map(async (unit): Promise<SalesCandidate> => {
      const [pricing, exceptions, contract] = await Promise.all([
        getUnitPricing(unit.id),
        fetchUnitExceptions(projectId, unit.id),
        fetchUnitContract(unit.id),
      ]);

      const hasApprovedException = exceptions.some(
        (ex) => ex.approval_status === "approved",
      );
      const contractStatus = contract ? contract.status : null;
      const readiness = deriveReadiness(
        unit,
        pricing,
        hasApprovedException,
        contractStatus,
      );

      return { unit, pricing, hasApprovedException, contractStatus, readiness };
    }),
  );

  return enriched;
}

/**
 * Fetch all sales-relevant data for a single unit.
 * Used by the guided sales workflow detail page.
 */
export async function getUnitSaleWorkflow(
  projectId: string,
  unitId: string,
): Promise<SalesWorkflowDetail> {
  const [unit, pricing, exceptions, contract] = await Promise.all([
    getUnitById(unitId),
    getUnitPricing(unitId),
    fetchUnitExceptions(projectId, unitId),
    fetchUnitContract(unitId),
  ]);

  const contractAction = deriveContractAction(unit, contract);

  let paymentPlanPreview: PaymentPlanPreview | null = null;
  if (contract && (contract.status === "active" || contract.status === "draft")) {
    paymentPlanPreview = await fetchPaymentPlanPreview(contract.id);
  }

  return {
    unit,
    pricing,
    approvedExceptions: exceptions.filter(
      (ex) => ex.approval_status === "approved",
    ),
    contractAction,
    paymentPlanPreview,
    readiness: deriveReadiness(
      unit,
      pricing,
      exceptions.some((ex) => ex.approval_status === "approved"),
      contract ? contract.status : null,
    ),
  };
}

/**
 * Apply UI filter state to a list of sales candidates.
 * All filtering is done client-side after the initial API fetch.
 */
export function filterSalesCandidates(
  candidates: SalesCandidate[],
  filters: SalesFiltersState,
): SalesCandidate[] {
  return candidates.filter((c) => {
    if (filters.status !== "" && c.unit.status !== filters.status) return false;
    if (filters.unit_type !== "" && c.unit.unit_type !== filters.unit_type) return false;
    if (filters.has_approved_exception === "yes" && !c.hasApprovedException) return false;
    if (filters.has_approved_exception === "no" && c.hasApprovedException) return false;
    if (filters.contract_status !== "" && c.contractStatus !== filters.contract_status) return false;
    if (filters.readiness !== "" && c.readiness !== filters.readiness) return false;
    if (filters.min_price !== "") {
      const min = parseFloat(filters.min_price);
      if (!c.pricing || c.pricing.final_unit_price < min) return false;
    }
    if (filters.max_price !== "") {
      const max = parseFloat(filters.max_price);
      if (!c.pricing || c.pricing.final_unit_price > max) return false;
    }
    return true;
  });
}

// ---------- Project and project-unit helpers ----------------------------

export { getUnitsByProject };
export type { Project, UnitListItem, UnitPrice };
