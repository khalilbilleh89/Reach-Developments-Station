"use client";

import React from "react";
import type { Reservation, UnitListItem } from "@/lib/units-types";
import { reservationStatusLabel, unitStatusLabel, unitTypeLabel } from "@/lib/units-types";
import styles from "@/styles/projects.module.css";

interface UnitsInventoryTableProps {
  units: UnitListItem[];
  /** Map of unit_id → active Reservation (or undefined if no active reservation). */
  activeReservations?: Map<string, Reservation>;
  onEdit: (unit: UnitListItem) => void;
  onDelete: (unit: UnitListItem) => void;
  onReserve: (unit: UnitListItem) => void;
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

function reservationStatusClass(status: string): string {
  switch (status) {
    case "active":
      return styles.statusPipeline;
    case "expired":
    case "cancelled":
      return styles.statusPipeline;
    case "converted":
      return styles.statusCompleted;
    default:
      return styles.statusActive;
  }
}

/**
 * UnitsInventoryTable — displays units belonging to a floor.
 *
 * Columns: Unit / Type / Internal Area / Gross Area / Status / Reservation / Actions
 *
 * The Reservation column shows the active reservation status for the unit.
 * The "Reserve Unit" action is disabled when the unit already has an active
 * reservation.
 *
 * This component handles inventory management (CRUD + reservation) and is
 * separate from the pricing-focused UnitsTable component used in the
 * units-pricing page.
 */
export function UnitsInventoryTable({
  units,
  activeReservations = new Map(),
  onEdit,
  onDelete,
  onReserve,
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
            <th scope="col">Reservation</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {units.map((unit) => {
            const reservation = activeReservations.get(unit.id);
            const isReserved = !!reservation;

            return (
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
                  {reservation ? (
                    <span
                      className={`${styles.badge} ${reservationStatusClass(reservation.status)}`}
                      title={`Reserved for ${reservation.customer_name}`}
                    >
                      {reservationStatusLabel(reservation.status)}
                    </span>
                  ) : (
                    <span className={`${styles.badge} ${styles.statusActive}`}>
                      Available
                    </span>
                  )}
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
                      className={styles.actionButton}
                      onClick={() => onReserve(unit)}
                      disabled={isReserved}
                      aria-label={
                        isReserved
                          ? `Unit ${unit.unit_number} is already reserved`
                          : `Reserve unit ${unit.unit_number}`
                      }
                      title={isReserved ? "Unit already has an active reservation" : undefined}
                    >
                      Reserve
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
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
