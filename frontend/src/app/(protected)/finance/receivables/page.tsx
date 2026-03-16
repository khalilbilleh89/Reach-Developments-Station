"use client";

import React, { useEffect, useState, useCallback } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { listProjectReceivables } from "@/lib/receivables-api";
import { receivableStatusLabel } from "@/lib/receivables-types";
import type { Receivable, ReceivableListResponse } from "@/lib/receivables-types";
import { getProjects } from "@/lib/finance-dashboard-api";
import type { Project } from "@/lib/finance-dashboard-api";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/payment-plans.module.css";
import finStyles from "@/styles/finance-dashboard.module.css";

/**
 * Finance Receivables page — project-scoped receivables browsing.
 *
 * Provides:
 *   - Project selector
 *   - Status filter
 *   - Due-date sorting
 *   - Receivables table with balance and status
 *
 * All data is sourced from the backend API. No financial calculations are
 * performed on the frontend.
 */
export default function FinanceReceivablesPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState<string | null>(null);

  const [receivables, setReceivables] = useState<Receivable[]>([]);
  const [summary, setSummary] = useState<Omit<ReceivableListResponse, "items"> | null>(null);
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<string>("");

  // Load project list on mount
  useEffect(() => {
    setProjectsLoading(true);
    setProjectsError(null);
    getProjects()
      .then((list) => {
        setProjects(list);
        if (list.length > 0) setSelectedProject(list[0]);
      })
      .catch((err: unknown) => {
        setProjectsError(
          err instanceof Error ? err.message : "Failed to load projects.",
        );
      })
      .finally(() => setProjectsLoading(false));
  }, []);

  // Load receivables whenever selected project changes
  const loadReceivables = useCallback(async (projectId: string) => {
    setDataLoading(true);
    setDataError(null);
    setReceivables([]);
    setSummary(null);
    try {
      const data = await listProjectReceivables(projectId);
      setReceivables(data.items);
      setSummary({
        total: data.total,
        total_amount_due: data.total_amount_due,
        total_amount_paid: data.total_amount_paid,
        total_balance_due: data.total_balance_due,
      });
    } catch (err: unknown) {
      setDataError(
        err instanceof Error ? err.message : "Failed to load receivables.",
      );
    } finally {
      setDataLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedProject) return;
    loadReceivables(selectedProject.id);
  }, [selectedProject, loadReceivables]);

  const handleProjectChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const project = projects.find((p) => p.id === e.target.value);
      if (project) setSelectedProject(project);
    },
    [projects],
  );

  // Client-side status filter
  const filtered = statusFilter
    ? receivables.filter((r) => r.status === statusFilter)
    : receivables;

  function statusClass(status: string): string {
    switch (status) {
      case "paid":
        return styles.statusPaid;
      case "partially_paid":
        return styles.statusPartiallyPaid;
      case "overdue":
        return styles.statusOverdue;
      case "due":
        return styles.statusDue;
      case "cancelled":
        return styles.statusCancelled;
      case "pending":
      default:
        return styles.statusPending;
    }
  }

  return (
    <PageContainer
      title="Receivables"
      subtitle="Project-level receivables ledger — outstanding and collected obligations."
    >
      {/* Project selector */}
      <div className={styles.selectorRow}>
        <label htmlFor="rcv-project-selector" className={styles.selectorLabel}>
          Project
        </label>
        {projectsLoading ? (
          <span className={finStyles.emptyMessage}>Loading projects…</span>
        ) : projectsError ? (
          <span className={finStyles.emptyMessage}>{projectsError}</span>
        ) : projects.length === 0 ? (
          <span className={finStyles.emptyMessage}>No projects found.</span>
        ) : (
          <select
            id="rcv-project-selector"
            className={styles.selectorSelect}
            value={selectedProject?.id ?? ""}
            onChange={handleProjectChange}
            aria-label="Select project"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Status filter */}
      {!dataLoading && receivables.length > 0 && (
        <div className={styles.selectorRow}>
          <label htmlFor="rcv-status-filter" className={styles.selectorLabel}>
            Status
          </label>
          <select
            id="rcv-status-filter"
            className={styles.selectorSelect}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="Filter by status"
          >
            <option value="">All statuses</option>
            <option value="pending">Upcoming</option>
            <option value="due">Due</option>
            <option value="overdue">Overdue</option>
            <option value="partially_paid">Partially Paid</option>
            <option value="paid">Paid</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
      )}

      {/* Summary totals */}
      {summary && !dataLoading && (
        <div className={styles.sectionMeta}>
          <span>
            <strong>Total Due:</strong> {formatCurrency(summary.total_amount_due)}
          </span>
          {" · "}
          <span>
            <strong>Paid:</strong> {formatCurrency(summary.total_amount_paid)}
          </span>
          {" · "}
          <span>
            <strong>Balance:</strong> {formatCurrency(summary.total_balance_due)}
          </span>
          {" · "}
          <span>
            <strong>Records:</strong> {summary.total}
          </span>
        </div>
      )}

      {/* Loading / error states */}
      {dataLoading && (
        <div className={styles.loadingState}>Loading receivables…</div>
      )}
      {!dataLoading && dataError && (
        <div className={styles.errorState}>{dataError}</div>
      )}

      {/* Empty state */}
      {!dataLoading && !dataError && receivables.length === 0 && selectedProject && (
        <div className={styles.emptyState}>
          <p className={styles.emptyStateTitle}>No receivables</p>
          <p className={styles.emptyStateBody}>
            No receivables have been generated for contracts in this project yet.
            Generate receivables from each contract&apos;s detail view.
          </p>
        </div>
      )}

      {/* Receivables table */}
      {!dataLoading && !dataError && filtered.length > 0 && (
        <div className={styles.tableWrapper}>
          <table className={styles.table} aria-label="Project receivables">
            <thead className={styles.tableHead}>
              <tr>
                <th scope="col">#</th>
                <th scope="col">Contract</th>
                <th scope="col">Due Date</th>
                <th scope="col">Amount Due</th>
                <th scope="col">Amount Paid</th>
                <th scope="col">Balance</th>
                <th scope="col">Currency</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody className={styles.tableBody}>
              {filtered.map((row) => (
                <tr key={row.id}>
                  <td>{row.receivable_number}</td>
                  <td>{row.contract_id}</td>
                  <td>{String(row.due_date)}</td>
                  <td>{formatCurrency(row.amount_due)}</td>
                  <td>{formatCurrency(row.amount_paid)}</td>
                  <td>{formatCurrency(row.balance_due)}</td>
                  <td>{row.currency}</td>
                  <td>
                    <span
                      className={`${styles.statusBadge} ${statusClass(row.status)}`}
                    >
                      {receivableStatusLabel(row.status)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* No results after filter */}
      {!dataLoading && !dataError && receivables.length > 0 && filtered.length === 0 && (
        <div className={styles.emptyState}>
          <p className={styles.emptyStateBody}>
            No receivables match the selected status filter.
          </p>
        </div>
      )}
    </PageContainer>
  );
}
