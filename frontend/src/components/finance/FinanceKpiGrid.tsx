"use client";

import React, { useEffect, useState } from "react";
import { getProjectFinanceSummary } from "@/lib/finance-dashboard-api";
import type { FinanceKpis } from "@/lib/finance-dashboard-types";
import { formatCurrency } from "@/lib/format-utils";
import { MetricCard } from "@/components/dashboard/MetricCard";
import styles from "@/styles/finance-dashboard.module.css";

interface FinanceKpiGridProps {
  projectId: string;
}

/**
 * FinanceKpiGrid — headline finance KPI card grid.
 *
 * Fetches /finance/projects/{id}/summary and renders the six top-level
 * financial metrics. No calculations are performed here — values come
 * directly from the backend summary endpoint.
 */
export function FinanceKpiGrid({ projectId }: FinanceKpiGridProps) {
  const [kpis, setKpis] = useState<FinanceKpis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getProjectFinanceSummary(projectId)
      .then(({ kpis: data }) => setKpis(data))
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Failed to load financial data.",
        );
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return (
      <div className={styles.loadingState}>Loading financial summary…</div>
    );
  }

  if (error || !kpis) {
    return (
      <div className={styles.loadingState}>
        {error ?? "Financial data unavailable."}
      </div>
    );
  }

  const collectionPct = `${(kpis.collection_ratio * 100).toFixed(1)}%`;

  return (
    <div className={styles.sectionCard}>
      <h2 className={styles.sectionTitle}>Finance KPIs</h2>
      <div className={styles.metricsRow}>
        <MetricCard
          title="Total Contract Value"
          value={formatCurrency(kpis.total_contract_value)}
          subtitle="Contracted revenue"
          icon="💰"
        />
        <MetricCard
          title="Total Collected"
          value={formatCurrency(kpis.total_collected)}
          subtitle={`Collection ratio: ${collectionPct}`}
          icon="✅"
        />
        <MetricCard
          title="Total Receivable"
          value={formatCurrency(kpis.total_receivable)}
          subtitle="Outstanding balance"
          icon="📋"
        />
        <MetricCard
          title="Collection Ratio"
          value={collectionPct}
          subtitle="Collected vs contracted"
          icon="📊"
        />
        <MetricCard
          title="Units Sold"
          value={`${kpis.units_sold} / ${kpis.total_units}`}
          subtitle="Sold vs total units"
          icon="🏠"
        />
        <MetricCard
          title="Avg Unit Price"
          value={formatCurrency(kpis.average_unit_price)}
          subtitle="Average contracted price"
          icon="🏷"
        />
      </div>
    </div>
  );
}
