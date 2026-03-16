/**
 * receivables-types.ts — frontend type definitions for the receivables module.
 *
 * These types reflect the backend API contracts for:
 *   POST /api/v1/contracts/{contract_id}/receivables/generate
 *   GET  /api/v1/contracts/{contract_id}/receivables
 *   GET  /api/v1/projects/{project_id}/receivables
 *   GET  /api/v1/receivables/{receivable_id}
 *   PATCH /api/v1/receivables/{receivable_id}
 */

// ---------- Status ----------------------------------------------------------

/**
 * Lifecycle status of a receivable.
 *
 *   pending       — due date in future, unpaid
 *   due           — due date is today, unpaid
 *   overdue       — due date passed, balance > 0
 *   partially_paid — amount_paid > 0 and balance > 0
 *   paid          — balance_due == 0
 *   cancelled     — voided (contract/plan cancellation)
 */
export type ReceivableStatus =
  | "pending"
  | "due"
  | "overdue"
  | "partially_paid"
  | "paid"
  | "cancelled";

/** Human-readable label for a ReceivableStatus. */
export function receivableStatusLabel(status: ReceivableStatus | string): string {
  const labels: Record<string, string> = {
    pending: "Upcoming",
    due: "Due",
    overdue: "Overdue",
    partially_paid: "Partially Paid",
    paid: "Paid",
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

// ---------- Core receivable type -------------------------------------------

/**
 * A single receivable record as returned by the backend.
 */
export interface Receivable {
  id: string;
  contract_id: string;
  payment_plan_id: string | null;
  installment_id: string;
  receivable_number: number;
  due_date: string;
  amount_due: number;
  amount_paid: number;
  balance_due: number;
  currency: string;
  status: ReceivableStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

// ---------- List response ---------------------------------------------------

/**
 * List of receivables with aggregate totals.
 */
export interface ReceivableListResponse {
  items: Receivable[];
  total: number;
  total_amount_due: number;
  total_amount_paid: number;
  total_balance_due: number;
}

// ---------- Generation response --------------------------------------------

/**
 * Response returned after generating receivables for a contract.
 */
export interface GenerateReceivablesResponse {
  contract_id: string;
  generated: number;
  items: Receivable[];
}

// ---------- Update payloads ------------------------------------------------

/**
 * Payload for recording a manual payment update.
 * amount_paid is the new cumulative total (not an incremental delta).
 */
export interface ReceivablePaymentUpdate {
  amount_paid: number;
  notes?: string;
}
