"use client";

import React from "react";
import type { Floor } from "@/lib/floors-types";
import styles from "@/styles/projects.module.css";

interface FloorsTableProps {
  floors: Floor[];
  onEdit: (floor: Floor) => void;
  onDelete: (floor: Floor) => void;
}

function floorStatusClass(status: string): string {
  switch (status) {
    case "active":
      return styles.statusActive;
    case "completed":
      return styles.statusCompleted;
    case "on_hold":
      return styles.statusOnHold;
    default:
      return styles.statusPipeline;
  }
}

function floorStatusLabel(status: string): string {
  switch (status) {
    case "on_hold":
      return "On Hold";
    default:
      return status.charAt(0).toUpperCase() + status.slice(1);
  }
}

/**
 * FloorsTable — displays the floors belonging to a building.
 *
 * Columns: Floor / Code / Sequence / Level / Status / Actions
 * Each row provides Edit and Delete action buttons.
 */
export function FloorsTable({ floors, onEdit, onDelete }: FloorsTableProps) {
  if (floors.length === 0) {
    return (
      <div className={styles.emptyState}>
        <div className={styles.emptyIcon}>🏗️</div>
        <div className={styles.emptyText}>No floors yet</div>
        <div className={styles.emptySubtext}>
          Create your first floor to start structuring this building.
        </div>
      </div>
    );
  }

  return (
    <div className={`${styles.tableWrapper} ${styles.floorsTable}`}>
      <table className={styles.table} aria-label="Building floors">
        <thead>
          <tr>
            <th scope="col">Floor</th>
            <th scope="col">Code</th>
            <th scope="col">Sequence</th>
            <th scope="col">Level</th>
            <th scope="col">Status</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {floors.map((floor) => (
            <tr key={floor.id}>
              <td>
                <div className={styles.projectName}>{floor.name}</div>
                {floor.description && (
                  <div className={styles.projectCode}>{floor.description}</div>
                )}
              </td>
              <td>{floor.code}</td>
              <td>{floor.sequence_number}</td>
              <td>{floor.level_number != null ? floor.level_number : "\u2014"}</td>
              <td>
                <span
                  className={`${styles.badge} ${floorStatusClass(floor.status)}`}
                >
                  {floorStatusLabel(floor.status)}
                </span>
              </td>
              <td>
                <div className={styles.actionGroup}>
                  <button
                    type="button"
                    className={styles.actionButton}
                    onClick={() => onEdit(floor)}
                    aria-label={`Edit floor ${floor.name}`}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className={`${styles.actionButton} ${styles.actionButtonDanger}`}
                    onClick={() => onDelete(floor)}
                    aria-label={`Delete floor ${floor.name}`}
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
