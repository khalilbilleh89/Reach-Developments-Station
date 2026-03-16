"use client";

import React, { useState } from "react";
import type { UnitListItem, UnitPrice, UnitPricingRecord } from "@/lib/units-types";
import { pricingStatusLabel, unitStatusLabel, unitTypeLabel } from "@/lib/units-types";
import { formatAmount, formatAdjustment, formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/units-pricing.module.css";

type SortField = "unit_number" | "floor_id" | "unit_type" | "status" | "internal_area" | "final_unit_price";
type SortDir = "asc" | "desc";

interface UnitsTableProps {
  units: UnitListItem[];
  /** Engine-calculated pricing map keyed by unit ID. May be partial. */
  pricing: Record<string, UnitPrice | undefined>;
  /** Formal pricing record map keyed by unit ID. May be partial. */
  pricingRecords: Partial<Record<string, UnitPricingRecord>>;
  onViewUnit: (unitId: string) => void;
  onEditPricing: (unit: UnitListItem) => void;
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
 * UnitsTable — sortable table of unit inventory with pricing data.
 *
 * Displays unit number, type, area, inventory status, and per-unit pricing
 * columns (Base Price, Adjustment, Final Price, Pricing Status).
 * Sorting is performed client-side on the provided units list.
 *
 * Pricing values are sourced from two backends:
 *   - `pricingRecords` — the formal per-unit pricing record (preferred)
 *   - `pricing` — the sqm-based engine calculation (fallback for Final Price)
 *
 * Both maps may be partial (not every unit has a record/calculation yet).
 * All monetary values are formatted using the record's own `currency` field
 * so that non-AED records display correctly.
 */
export function UnitsTable({ units, pricing, pricingRecords, onViewUnit, onEditPricing }: UnitsTableProps) {
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
            <th scope="col">Base Price</th>
            <th scope="col">Adjustment</th>
            <SortHeader field="final_unit_price">Final Price</SortHeader>
            <th scope="col">Pricing Status</th>
            <th scope="col" aria-label="Actions" />
          </tr>
        </thead>
        <tbody className={styles.tableBody}>
          {sorted.map((unit) => {
            const p = pricing[unit.id];
            const r = pricingRecords[unit.id];

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
                  {r ? formatAmount(r.base_price, r.currency) : <span aria-label="Not set">—</span>}
                </td>
                <td>
                  {r
                    ? r.manual_adjustment !== 0
                      ? formatAdjustment(r.manual_adjustment, r.currency)
                      : "—"
                    : <span aria-label="Not set">—</span>}
                </td>
                <td>
                  {r
                    ? formatAmount(r.final_price, r.currency)
                    : p
                      ? formatCurrency(p.final_unit_price)
                      : <span aria-label="Not priced">—</span>}
                </td>
                <td>
                  {r ? (
                    <span className={styles.statusBadge}>
                      {pricingStatusLabel(r.pricing_status)}
                    </span>
                  ) : (
                    <span aria-label="Not set">—</span>
                  )}
                </td>
                <td style={{ display: "flex", gap: "0.5rem" }}>
                  <button
                    type="button"
                    className={styles.actionBtn}
                    onClick={() => onEditPricing(unit)}
                    aria-label={`Edit pricing for unit ${unit.unit_number}`}
                  >
                    Edit Pricing
                  </button>
                  <button
                    type="button"
                    className={styles.actionBtn}
                    onClick={() => onViewUnit(unit.id)}
                    aria-label={`View detail for unit ${unit.unit_number}`}
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
