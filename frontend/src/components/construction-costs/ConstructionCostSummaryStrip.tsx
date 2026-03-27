/**
 * ConstructionCostSummaryStrip — compact summary bar showing grand total
 * and per-category active-record totals for a project.
 */

"use client";

import React from "react";
import type { ConstructionCostSummary } from "@/lib/construction-cost-types";
import { COST_CATEGORY_LABELS } from "@/lib/construction-cost-types";
import styles from "@/styles/construction.module.css";

interface ConstructionCostSummaryStripProps {
  summary: ConstructionCostSummary;
}

function fmt(value: string): string {
  const num = parseFloat(value);
  if (isNaN(num)) return value;
  return num.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function ConstructionCostSummaryStrip({
  summary,
}: ConstructionCostSummaryStripProps) {
  const categoryEntries = Object.entries(summary.by_category);

  return (
    <div className={styles.summaryStrip} data-testid="cost-summary-strip">
      <div className={styles.summaryCard}>
        <div className={styles.summaryLabel}>Active Records</div>
        <div className={styles.summaryValue}>{summary.active_record_count}</div>
      </div>
      <div className={styles.summaryCard}>
        <div className={styles.summaryLabel}>Grand Total (AED)</div>
        <div className={styles.summaryValue}>{fmt(summary.grand_total)}</div>
      </div>
      {categoryEntries.map(([cat, total]) => (
        <div key={cat} className={styles.summaryCard}>
          <div className={styles.summaryLabel}>
            {COST_CATEGORY_LABELS[cat as keyof typeof COST_CATEGORY_LABELS] ?? cat}
          </div>
          <div className={styles.summaryValue}>{fmt(total)}</div>
        </div>
      ))}
    </div>
  );
}
