"use client";

import React from "react";
import type { Installment } from "@/lib/payment-plans-types";
import { installmentStatusLabel } from "@/lib/payment-plans-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/payment-plans.module.css";

interface InstallmentsTableProps {
  installments: Installment[];
}

/** Map an installment status to its CSS class. */
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
 * InstallmentsTable — displays the installment schedule for a contract's
 * payment plan.
 *
 * Columns: installment #, due date, amount, status.
 *
 * This component is display-only and receives its data via props.
 */
export function InstallmentsTable({ installments }: InstallmentsTableProps) {
  if (installments.length === 0) {
    return (
      <div className={styles.emptyState}>
        <p className={styles.emptyStateTitle}>No installments</p>
        <p className={styles.emptyStateBody}>
          No installment schedule has been generated for this contract yet.
        </p>
      </div>
    );
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table} aria-label="Installment schedule">
        <thead className={styles.tableHead}>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Due Date</th>
            <th scope="col">Amount</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody className={styles.tableBody}>
          {installments.map((row) => (
            <tr key={row.id}>
              <td>{row.installment_number}</td>
              <td>{String(row.due_date)}</td>
              <td>{formatCurrency(row.due_amount)}</td>
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
