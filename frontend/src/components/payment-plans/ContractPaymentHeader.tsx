"use client";

import React from "react";
import type { PaymentPlanDetail } from "@/lib/payment-plans-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/payment-plans.module.css";

interface ContractPaymentHeaderProps {
  detail: PaymentPlanDetail;
}

function contractStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    active: "Active",
    draft: "Draft",
    cancelled: "Cancelled",
    completed: "Completed",
  };
  return labels[status] ?? status;
}

function contractStatusClass(status: string): string {
  switch (status) {
    case "active":
      return styles.contractActive;
    case "draft":
      return styles.contractDraft;
    case "cancelled":
      return styles.contractCancelled;
    case "completed":
      return styles.contractCompleted;
    default:
      return "";
  }
}

/**
 * ContractPaymentHeader — compact contract + unit + buyer context block.
 *
 * Displays: contract number, unit number, project, buyer ID, contract status,
 * contract date, and contract price.
 *
 * Read-only — all values sourced from the backend via props.
 */
export function ContractPaymentHeader({ detail }: ContractPaymentHeaderProps) {
  return (
    <div className={styles.contractHeader}>
      <p className={styles.contractHeaderTitle}>Contract Details</p>
      <p className={styles.contractHeaderNumber}>{detail.contractNumber}</p>
      <div className={styles.contractHeaderGrid}>
        <div className={styles.contractHeaderField}>
          <span className={styles.contractHeaderFieldLabel}>Unit</span>
          <span className={styles.contractHeaderFieldValue}>{detail.unitNumber}</span>
        </div>
        {detail.project && (
          <div className={styles.contractHeaderField}>
            <span className={styles.contractHeaderFieldLabel}>Project</span>
            <span className={styles.contractHeaderFieldValue}>{detail.project}</span>
          </div>
        )}
        <div className={styles.contractHeaderField}>
          <span className={styles.contractHeaderFieldLabel}>Buyer ID</span>
          <span className={styles.contractHeaderFieldValue}>{detail.buyerId}</span>
        </div>
        <div className={styles.contractHeaderField}>
          <span className={styles.contractHeaderFieldLabel}>Contract Status</span>
          <span
            className={`${styles.contractStatusBadge} ${contractStatusClass(detail.contractStatus)}`}
          >
            {contractStatusLabel(detail.contractStatus)}
          </span>
        </div>
        <div className={styles.contractHeaderField}>
          <span className={styles.contractHeaderFieldLabel}>Contract Date</span>
          <span className={styles.contractHeaderFieldValue}>{detail.contractDate}</span>
        </div>
        <div className={styles.contractHeaderField}>
          <span className={styles.contractHeaderFieldLabel}>Contract Price</span>
          <span className={styles.contractHeaderFieldValue}>
            {formatCurrency(detail.contractPrice)}
          </span>
        </div>
      </div>
    </div>
  );
}
