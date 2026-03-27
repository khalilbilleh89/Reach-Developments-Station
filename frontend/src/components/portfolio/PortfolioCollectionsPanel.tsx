/**
 * PortfolioCollectionsPanel — collections health panel for the portfolio
 * dashboard.
 *
 * Renders collections signals sourced directly from the backend collections
 * summary contract. Collection rate is not recomputed here.
 */

import React from "react";
import type { PortfolioCollectionsSummary } from "@/lib/portfolio-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/portfolio.module.css";

interface PortfolioCollectionsPanelProps {
  collections: PortfolioCollectionsSummary;
}

export function PortfolioCollectionsPanel({
  collections,
}: PortfolioCollectionsPanelProps) {
  const metrics: { label: string; value: string }[] = [
    {
      label: "Total Receivables",
      value: String(collections.total_receivables),
    },
    {
      label: "Overdue Receivables",
      value: String(collections.overdue_receivables),
    },
    {
      label: "Overdue Balance",
      value: formatCurrency(collections.overdue_balance),
    },
    {
      label: "Collection Rate",
      value:
        collections.collection_rate_pct !== null
          ? `${collections.collection_rate_pct.toFixed(1)}%`
          : "—",
    },
  ];

  return (
    <div className={styles.panelCard}>
      <h2 className={styles.panelTitle}>Collections</h2>
      <div className={styles.metricsRow}>
        {metrics.map((m) => (
          <div key={m.label} className={styles.metricItem}>
            <span className={styles.metricLabel}>{m.label}</span>
            <span className={styles.metricValue}>{m.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
