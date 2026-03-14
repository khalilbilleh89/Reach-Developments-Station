import React from "react";
import type { CashflowHealth } from "@/lib/finance-dashboard-types";
import { formatCurrency } from "@/lib/format-utils";
import { MetricCard } from "@/components/dashboard/MetricCard";
import styles from "@/styles/finance-dashboard.module.css";

interface CashflowHealthCardProps {
  cashflow: CashflowHealth | null;
  loading: boolean;
  error: string | null;
}

/**
 * CashflowHealthCard — cashflow forecast posture.
 *
 * Purely presentational. Receives pre-fetched cashflow data from the parent
 * page. Net position direction is derived purely from the backend-returned
 * net_cashflow value — no financial math in the browser.
 */
export function CashflowHealthCard({
  cashflow,
  loading,
  error,
}: CashflowHealthCardProps) {
  if (loading) {
    return <div className={styles.loadingState}>Loading cashflow data…</div>;
  }

  if (error || !cashflow) {
    return (
      <div className={styles.loadingState}>
        {error ?? "Cashflow data unavailable."}
      </div>
    );
  }

  const netDirection =
    cashflow.net_cashflow > 0
      ? "up"
      : cashflow.net_cashflow < 0
        ? "down"
        : "neutral";

  const netLabel =
    netDirection === "up"
      ? "Positive cashflow"
      : netDirection === "down"
        ? "Negative cashflow"
        : "Neutral";

  return (
    <div className={styles.sectionCard}>
      <h2 className={styles.sectionTitle}>Cashflow Health</h2>
      <div className={styles.metricsRow}>
        <MetricCard
          title="Expected Inflows"
          value={formatCurrency(cashflow.expected_inflows)}
          subtitle="Forecast inflows"
          icon="⬇️"
        />
        <MetricCard
          title="Expected Outflows"
          value={formatCurrency(cashflow.expected_outflows)}
          subtitle="Forecast outflows"
          icon="⬆️"
        />
        <MetricCard
          title="Net Cashflow"
          value={formatCurrency(cashflow.net_cashflow)}
          subtitle="Inflows minus outflows"
          icon="⚖️"
          trend={{ direction: netDirection, label: netLabel }}
        />
        <MetricCard
          title="Closing Balance"
          value={formatCurrency(cashflow.closing_balance)}
          subtitle="Forecast closing position"
          icon="🏦"
        />
      </div>
    </div>
  );
}
