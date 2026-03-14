"use client";

import React from "react";
import type { CollectionSummary } from "@/lib/payment-plans-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/payment-plans.module.css";

interface CollectionsProgressCardProps {
  summary: CollectionSummary;
}

/**
 * CollectionsProgressCard — compact summary of collection performance.
 *
 * Displays total collected, outstanding, collection %, paid and overdue
 * installment counts, and a progress bar.
 *
 * Visualization uses a simple progress bar and metric rows.
 * No heavy charting. All values sourced from the backend via props.
 */
export function CollectionsProgressCard({ summary }: CollectionsProgressCardProps) {
  const collectionPercent =
    summary.totalDue > 0
      ? (summary.totalReceived / summary.totalDue) * 100
      : 0;

  // Clamp to [0, 100] for progress bar, ARIA, and label so that they remain
  // consistent even when over-collected (totalReceived > totalDue).
  const displayPercent = Math.min(100, Math.max(0, Math.round(collectionPercent)));

  return (
    <div className={styles.collectionsCard}>
      <p className={styles.collectionsCardTitle}>Collections Progress</p>

      <div className={styles.collectionsProgressRow}>
        <div className={styles.collectionsProgressLabel}>
          <span>Collection progress</span>
          <span>{displayPercent}%</span>
        </div>
        <div
          className={styles.progressBar}
          role="progressbar"
          aria-valuenow={displayPercent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Collection progress: ${displayPercent}%`}
        >
          <div
            className={styles.progressFill}
            style={{ width: `${displayPercent}%` }}
          />
        </div>
      </div>

      <div className={styles.collectionsMetrics}>
        <div className={styles.collectionsMetricItem}>
          <span className={styles.collectionsMetricLabel}>Total Collected</span>
          <span className={styles.collectionsMetricValue}>
            {formatCurrency(summary.totalReceived)}
          </span>
        </div>
        <div className={styles.collectionsMetricItem}>
          <span className={styles.collectionsMetricLabel}>Outstanding</span>
          <span className={styles.collectionsMetricValue}>
            {formatCurrency(summary.totalOutstanding)}
          </span>
        </div>
        <div className={styles.collectionsMetricItem}>
          <span className={styles.collectionsMetricLabel}>Paid Installments</span>
          <span className={styles.collectionsMetricValue}>
            {summary.paidInstallments} / {summary.totalInstallments}
          </span>
        </div>
        {summary.overdueInstallments > 0 && (
          <div className={styles.collectionsMetricItem}>
            <span className={styles.collectionsMetricLabel}>Overdue Installments</span>
            <span className={`${styles.collectionsMetricValue} ${styles.overdueAmount}`}>
              {summary.overdueInstallments}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
