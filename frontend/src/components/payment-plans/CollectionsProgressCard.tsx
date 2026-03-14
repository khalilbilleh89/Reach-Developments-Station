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

  return (
    <div className={styles.collectionsCard}>
      <p className={styles.collectionsCardTitle}>Collections Progress</p>

      <div className={styles.collectionsProgressRow}>
        <div className={styles.collectionsProgressLabel}>
          <span>Collection progress</span>
          <span>{Math.round(collectionPercent)}%</span>
        </div>
        <div
          className={styles.progressBar}
          role="progressbar"
          aria-valuenow={Math.round(collectionPercent)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Collection progress: ${Math.round(collectionPercent)}%`}
        >
          <div
            className={styles.progressFill}
            style={{ width: `${Math.min(100, collectionPercent)}%` }}
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
