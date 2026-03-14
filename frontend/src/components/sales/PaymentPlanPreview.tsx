"use client";

import React from "react";
import type { PaymentPlanPreview } from "@/lib/sales-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/sales-workflow.module.css";

interface PaymentPlanPreviewProps {
  preview: PaymentPlanPreview | null;
}

/**
 * PaymentPlanPreview — read-only summary of the linked payment plan.
 *
 * Shows total installments, total amount due, and the next upcoming
 * installment if one exists. This component is display-only; editing
 * payment plans is out of scope for this PR.
 */
export function PaymentPlanPreview({ preview }: PaymentPlanPreviewProps) {
  return (
    <div className={styles.paymentPlanPanel}>
      <p className={styles.paymentPlanTitle}>Payment Plan Preview</p>

      {preview === null ? (
        <p className={styles.paymentPlanEmpty}>
          No payment schedule available for this unit.
        </p>
      ) : (
        <div className={styles.paymentPlanGrid}>
          <div className={styles.paymentPlanItem}>
            <span className={styles.paymentPlanItemLabel}>Installments</span>
            <span className={styles.paymentPlanItemValue}>
              {preview.totalInstallments}
            </span>
          </div>

          <div className={styles.paymentPlanItem}>
            <span className={styles.paymentPlanItemLabel}>Total Due</span>
            <span className={`${styles.paymentPlanItemValue} ${styles.paymentPlanTotal}`}>
              {formatCurrency(preview.totalDue)}
            </span>
          </div>

          {preview.nextDueDate && preview.nextDueAmount !== null && (
            <>
              <div className={styles.paymentPlanItem}>
                <span className={styles.paymentPlanItemLabel}>Next Due Date</span>
                <span className={styles.paymentPlanItemValue}>
                  {preview.nextDueDate}
                </span>
              </div>

              <div className={styles.paymentPlanItem}>
                <span className={styles.paymentPlanItemLabel}>Next Amount</span>
                <span className={styles.paymentPlanItemValue}>
                  {formatCurrency(preview.nextDueAmount)}
                </span>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
