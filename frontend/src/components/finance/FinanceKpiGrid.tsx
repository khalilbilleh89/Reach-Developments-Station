import React from "react";
import type { FinanceKpis } from "@/lib/finance-dashboard-types";
import { formatAmount } from "@/lib/format-utils";
import { DEFAULT_CURRENCY } from "@/lib/currency-constants";
import { MetricCard } from "@/components/dashboard/MetricCard";
import styles from "@/styles/finance-dashboard.module.css";

interface FinanceKpiGridProps {
  kpis: FinanceKpis | null;
  loading: boolean;
  error: string | null;
}

/**
 * FinanceKpiGrid — headline finance KPI card grid.
 *
 * Purely presentational. Receives pre-fetched KPI data from the parent page.
 * The parent is responsible for all data fetching and loading state.
 * No financial calculations are performed here — values come from the backend.
 */
export function FinanceKpiGrid({ kpis, loading, error }: FinanceKpiGridProps) {
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
  const currency = kpis.currency ?? DEFAULT_CURRENCY;

  return (
    <div className={styles.sectionCard}>
      <h2 className={styles.sectionTitle}>Finance KPIs</h2>
      <div className={styles.metricsRow}>
        <MetricCard
          title="Total Contract Value"
          value={formatAmount(kpis.total_contract_value, currency)}
          subtitle="Contracted revenue"
          icon="💰"
        />
        <MetricCard
          title="Total Collected"
          value={formatAmount(kpis.total_collected, currency)}
          subtitle={`Collection ratio: ${collectionPct}`}
          icon="✅"
        />
        <MetricCard
          title="Total Receivable"
          value={formatAmount(kpis.total_receivable, currency)}
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
          value={formatAmount(kpis.average_unit_price, currency)}
          subtitle="Average contracted price"
          icon="🏷"
        />
      </div>
    </div>
  );
}
