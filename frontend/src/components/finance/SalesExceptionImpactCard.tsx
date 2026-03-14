import React from "react";
import type { SalesExceptionImpact } from "@/lib/finance-dashboard-types";
import { formatCurrency } from "@/lib/format-utils";
import { MetricCard } from "@/components/dashboard/MetricCard";
import styles from "@/styles/finance-dashboard.module.css";

interface SalesExceptionImpactCardProps {
  exceptions: SalesExceptionImpact | null;
  loading: boolean;
  error: string | null;
}

/**
 * SalesExceptionImpactCard — discount and incentive impact from sales exceptions.
 *
 * Purely presentational. Receives pre-fetched exception data from the parent
 * page. No calculations are performed — all values come directly from the backend.
 */
export function SalesExceptionImpactCard({
  exceptions,
  loading,
  error,
}: SalesExceptionImpactCardProps) {
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
