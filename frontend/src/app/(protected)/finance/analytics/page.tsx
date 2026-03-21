"use client";

import React, { useEffect, useState } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { getPortfolioAnalytics } from "@/lib/finance-api";
import type {
  CollectionsTrendEntry,
  PortfolioAnalytics,
  ReceivablesTrendEntry,
  RevenueTrendEntry,
} from "@/lib/finance-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/finance-dashboard.module.css";

/**
 * Portfolio Analytics Dashboard.
 *
 * Displays executive-level portfolio KPIs and trend tables for revenue,
 * collections, and receivables — all derived from the analytics fact tables.
 *
 * Data source:
 *   GET /finance/analytics/portfolio
 *
 * No financial calculations are performed on this page — all values are
 * sourced directly from the backend analytics dashboard service.
 */
export default function FinanceAnalyticsPage() {
  const [analytics, setAnalytics] = useState<PortfolioAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getPortfolioAnalytics()
      .then(setAnalytics)
      .catch((err: unknown) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load portfolio analytics.",
        );
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <PageContainer
      title="Portfolio Analytics Dashboard"
      subtitle="Revenue trends, collections performance, and receivable exposure from the analytics fact layer."
    >
      {loading && <p>Loading analytics data…</p>}
      {error && <p className={styles.errorText}>{error}</p>}

      {analytics && (
        <>
          {/* Portfolio KPI cards */}
          <div className={styles.kpiGrid}>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Total Revenue Recognized</div>
              <div className={styles.kpiValue}>
                {formatCurrency(analytics.kpis.totalRevenue)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Total Collections</div>
              <div className={styles.kpiValue}>
                {formatCurrency(analytics.kpis.totalCollections)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Total Receivables</div>
              <div className={styles.kpiValue}>
                {formatCurrency(analytics.kpis.totalReceivables)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Collection Efficiency</div>
              <div className={styles.kpiValue}>
                {(analytics.kpis.collectionEfficiency * 100).toFixed(2)}%
              </div>
            </div>
          </div>

          {/* Revenue Trend */}
          {analytics.revenueTrend.length > 0 ? (
            <>
              <h3 className={styles.sectionHeading}>
                Revenue Trend
              </h3>
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
                  {analytics.revenueTrend.map((entry: RevenueTrendEntry) => (
                    <tr key={entry.month}>
                      <td>{entry.month}</td>
                      <td>{formatCurrency(entry.totalRecognizedRevenue)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <p>No revenue trend data available.</p>
          )}

          {/* Collections Trend */}
          {analytics.collectionsTrend.length > 0 ? (
            <>
              <h3 className={styles.sectionHeading}>
                Collections Trend
              </h3>
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
                  {analytics.collectionsTrend.map(
                    (entry: CollectionsTrendEntry) => (
                      <tr key={entry.month}>
                        <td>{entry.month}</td>
                        <td>{formatCurrency(entry.totalAmount)}</td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </>
          ) : (
            <p>No collections trend data available.</p>
          )}

          {/* Receivables Trend */}
          {analytics.receivablesTrend.length > 0 ? (
            <>
              <h3 className={styles.sectionHeading}>
                Receivables Trend
              </h3>
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
                  {analytics.receivablesTrend.map(
                    (entry: ReceivablesTrendEntry) => (
                      <tr key={entry.snapshotDate}>
                        <td>{entry.snapshotDate}</td>
                        <td>{formatCurrency(entry.totalReceivables)}</td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </>
          ) : (
            <p>No receivables trend data available.</p>
          )}
        </>
      )}
    </PageContainer>
  );
}
