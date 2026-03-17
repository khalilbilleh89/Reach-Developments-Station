"use client";

import React, { useState } from "react";
import type { SalesCandidate } from "@/lib/sales-types";
import { readinessLabel, contractStatusLabel } from "@/lib/sales-types";
import { unitStatusLabel, unitTypeLabel } from "@/lib/units-types";
import { formatAmount } from "@/lib/format-utils";
import styles from "@/styles/sales-workflow.module.css";

type SortField =
  | "unit_number"
  | "unit_type"
  | "status"
  | "final_unit_price"
  | "readiness"
  | "contract_status";
type SortDir = "asc" | "desc";

interface SalesCandidatesTableProps {
  candidates: SalesCandidate[];
  onSelectUnit: (unitId: string) => void;
}

/** Map a backend UnitStatus to its CSS module class. */
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

/** Map a readiness value to its CSS module class. */
function readinessClass(readiness: string): string {
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
 * SalesCandidatesTable — sortable, linked table of sales candidates.
 *
 * Displays unit, pricing, exception, contract status, and readiness.
 * Each row links to the guided unit-level sales workflow page.
 *
 * All financial values come from the backend pricing engine via props.
 * No calculations are performed here.
 */
export function SalesCandidatesTable({
  candidates,
  onSelectUnit,
}: SalesCandidatesTableProps) {
  const [sortField, setSortField] = useState<SortField>("unit_number");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const handleSort = (field: SortField) => {
    if (field === sortField) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  };

  const sorted = [...candidates].sort((a, b) => {
    let aVal: string | number;
    let bVal: string | number;

    switch (sortField) {
      case "final_unit_price":
        aVal = a.pricing?.final_unit_price ?? -1;
        bVal = b.pricing?.final_unit_price ?? -1;
        break;
      case "readiness":
        aVal = a.readiness;
        bVal = b.readiness;
        break;
      case "contract_status":
        aVal = a.contractStatus ?? "";
        bVal = b.contractStatus ?? "";
        break;
      default:
        aVal = (a.unit[sortField as keyof typeof a.unit] as string) ?? "";
        bVal = (b.unit[sortField as keyof typeof b.unit] as string) ?? "";
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

  if (candidates.length === 0) {
    return (
      <div className={styles.emptyState}>
        <p className={styles.emptyStateTitle}>No units found</p>
        <p className={styles.emptyStateBody}>
          Try adjusting the filters or select a different project.
        </p>
      </div>
    );
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table} aria-label="Sales candidates">
        <thead className={styles.tableHead}>
          <tr>
            <SortHeader field="unit_number">Unit</SortHeader>
            <SortHeader field="unit_type">Type</SortHeader>
            <SortHeader field="status">Status</SortHeader>
            <SortHeader field="final_unit_price">Price</SortHeader>
            <th scope="col">Approved Exception?</th>
            <SortHeader field="contract_status">Contract</SortHeader>
            <SortHeader field="readiness">Readiness</SortHeader>
            <th scope="col" aria-label="Actions" />
          </tr>
        </thead>
        <tbody className={styles.tableBody}>
          {sorted.map((candidate) => {
            const { unit, pricing, hasApprovedException, contractStatus, readiness } =
              candidate;
            return (
              <tr key={unit.id}>
                <td>
                  <span className={styles.unitNumber}>{unit.unit_number}</span>
                </td>
                <td>{unitTypeLabel(unit.unit_type)}</td>
                <td>
                  <span
                    className={`${styles.statusBadge} ${statusClass(unit.status)}`}
                  >
                    {unitStatusLabel(unit.status)}
                  </span>
                </td>
                <td>
                  {pricing ? (
                    formatAmount(pricing.final_unit_price, pricing.currency)
                  ) : (
                    <span aria-label="Not priced">—</span>
                  )}
                </td>
                <td>
                  {hasApprovedException ? (
                    <span className={`${styles.exceptionBadge} ${styles.exceptionYes}`}>
                      Yes
                    </span>
                  ) : (
                    <span className={`${styles.exceptionBadge} ${styles.exceptionNo}`}>
                      No
                    </span>
                  )}
                </td>
                <td>
                  {contractStatus ? (
                    contractStatusLabel(contractStatus)
                  ) : (
                    <span aria-label="No contract">—</span>
                  )}
                </td>
                <td>
                  <span className={`${styles.readinessBadge} ${readinessClass(readiness)}`}>
                    {readinessLabel(readiness)}
                  </span>
                </td>
                <td>
                  <button
                    type="button"
                    className={styles.actionBtn}
                    onClick={() => onSelectUnit(unit.id)}
                    aria-label={`Open sales workflow for unit ${unit.unit_number}`}
                  >
                    Open
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
