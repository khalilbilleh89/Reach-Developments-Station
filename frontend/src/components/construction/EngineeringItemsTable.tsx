/**
 * EngineeringItemsTable — renders a list of engineering items for a scope.
 *
 * Engineering = technical coordination, consultant deliverables, and
 * consultant cost entries. This is the Engineering workspace inside a
 * construction scope.
 */

"use client";

import React from "react";
import type {
  ConstructionEngineeringItem,
  EngineeringStatus,
} from "@/lib/construction-types";
import styles from "@/styles/construction.module.css";

const STATUS_LABELS: Record<EngineeringStatus, string> = {
  pending: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
  delayed: "Delayed",
  on_hold: "On Hold",
};

function EngineeringStatusBadge({ status }: { status: EngineeringStatus }) {
  const cls =
    status === "pending"
      ? styles.statusPipeline
      : status === "in_progress"
        ? styles.statusActive
        : status === "completed"
          ? styles.statusCompleted
          : styles.statusOnHold;
  return (
    <span className={`${styles.badge} ${cls}`}>{STATUS_LABELS[status]}</span>
  );
}

interface EngineeringItemsTableProps {
  items: ConstructionEngineeringItem[];
  onUpdateStatus: (itemId: string, status: EngineeringStatus) => void;
  onDeleteItem: (itemId: string) => void;
}

export function EngineeringItemsTable({
  items,
  onUpdateStatus,
  onDeleteItem,
}: EngineeringItemsTableProps) {
  if (items.length === 0) {
    return (
      <div className={styles.emptyState}>
        <div className={styles.emptyIcon}>📐</div>
        <div className={styles.emptyText}>No engineering items yet</div>
        <div className={styles.emptySubtext}>
          Add engineering tasks, deliverables, or consultant entries to track
          technical progress.
        </div>
      </div>
    );
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Title</th>
            <th>Type</th>
            <th>Status</th>
            <th>Consultant</th>
            <th>Cost</th>
            <th>Target Date</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <div className={styles.projectName}>{item.title}</div>
                {item.notes && (
                  <div className={styles.projectCode}>{item.notes}</div>
                )}
              </td>
              <td>{item.item_type ?? "—"}</td>
              <td>
                <EngineeringStatusBadge status={item.status} />
              </td>
              <td>{item.consultant_name ?? "—"}</td>
              <td>
                {item.consultant_cost != null
                  ? Number(item.consultant_cost).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })
                  : "—"}
              </td>
              <td>{item.target_date ?? "—"}</td>
              <td>
                <div className={styles.actionGroup}>
                  {item.status !== "completed" && (
                    <button
                      type="button"
                      className={styles.actionButton}
                      onClick={() => onUpdateStatus(item.id, "completed")}
                    >
                      Mark Done
                    </button>
                  )}
                  {item.status === "pending" && (
                    <button
                      type="button"
                      className={styles.actionButton}
                      onClick={() => onUpdateStatus(item.id, "in_progress")}
                    >
                      Start
                    </button>
                  )}
                  <button
                    type="button"
                    className={`${styles.actionButton} ${styles.actionButtonDanger}`}
                    onClick={() => onDeleteItem(item.id)}
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
