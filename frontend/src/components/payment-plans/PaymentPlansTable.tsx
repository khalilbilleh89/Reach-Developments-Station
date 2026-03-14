"use client";

import React, { useState } from "react";
import Link from "next/link";
import type { PaymentPlanListItem } from "@/lib/payment-plans-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/payment-plans.module.css";

type SortField =
  | "contractNumber"
  | "unitNumber"
  | "contractPrice"
  | "totalCollected"
  | "totalOutstanding"
  | "nextDueDate"
  | "overdueAmount"
  | "collectionPercent";

type SortDir = "asc" | "desc";

interface PaymentPlansTableProps {
  items: PaymentPlanListItem[];
}

/** Map a contract status to its CSS class. */
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

function contractStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    active: "Active",
    draft: "Draft",
    cancelled: "Cancelled",
    completed: "Completed",
  };
  return labels[status] ?? status;
}

/**
 * PaymentPlansTable — sortable queue table of payment plans.
 *
 * Shows contract, unit, collected vs outstanding amounts, next due date,
 * overdue amount, and collection progress. Each row links to the contract-
 * level detail page.
 *
 * All financial values come from the backend via props. No calculations here.
 */
export function PaymentPlansTable({ items }: PaymentPlansTableProps) {
  const [sortField, setSortField] = useState<SortField>("contractNumber");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const handleSort = (field: SortField) => {
    if (field === sortField) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  };

  const sorted = [...items].sort((a, b) => {
    let aVal: string | number;
    let bVal: string | number;

    switch (sortField) {
      case "contractNumber":
        aVal = a.contractNumber;
        bVal = b.contractNumber;
        break;
      case "unitNumber":
        aVal = a.unitNumber;
        bVal = b.unitNumber;
        break;
      case "contractPrice":
        aVal = a.contractPrice;
        bVal = b.contractPrice;
        break;
      case "totalCollected":
        aVal = a.totalCollected;
        bVal = b.totalCollected;
        break;
      case "totalOutstanding":
        aVal = a.totalOutstanding;
        bVal = b.totalOutstanding;
        break;
      case "nextDueDate":
        aVal = a.nextDueDate ?? "";
        bVal = b.nextDueDate ?? "";
        break;
      case "overdueAmount":
        aVal = a.overdueAmount;
        bVal = b.overdueAmount;
        break;
      case "collectionPercent":
        aVal = a.collectionPercent;
        bVal = b.collectionPercent;
        break;
      default:
        aVal = "";
        bVal = "";
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
        sortField === field
          ? sortDir === "asc"
            ? "ascending"
            : "descending"
          : "none"
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

  if (items.length === 0) {
    return (
      <div className={styles.emptyState}>
        <p className={styles.emptyStateTitle}>No payment plans found</p>
        <p className={styles.emptyStateBody}>
          Try adjusting the filters or select a different project.
        </p>
      </div>
    );
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table} aria-label="Payment plans">
        <thead className={styles.tableHead}>
          <tr>
            <SortHeader field="contractNumber">Contract</SortHeader>
            <SortHeader field="unitNumber">Unit</SortHeader>
            <th scope="col">Contract Status</th>
            <SortHeader field="contractPrice">Contract Value</SortHeader>
            <SortHeader field="totalCollected">Collected</SortHeader>
            <SortHeader field="totalOutstanding">Outstanding</SortHeader>
            <SortHeader field="nextDueDate">Next Due</SortHeader>
            <SortHeader field="overdueAmount">Overdue</SortHeader>
            <SortHeader field="collectionPercent">Progress</SortHeader>
            <th scope="col" aria-label="Actions" />
          </tr>
        </thead>
        <tbody className={styles.tableBody}>
          {sorted.map((item) => {
            // Clamp collection percent to [0, 100] for progress bar, ARIA,
            // and label so they remain consistent when over-collected.
            const displayPercent = Math.min(
              100,
              Math.max(0, Math.round(item.collectionPercent)),
            );
            return (
            <tr key={item.contractId}>
              <td>
                <Link
                  href={`/payment-plans/${item.contractId}`}
                  className={styles.contractLink}
                  aria-label={`View payment plan for contract ${item.contractNumber}`}
                >
                  {item.contractNumber}
                </Link>
              </td>
              <td>{item.unitNumber}</td>
              <td>
                <span
                  className={`${styles.contractStatusBadge} ${contractStatusClass(item.contractStatus)}`}
                >
                  {contractStatusLabel(item.contractStatus)}
                </span>
              </td>
              <td>{formatCurrency(item.contractPrice)}</td>
              <td>{formatCurrency(item.totalCollected)}</td>
              <td>{formatCurrency(item.totalOutstanding)}</td>
              <td>
                {item.nextDueDate ? (
                  item.nextDueDate
                ) : (
                  <span aria-label="No upcoming due date">—</span>
                )}
              </td>
              <td>
                {item.overdueAmount > 0 ? (
                  <span className={styles.overdueAmount}>
                    {formatCurrency(item.overdueAmount)}
                    {item.overdueCount > 1 && ` (${item.overdueCount})`}
                  </span>
                ) : (
                  <span aria-label="No overdue amount">—</span>
                )}
              </td>
              <td>
                <div className={styles.progressBarWrapper}>
                  <div
                    className={styles.progressBar}
                    role="progressbar"
                    aria-valuenow={displayPercent}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`Collection progress: ${displayPercent}%`}
                  >
                    <div
                      className={styles.progressFill}
                      style={{
                        width: `${displayPercent}%`,
                      }}
                    />
                  </div>
                  <span className={styles.progressLabel}>
                    {displayPercent}%
                  </span>
                </div>
              </td>
              <td>
                <Link
                  href={`/payment-plans/${item.contractId}`}
                  className={styles.actionBtn}
                  aria-label={`Open payment plan detail for contract ${item.contractNumber}`}
                >
                  View
                </Link>
              </td>
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
