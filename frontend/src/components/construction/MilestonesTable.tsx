/**
 * MilestonesTable — renders a list of construction milestones for a scope.
 */

"use client";

import React from "react";
import type { ConstructionMilestone, MilestoneStatus } from "@/lib/construction-types";
import styles from "@/styles/construction.module.css";

const STATUS_LABELS: Record<MilestoneStatus, string> = {
  pending: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
  delayed: "Delayed",
};

function MilestoneStatusBadge({ status }: { status: MilestoneStatus }) {
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

interface MilestonesTableProps {
  milestones: ConstructionMilestone[];
  onUpdateStatus: (milestoneId: string, status: MilestoneStatus) => void;
  onDeleteMilestone: (milestoneId: string) => void;
}

export function MilestonesTable({
  milestones,
  onUpdateStatus,
  onDeleteMilestone,
}: MilestonesTableProps) {
  if (milestones.length === 0) {
    return (
      <div className={styles.emptyState}>
        <div className={styles.emptyIcon}>📋</div>
        <div className={styles.emptyText}>No milestones yet</div>
        <div className={styles.emptySubtext}>
          Add milestones to track construction progress.
        </div>
      </div>
    );
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>#</th>
            <th>Name</th>
            <th>Status</th>
            <th>Target Date</th>
            <th>Completion Date</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {milestones.map((m) => (
            <tr key={m.id}>
              <td>{m.sequence}</td>
              <td>
                <div className={styles.projectName}>{m.name}</div>
                {m.notes && (
                  <div className={styles.projectCode}>{m.notes}</div>
                )}
              </td>
              <td>
                <MilestoneStatusBadge status={m.status} />
              </td>
              <td>{m.target_date ?? "—"}</td>
              <td>{m.completion_date ?? "—"}</td>
              <td>
                <div className={styles.actionGroup}>
                  {m.status !== "completed" && (
                    <button
                      type="button"
                      className={styles.actionButton}
                      onClick={() => onUpdateStatus(m.id, "completed")}
                    >
                      Mark Done
                    </button>
                  )}
                  {m.status === "pending" && (
                    <button
                      type="button"
                      className={styles.actionButton}
                      onClick={() => onUpdateStatus(m.id, "in_progress")}
                    >
                      Start
                    </button>
                  )}
                  <button
                    type="button"
                    className={`${styles.actionButton} ${styles.actionButtonDanger}`}
                    onClick={() => onDeleteMilestone(m.id)}
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
