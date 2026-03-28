/**
 * TenderComparisonSummaryStrip — compact summary bar showing totals
 * for a comparison set (total baseline, comparison, variance, and variance %).
 */

"use client";

import React from "react";
import type { ConstructionCostComparisonSummary } from "@/lib/tender-comparison-types";
import styles from "@/styles/construction.module.css";

interface TenderComparisonSummaryStripProps {
  summary: ConstructionCostComparisonSummary;
}

function fmt(value: string | null): string {
  if (value === null || value === undefined) return "—";
  const num = parseFloat(value);
  if (isNaN(num)) return String(value);
  return num.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmtPct(value: string | null): string {
  if (value === null || value === undefined) return "—";
  const num = parseFloat(value);
  if (isNaN(num)) return "—";
  const sign = num > 0 ? "+" : "";
  return `${sign}${num.toFixed(2)}%`;
}

export function TenderComparisonSummaryStrip({
  summary,
}: TenderComparisonSummaryStripProps) {
  return (
    <div className={styles.summaryStrip} data-testid="tender-comparison-summary-strip">
      <div className={styles.summaryCard}>
        <div className={styles.summaryLabel}>Lines</div>
        <div className={styles.summaryValue}>{summary.line_count}</div>
      </div>
      <div className={styles.summaryCard}>
        <div className={styles.summaryLabel}>Total Baseline</div>
        <div className={styles.summaryValue}>{fmt(summary.total_baseline)}</div>
      </div>
      <div className={styles.summaryCard}>
        <div className={styles.summaryLabel}>Total Comparison</div>
        <div className={styles.summaryValue}>
          {fmt(summary.total_comparison)}
        </div>
      </div>
      <div className={styles.summaryCard}>
        <div className={styles.summaryLabel}>Total Variance</div>
        <div className={styles.summaryValue}>{fmt(summary.total_variance)}</div>
      </div>
      <div className={styles.summaryCard}>
        <div className={styles.summaryLabel}>Variance %</div>
        <div className={styles.summaryValue}>
          {fmtPct(summary.total_variance_pct)}
        </div>
      </div>
    </div>
  );
}
