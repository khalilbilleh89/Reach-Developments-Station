import React from "react";
import type { UnitPrice, UnitPricingAttributes } from "@/lib/units-types";
import { formatAmount } from "@/lib/format-utils";
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
          {formatAmount(pricing.base_unit_price, pricing.currency)}
        </span>
      </div>

      {/* Attribute-level premiums — only shown when attributes are available */}
      {hasAttributes && (
        <>
          {(attributes.floor_premium ?? 0) !== 0 && (
            <div className={styles.breakdownRow}>
              <span className={styles.breakdownKey}>Floor Premium</span>
              <span className={styles.breakdownValue}>
                {formatAmount(attributes.floor_premium!, pricing.currency)}
              </span>
            </div>
          )}

          {(attributes.view_premium ?? 0) !== 0 && (
            <div className={styles.breakdownRow}>
              <span className={styles.breakdownKey}>View Premium</span>
              <span className={styles.breakdownValue}>
                {formatAmount(attributes.view_premium!, pricing.currency)}
              </span>
            </div>
          )}

          {(attributes.corner_premium ?? 0) !== 0 && (
            <div className={styles.breakdownRow}>
              <span className={styles.breakdownKey}>Corner Premium</span>
              <span className={styles.breakdownValue}>
                {formatAmount(attributes.corner_premium!, pricing.currency)}
              </span>
            </div>
          )}

          {(attributes.size_adjustment ?? 0) !== 0 && (
            <div className={styles.breakdownRow}>
              <span className={styles.breakdownKey}>Size Adjustment</span>
              <span className={styles.breakdownValue}>
                {formatAmount(attributes.size_adjustment!, pricing.currency)}
              </span>
            </div>
          )}

          {(attributes.custom_adjustment ?? 0) !== 0 && (
            <div className={styles.breakdownRow}>
              <span className={styles.breakdownKey}>Custom Adjustment</span>
              <span className={styles.breakdownValue}>
                {formatAmount(attributes.custom_adjustment!, pricing.currency)}
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
            {formatAmount(pricing.premium_total, pricing.currency)}
          </span>
        </div>
      )}

      {/* Final price — always shown */}
      <div className={`${styles.breakdownRow} ${styles.breakdownRowFinal}`}>
        <span className={styles.breakdownKey}>Final Selling Price</span>
        <span className={styles.breakdownValueFinal}>
          {formatAmount(pricing.final_unit_price, pricing.currency)}
        </span>
      </div>
    </div>
  );
}
