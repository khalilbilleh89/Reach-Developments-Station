"use client";

import React from "react";
import type { UnitListItem, UnitPrice } from "@/lib/units-types";
import { unitStatusLabel, unitTypeLabel } from "@/lib/units-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/sales-workflow.module.css";

interface SalesUnitSummaryProps {
  unit: UnitListItem;
  pricing: UnitPrice | null;
}

/**
 * SalesUnitSummary — compact unit summary for the sales workflow detail page.
 *
 * Displays physical and commercial attributes for the selected unit.
 * Pricing values are sourced from the backend pricing engine via props.
 * No financial calculations are performed here.
 */
export function SalesUnitSummary({ unit, pricing }: SalesUnitSummaryProps) {
  const outdoorArea =
    (unit.balcony_area ?? 0) +
    (unit.terrace_area ?? 0) +
    (unit.roof_garden_area ?? 0) +
    (unit.front_garden_area ?? 0);

  const pricePerSqm =
    pricing && pricing.unit_area > 0
      ? pricing.final_unit_price / pricing.unit_area
      : null;

  return (
    <div className={styles.summaryCard}>
      <p className={styles.summaryCardTitle}>Unit Summary</p>

      <p className={styles.summaryUnitNumber}>{unit.unit_number}</p>

      <div className={styles.summaryGrid}>
        <div className={styles.summaryItem}>
          <span className={styles.summaryItemLabel}>Type</span>
          <span className={styles.summaryItemValue}>
            {unitTypeLabel(unit.unit_type)}
          </span>
        </div>

        <div className={styles.summaryItem}>
          <span className={styles.summaryItemLabel}>Status</span>
          <span className={styles.summaryItemValue}>
            {unitStatusLabel(unit.status)}
          </span>
        </div>

        <div className={styles.summaryItem}>
          <span className={styles.summaryItemLabel}>Internal Area</span>
          <span className={styles.summaryItemValue}>
            {unit.internal_area.toFixed(1)} sqm
          </span>
        </div>

        {outdoorArea > 0 && (
          <div className={styles.summaryItem}>
            <span className={styles.summaryItemLabel}>Outdoor Area</span>
            <span className={styles.summaryItemValue}>
              {outdoorArea.toFixed(1)} sqm
            </span>
          </div>
        )}

        <div className={styles.summaryItem}>
          <span className={styles.summaryItemLabel}>Final Price</span>
          <span className={`${styles.summaryItemValue} ${styles.summaryPrice}`}>
            {pricing ? formatCurrency(pricing.final_unit_price) : "Not priced"}
          </span>
        </div>

        {pricePerSqm !== null && (
          <div className={styles.summaryItem}>
            <span className={styles.summaryItemLabel}>Price / sqm</span>
            <span className={styles.summaryItemValue}>
              AED {Math.round(pricePerSqm).toLocaleString()}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
