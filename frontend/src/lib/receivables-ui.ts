/**
 * receivables-ui.ts
 *
 * Shared UI helpers for receivable status badge rendering.
 * Imported by both ReceivablesTable and the finance receivables page so that
 * badge styling stays consistent when statuses are added or renamed.
 */

// Receivables tables reuse the same CSS module as payment-plan tables
// (statusPaid, statusOverdue, etc. are shared finance-table utilities).
import styles from "@/styles/payment-plans.module.css";

/**
 * Map a receivable status string to its CSS badge class.
 *
 * Centralised here to avoid duplicating the mapping in every table component.
 */
export function receivableStatusBadgeClass(status: string): string {
  switch (status) {
    case "paid":
      return styles.statusPaid;
    case "partially_paid":
      return styles.statusPartiallyPaid;
    case "overdue":
      return styles.statusOverdue;
    case "due":
      return styles.statusDue;
    case "cancelled":
      return styles.statusCancelled;
    case "pending":
    default:
      return styles.statusPending;
  }
}
