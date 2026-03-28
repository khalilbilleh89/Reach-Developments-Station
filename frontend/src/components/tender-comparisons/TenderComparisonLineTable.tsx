/**
 * TenderComparisonLineTable — tabular list of comparison lines within a set.
 *
 * Renders all lines with columns for category, baseline, comparison,
 * variance amount, variance %, reason, and row-level actions (edit / delete).
 */

"use client";

import React from "react";
import type { ConstructionCostComparisonLine } from "@/lib/tender-comparison-types";
import { VARIANCE_REASON_LABELS } from "@/lib/tender-comparison-types";
import { COST_CATEGORY_LABELS } from "@/lib/construction-cost-types";
import styles from "@/styles/construction.module.css";

interface TenderComparisonLineTableProps {
  lines: ConstructionCostComparisonLine[];
  baselineLabel: string;
  comparisonLabel: string;
  onEdit: (line: ConstructionCostComparisonLine) => void;
  onDelete: (line: ConstructionCostComparisonLine) => void;
  deletingId: string | null;
}

function fmt(amount: string | number): string {
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  if (isNaN(num)) return String(amount);
  return num.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmtVariance(amount: string): string {
  const num = parseFloat(amount);
  if (isNaN(num)) return amount;
  const sign = num > 0 ? "+" : "";
  return `${sign}${num.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function fmtPct(pct: string | null): string {
  if (pct === null || pct === undefined) return "—";
  const num = parseFloat(pct);
  if (isNaN(num)) return "—";
  const sign = num > 0 ? "+" : "";
  return `${sign}${num.toFixed(2)}%`;
}

export function TenderComparisonLineTable({
  lines,
  baselineLabel,
  comparisonLabel,
  onEdit,
  onDelete,
  deletingId,
}: TenderComparisonLineTableProps) {
  if (lines.length === 0) {
    return (
      <div className={styles.emptyState} data-testid="lines-empty-state">
        <p className={styles.emptyStateTitle}>No comparison lines yet.</p>
        <p className={styles.emptyStateBody}>
          Add a line to begin comparing costs.
        </p>
      </div>
    );
  }

  return (
    <div className={styles.tableWrapper}>
      <table
        className={styles.table}
        aria-label="Comparison cost lines"
      >
        <thead>
          <tr>
            <th scope="col">Category</th>
            <th scope="col">{baselineLabel}</th>
            <th scope="col">{comparisonLabel}</th>
            <th scope="col">Variance</th>
            <th scope="col">Var %</th>
            <th scope="col">Reason</th>
            <th scope="col">Notes</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((line) => {
            const varianceNum = parseFloat(line.variance_amount);
            const varianceClass =
              varianceNum > 0
                ? styles.variancePositive
                : varianceNum < 0
                  ? styles.varianceNegative
                  : undefined;

            return (
              <tr key={line.id} data-testid={`comparison-line-row-${line.id}`}>
                <td>
                  {COST_CATEGORY_LABELS[line.cost_category] ??
                    line.cost_category}
                </td>
                <td className={styles.amountCell}>
                  {fmt(line.baseline_amount)}
                </td>
                <td className={styles.amountCell}>
                  {fmt(line.comparison_amount)}
                </td>
                <td className={`${styles.amountCell} ${varianceClass ?? ""}`}>
                  {fmtVariance(line.variance_amount)}
                </td>
                <td className={varianceClass ?? undefined}>
                  {fmtPct(line.variance_pct)}
                </td>
                <td>
                  {VARIANCE_REASON_LABELS[line.variance_reason] ??
                    line.variance_reason}
                </td>
                <td>{line.notes ?? "—"}</td>
                <td>
                  <div className={styles.rowActions}>
                    <button
                      className={styles.actionButton}
                      onClick={() => onEdit(line)}
                      aria-label={`Edit line ${line.id}`}
                    >
                      Edit
                    </button>
                    <button
                      className={styles.actionButtonDanger}
                      onClick={() => onDelete(line)}
                      disabled={deletingId === line.id}
                      aria-label={`Delete line ${line.id}`}
                    >
                      {deletingId === line.id ? "Deleting…" : "Delete"}
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
