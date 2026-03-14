"use client";

import React, { useState } from "react";
import type { UnitListItem, UnitPrice } from "@/lib/units-types";
import { unitStatusLabel, unitTypeLabel } from "@/lib/units-types";
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

/** Map a backend UnitStatus value to the corresponding CSS module class. */
function statusClass(status: string): string {
  switch (status) {
    case "available":
      return styles.statusAvailable;
    case "reserved":
      return styles.statusReserved;
    case "under_contract":
      return styles.statusUnderContract;
    case "registered":
      return styles.statusRegistered;
    default:
      return "";
  }
}

/**
 * UnitsTable — sortable table of unit inventory.
 *
 * Displays unit number, type, area, status, and pricing data.
 * Sorting is performed client-side on the provided units list.
 *
 * Explicitly does NOT compute pricing formulas — all pricing values
 * are sourced from the backend pricing engine via the pricing prop.
 *
 * Price / sqm uses `pricing.unit_area` (which reflects the backend pricing
 * engine's resolved area — gross_area when set, otherwise internal_area)
 * rather than raw `unit.internal_area`, keeping the UI consistent with how
 * `final_unit_price` was derived on the backend.
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

  const SortHeader = ({
    field,
    children,
  }: {
    field: SortField;
    children: React.ReactNode;
  }) => (
    <th
      scope="col"
      className={styles.sortableHeader}
      aria-sort={
        sortField === field ? (sortDir === "asc" ? "ascending" : "descending") : "none"
      }
    >
      <button
        type="button"
        className={styles.sortBtn}
        onClick={() => handleSort(field)}
      >
        {children}
        {indicator(field)}
      </button>
    </th>
  );

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
            <SortHeader field="unit_number">Unit</SortHeader>
            <SortHeader field="unit_type">Type</SortHeader>
            <SortHeader field="internal_area">Area (sqm)</SortHeader>
            <SortHeader field="status">Status</SortHeader>
            <SortHeader field="final_unit_price">Final Price</SortHeader>
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
            // Use backend-resolved unit_area (which accounts for gross_area) for
            // price/sqm, falling back to internal_area when pricing is not available.
            const effectiveArea = p ? p.unit_area : unit.internal_area;
            const pricePerSqm =
              p && effectiveArea > 0
                ? p.final_unit_price / effectiveArea
                : null;

            return (
              <tr key={unit.id}>
                <td>
                  <span className={styles.unitNumber}>{unit.unit_number}</span>
                </td>
                <td>{unitTypeLabel(unit.unit_type)}</td>
                <td>{unit.internal_area.toFixed(1)}</td>
                <td>
                  <span
                    className={`${styles.statusBadge} ${statusClass(unit.status)}`}
                  >
                    {unitStatusLabel(unit.status)}
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
