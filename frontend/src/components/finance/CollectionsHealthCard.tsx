import React from "react";
import type { CollectionsHealth } from "@/lib/finance-dashboard-types";
import { formatCurrency } from "@/lib/format-utils";
import { MetricCard } from "@/components/dashboard/MetricCard";
import styles from "@/styles/finance-dashboard.module.css";

interface CollectionsHealthCardProps {
  collections: CollectionsHealth | null;
  loading: boolean;
  error: string | null;
}

/**
 * CollectionsHealthCard — receivables and collections performance.
 *
 * Purely presentational. Receives pre-fetched collections data from the parent
 * page. No data fetching or financial calculations are performed here — all
 * values come directly from the backend.
 */
export function CollectionsHealthCard({
  collections,
  loading,
  error,
}: CollectionsHealthCardProps) {
  if (loading) {
    return (
      <div className={styles.loadingState}>Loading collections data…</div>
    );
  }

  if (error || !collections) {
    return (
      <div className={styles.loadingState}>
        {error ?? "Collections data unavailable."}
      </div>
    );
  }

  const collectionPct = `${(collections.collection_ratio * 100).toFixed(1)}%`;

  return (
    <div className={styles.sectionCard}>
      <h2 className={styles.sectionTitle}>Collections Health</h2>
      <div className={styles.metricsRow}>
        <MetricCard
          title="Collected"
          value={formatCurrency(collections.total_collected)}
          subtitle="Cash received to date"
          icon="✅"
        />
        <MetricCard
          title="Outstanding"
          value={formatCurrency(collections.total_receivable)}
          subtitle="Receivables remaining"
          icon="📋"
          trend={{
            direction: collections.total_receivable > 0 ? "down" : "neutral",
            label:
              collections.total_receivable > 0
                ? "Receivable pressure"
                : "Cleared",
          }}
        />
        <MetricCard
          title="Collection Ratio"
          value={collectionPct}
          subtitle="Collected vs contracted"
          icon="📊"
        />
      </div>
    </div>
  );
}
