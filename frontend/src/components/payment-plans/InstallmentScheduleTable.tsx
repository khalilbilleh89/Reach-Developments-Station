"use client";

import React from "react";
import type { InstallmentRow } from "@/lib/payment-plans-types";
import { installmentStatusLabel } from "@/lib/payment-plans-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/payment-plans.module.css";

interface InstallmentScheduleTableProps {
  rows: InstallmentRow[];
}

/** Map an installment UI status to its CSS class. */
function statusClass(status: string): string {
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

/**
 * InstallmentScheduleTable — displays the full installment schedule for a
 * contract.
 *
 * Columns: installment #, due date, scheduled amount, collected amount,
 * remaining amount, status.
 *
 * Status values cover both receivable statuses (when a receivable exists) and
 * payment schedule statuses (when no receivable exists yet):
 *   Paid / Partially Paid / Due / Upcoming / Overdue / Cancelled
 *
 * All values sourced from backend via props. No calculations performed here.
 */
export function InstallmentScheduleTable({ rows }: InstallmentScheduleTableProps) {
  if (rows.length === 0) {
    return (
      <div className={styles.emptyState}>
        <p className={styles.emptyStateTitle}>No installment schedule</p>
        <p className={styles.emptyStateBody}>
          No payment schedule has been generated for this contract yet.
        </p>
      </div>
    );
  }

  return (
    <div className={styles.tableWrapper}>
      <table
        className={styles.table}
        aria-label="Installment schedule"
      >
        <thead className={styles.tableHead}>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Due Date</th>
            <th scope="col">Scheduled Amount</th>
            <th scope="col">Collected</th>
            <th scope="col">Remaining</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody className={styles.tableBody}>
          {rows.map((row) => (
            <tr key={row.installmentNumber}>
              <td>{row.installmentNumber}</td>
              <td>{row.dueDate}</td>
              <td>{formatCurrency(row.scheduledAmount)}</td>
              <td>{formatCurrency(row.collectedAmount)}</td>
              <td>
                {row.remainingAmount > 0 ? (
                  formatCurrency(row.remainingAmount)
                ) : (
                  <span aria-label="Fully paid">—</span>
                )}
              </td>
              <td>
                <span
                  className={`${styles.statusBadge} ${statusClass(row.status)}`}
                >
                  {installmentStatusLabel(row.status)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
