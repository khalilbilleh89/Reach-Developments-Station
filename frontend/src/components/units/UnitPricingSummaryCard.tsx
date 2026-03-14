import React from "react";
import type { UnitListItem, UnitPrice } from "@/lib/units-types";
import { unitStatusLabel } from "@/lib/units-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/units-pricing.module.css";

interface UnitPricingSummaryCardProps {
  unit: UnitListItem;
  pricing: UnitPrice | null;
}

/** Map a backend UnitStatus value to its CSS class. */
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
 * UnitPricingSummaryCard — compact pricing snapshot for a single unit.
 *
 * Displays total price, price per sqm, internal area, outdoor area,
 * and commercial status. Reusable in both the list and detail page.
 *
 * Price / sqm uses `pricing.unit_area` (the backend-resolved effective area)
 * when available, falling back to `unit.internal_area` only when pricing is
 * absent, keeping the UI consistent with backend pricing truth.
 *
 * No pricing calculations are performed here beyond display formatting.
 */
export function UnitPricingSummaryCard({
  unit,
  pricing,
}: UnitPricingSummaryCardProps) {
  const outdoorArea =
    (unit.balcony_area ?? 0) +
    (unit.terrace_area ?? 0) +
    (unit.roof_garden_area ?? 0) +
    (unit.front_garden_area ?? 0);

  // Use backend-resolved unit_area (may use gross_area) for price/sqm.
  const effectiveArea = pricing ? pricing.unit_area : unit.internal_area;
  const pricePerSqm =
    pricing && effectiveArea > 0
      ? pricing.final_unit_price / effectiveArea
      : null;

  return (
    <div className={styles.summaryCard} aria-label="Pricing summary">
      <div>
        <p className={styles.summaryCardTitle}>Pricing Summary</p>
        <p className={styles.summaryPriceMain}>
          {pricing ? formatCurrency(pricing.final_unit_price) : "Not priced"}
        </p>
      </div>

      <div className={styles.summaryMetaRow}>
        <div className={styles.summaryMetaItem}>
          <span className={styles.summaryMetaLabel}>Price / sqm</span>
          <span className={styles.summaryMetaValue}>
            {pricePerSqm !== null
              ? `AED ${Math.round(pricePerSqm).toLocaleString()}`
              : "—"}
          </span>
        </div>

        <div className={styles.summaryMetaItem}>
          <span className={styles.summaryMetaLabel}>Internal Area</span>
          <span className={styles.summaryMetaValue}>
            {unit.internal_area.toFixed(1)} sqm
          </span>
        </div>

        {outdoorArea > 0 && (
          <div className={styles.summaryMetaItem}>
            <span className={styles.summaryMetaLabel}>Outdoor Area</span>
            <span className={styles.summaryMetaValue}>
              {outdoorArea.toFixed(1)} sqm
            </span>
          </div>
        )}

        <div className={styles.summaryMetaItem}>
          <span className={styles.summaryMetaLabel}>Status</span>
          <span
            className={`${styles.statusBadge} ${statusClass(unit.status)}`}
            style={{ display: "inline-block" }}
          >
            {unitStatusLabel(unit.status)}
          </span>
        </div>
      </div>
    </div>
  );
}
