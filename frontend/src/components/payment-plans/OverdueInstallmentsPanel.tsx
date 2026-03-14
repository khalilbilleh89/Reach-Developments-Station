"use client";

import React from "react";
import type { OverdueInstallment } from "@/lib/payment-plans-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/payment-plans.module.css";

interface OverdueInstallmentsPanelProps {
  overdueInstallments: OverdueInstallment[];
}

/**
 * OverdueInstallmentsPanel — highlights overdue installments clearly.
 *
 * Renders nothing when there are no overdue installments.
 *
 * Displays: installment #, due date, overdue amount, days overdue.
 * Days overdue is derived from due date vs. current date for display only —
 * it is not an accounting truth.
 *
 * All values sourced from the backend via props.
 */
export function OverdueInstallmentsPanel({
  overdueInstallments,
}: OverdueInstallmentsPanelProps) {
  if (overdueInstallments.length === 0) {
    return null;
  }

  return (
    <div className={styles.overduePanel} role="alert" aria-label="Overdue installments">
      <p className={styles.overduePanelTitle}>
        ⚠ Overdue Installments ({overdueInstallments.length})
      </p>
      <div className={styles.tableWrapper}>
        <table className={styles.table} aria-label="Overdue installments">
          <thead className={styles.tableHead}>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Due Date</th>
              <th scope="col">Amount Overdue</th>
              <th scope="col">Days Overdue</th>
            </tr>
          </thead>
          <tbody className={styles.tableBody}>
            {overdueInstallments.map((item) => (
              <tr key={item.installmentNumber}>
                <td>{item.installmentNumber}</td>
                <td>{item.dueDate}</td>
                <td>
                  <span className={styles.overdueAmount}>
                    {formatCurrency(item.overdueAmount)}
                  </span>
                </td>
                <td>
                  <span className={styles.overdueBadge}>
                    {item.daysOverdue}d overdue
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
