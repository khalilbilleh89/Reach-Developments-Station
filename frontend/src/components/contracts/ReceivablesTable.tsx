"use client";

import React from "react";
import type { Receivable } from "@/lib/receivables-types";
import { receivableStatusLabel } from "@/lib/receivables-types";
import { receivableStatusBadgeClass } from "@/lib/receivables-ui";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/payment-plans.module.css";

interface ReceivablesTableProps {
  receivables: Receivable[];
}

/**
 * ReceivablesTable — displays the receivables ledger for a contract.
 *
 * Columns: Receivable #, Due Date, Amount Due, Amount Paid, Balance, Status.
 *
 * This component is display-only and receives its data via props.
 */
export function ReceivablesTable({ receivables }: ReceivablesTableProps) {
  if (receivables.length === 0) {
    return (
      <div className={styles.emptyState}>
        <p className={styles.emptyStateTitle}>No receivables</p>
        <p className={styles.emptyStateBody}>
          No receivables have been generated for this contract yet.
        </p>
      </div>
    );
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table} aria-label="Receivables ledger">
        <thead className={styles.tableHead}>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Due Date</th>
            <th scope="col">Amount Due</th>
            <th scope="col">Amount Paid</th>
            <th scope="col">Balance</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody className={styles.tableBody}>
          {receivables.map((row) => (
            <tr key={row.id}>
              <td>{row.receivable_number}</td>
              <td>{String(row.due_date)}</td>
              <td>{formatCurrency(row.amount_due)}</td>
              <td>{formatCurrency(row.amount_paid)}</td>
              <td>{formatCurrency(row.balance_due)}</td>
              <td>
                <span
                  className={`${styles.statusBadge} ${receivableStatusBadgeClass(row.status)}`}
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
