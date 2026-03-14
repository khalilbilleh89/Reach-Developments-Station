/**
 * payment-plans-types.ts — shared frontend types for the payment plans and
 * collections UI.
 *
 * Centralised here so that pages, components, and the API wrapper all
 * reference the same shapes.
 *
 * These types reflect the backend API contracts for:
 *   GET /api/v1/sales/contracts?unit_id=             → contract list
 *   GET /api/v1/payment-plans/contracts/{id}/schedule → payment schedule
 *   GET /api/v1/collections/contracts/{id}/receivables → receivables summary
 */

// ---------- Installment status -------------------------------------------

/**
 * UI status for a single installment row.
 *
 * Covers both payment schedule statuses (pending/due/paid/overdue/cancelled)
 * and receivable statuses (partially_paid). When a receivable exists the
 * receivable_status is used; otherwise the schedule status is mapped to a
 * UI-safe value via mapScheduleStatusToUiStatus() in the API layer.
 */
export type InstallmentStatus =
  | "pending"
  | "due"
  | "paid"
  | "partially_paid"
  | "overdue"
  | "cancelled";

/** Human-readable label for an InstallmentStatus value. */
export function installmentStatusLabel(status: InstallmentStatus | string): string {
  const labels: Record<string, string> = {
    pending: "Upcoming",
    due: "Due",
    paid: "Paid",
    partially_paid: "Partially Paid",
    overdue: "Overdue",
    cancelled: "Cancelled",
  };
  return (
    labels[status] ??
    status
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ")
  );
}

// ---------- Receivable status ---------------------------------------------

/**
 * Computed receivable status for a single schedule line as returned by the
 * collections module.
 */
export type ReceivableStatus =
  | "pending"
  | "partially_paid"
  | "paid"
  | "overdue";

/** Human-readable label for a ReceivableStatus value. */
export function receivableStatusLabel(status: ReceivableStatus | string): string {
  const labels: Record<string, string> = {
    pending: "Upcoming",
    partially_paid: "Partially Paid",
    paid: "Paid",
    overdue: "Overdue",
  };
  return (
    labels[status] ??
    status
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ")
  );
}

// ---------- Installment row (schedule line) ------------------------------

/**
 * A single row in the installment schedule table.
 * Combines payment schedule data with collected amounts from the receivables
 * view so the UI can show scheduled, collected, and remaining amounts together.
 */
export interface InstallmentRow {
  installmentNumber: number;
  dueDate: string;
  scheduledAmount: number;
  collectedAmount: number;
  remainingAmount: number;
  /**
   * UI-facing installment status. When a receivable exists this reflects the
   * receivable_status (which can be partially_paid); when only a payment
   * schedule entry exists the schedule status is explicitly mapped via
   * mapScheduleStatusToUiStatus() in the API layer.
   */
  status: InstallmentStatus;
}

// ---------- Collection summary -------------------------------------------

/**
 * High-level collections summary for a contract.
 * Sourced from GET /collections/contracts/{id}/receivables.
 */
export interface CollectionSummary {
  contractId: string;
  totalDue: number;
  totalReceived: number;
  totalOutstanding: number;
  /** Number of installments with paid status. */
  paidInstallments: number;
  /** Number of installments with overdue status. */
  overdueInstallments: number;
  /** Total installment count. */
  totalInstallments: number;
}

// ---------- Overdue installment ------------------------------------------

/**
 * An overdue installment for the overdue panel.
 */
export interface OverdueInstallment {
  installmentNumber: number;
  dueDate: string;
  overdueAmount: number;
  /** Days overdue derived from due date and current date — display only. */
  daysOverdue: number;
}

// ---------- Payment plan list item (queue) --------------------------------

/**
 * A payment plan list item enriched with contract, unit, and collection data.
 * Displayed in the payment plans queue table.
 */
export interface PaymentPlanListItem {
  contractId: string;
  contractNumber: string;
  contractPrice: number;
  contractStatus: string;
  unitId: string;
  unitNumber: string;
  project: string;
  /** Total amount collected to date. */
  totalCollected: number;
  /** Outstanding balance. */
  totalOutstanding: number;
  /** Total amount due per schedule. */
  totalDue: number;
  /** Next due date from schedule (null if fully paid or no schedule). */
  nextDueDate: string | null;
  /** Total overdue amount. */
  overdueAmount: number;
  /** Number of installments with overdue status. */
  overdueCount: number;
  /** Collection progress (0–100). */
  collectionPercent: number;
}

// ---------- Payment plan detail ------------------------------------------

/**
 * Full contract-level payment plan detail, combining contract, schedule, and
 * receivables data for the detail page.
 */
export interface PaymentPlanDetail {
  contractId: string;
  contractNumber: string;
  contractPrice: number;
  contractStatus: string;
  contractDate: string;
  unitId: string;
  unitNumber: string;
  project: string;
  buyerId: string;
  schedule: InstallmentRow[];
  collectionSummary: CollectionSummary;
  overdueInstallments: OverdueInstallment[];
}

// ---------- Filter state -------------------------------------------------

/** UI filter state for the payment plans queue listing page. */
export interface PaymentPlanFiltersState {
  collectionStatus: "" | "has_overdue" | "fully_paid" | "in_progress";
  contractStatus: "" | "draft" | "active" | "cancelled" | "completed";
  minOutstanding: string;
  maxOutstanding: string;
}
