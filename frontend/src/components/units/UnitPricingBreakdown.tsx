import React from "react";
import type { UnitPrice, UnitPricingAttributes } from "@/lib/units-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/units-pricing.module.css";

interface UnitPricingBreakdownProps {
  pricing: UnitPrice | null;
  attributes: UnitPricingAttributes | null;
}

/**
 * UnitPricingBreakdown — displays pricing composition for a unit.
 *
 * Shows base price, individual premium components (floor, view, corner,
 * size, custom), the total premium, and the final selling price.
 *
 * Only renders fields that are actually available from the backend.
 * Does NOT compute or fabricate any pricing formulas client-side.
 *
 * The component structure is forward-compatible: as the backend exposes
 * additional breakdown fields, they can be added here without refactoring.
 */
export function UnitPricingBreakdown({
  pricing,
  attributes,
}: UnitPricingBreakdownProps) {
  if (!pricing) {
    return (
      <div className={styles.breakdownCard}>
        <h2 className={styles.breakdownTitle}>Pricing Breakdown</h2>
        <p className={styles.loadingState}>
          Pricing has not been configured for this unit yet.
        </p>
      </div>
    );
  }

  const hasAttributes = attributes !== null;

  return (
    <div className={styles.breakdownCard}>
      <h2 className={styles.breakdownTitle}>Pricing Breakdown</h2>

      {/* Base price */}
      <div className={styles.breakdownRow}>
        <span className={styles.breakdownKey}>Base Unit Price</span>
        <span className={styles.breakdownValue}>
          {formatCurrency(pricing.base_unit_price)}
        </span>
      </div>

      {/* Attribute-level premiums — only shown when attributes are available */}
      {hasAttributes && (
        <>
          {(attributes.floor_premium ?? 0) !== 0 && (
            <div className={styles.breakdownRow}>
              <span className={styles.breakdownKey}>Floor Premium</span>
              <span className={styles.breakdownValue}>
                {formatCurrency(attributes.floor_premium!)}
              </span>
            </div>
          )}

          {(attributes.view_premium ?? 0) !== 0 && (
            <div className={styles.breakdownRow}>
              <span className={styles.breakdownKey}>View Premium</span>
              <span className={styles.breakdownValue}>
                {formatCurrency(attributes.view_premium!)}
              </span>
            </div>
          )}

          {(attributes.corner_premium ?? 0) !== 0 && (
            <div className={styles.breakdownRow}>
              <span className={styles.breakdownKey}>Corner Premium</span>
              <span className={styles.breakdownValue}>
                {formatCurrency(attributes.corner_premium!)}
              </span>
            </div>
          )}

          {(attributes.size_adjustment ?? 0) !== 0 && (
            <div className={styles.breakdownRow}>
              <span className={styles.breakdownKey}>Size Adjustment</span>
              <span className={styles.breakdownValue}>
                {formatCurrency(attributes.size_adjustment!)}
              </span>
            </div>
          )}

          {(attributes.custom_adjustment ?? 0) !== 0 && (
            <div className={styles.breakdownRow}>
              <span className={styles.breakdownKey}>Custom Adjustment</span>
              <span className={styles.breakdownValue}>
                {formatCurrency(attributes.custom_adjustment!)}
              </span>
            </div>
          )}
        </>
      )}

      {/* Total premium from backend */}
      {pricing.premium_total !== 0 && (
        <div className={styles.breakdownRow}>
          <span className={styles.breakdownKey}>Total Premiums</span>
          <span className={styles.breakdownValue}>
            {formatCurrency(pricing.premium_total)}
          </span>
        </div>
      )}

      {/* Final price — always shown */}
      <div className={`${styles.breakdownRow} ${styles.breakdownRowFinal}`}>
        <span className={styles.breakdownKey}>Final Selling Price</span>
        <span className={styles.breakdownValueFinal}>
          {formatCurrency(pricing.final_unit_price)}
        </span>
      </div>
    </div>
  );
}
