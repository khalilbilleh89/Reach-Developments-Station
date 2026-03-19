/**
 * ConstructionScopeSummaryTable — renders per-scope construction summary rows.
 *
 * Shows engineering counts, milestone counts, progress, budget/actual/variance,
 * and provides a quick link to the scope detail view.
 *
 * Visual status emphasis:
 *   - overdue milestones row highlighted in red
 *   - over-budget scopes highlighted in red
 *   - under-budget scopes highlighted in green
 */

"use client";

import React from "react";
import type { ConstructionDashboardScopeSummary } from "@/lib/construction-types";
import styles from "@/styles/construction.module.css";

interface ConstructionScopeSummaryTableProps {
  scopes: ConstructionDashboardScopeSummary[];
  onSelectScope: (scopeId: string) => void;
}

function _fmt(value: string): string {
  const n = parseFloat(value);
  if (isNaN(n)) return value;
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(n);
}

export function ConstructionScopeSummaryTable({
  scopes,
  onSelectScope,
}: ConstructionScopeSummaryTableProps) {
  if (scopes.length === 0) {
    return (
      <div className={styles.emptyState}>
        <div className={styles.emptyIcon}>🏗️</div>
        <div className={styles.emptyText}>
          No construction scopes found for this project.
        </div>
      </div>
    );
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Scope</th>
            <th>Engineering</th>
            <th>Milestones</th>
            <th>Progress</th>
            <th>Budget (AED)</th>
            <th>Actual (AED)</th>
            <th>Variance (AED)</th>
          </tr>
        </thead>
        <tbody>
          {scopes.map((scope) => {
            const variance = parseFloat(scope.variance_to_budget);
            const isOverBudget = variance > 0;
            const isUnderBudget = variance < 0;
            const hasOverdue = scope.milestones_overdue > 0;

            const rowClass = [
              hasOverdue ? styles.rowOverdue : "",
              isOverBudget ? styles.rowOverBudget : "",
              isUnderBudget && !hasOverdue ? styles.rowUnderBudget : "",
            ]
              .filter(Boolean)
              .join(" ");

            return (
              <tr key={scope.scope_id} className={rowClass || undefined}>
                <td>
                  <button
                    type="button"
                    className={styles.linkButton}
                    onClick={() => onSelectScope(scope.scope_id)}
                  >
                    {scope.scope_name}
                  </button>
                </td>
                <td>
                  {scope.engineering_items_open} open /{" "}
                  {scope.engineering_items_total} total
                </td>
                <td>
                  {scope.milestones_completed}/{scope.milestones_total} done
                  {hasOverdue && (
                    <span className={styles.overdueTag}>
                      {" "}
                      ⚠ {scope.milestones_overdue} overdue
                    </span>
                  )}
                </td>
                <td>
                  {scope.latest_progress_percent !== null
                    ? `${scope.latest_progress_percent}%`
                    : "—"}
                </td>
                <td>{_fmt(scope.total_budget)}</td>
                <td>{_fmt(scope.total_actual)}</td>
                <td
                  className={
                    isOverBudget
                      ? styles.varianceOver
                      : isUnderBudget
                        ? styles.varianceUnder
                        : undefined
                  }
                >
                  {_fmt(scope.variance_to_budget)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

