"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { listProjects } from "@/lib/projects-api";
import type { Project } from "@/lib/projects-types";
import {
  listProjectCommissionPayouts,
  getProjectCommissionSummary,
} from "@/lib/commission-api";
import type {
  CommissionPayoutListItem,
  CommissionPayoutStatus,
  CommissionSummary,
} from "@/lib/commission-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/demo-shell.module.css";

/**
 * Commission — live data dashboard.
 *
 * Fetches commission payouts and summary from the backend commission API.
 * No demo data is used.
 */
export default function Page() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState<string | null>(null);

  const [summary, setSummary] = useState<CommissionSummary | null>(null);
  const [payouts, setPayouts] = useState<CommissionPayoutListItem[]>([]);
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState<string | null>(null);

  // Request counter: guards against stale async responses overwriting state
  // when the user switches projects before the previous fetch completes.
  const requestIdRef = useRef(0);

  // Load project list on mount
  useEffect(() => {
    setProjectsLoading(true);
    setProjectsError(null);
    listProjects({ limit: 100 })
      .then((res) => {
        setProjects(res.items);
        if (res.items.length > 0) {
          setSelectedProject(res.items[0]);
        }
      })
      .catch((err: unknown) => {
        setProjectsError(
          err instanceof Error ? err.message : "Failed to load projects",
        );
      })
      .finally(() => setProjectsLoading(false));
  }, []);

  // Fetch commission data when project changes
  const loadCommissionData = useCallback((projectId: string) => {
    // Increment and capture this request's ID before starting async work.
    const thisRequestId = ++requestIdRef.current;

    setDataLoading(true);
    setDataError(null);
    setSummary(null);
    setPayouts([]);
    Promise.all([
      getProjectCommissionSummary(projectId),
      listProjectCommissionPayouts(projectId, { limit: 200 }),
    ])
      .then(([summaryData, payoutData]) => {
        // Discard the result if a newer request has already been issued.
        if (thisRequestId !== requestIdRef.current) return;
        setSummary(summaryData);
        setPayouts(payoutData.items);
      })
      .catch((err: unknown) => {
        if (thisRequestId !== requestIdRef.current) return;
        setDataError(
          err instanceof Error ? err.message : "Failed to load commission data",
        );
      })
      .finally(() => {
        if (thisRequestId !== requestIdRef.current) return;
        setDataLoading(false);
      });
  }, []);

  useEffect(() => {
    if (selectedProject) {
      loadCommissionData(selectedProject.id);
    }
  }, [selectedProject, loadCommissionData]);

  function statusBadgeClass(status: CommissionPayoutStatus): string {
    switch (status) {
      case "approved":
        return styles.badgeBlue;
      case "calculated":
        return styles.badgeGreen;
      case "draft":
        return styles.badgeYellow;
      case "cancelled":
        return styles.badgeRed;
      default:
        return styles.badgeGray;
    }
  }

  function statusLabel(status: CommissionPayoutStatus): string {
    switch (status) {
      case "approved":
        return "Approved";
      case "calculated":
        return "Calculated";
      case "draft":
        return "Draft";
      case "cancelled":
        return "Cancelled";
      default:
        return status;
    }
  }

  // Count of pending payouts (draft + calculated), not a monetary amount.
  const pendingCount =
    summary !== null
      ? summary.draft_payouts + summary.calculated_payouts
      : null;

  function recordCountLabel(total: number, visible: number): string {
    if (visible < total) {
      return `Showing ${visible} of ${total} record${total !== 1 ? "s" : ""}`;
    }
    return `${total} record${total !== 1 ? "s" : ""}`;
  }

  return (
    <PageContainer
      title="Commission"
      subtitle="Commission plans, slabs, and payout tracking."
    >
      {/* Project selector */}
      {projectsLoading && (
        <p className={styles.sectionNote}>Loading projects…</p>
      )}
      {projectsError && (
        <p className={styles.sectionNote} style={{ color: "var(--color-danger)" }}>
          {projectsError}
        </p>
      )}
      {!projectsLoading && !projectsError && projects.length === 0 && (
        <p className={styles.sectionNote}>No projects found.</p>
      )}
      {!projectsLoading && projects.length > 0 && (
        <div className={styles.sectionHeader}>
          <label htmlFor="project-select" className={styles.sectionTitle}>
            Project
          </label>
          <select
            id="project-select"
            value={selectedProject?.id ?? ""}
            onChange={(e) => {
              const project = projects.find((p) => p.id === e.target.value);
              setSelectedProject(project ?? null);
            }}
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* KPI summary */}
      <div className={styles.kpiGrid}>
        <MetricCard
          title="Total Commission Pool"
          value={
            summary !== null
              ? formatCurrency(summary.total_commission_pool)
              : "—"
          }
          subtitle={
            summary !== null
              ? `${summary.total_payouts} payout record${summary.total_payouts !== 1 ? "s" : ""}`
              : "Select a project"
          }
          icon="💰"
        />
        <MetricCard
          title="Approved"
          value={summary !== null ? String(summary.approved_payouts) : "—"}
          subtitle="Approved payouts"
          icon="✅"
        />
        <MetricCard
          title="Pending"
          value={pendingCount !== null ? String(pendingCount) : "—"}
          subtitle="Draft + calculated payouts"
          icon="⏳"
        />
        <MetricCard
          title="Total Gross Value"
          value={
            summary !== null
              ? formatCurrency(summary.total_gross_value)
              : "—"
          }
          subtitle="Sum of all contract values"
          icon="📊"
        />
      </div>

      {/* Payout table */}
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Commission Payout Queue</h2>
        <span className={styles.sectionNote}>
          {dataLoading
            ? "Loading…"
            : summary !== null
              ? recordCountLabel(summary.total_payouts, payouts.length)
              : ""}
        </span>
      </div>

      {dataError && (
        <p className={styles.sectionNote} style={{ color: "var(--color-danger)" }}>
          {dataError}
        </p>
      )}

      {!dataLoading && !dataError && payouts.length === 0 && selectedProject && (
        <p className={styles.sectionNote}>
          No commission payouts found for {selectedProject.name}.
        </p>
      )}

      {payouts.length > 0 && (
        <div className={styles.tableWrapper}>
          <table className={styles.table} aria-label="Commission payout queue">
            <thead>
              <tr>
                <th scope="col">ID</th>
                <th scope="col">Contract ID</th>
                <th scope="col">Plan ID</th>
                <th scope="col">Gross Sale Value</th>
                <th scope="col">Commission Pool</th>
                <th scope="col">Mode</th>
                <th scope="col">Status</th>
                <th scope="col">Calculated At</th>
              </tr>
            </thead>
            <tbody>
              {payouts.map((payout) => (
                <tr key={payout.id}>
                  <td
                    style={{
                      fontFamily: "monospace",
                      fontSize: "var(--font-size-xs)",
                    }}
                  >
                    {payout.id}
                  </td>
                  <td
                    style={{
                      fontFamily: "monospace",
                      fontSize: "var(--font-size-xs)",
                    }}
                  >
                    {payout.sale_contract_id}
                  </td>
                  <td
                    style={{
                      fontFamily: "monospace",
                      fontSize: "var(--font-size-xs)",
                    }}
                  >
                    {payout.commission_plan_id}
                  </td>
                  <td>{formatCurrency(payout.gross_sale_value)}</td>
                  <td style={{ fontWeight: "var(--font-weight-semibold)" }}>
                    {formatCurrency(payout.commission_pool_value)}
                  </td>
                  <td>{payout.calculation_mode}</td>
                  <td>
                    <span
                      className={`${styles.badge} ${statusBadgeClass(payout.status)}`}
                    >
                      {statusLabel(payout.status)}
                    </span>
                  </td>
                  <td>
                    {payout.calculated_at
                      ? new Date(payout.calculated_at).toLocaleDateString(
                          "en-GB",
                        )
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PageContainer>
  );
}
