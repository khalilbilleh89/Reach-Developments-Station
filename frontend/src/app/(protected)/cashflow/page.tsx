"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { listProjects } from "@/lib/projects-api";
import type { Project } from "@/lib/projects-types";
import {
  getProjectCashflowSummary,
  listCashflowForecastPeriods,
} from "@/lib/cashflow-api";
import type {
  CashflowSummary,
  CashflowForecastPeriod,
} from "@/lib/cashflow-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/demo-shell.module.css";

/**
 * Cashflow — live data dashboard.
 *
 * Fetches cashflow summary and forecast periods from the backend cashflow API.
 * No demo data is used.
 */
export default function Page() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState<string | null>(null);

  const [summary, setSummary] = useState<CashflowSummary | null>(null);
  const [periods, setPeriods] = useState<CashflowForecastPeriod[]>([]);
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

  // Fetch cashflow data when project changes
  const loadCashflowData = useCallback((projectId: string) => {
    // Increment and capture this request's ID before starting async work.
    const thisRequestId = ++requestIdRef.current;

    setDataLoading(true);
    setDataError(null);
    setSummary(null);
    setPeriods([]);

    getProjectCashflowSummary(projectId)
      .then(async (summaryData) => {
        if (thisRequestId !== requestIdRef.current) return;
        setSummary(summaryData);

        // If a latest forecast exists, load its periods
        if (summaryData.latest_forecast_id) {
          const periodsData = await listCashflowForecastPeriods(
            summaryData.latest_forecast_id,
          );
          if (thisRequestId !== requestIdRef.current) return;
          setPeriods(periodsData);
        }
      })
      .catch((err: unknown) => {
        if (thisRequestId !== requestIdRef.current) return;
        setDataError(
          err instanceof Error ? err.message : "Failed to load cashflow data",
        );
      })
      .finally(() => {
        if (thisRequestId !== requestIdRef.current) return;
        setDataLoading(false);
      });
  }, []);

  useEffect(() => {
    if (selectedProject) {
      loadCashflowData(selectedProject.id);
    }
  }, [selectedProject, loadCashflowData]);

  function periodLabel(period: CashflowForecastPeriod): string {
    const [yearStr, monthStr, dayStr] = period.period_start.split("-");
    const year = Number(yearStr);
    const monthIndex = Number(monthStr) - 1; // 0-based month index
    const day = Number(dayStr);
    const startUtc = new Date(Date.UTC(year, monthIndex, day));
    return new Intl.DateTimeFormat("en-GB", {
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    }).format(startUtc);
  }

  function netBadgeClass(net: number): string {
    if (net > 0) return styles.badgeGreen;
    if (net < 0) return styles.badgeRed;
    return styles.badgeGray;
  }

  function netTrendClass(net: number): string {
    if (net > 0) return styles.trendPositive;
    if (net < 0) return styles.trendNegative;
    return "";
  }

  function netLabel(net: number): string {
    if (net > 0) return "Surplus";
    if (net < 0) return "Shortfall";
    return "Neutral";
  }

  function recordCountLabel(count: number): string {
    return `${count} period${count !== 1 ? "s" : ""}`;
  }

  const showNoForecastsMessage =
    !dataLoading && !dataError && summary !== null && summary.total_forecasts === 0;
  const showNoPeriodsMessage =
    !dataLoading &&
    !dataError &&
    summary !== null &&
    summary.total_forecasts > 0 &&
    periods.length === 0;

  return (
    <PageContainer
      title="Cashflow"
      subtitle="Cashflow forecasting and period analysis."
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
          title="Total Expected Inflows"
          value={
            summary !== null
              ? formatCurrency(summary.total_expected_inflows)
              : "—"
          }
          subtitle={
            summary !== null
              ? `${summary.total_forecasts} forecast${summary.total_forecasts !== 1 ? "s" : ""}`
              : "Select a project"
          }
          icon="📈"
        />
        <MetricCard
          title="Total Expected Outflows"
          value={
            summary !== null
              ? formatCurrency(summary.total_expected_outflows)
              : "—"
          }
          subtitle="Scheduled outflows across all periods"
          icon="📉"
        />
        <MetricCard
          title="Net Cashflow"
          value={
            summary !== null ? formatCurrency(summary.total_net_cashflow) : "—"
          }
          subtitle="Inflows minus outflows"
          icon="💵"
          trend={
            summary !== null
              ? {
                  label:
                    summary.total_net_cashflow >= 0 ? "Positive" : "Negative",
                  direction: summary.total_net_cashflow >= 0 ? "up" : "down",
                }
              : undefined
          }
        />
        <MetricCard
          title="Closing Balance"
          value={
            summary !== null ? formatCurrency(summary.closing_balance) : "—"
          }
          subtitle={
            summary?.latest_forecast_name
              ? `Latest: ${summary.latest_forecast_name}`
              : "Latest forecast closing balance"
          }
          icon="🔒"
        />
      </div>

      {/* Forecast periods table */}
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Forecast Periods</h2>
        <span className={styles.sectionNote}>
          {dataLoading
            ? "Loading…"
            : summary !== null
              ? recordCountLabel(periods.length)
              : ""}
        </span>
      </div>

      {dataError && (
        <p className={styles.sectionNote} style={{ color: "var(--color-danger)" }}>
          {dataError}
        </p>
      )}

      {showNoForecastsMessage && (
        <p className={styles.sectionNote}>
          No cashflow forecasts found for{" "}
          {selectedProject?.name ?? "this project"}.
        </p>
      )}

      {showNoPeriodsMessage && (
        <p className={styles.sectionNote}>No forecast periods available.</p>
      )}

      {periods.length > 0 && (
        <div className={styles.tableWrapper}>
          <table className={styles.table} aria-label="Forecast periods">
            <thead>
              <tr>
                <th scope="col">Period</th>
                <th scope="col">Expected Inflows</th>
                <th scope="col">Actual Inflows</th>
                <th scope="col">Expected Outflows</th>
                <th scope="col">Net Cashflow</th>
                <th scope="col">Closing Balance</th>
                <th scope="col">Net Position</th>
              </tr>
            </thead>
            <tbody>
              {periods.map((period) => (
                <tr key={period.id}>
                  <td style={{ fontWeight: "var(--font-weight-medium)" }}>
                    {periodLabel(period)}
                  </td>
                  <td>{formatCurrency(period.expected_inflows)}</td>
                  <td>{formatCurrency(period.actual_inflows)}</td>
                  <td>{formatCurrency(period.expected_outflows)}</td>
                  <td className={netTrendClass(period.net_cashflow)}>
                    {formatCurrency(period.net_cashflow)}
                  </td>
                  <td>{formatCurrency(period.closing_balance)}</td>
                  <td>
                    <span
                      className={`${styles.badge} ${netBadgeClass(period.net_cashflow)}`}
                    >
                      {netLabel(period.net_cashflow)}
                    </span>
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

