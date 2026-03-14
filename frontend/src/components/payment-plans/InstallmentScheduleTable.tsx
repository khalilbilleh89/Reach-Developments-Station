"use client";

import React from "react";
import type { InstallmentRow } from "@/lib/payment-plans-types";
import { receivableStatusLabel } from "@/lib/payment-plans-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/payment-plans.module.css";

interface InstallmentScheduleTableProps {
  rows: InstallmentRow[];
}

/** Map a receivable status to its CSS class. */
function statusClass(status: string): string {
  switch (status) {
    case "paid":
      return styles.statusPaid;
    case "partially_paid":
      return styles.statusPartiallyPaid;
    case "overdue":
      return styles.statusOverdue;
    case "pending":
      return styles.statusPending;
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
 * Status values reflect backend receivable_status facts:
 *   Paid / Partially Paid / Upcoming / Overdue
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
                  {receivableStatusLabel(row.status)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
