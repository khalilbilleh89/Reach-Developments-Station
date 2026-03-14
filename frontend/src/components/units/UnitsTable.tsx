"use client";

import React, { useState } from "react";
import type { UnitListItem, UnitPrice } from "@/lib/units-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/units-pricing.module.css";

type SortField = "unit_number" | "floor_id" | "unit_type" | "status" | "internal_area" | "final_unit_price";
type SortDir = "asc" | "desc";

interface UnitsTableProps {
  units: UnitListItem[];
  /** Pricing map keyed by unit ID. May be partial if pricing is not available for all units. */
  pricing: Record<string, UnitPrice>;
  onViewUnit: (unitId: string) => void;
}

/** Map a UnitStatus string to the corresponding CSS module class. */
function statusClass(status: string): string {
  switch (status) {
    case "available":
      return styles.statusAvailable;
    case "reserved":
      return styles.statusReserved;
    case "sold":
      return styles.statusSold;
    case "blocked":
      return styles.statusBlocked;
    case "under_offer":
      return styles.statusUnderOffer;
    default:
      return "";
  }
}

/** Human-readable status label. */
function statusLabel(status: string): string {
  return status.replace(/_/g, " ");
}

/**
 * UnitsTable — sortable table of unit inventory.
 *
 * Displays unit number, type, area, status, and pricing data.
 * Sorting is performed client-side on the provided units list.
 *
 * Explicitly does NOT compute pricing formulas — all pricing values
 * are sourced from the backend pricing engine via the pricing prop.
 */
export function UnitsTable({ units, pricing, onViewUnit }: UnitsTableProps) {
  const [sortField, setSortField] = useState<SortField>("unit_number");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const handleSort = (field: SortField) => {
    if (field === sortField) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  };

  const sorted = [...units].sort((a, b) => {
    let aVal: string | number;
    let bVal: string | number;

    switch (sortField) {
      case "final_unit_price":
        aVal = pricing[a.id]?.final_unit_price ?? -1;
        bVal = pricing[b.id]?.final_unit_price ?? -1;
        break;
      case "internal_area":
        aVal = a.internal_area;
        bVal = b.internal_area;
        break;
      default:
        aVal = (a[sortField as keyof UnitListItem] as string) ?? "";
        bVal = (b[sortField as keyof UnitListItem] as string) ?? "";
    }

    if (aVal < bVal) return sortDir === "asc" ? -1 : 1;
    if (aVal > bVal) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  const indicator = (field: SortField) => {
    if (field !== sortField) return null;
    return (
      <span className={styles.sortIndicator} aria-hidden="true">
        {sortDir === "asc" ? "↑" : "↓"}
      </span>
    );
  };

  if (units.length === 0) {
    return (
      <div className={styles.emptyState}>
        <p className={styles.emptyStateTitle}>No units found</p>
        <p className={styles.emptyStateBody}>
          Try adjusting the filters or select a different project.
        </p>
      </div>
    );
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table} aria-label="Units list">
        <thead className={styles.tableHead}>
          <tr>
            <th
              scope="col"
              onClick={() => handleSort("unit_number")}
              aria-sort={sortField === "unit_number" ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
            >
              Unit {indicator("unit_number")}
            </th>
            <th
              scope="col"
              onClick={() => handleSort("unit_type")}
              aria-sort={sortField === "unit_type" ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
            >
              Type {indicator("unit_type")}
            </th>
            <th
              scope="col"
              onClick={() => handleSort("internal_area")}
              aria-sort={sortField === "internal_area" ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
            >
              Area (sqm) {indicator("internal_area")}
            </th>
            <th
              scope="col"
              onClick={() => handleSort("status")}
              aria-sort={sortField === "status" ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
            >
              Status {indicator("status")}
            </th>
            <th
              scope="col"
              onClick={() => handleSort("final_unit_price")}
              aria-sort={sortField === "final_unit_price" ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
            >
              Final Price {indicator("final_unit_price")}
            </th>
            <th scope="col">Price / sqm</th>
            <th scope="col">Outdoor Area</th>
            <th scope="col" aria-label="Actions" />
          </tr>
        </thead>
        <tbody className={styles.tableBody}>
          {sorted.map((unit) => {
            const p = pricing[unit.id];
            const outdoorArea =
              (unit.balcony_area ?? 0) +
              (unit.terrace_area ?? 0) +
              (unit.roof_garden_area ?? 0) +
              (unit.front_garden_area ?? 0);
            const pricePerSqm =
              p && unit.internal_area > 0
                ? p.final_unit_price / unit.internal_area
                : null;

            return (
              <tr key={unit.id}>
                <td>
                  <span className={styles.unitNumber}>{unit.unit_number}</span>
                </td>
                <td style={{ textTransform: "capitalize" }}>
                  {unit.unit_type.replace(/_/g, " ")}
                </td>
                <td>{unit.internal_area.toFixed(1)}</td>
                <td>
                  <span
                    className={`${styles.statusBadge} ${statusClass(unit.status)}`}
                  >
                    {statusLabel(unit.status)}
                  </span>
                </td>
                <td>
                  {p ? formatCurrency(p.final_unit_price) : <span aria-label="Not priced">—</span>}
                </td>
                <td>
                  {pricePerSqm !== null
                    ? `AED ${Math.round(pricePerSqm).toLocaleString()}`
                    : <span aria-label="Not available">—</span>}
                </td>
                <td>
                  {outdoorArea > 0
                    ? `${outdoorArea.toFixed(1)} sqm`
                    : <span aria-label="None">—</span>}
                </td>
                <td>
                  <button
                    type="button"
                    className={styles.actionBtn}
                    onClick={() => onViewUnit(unit.id)}
                    aria-label={`View pricing for unit ${unit.unit_number}`}
                  >
                    View
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
