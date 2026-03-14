"use client";

import React, { useEffect, useState } from "react";
import {
  getSalesExceptionsSummary,
  type SalesExceptionsSummary,
} from "@/lib/dashboard-api";
import { formatCurrency } from "@/lib/format-utils";
import { MetricCard } from "./MetricCard";
import styles from "@/styles/dashboard.module.css";

interface SalesExceptionImpactProps {
  projectId: string;
}

/**
 * SalesExceptionImpact — shows the commercial impact of manual sales exceptions.
 *
 * Fetches /sales-exceptions/projects/{id}/summary and renders the aggregate
 * discount metrics to give commercial visibility over approved exceptions.
 */
export function SalesExceptionImpact({ projectId }: SalesExceptionImpactProps) {
  const [summary, setSummary] = useState<SalesExceptionsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getSalesExceptionsSummary(projectId)
      .then(setSummary)
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Failed to load exception data.",
        );
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return <div className={styles.loadingState}>Loading exception data…</div>;
  }

  if (error || !summary) {
    return (
      <div className={styles.loadingState}>
        {error ?? "Exception data unavailable."}
      </div>
    );
  }

  return (
    <div className={styles.sectionCard}>
      <h2 className={styles.sectionTitle}>Sales Exception Impact</h2>
      <div className={styles.metricsRow}>
        <MetricCard
          title="Total Exceptions"
          value={summary.total_exceptions}
          subtitle="Approved manual exceptions"
          icon="⚠️"
        />
        <MetricCard
          title="Total Discount"
          value={formatCurrency(summary.total_discount_amount)}
          subtitle="Cumulative discount value"
          icon="🏷"
          trend={{
            direction: summary.total_discount_amount > 0 ? "down" : "neutral",
            label:
              summary.total_discount_amount > 0
                ? "Revenue impact"
                : "No discounts",
          }}
        />
        <MetricCard
          title="Avg Discount %"
          value={`${summary.average_discount_pct.toFixed(1)}%`}
          subtitle="Average per exception"
          icon="📉"
        />
      </div>
    </div>
  );
}
