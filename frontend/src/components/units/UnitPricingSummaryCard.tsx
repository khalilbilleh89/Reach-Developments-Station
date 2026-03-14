import React from "react";
import type { UnitListItem, UnitPrice } from "@/lib/units-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/units-pricing.module.css";

interface UnitPricingSummaryCardProps {
  unit: UnitListItem;
  pricing: UnitPrice | null;
}

/** Map a status string to its CSS class. */
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

/**
 * UnitPricingSummaryCard — compact pricing snapshot for a single unit.
 *
 * Displays total price, price per sqm, internal area, outdoor area,
 * and commercial status. Reusable in both the list and detail page.
 *
 * Pricing values are sourced directly from the backend; no calculations
 * are performed here beyond simple presentation formatting.
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

  const pricePerSqm =
    pricing && unit.internal_area > 0
      ? pricing.final_unit_price / unit.internal_area
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
            {unit.status.replace(/_/g, " ")}
          </span>
        </div>
      </div>
    </div>
  );
}
