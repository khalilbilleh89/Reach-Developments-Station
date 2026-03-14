"use client";

import React from "react";
import type { ApprovedSalesException } from "@/lib/sales-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/sales-workflow.module.css";

interface ApprovedExceptionPanelProps {
  exceptions: ApprovedSalesException[];
}

/** Human-readable exception type label. */
function exceptionTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    discount: "Discount",
    price_override: "Price Override",
    incentive_package: "Incentive Package",
    payment_concession: "Payment Concession",
    marketing_promo: "Marketing Promo",
  };
  return (
    labels[type] ??
    type
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ")
  );
}

/**
 * ApprovedExceptionPanel — displays approved sales exceptions for a unit.
 *
 * Only approved exceptions are shown. Each exception displays the commercial
 * terms that affect the deal: requested price, discount amount, discount %,
 * and any incentive information.
 *
 * This panel is read-only. Exception approval is handled by the backend.
 */
export function ApprovedExceptionPanel({ exceptions }: ApprovedExceptionPanelProps) {
  return (
    <div className={styles.exceptionPanel}>
      <p className={styles.exceptionPanelTitle}>Approved Exceptions</p>

      {exceptions.length === 0 ? (
        <p className={styles.exceptionEmpty}>
          No approved exceptions for this unit.
        </p>
      ) : (
        <div className={styles.exceptionList}>
          {exceptions.map((ex) => (
            <div key={ex.id} className={styles.exceptionItem}>
              <div className={styles.exceptionItemHeader}>
                <span className={styles.exceptionItemType}>
                  {exceptionTypeLabel(ex.exception_type)}
                </span>
                <span
                  className={`${styles.readinessBadge} ${styles.readinessReady}`}
                >
                  Approved
                </span>
              </div>

              <div className={styles.exceptionGrid}>
                <div className={styles.exceptionField}>
                  <span className={styles.exceptionFieldLabel}>Base Price</span>
                  <span className={styles.exceptionFieldValue}>
                    {formatCurrency(ex.base_price)}
                  </span>
                </div>

                <div className={styles.exceptionField}>
                  <span className={styles.exceptionFieldLabel}>Approved Price</span>
                  <span className={styles.exceptionFieldValue}>
                    {formatCurrency(ex.requested_price)}
                  </span>
                </div>

                <div className={styles.exceptionField}>
                  <span className={styles.exceptionFieldLabel}>Discount</span>
                  <span className={styles.exceptionFieldValue}>
                    {formatCurrency(ex.discount_amount)} (
                    {ex.discount_percentage.toFixed(1)}%)
                  </span>
                </div>

                {ex.incentive_value !== null && ex.incentive_value > 0 && (
                  <div className={styles.exceptionField}>
                    <span className={styles.exceptionFieldLabel}>Incentive Value</span>
                    <span className={styles.exceptionFieldValue}>
                      {formatCurrency(ex.incentive_value)}
                    </span>
                  </div>
                )}

                {ex.incentive_description && (
                  <div className={styles.exceptionField}>
                    <span className={styles.exceptionFieldLabel}>Incentive</span>
                    <span className={styles.exceptionFieldValue}>
                      {ex.incentive_description}
                    </span>
                  </div>
                )}

                {ex.approved_by && (
                  <div className={styles.exceptionField}>
                    <span className={styles.exceptionFieldLabel}>Approved By</span>
                    <span className={styles.exceptionFieldValue}>
                      {ex.approved_by}
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
