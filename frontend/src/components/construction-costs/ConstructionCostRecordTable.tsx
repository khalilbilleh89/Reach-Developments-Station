/**
 * ConstructionCostRecordTable — tabular list of construction cost records.
 *
 * Renders all records for a project with columns for title, category, source,
 * stage, amount, currency, effective date, reference number, status, and
 * row-level actions (edit / archive).
 */

"use client";

import React from "react";
import type { ConstructionCostRecord } from "@/lib/construction-cost-types";
import {
  COST_CATEGORY_LABELS,
  COST_SOURCE_LABELS,
  COST_STAGE_LABELS,
} from "@/lib/construction-cost-types";
import styles from "@/styles/construction.module.css";

interface ConstructionCostRecordTableProps {
  records: ConstructionCostRecord[];
  onEdit: (record: ConstructionCostRecord) => void;
  onArchive: (record: ConstructionCostRecord) => void;
  archivingId: string | null;
}

function fmt(amount: string | number): string {
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  if (isNaN(num)) return String(amount);
  return num.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function ConstructionCostRecordTable({
  records,
  onEdit,
  onArchive,
  archivingId,
}: ConstructionCostRecordTableProps) {
  if (records.length === 0) {
    return (
      <div className={styles.emptyState} data-testid="records-empty-state">
        <p className={styles.emptyStateTitle}>No cost records yet.</p>
        <p className={styles.emptyStateBody}>
          Add a construction cost record to get started.
        </p>
      </div>
    );
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table} aria-label="Construction cost records">
        <thead>
          <tr>
            <th scope="col">Title</th>
            <th scope="col">Category</th>
            <th scope="col">Source</th>
            <th scope="col">Stage</th>
            <th scope="col">Amount</th>
            <th scope="col">Currency</th>
            <th scope="col">Effective Date</th>
            <th scope="col">Reference</th>
            <th scope="col">Status</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {records.map((record) => (
            <tr
              key={record.id}
              data-testid={`cost-record-row-${record.id}`}
              className={record.is_active ? undefined : styles.archivedRow}
            >
              <td>{record.title}</td>
              <td>
                {COST_CATEGORY_LABELS[record.cost_category] ?? record.cost_category}
              </td>
              <td>{COST_SOURCE_LABELS[record.cost_source] ?? record.cost_source}</td>
              <td>{COST_STAGE_LABELS[record.cost_stage] ?? record.cost_stage}</td>
              <td className={styles.amountCell}>{fmt(record.amount)}</td>
              <td>{record.currency}</td>
              <td>{record.effective_date ?? "—"}</td>
              <td>{record.reference_number ?? "—"}</td>
              <td>
                <span
                  className={
                    record.is_active ? styles.badgeActive : styles.badgeArchived
                  }
                >
                  {record.is_active ? "Active" : "Archived"}
                </span>
              </td>
              <td>
                <div className={styles.rowActions}>
                  <button
                    className={styles.actionButton}
                    onClick={() => onEdit(record)}
                    aria-label={`Edit ${record.title}`}
                  >
                    Edit
                  </button>
                  {record.is_active && (
                    <button
                      className={styles.actionButtonDanger}
                      onClick={() => onArchive(record)}
                      disabled={archivingId === record.id}
                      aria-label={`Archive ${record.title}`}
                    >
                      {archivingId === record.id ? "Archiving…" : "Archive"}
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
