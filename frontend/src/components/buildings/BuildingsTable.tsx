"use client";

import React from "react";
import type { Building } from "@/lib/buildings-types";
import styles from "@/styles/projects.module.css";

interface BuildingsTableProps {
  buildings: Building[];
  onEdit: (building: Building) => void;
  onDelete: (building: Building) => void;
}

function buildingStatusClass(status: string): string {
  switch (status) {
    case "under_construction":
      return styles.statusActive;
    case "completed":
      return styles.statusCompleted;
    case "on_hold":
      return styles.statusOnHold;
    default:
      return styles.statusPipeline;
  }
}

function buildingStatusLabel(status: string): string {
  switch (status) {
    case "under_construction":
      return "Under Construction";
    case "on_hold":
      return "On Hold";
    default:
      return status.charAt(0).toUpperCase() + status.slice(1);
  }
}

/**
 * BuildingsTable — displays the buildings belonging to a phase.
 *
 * Columns: Building / Code / Status / Floors / Actions
 * Each row provides Edit and Delete action buttons.
 */
export function BuildingsTable({
  buildings,
  onEdit,
  onDelete,
}: BuildingsTableProps) {
  if (buildings.length === 0) {
    return (
      <div className={styles.emptyState}>
        <div className={styles.emptyIcon}>🏢</div>
        <div className={styles.emptyText}>No buildings yet</div>
        <div className={styles.emptySubtext}>
          Add the first building to start structuring this phase.
        </div>
      </div>
    );
  }

  return (
    <div className={`${styles.tableWrapper} ${styles.buildingsTable}`}>
      <table className={styles.table} aria-label="Phase buildings">
        <thead>
          <tr>
            <th scope="col">Building</th>
            <th scope="col">Code</th>
            <th scope="col">Status</th>
            <th scope="col">Floors</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {buildings.map((building) => (
            <tr key={building.id}>
              <td>
                <div className={styles.projectName}>{building.name}</div>
              </td>
              <td>{building.code}</td>
              <td>
                <span
                  className={`${styles.badge} ${buildingStatusClass(building.status)}`}
                >
                  {buildingStatusLabel(building.status)}
                </span>
              </td>
              <td>{building.floors_count ?? "\u2014"}</td>
              <td>
                <div className={styles.actionGroup}>
                  <button
                    type="button"
                    className={styles.actionButton}
                    onClick={() => onEdit(building)}
                    aria-label={`Edit building ${building.name}`}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className={`${styles.actionButton} ${styles.actionButtonDanger}`}
                    onClick={() => onDelete(building)}
                    aria-label={`Delete building ${building.name}`}
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
