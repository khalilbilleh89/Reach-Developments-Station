/**
 * ConstructionCostSummaryCard — displays aggregated scope-level cost totals.
 *
 * Shows total budget, committed, actual, variance to budget, and variance
 * to commitment. A per-category breakdown is rendered as a compact table.
 */

"use client";

import React from "react";
import type { ConstructionCostSummary } from "@/lib/construction-types";
import styles from "@/styles/construction.module.css";

interface ConstructionCostSummaryCardProps {
  summary: ConstructionCostSummary;
  currency?: string;
}

function fmt(value: string | number, currency: string): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  return `${currency} ${num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function varianceClass(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (num > 0) return styles.varianceOver;
  if (num < 0) return styles.varianceUnder;
  return "";
}

export function ConstructionCostSummaryCard({
  summary,
  currency = "AED",
}: ConstructionCostSummaryCardProps) {
  const categories = Object.entries(summary.by_category);

  return (
    <div className={styles.costSummaryCard}>
      <h3 className={styles.costSummaryTitle}>Cost Summary</h3>

      {/* Top-level KPI row */}
      <div className={styles.costSummaryKpis}>
        <div className={styles.costKpi}>
          <span className={styles.costKpiLabel}>Budget</span>
          <span className={styles.costKpiValue}>
            {fmt(summary.total_budget, currency)}
          </span>
        </div>
        <div className={styles.costKpi}>
          <span className={styles.costKpiLabel}>Committed</span>
          <span className={styles.costKpiValue}>
            {fmt(summary.total_committed, currency)}
          </span>
        </div>
        <div className={styles.costKpi}>
          <span className={styles.costKpiLabel}>Actual</span>
          <span className={styles.costKpiValue}>
            {fmt(summary.total_actual, currency)}
          </span>
        </div>
        <div className={styles.costKpi}>
          <span className={styles.costKpiLabel}>Variance (vs Budget)</span>
          <span
            className={`${styles.costKpiValue} ${varianceClass(summary.total_variance_to_budget)}`}
          >
            {fmt(summary.total_variance_to_budget, currency)}
          </span>
        </div>
        <div className={styles.costKpi}>
          <span className={styles.costKpiLabel}>Variance (vs Commitment)</span>
          <span
            className={`${styles.costKpiValue} ${varianceClass(summary.total_variance_to_commitment)}`}
          >
            {fmt(summary.total_variance_to_commitment, currency)}
          </span>
        </div>
      </div>

      {/* Per-category breakdown */}
      {categories.length > 0 && (
        <>
          <h4 className={styles.costSummarySubtitle}>By Category</h4>
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th className={styles.th}>Category</th>
                  <th className={styles.th}>Budget</th>
                  <th className={styles.th}>Committed</th>
                  <th className={styles.th}>Actual</th>
                  <th className={styles.th}>Var. vs Budget</th>
                  <th className={styles.th}>Var. vs Commit.</th>
                </tr>
              </thead>
              <tbody>
                {categories.map(([cat, data]) => (
                  <tr key={cat} className={styles.tr}>
                    <td className={styles.td}>
                      {cat.replace(/_/g, " ")}
                    </td>
                    <td className={styles.td}>{fmt(data.budget, currency)}</td>
                    <td className={styles.td}>{fmt(data.committed, currency)}</td>
                    <td className={styles.td}>{fmt(data.actual, currency)}</td>
                    <td className={`${styles.td} ${varianceClass(data.variance_to_budget)}`}>
                      {fmt(data.variance_to_budget, currency)}
                    </td>
                    <td className={`${styles.td} ${varianceClass(data.variance_to_commitment)}`}>
                      {fmt(data.variance_to_commitment, currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
