"use client";

import React, { useEffect, useState } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { getPortfolioFinancialSummary } from "@/lib/finance-api";
import type {
  PortfolioFinancialSummary,
  ProjectFinancialSummary,
} from "@/lib/finance-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/finance-dashboard.module.css";

/**
 * Portfolio Financial Summary Dashboard.
 *
 * Displays executive-level portfolio KPIs and a per-project comparison
 * table derived from the aggregated financial engines.
 *
 * Data source:
 *   GET /finance/portfolio/summary
 *
 * No financial calculations are performed on this page — all values are
 * sourced directly from the backend portfolio summary engine.
 */
export default function FinancePortfolioPage() {
  const [summary, setSummary] = useState<PortfolioFinancialSummary | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getPortfolioFinancialSummary()
      .then(setSummary)
      .catch((err: unknown) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load portfolio summary.",
        );
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <PageContainer
      title="Portfolio Financial Summary"
      subtitle="Consolidated financial overview across all projects."
    >
      {loading && <p>Loading portfolio summary…</p>}
      {error && <p className={styles.errorText}>{error}</p>}

      {summary && (
        <>
          {/* Portfolio KPI cards */}
          <div className={styles.kpiGrid}>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Total Revenue Recognized</div>
              <div className={styles.kpiValue}>
                {formatCurrency(summary.totalRevenueRecognized)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Total Deferred Revenue</div>
              <div className={styles.kpiValue}>
                {formatCurrency(summary.totalDeferredRevenue)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Total Receivables</div>
              <div className={styles.kpiValue}>
                {formatCurrency(summary.totalReceivables)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Overdue Receivables</div>
              <div className={styles.kpiValue}>
                {formatCurrency(summary.overdueReceivables)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Overdue %</div>
              <div className={styles.kpiValue}>
                {summary.overdueReceivablesPct.toFixed(2)}%
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Next-Month Forecast</div>
              <div className={styles.kpiValue}>
                {formatCurrency(summary.forecastNextMonth)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Projects</div>
              <div className={styles.kpiValue}>{summary.projectCount}</div>
            </div>
          </div>

          {/* Per-project comparison table */}
          {summary.projectSummaries.length > 0 ? (
            <>
              <h3 className={styles.sectionHeading ?? undefined}>
                Project Financial Comparison
              </h3>
              <table className={styles.dataTable ?? undefined}>
                <thead>
                  <tr>
                    <th>Project</th>
                    <th>Recognized Revenue</th>
                    <th>Receivables Exposure</th>
                    <th>Collection Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.projectSummaries.map(
                    (entry: ProjectFinancialSummary) => (
                      <tr key={entry.projectId}>
                        <td>{entry.projectId}</td>
                        <td>{formatCurrency(entry.recognizedRevenue)}</td>
                        <td>{formatCurrency(entry.receivablesExposure)}</td>
                        <td>
                          {(entry.collectionRate * 100).toFixed(2)}%
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </>
          ) : (
            <p>No project financial data available.</p>
          )}
        </>
      )}
    </PageContainer>
  );
}
