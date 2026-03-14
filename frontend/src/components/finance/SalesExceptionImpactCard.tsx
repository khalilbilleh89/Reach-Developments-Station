"use client";

import React, { useEffect, useState } from "react";
import { getProjectSalesExceptionsSummary } from "@/lib/finance-dashboard-api";
import type { SalesExceptionImpact } from "@/lib/finance-dashboard-types";
import { formatCurrency } from "@/lib/format-utils";
import { MetricCard } from "@/components/dashboard/MetricCard";
import styles from "@/styles/finance-dashboard.module.css";

interface SalesExceptionImpactCardProps {
  projectId: string;
}

/**
 * SalesExceptionImpactCard — discount and incentive impact from sales exceptions.
 *
 * Fetches /sales-exceptions/projects/{id}/summary and renders the aggregate
 * exception counts and financial impact. No calculations are performed —
 * all values come directly from the backend.
 */
export function SalesExceptionImpactCard({
  projectId,
}: SalesExceptionImpactCardProps) {
  const [exceptions, setExceptions] = useState<SalesExceptionImpact | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getProjectSalesExceptionsSummary(projectId)
      .then(setExceptions)
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

  if (error || !exceptions) {
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
          value={exceptions.total_exceptions}
          subtitle={`${exceptions.approved_exceptions} approved · ${exceptions.pending_exceptions} pending`}
          icon="⚠️"
        />
        <MetricCard
          title="Approved"
          value={exceptions.approved_exceptions}
          subtitle="Approved exceptions"
          icon="✅"
        />
        <MetricCard
          title="Pending"
          value={exceptions.pending_exceptions}
          subtitle="Awaiting review"
          icon="⏳"
        />
        <MetricCard
          title="Total Discount"
          value={formatCurrency(exceptions.total_discount_amount)}
          subtitle="Cumulative discount value"
          icon="🏷"
          trend={{
            direction: exceptions.total_discount_amount > 0 ? "down" : "neutral",
            label:
              exceptions.total_discount_amount > 0
                ? "Revenue impact"
                : "No discounts",
          }}
        />
        <MetricCard
          title="Incentive Value"
          value={formatCurrency(exceptions.total_incentive_value)}
          subtitle="Total approved incentives"
          icon="🎁"
        />
      </div>
    </div>
  );
}
