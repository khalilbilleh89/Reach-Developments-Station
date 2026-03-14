"use client";

import React, { useEffect, useState } from "react";
import { getFinancialSummary, type FinancialSummary } from "@/lib/dashboard-api";
import { MetricCard } from "./MetricCard";
import styles from "@/styles/dashboard.module.css";

interface FinancialSummaryGridProps {
  projectId: string;
}

/** Format a number as a compact currency string (e.g. 1 500 000 → AED 1.5M). */
function formatCurrency(value: number): string {
  if (value >= 1_000_000) {
    return `AED ${(value / 1_000_000).toFixed(1)}M`;
  }
  if (value >= 1_000) {
    return `AED ${(value / 1_000).toFixed(0)}K`;
  }
  return `AED ${value.toLocaleString()}`;
}

/** Format a ratio as a percentage string. */
function formatPct(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}%`;
}

/**
 * FinancialSummaryGrid — displays core financial metrics for a project.
 *
 * Fetches /finance/projects/{id}/summary and renders the results as
 * MetricCards. All calculations are done by the backend; this component
 * only formats the values for display.
 */
export function FinancialSummaryGrid({ projectId }: FinancialSummaryGridProps) {
  const [summary, setSummary] = useState<FinancialSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getFinancialSummary(projectId)
      .then(setSummary)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load financial data.");
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return <div className={styles.loadingState}>Loading financial summary…</div>;
  }

  if (error || !summary) {
    return (
      <div className={styles.loadingState}>
        {error ?? "Financial data unavailable."}
      </div>
    );
  }

  return (
    <div className={styles.sectionCard}>
      <h2 className={styles.sectionTitle}>Financial Summary</h2>
      <div className={styles.metricsRow}>
        <MetricCard
          title="Total Revenue"
          value={formatCurrency(summary.total_contract_value)}
          subtitle="Total contracted sales value"
          icon="💰"
        />
        <MetricCard
          title="Units Sold"
          value={`${summary.units_sold} / ${summary.total_units}`}
          subtitle="Units sold vs total"
          icon="🏠"
        />
        <MetricCard
          title="Collections Received"
          value={formatCurrency(summary.total_collected)}
          subtitle={`Collection ratio: ${formatPct(summary.collection_ratio)}`}
          icon="✅"
        />
        <MetricCard
          title="Receivables Outstanding"
          value={formatCurrency(summary.total_receivable)}
          subtitle="Amount still to be collected"
          icon="📋"
        />
        <MetricCard
          title="Avg Unit Price"
          value={formatCurrency(summary.average_unit_price)}
          subtitle="Average contracted price per unit"
          icon="📊"
        />
      </div>
    </div>
  );
}
