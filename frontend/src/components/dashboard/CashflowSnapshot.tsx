"use client";

import React, { useEffect, useState } from "react";
import { getCashflowSummary, type CashflowSummary } from "@/lib/dashboard-api";
import { MetricCard } from "./MetricCard";
import styles from "@/styles/dashboard.module.css";

interface CashflowSnapshotProps {
  projectId: string;
}

function formatCurrency(value: number): string {
  if (value >= 1_000_000) {
    return `AED ${(value / 1_000_000).toFixed(1)}M`;
  }
  if (value >= 1_000) {
    return `AED ${(value / 1_000).toFixed(0)}K`;
  }
  return `AED ${value.toLocaleString()}`;
}

/**
 * CashflowSnapshot — high-level cashflow forecast status.
 *
 * Fetches /cashflow/projects/{id}/cashflow-summary and renders the key
 * cashflow positions as MetricCards. No chart is included yet — that
 * comes in a later PR.
 */
export function CashflowSnapshot({ projectId }: CashflowSnapshotProps) {
  const [summary, setSummary] = useState<CashflowSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getCashflowSummary(projectId)
      .then(setSummary)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load cashflow data.");
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return <div className={styles.loadingState}>Loading cashflow data…</div>;
  }

  if (error || !summary) {
    return (
      <div className={styles.loadingState}>
        {error ?? "Cashflow data unavailable."}
      </div>
    );
  }

  const netDirection =
    summary.net_position > 0
      ? "up"
      : summary.net_position < 0
        ? "down"
        : "neutral";

  return (
    <div className={styles.sectionCard}>
      <h2 className={styles.sectionTitle}>Cashflow Snapshot</h2>
      <div className={styles.metricsRow}>
        <MetricCard
          title="Cash Position"
          value={formatCurrency(summary.current_cash_position)}
          subtitle="Current balance"
          icon="🏦"
        />
        <MetricCard
          title="Expected Inflows"
          value={formatCurrency(summary.expected_inflows)}
          subtitle="Next period"
          icon="⬇️"
        />
        <MetricCard
          title="Expected Outflows"
          value={formatCurrency(summary.expected_outflows)}
          subtitle="Next period"
          icon="⬆️"
        />
        <MetricCard
          title="Net Position"
          value={formatCurrency(summary.net_position)}
          subtitle="Inflows minus outflows"
          icon="⚖️"
          trend={{
            direction: netDirection,
            label: netDirection === "up" ? "Positive" : netDirection === "down" ? "Negative" : "Neutral",
          }}
        />
      </div>
    </div>
  );
}
