"use client";

import React from "react";
import type { PaymentPlanListItem } from "@/lib/payment-plans-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/payment-plans.module.css";

interface PaymentPlanSummaryCardProps {
  item: PaymentPlanListItem;
}

/**
 * PaymentPlanSummaryCard — high-level contract/payment plan snapshot card.
 *
 * Displays contract value, total collected, outstanding balance, collection
 * ratio, installment count, and next due date. Reuses metric-card visual
 * patterns from the dashboard.
 *
 * All values are sourced from the backend via props. No calculations here.
 */
export function PaymentPlanSummaryCard({ item }: PaymentPlanSummaryCardProps) {
  return (
    <div className={styles.summaryCard}>
      <p className={styles.summaryCardTitle}>Payment Plan Summary</p>
      <div className={styles.summaryGrid}>
        <div className={styles.summaryItem}>
          <span className={styles.summaryItemLabel}>Contract Value</span>
          <span className={styles.summaryItemValueLarge}>
            {formatCurrency(item.contractPrice)}
          </span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryItemLabel}>Total Collected</span>
          <span className={styles.summaryItemValueLarge}>
            {formatCurrency(item.totalCollected)}
          </span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryItemLabel}>Outstanding Balance</span>
          <span className={styles.summaryItemValueLarge}>
            {formatCurrency(item.totalOutstanding)}
          </span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryItemLabel}>Collection Ratio</span>
          <span className={styles.summaryItemValueLarge}>
            {Math.round(item.collectionPercent)}%
          </span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryItemLabel}>Next Due Date</span>
          <span className={styles.summaryItemValue}>
            {item.nextDueDate ?? "—"}
          </span>
        </div>
        {item.overdueAmount > 0 && (
          <div className={styles.summaryItem}>
            <span className={styles.summaryItemLabel}>Overdue</span>
            <span className={`${styles.summaryItemValue} ${styles.overdueAmount}`}>
              {formatCurrency(item.overdueAmount)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
