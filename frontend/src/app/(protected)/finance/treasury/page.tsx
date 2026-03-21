"use client";

import React, { useEffect, useState } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { getTreasuryMonitoring } from "@/lib/finance-api";
import type {
  ProjectExposure,
  TreasuryMonitoring,
} from "@/lib/finance-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/finance-dashboard.module.css";

/**
 * Treasury Monitoring Dashboard.
 *
 * Displays portfolio-level treasury KPIs and a project exposure ranking
 * table derived from the aggregated financial engines.
 *
 * Data source:
 *   GET /finance/treasury/monitoring
 *
 * No financial calculations are performed on this page — all values are
 * sourced directly from the backend treasury monitoring service.
 */
export default function FinanceTreasuryPage() {
  const [monitoring, setMonitoring] = useState<TreasuryMonitoring | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getTreasuryMonitoring()
      .then(setMonitoring)
      .catch((err: unknown) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load treasury monitoring data.",
        );
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <PageContainer
      title="Treasury Monitoring"
      subtitle="Portfolio liquidity and receivable exposure overview."
    >
      {loading && <p>Loading treasury data…</p>}
      {error && <p className={styles.errorText}>{error}</p>}

      {monitoring && (
        <>
          {/* Treasury KPI cards */}
          <div className={styles.kpiGrid}>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Cash Position</div>
              <div className={styles.kpiValue}>
                {formatCurrency(monitoring.cashPosition)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Receivables Exposure</div>
              <div className={styles.kpiValue}>
                {formatCurrency(monitoring.receivablesExposure)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Overdue Receivables</div>
              <div className={styles.kpiValue}>
                {formatCurrency(monitoring.overdueReceivables)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Liquidity Ratio</div>
              <div className={styles.kpiValue}>
                {(monitoring.liquidityRatio * 100).toFixed(2)}%
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Next-Month Forecast</div>
              <div className={styles.kpiValue}>
                {formatCurrency(monitoring.forecastNextMonth)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Projects</div>
              <div className={styles.kpiValue}>{monitoring.projectCount}</div>
            </div>
          </div>

          {/* Project exposure ranking table */}
          {monitoring.projectExposures.length > 0 ? (
            <>
              <h3 className={styles.sectionHeading ?? undefined}>
                Project Exposure Ranking
              </h3>
              <table
                className={styles.dataTable ?? undefined}
                aria-label="Project exposure ranking table"
              >
                <thead>
                  <tr>
                    <th scope="col">Project</th>
                    <th scope="col">Receivable Exposure</th>
                    <th scope="col">Exposure %</th>
                    <th scope="col">Forecast Inflow (Next Month)</th>
                  </tr>
                </thead>
                <tbody>
                  {monitoring.projectExposures.map(
                    (entry: ProjectExposure) => (
                      <tr key={entry.projectId}>
                        <td>{entry.projectId}</td>
                        <td>{formatCurrency(entry.receivableExposure)}</td>
                        <td>{entry.exposurePercentage.toFixed(2)}%</td>
                        <td>{formatCurrency(entry.forecastInflow)}</td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </>
          ) : (
            <p>No project exposure data available.</p>
          )}
        </>
      )}
    </PageContainer>
  );
}
