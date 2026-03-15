"use client";

import React from "react";
import type { Phase } from "@/lib/phases-types";
import styles from "@/styles/projects.module.css";

interface ProjectPhasesTableProps {
  phases: Phase[];
  onEdit: (phase: Phase) => void;
  onDelete: (phase: Phase) => void;
}

function phaseStatusClass(status: string): string {
  switch (status) {
    case "active":
      return styles.statusActive;
    case "completed":
      return styles.statusCompleted;
    default:
      return styles.statusPipeline;
  }
}

function phaseStatusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "\u2014";
  return new Date(dateStr).toLocaleDateString("en-GB", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/**
 * ProjectPhasesTable — displays the phases belonging to a project.
 *
 * Columns: Phase / Code / Sequence / Status / Launch Date / Target Completion / Actions
 * Each row provides Edit and Delete action buttons.
 */
export function ProjectPhasesTable({
  phases,
  onEdit,
  onDelete,
}: ProjectPhasesTableProps) {
  if (phases.length === 0) {
    return (
      <div className={styles.emptyState}>
        <div className={styles.emptyIcon}>📋</div>
        <div className={styles.emptyText}>No phases yet</div>
        <div className={styles.emptySubtext}>
          Add the first phase to start structuring this project.
        </div>
      </div>
    );
  }

  const sorted = [...phases].sort((a, b) => a.sequence - b.sequence);

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table} aria-label="Project phases">
        <thead>
          <tr>
            <th scope="col">Phase</th>
            <th scope="col">Code</th>
            <th scope="col">Sequence</th>
            <th scope="col">Status</th>
            <th scope="col">Launch Date</th>
            <th scope="col">Target Completion</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((phase) => (
            <tr key={phase.id}>
              <td>
                <div className={styles.projectName}>{phase.name}</div>
                {phase.description && (
                  <div className={styles.projectCode}>{phase.description}</div>
                )}
              </td>
              <td>{phase.code ?? "\u2014"}</td>
              <td>{phase.sequence}</td>
              <td>
                <span
                  className={`${styles.badge} ${phaseStatusClass(phase.status)}`}
                >
                  {phaseStatusLabel(phase.status)}
                </span>
              </td>
              <td>{formatDate(phase.start_date)}</td>
              <td>{formatDate(phase.end_date)}</td>
              <td>
                <div className={styles.actionGroup}>
                  <button
                    type="button"
                    className={styles.actionButton}
                    onClick={() => onEdit(phase)}
                    aria-label={`Edit phase ${phase.name}`}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className={`${styles.actionButton} ${styles.actionButtonDanger}`}
                    onClick={() => onDelete(phase)}
                    aria-label={`Delete phase ${phase.name}`}
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
