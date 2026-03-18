/**
 * ConstructionScopesTable — renders a list of construction scopes.
 */

"use client";

import React from "react";
import type { ConstructionScope, ConstructionStatus } from "@/lib/construction-types";
import styles from "@/styles/construction.module.css";

const STATUS_LABELS: Record<ConstructionStatus, string> = {
  planned: "Planned",
  in_progress: "In Progress",
  on_hold: "On Hold",
  completed: "Completed",
};

function StatusBadge({ status }: { status: ConstructionStatus }) {
  const cls =
    status === "planned"
      ? styles.statusPipeline
      : status === "in_progress"
        ? styles.statusActive
        : status === "completed"
          ? styles.statusCompleted
          : styles.statusOnHold;
  return <span className={`${styles.badge} ${cls}`}>{STATUS_LABELS[status]}</span>;
}

interface ConstructionScopesTableProps {
  scopes: ConstructionScope[];
  onSelectScope: (scopeId: string) => void;
  onDeleteScope: (scopeId: string) => void;
}

export function ConstructionScopesTable({
  scopes,
  onSelectScope,
  onDeleteScope,
}: ConstructionScopesTableProps) {
  if (scopes.length === 0) {
    return (
      <div className={styles.emptyState}>
        <div className={styles.emptyIcon}>🏗️</div>
        <div className={styles.emptyText}>No construction scopes yet</div>
        <div className={styles.emptySubtext}>
          Create a scope to start tracking construction progress.
        </div>
      </div>
    );
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Name</th>
            <th>Status</th>
            <th>Start Date</th>
            <th>Target End</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {scopes.map((scope) => (
            <tr
              key={scope.id}
              className={styles.clickableRow}
              onClick={() => onSelectScope(scope.id)}
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && onSelectScope(scope.id)}
            >
              <td>
                <div className={styles.projectName}>{scope.name}</div>
                {scope.description && (
                  <div className={styles.projectCode}>{scope.description}</div>
                )}
              </td>
              <td>
                <StatusBadge status={scope.status} />
              </td>
              <td>{scope.start_date ?? "—"}</td>
              <td>{scope.target_end_date ?? "—"}</td>
              <td>
                <div className={styles.actionGroup} onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    className={styles.actionButton}
                    onClick={() => onSelectScope(scope.id)}
                  >
                    View
                  </button>
                  <button
                    type="button"
                    className={`${styles.actionButton} ${styles.actionButtonDanger}`}
                    onClick={() => onDeleteScope(scope.id)}
                  >
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
