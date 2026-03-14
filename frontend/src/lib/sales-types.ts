/**
 * sales-types.ts — shared frontend types for the sales workflow UI.
 *
 * Centralised here so that pages, components, and the API wrapper all
 * reference the same shapes.
 *
 * These types reflect the backend API contracts for:
 *   GET /api/v1/units/{unitId}
 *   GET /api/v1/pricing/unit/{unitId}
 *   GET /api/v1/sales-exceptions/projects/{projectId}  (filtered by unit)
 *   GET /api/v1/sales/contracts?unit_id=
 *   GET /api/v1/payment-plans/contracts/{contractId}/schedule
 */

import type { UnitListItem, UnitPrice } from "./units-types";

// ---------- Re-exports for consumer convenience --------------------------

export type { UnitListItem, UnitPrice };

// ---------- Sales candidate (queue item) --------------------------------

/**
 * A sales candidate is a unit enriched with pricing, exception, and
 * contract information suitable for display in the sales queue.
 */
export interface SalesCandidate {
  unit: UnitListItem;
  pricing: UnitPrice | null;
  /** Whether there is at least one approved sales exception for this unit. */
  hasApprovedException: boolean;
  /** Current contract status, or null if no contract exists. */
  contractStatus: ContractStatus | null;
  /** Derived commercial readiness state. */
  readiness: SalesReadinessStatus;
}

// ---------- Sales workflow detail (unit-level) ---------------------------

/**
 * Full sales workflow detail for a single unit.
 * Aggregates unit, pricing, exceptions, contract, and payment plan data.
 */
export interface SalesWorkflowDetail {
  unit: UnitListItem;
  pricing: UnitPrice | null;
  approvedExceptions: ApprovedSalesException[];
  contractAction: ContractActionState;
  paymentPlanPreview: PaymentPlanPreview | null;
  /** Derived commercial readiness — computed once in the API layer. */
  readiness: SalesReadinessStatus;
}

// ---------- Readiness ----------------------------------------------------

/**
 * Commercial readiness state for a unit.
 * Derived on the frontend from available backend facts.
 */
export type SalesReadinessStatus =
  | "ready"
  | "needs_exception_approval"
  | "under_contract"
  | "missing_pricing"
  | "blocked";

/** Human-readable label for a SalesReadinessStatus value. */
export function readinessLabel(status: SalesReadinessStatus): string {
  const labels: Record<SalesReadinessStatus, string> = {
    ready: "Ready",
    needs_exception_approval: "Needs Exception Approval",
    under_contract: "Under Contract",
    missing_pricing: "Missing Pricing",
    blocked: "Blocked",
  };
  return labels[status];
}

// ---------- Approved sales exception ------------------------------------

/**
 * A sales exception that is relevant to the unit sale.
 * Reflects the backend SalesExceptionResponse schema.
 */
export interface ApprovedSalesException {
  id: string;
  exception_type: string;
  approval_status: string;
  base_price: number;
  requested_price: number;
  discount_amount: number;
  discount_percentage: number;
  incentive_value: number | null;
  incentive_description: string | null;
  requested_by: string | null;
  approved_by: string | null;
}

// ---------- Contract action state ---------------------------------------

/**
 * Describes the available contract action for a unit from the frontend's
 * perspective, based on backend data.
 */
export type ContractActionKind =
  | "available"       // unit is available; contract creation is possible
  | "already_active"  // contract already exists and is active
  | "already_draft"   // contract exists but is in draft state
  | "unavailable";    // unit is reserved/registered or otherwise blocked

export interface ContractActionState {
  kind: ContractActionKind;
  /** Contract ID, present when a contract already exists. */
  contractId: string | null;
  /** Contract number, present when a contract already exists. */
  contractNumber: string | null;
  /** Contract status value from the backend. */
  contractStatus: ContractStatus | null;
}

// ---------- Contract status (mirrors backend enum) ----------------------

export type ContractStatus = "draft" | "active" | "cancelled" | "completed";

/** Human-readable label for a ContractStatus value. */
export function contractStatusLabel(status: ContractStatus | string): string {
  const labels: Record<string, string> = {
    draft: "Draft",
    active: "Active",
    cancelled: "Cancelled",
    completed: "Completed",
  };
  return (
    labels[status] ??
    status
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ")
  );
}

// ---------- Payment plan preview ----------------------------------------

/**
 * Minimal payment plan summary for the sales workflow detail page.
 * Read-only — editing is out of scope for this PR.
 */
export interface PaymentPlanPreview {
  contractId: string;
  totalInstallments: number;
  totalDue: number;
  nextDueDate: string | null;
  nextDueAmount: number | null;
}

// ---------- Filter state ------------------------------------------------

/** UI filter state for the sales queue listing page. */
export interface SalesFiltersState {
  status: string;
  unit_type: string;
  has_approved_exception: "" | "yes" | "no";
  contract_status: ContractStatus | "";
  readiness: SalesReadinessStatus | "";
  min_price: string;
  max_price: string;
}
