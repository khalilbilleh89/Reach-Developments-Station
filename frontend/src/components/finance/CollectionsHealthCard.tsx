"use client";

import React, { useEffect, useState } from "react";
import { getProjectFinanceSummary } from "@/lib/finance-dashboard-api";
import type { CollectionsHealth } from "@/lib/finance-dashboard-types";
import { formatCurrency } from "@/lib/format-utils";
import { MetricCard } from "@/components/dashboard/MetricCard";
import styles from "@/styles/finance-dashboard.module.css";

interface CollectionsHealthCardProps {
  projectId: string;
}

/**
 * CollectionsHealthCard — receivables and collections performance.
 *
 * Fetches /finance/projects/{id}/summary and surfaces the three key
 * collections metrics. No calculations are performed — all values
 * come directly from the backend.
 */
export function CollectionsHealthCard({
  projectId,
}: CollectionsHealthCardProps) {
  const [health, setHealth] = useState<CollectionsHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getProjectFinanceSummary(projectId)
      .then(({ collections }) => setHealth(collections))
      .catch((err: unknown) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load collections data.",
        );
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return (
      <div className={styles.loadingState}>Loading collections data…</div>
    );
  }

  if (error || !health) {
    return (
      <div className={styles.loadingState}>
        {error ?? "Collections data unavailable."}
      </div>
    );
  }

  const collectionPct = `${(health.collection_ratio * 100).toFixed(1)}%`;

  return (
    <div className={styles.sectionCard}>
      <h2 className={styles.sectionTitle}>Collections Health</h2>
      <div className={styles.metricsRow}>
        <MetricCard
          title="Collected"
          value={formatCurrency(health.total_collected)}
          subtitle="Cash received to date"
          icon="✅"
        />
        <MetricCard
          title="Outstanding"
          value={formatCurrency(health.total_receivable)}
          subtitle="Receivables remaining"
          icon="📋"
          trend={{
            direction: health.total_receivable > 0 ? "down" : "neutral",
            label:
              health.total_receivable > 0 ? "Receivable pressure" : "Cleared",
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
