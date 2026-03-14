"use client";

import React from "react";
import type { SalesReadinessStatus, ContractStatus } from "@/lib/sales-types";
import { readinessLabel } from "@/lib/sales-types";
import type { UnitListItem, UnitPrice } from "@/lib/units-types";
import styles from "@/styles/sales-workflow.module.css";

interface SalesReadinessCardProps {
  unit: UnitListItem;
  pricing: UnitPrice | null;
  hasApprovedException: boolean;
  /** Whether any non-approved (pending) exceptions exist for this unit. */
  hasPendingException?: boolean;
  contractStatus: ContractStatus | null;
  readiness: SalesReadinessStatus;
}

interface CheckItem {
  label: string;
  pass: boolean;
}

/** Map a readiness value to the CSS badge class. */
function readinessClass(readiness: SalesReadinessStatus): string {
  switch (readiness) {
    case "ready":
      return styles.readinessReady;
    case "needs_exception_approval":
      return styles.readinessNeedsException;
    case "under_contract":
      return styles.readinessUnderContract;
    case "missing_pricing":
      return styles.readinessMissingPricing;
    case "blocked":
      return styles.readinessBlocked;
    default:
      return "";
  }
}

/**
 * SalesReadinessCard — displays commercial readiness status for a unit.
 *
 * Shows a readiness badge and a checklist of backend-sourced facts.
 * No frontend business calculations are performed — all values come from
 * props sourced from the backend.
 */
export function SalesReadinessCard({
  unit,
  pricing,
  hasApprovedException,
  hasPendingException = false,
  contractStatus,
  readiness,
}: SalesReadinessCardProps) {
  const checks: CheckItem[] = [
    {
      label: "Unit is available or reserved",
      pass: unit.status === "available" || unit.status === "reserved",
    },
    {
      label: "Pricing is available",
      pass: pricing !== null,
    },
    {
      label: "No active contract",
      pass: contractStatus !== "active",
    },
  ];

  if (hasPendingException) {
    checks.push({
      label: "Pending exception awaiting approval",
      pass: false,
    });
  }

  if (hasApprovedException) {
    checks.push({
      label: "Approved exception on file",
      pass: true,
    });
  }

  return (
    <div className={styles.readinessCard}>
      <p className={styles.readinessCardTitle}>Commercial Readiness</p>

      <div className={styles.readinessStatusRow}>
        <span
          className={`${styles.readinessBadge} ${readinessClass(readiness)}`}
          aria-label={`Readiness: ${readinessLabel(readiness)}`}
        >
          {readinessLabel(readiness)}
        </span>
      </div>

      <ul className={styles.readinessChecklist} aria-label="Readiness checklist">
        {checks.map((item) => (
          <li
            key={item.label}
            className={`${styles.readinessCheckItem} ${item.pass ? styles.checkPass : styles.checkFail}`}
          >
            <span aria-hidden="true">{item.pass ? "✓" : "✗"}</span>
            {item.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
