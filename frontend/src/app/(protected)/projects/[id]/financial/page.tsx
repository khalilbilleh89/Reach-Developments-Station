"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import { getProjectFinancialDashboard } from "@/lib/finance-api";
import type { ProjectFinancialDashboard, ProjectFinancialTrendEntry } from "@/lib/finance-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/finance-dashboard.module.css";

/**
 * Project Financial Dashboard.
 *
 * Displays project-level financial KPIs and trend tables for revenue,
 * collections, and receivables — composed from the finance engines and
 * analytics fact tables.
 *
 * Data source:
 *   GET /finance/projects/{projectId}/dashboard
 *
 * No financial calculations are performed on this page — all values are
 * sourced directly from the backend project financial dashboard service.
 */

export function generateStaticParams() {
  return [{ id: "_" }];
}

export const dynamicParams = false;

export default function ProjectFinancialDashboardPage() {
  const params = useParams<{ id: string }>();
  const projectId = params?.id ?? "";

  const [dashboard, setDashboard] = useState<ProjectFinancialDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId || projectId === "_") return;

    setLoading(true);
    setError(null);
    getProjectFinancialDashboard(projectId)
      .then(setDashboard)
      .catch((err: unknown) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load project financial dashboard.",
        );
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  const healthLabel = (dashboard: ProjectFinancialDashboard): string => {
    const { overduePercentage, collectionEfficiency } = dashboard.kpis;
    if (overduePercentage > 30 || collectionEfficiency < 0.5) return "critical";
    if (overduePercentage > 10 || collectionEfficiency < 0.75) return "watch";
    return "healthy";
  };

  const healthBadgeClass = (status: string): string => {
    if (status === "critical") return styles.badgeCritical;
    if (status === "watch") return styles.badgeWatch;
    return styles.badgeHealthy;
  };

  return (
    <PageContainer
      title="Project Financial Dashboard"
      subtitle="Project-level financial KPIs and trends from the finance engines and analytics fact layer."
    >
      {loading && <p>Loading project financial data…</p>}
      {error && <p className={styles.errorText}>{error}</p>}

      {dashboard && (
        <>
          {/* KPI Cards */}
          <div className={styles.kpiGrid}>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Recognized Revenue</div>
              <div className={styles.kpiValue}>
                {formatCurrency(dashboard.kpis.recognizedRevenue)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Deferred Revenue</div>
              <div className={styles.kpiValue}>
                {formatCurrency(dashboard.kpis.deferredRevenue)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Receivables Exposure</div>
              <div className={styles.kpiValue}>
                {formatCurrency(dashboard.kpis.receivablesExposure)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Overdue Receivables</div>
              <div className={styles.kpiValue}>
                {formatCurrency(dashboard.kpis.overdueReceivables)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Overdue %</div>
              <div className={styles.kpiValue}>
                {dashboard.kpis.overduePercentage.toFixed(2)}%
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Forecast Next Month</div>
              <div className={styles.kpiValue}>
                {formatCurrency(dashboard.kpis.forecastNextMonth)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Collection Efficiency</div>
              <div className={styles.kpiValue}>
                {(dashboard.kpis.collectionEfficiency * 100).toFixed(2)}%
              </div>
            </div>
          </div>

          {/* Revenue Trend */}
          {dashboard.revenueTrend.length > 0 ? (
            <>
              <h3 className={styles.sectionHeading}>Revenue Trend</h3>
              <table
                className={styles.dataTable ?? undefined}
                aria-label="Revenue trend table"
              >
                <thead>
                  <tr>
                    <th scope="col">Month</th>
                    <th scope="col">Recognized Revenue</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.revenueTrend.map((entry: ProjectFinancialTrendEntry) => (
                    <tr key={entry.period}>
                      <td>{entry.period}</td>
                      <td>{formatCurrency(entry.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <p>No revenue trend data available. Run the analytics rebuild to populate fact tables.</p>
          )}

          {/* Collections Trend */}
          {dashboard.collectionsTrend.length > 0 ? (
            <>
              <h3 className={styles.sectionHeading}>Collections Trend</h3>
              <table
                className={styles.dataTable ?? undefined}
                aria-label="Collections trend table"
              >
                <thead>
                  <tr>
                    <th scope="col">Month</th>
                    <th scope="col">Collections Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.collectionsTrend.map(
                    (entry: ProjectFinancialTrendEntry) => (
                      <tr key={entry.period}>
                        <td>{entry.period}</td>
                        <td>{formatCurrency(entry.value)}</td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </>
          ) : (
            <p>No collections trend data available. Run the analytics rebuild to populate fact tables.</p>
          )}

          {/* Receivables Trend */}
          {dashboard.receivablesTrend.length > 0 ? (
            <>
              <h3 className={styles.sectionHeading}>Receivables Trend</h3>
              <table
                className={styles.dataTable ?? undefined}
                aria-label="Receivables trend table"
              >
                <thead>
                  <tr>
                    <th scope="col">Snapshot Date</th>
                    <th scope="col">Total Receivables</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.receivablesTrend.map(
                    (entry: ProjectFinancialTrendEntry) => (
                      <tr key={entry.period}>
                        <td>{entry.period}</td>
                        <td>{formatCurrency(entry.value)}</td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </>
          ) : (
            <p>No receivables trend data available. Run the analytics rebuild to populate fact tables.</p>
          )}

          {/* Project Health Summary */}
          {(() => {
            const status = healthLabel(dashboard);
            return (
              <div className={styles.healthSummaryCard}>
                <h3 className={styles.sectionTitle}>Project Health Summary</h3>
                <div className={styles.healthBadgesRow}>
                  <span
                    className={`${styles.healthBadge} ${healthBadgeClass(status)}`}
                    aria-label={`Project health status: ${status}`}
                  >
                    {status === "healthy" && "✅ Healthy"}
                    {status === "watch" && "⚠️ Watch"}
                    {status === "critical" && "🔴 Critical"}
                  </span>
                  <span className={styles.healthBadge}>
                    Overdue: {dashboard.kpis.overduePercentage.toFixed(1)}%
                  </span>
                  <span className={styles.healthBadge}>
                    Collection Efficiency:{" "}
                    {(dashboard.kpis.collectionEfficiency * 100).toFixed(1)}%
                  </span>
                  <span className={styles.healthBadge}>
                    Next Month Forecast:{" "}
                    {formatCurrency(dashboard.kpis.forecastNextMonth)}
                  </span>
                </div>
              </div>
            );
          })()}
        </>
      )}
    </PageContainer>
  );
}
