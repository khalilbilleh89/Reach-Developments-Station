"use client";

import React from "react";
import type { UnitListItem } from "@/lib/units-types";
import { unitStatusLabel, unitTypeLabel } from "@/lib/units-types";
import styles from "@/styles/projects.module.css";

interface UnitsInventoryTableProps {
  units: UnitListItem[];
  onEdit: (unit: UnitListItem) => void;
  onDelete: (unit: UnitListItem) => void;
}

function unitStatusClass(status: string): string {
  switch (status) {
    case "available":
      return styles.statusActive;
    case "reserved":
      return styles.statusPipeline;
    case "under_contract":
      return styles.statusCompleted;
    case "registered":
      return styles.statusCompleted;
    default:
      return styles.statusPipeline;
  }
}

/**
 * UnitsInventoryTable — displays units belonging to a floor.
 *
 * Columns: Unit / Type / Internal Area / Status / Actions
 * Each row provides Edit and Delete action buttons.
 *
 * This component handles inventory management (CRUD) and is separate from
 * the pricing-focused UnitsTable component used in the units-pricing page.
 */
export function UnitsInventoryTable({
  units,
  onEdit,
  onDelete,
}: UnitsInventoryTableProps) {
  if (units.length === 0) {
    return (
      <div className={styles.emptyState}>
        <div className={styles.emptyIcon}>🏠</div>
        <div className={styles.emptyText}>No units yet</div>
        <div className={styles.emptySubtext}>
          Create your first unit to start building the inventory for this floor.
        </div>
      </div>
    );
  }

  return (
    <div className={`${styles.tableWrapper} ${styles.floorsTable}`}>
      <table className={styles.table} aria-label="Floor units">
        <thead>
          <tr>
            <th scope="col">Unit</th>
            <th scope="col">Type</th>
            <th scope="col">Internal Area (sqm)</th>
            <th scope="col">Gross Area (sqm)</th>
            <th scope="col">Status</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {units.map((unit) => (
            <tr key={unit.id}>
              <td>
                <div className={styles.projectName}>{unit.unit_number}</div>
              </td>
              <td>{unitTypeLabel(unit.unit_type)}</td>
              <td>{unit.internal_area.toFixed(1)}</td>
              <td>
                {unit.gross_area != null ? unit.gross_area.toFixed(1) : "\u2014"}
              </td>
              <td>
                <span
                  className={`${styles.badge} ${unitStatusClass(unit.status)}`}
                >
                  {unitStatusLabel(unit.status)}
                </span>
              </td>
              <td>
                <div className={styles.actionGroup}>
                  <button
                    type="button"
                    className={styles.actionButton}
                    onClick={() => onEdit(unit)}
                    aria-label={`Edit unit ${unit.unit_number}`}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className={`${styles.actionButton} ${styles.actionButtonDanger}`}
                    onClick={() => onDelete(unit)}
                    aria-label={`Delete unit ${unit.unit_number}`}
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
