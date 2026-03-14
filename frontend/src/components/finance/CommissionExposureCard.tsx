import React from "react";
import type { CommissionExposure } from "@/lib/finance-dashboard-types";
import { formatCurrency } from "@/lib/format-utils";
import { MetricCard } from "@/components/dashboard/MetricCard";
import styles from "@/styles/finance-dashboard.module.css";

interface CommissionExposureCardProps {
  commission: CommissionExposure | null;
  loading: boolean;
  error: string | null;
}

/**
 * CommissionExposureCard — commission burden and payout exposure.
 *
 * Purely presentational. Receives pre-fetched commission data from the parent
 * page. No commission math is performed in the browser.
 *
 * Pending exposure = draft_payouts + calculated_payouts.
 * Cancelled payouts are explicitly excluded — cancelled is not pending.
 */
export function CommissionExposureCard({
  commission,
  loading,
  error,
}: CommissionExposureCardProps) {
  if (loading) {
    return (
      <div className={styles.loadingState}>Loading commission data…</div>
    );
  }

  if (error || !commission) {
    return (
      <div className={styles.loadingState}>
        {error ?? "Commission data unavailable."}
      </div>
    );
  }

  // Pending = draft + calculated. Approved and cancelled are excluded.
  const pendingPayouts = commission.draft_payouts + commission.calculated_payouts;

  return (
    <div className={styles.sectionCard}>
      <h2 className={styles.sectionTitle}>Commission Exposure</h2>
      <div className={styles.metricsRow}>
        <MetricCard
          title="Total Gross Value"
          value={formatCurrency(commission.total_gross_value)}
          subtitle="Gross contract value in scope"
          icon="💼"
        />
        <MetricCard
          title="Commission Pool"
          value={formatCurrency(commission.total_commission_pool)}
          subtitle="Total commission calculated"
          icon="💰"
        />
        <MetricCard
          title="Approved Payouts"
          value={commission.approved_payouts}
          subtitle="Payouts approved for release"
          icon="✅"
        />
        <MetricCard
          title="Pending Exposure"
          value={pendingPayouts}
          subtitle="Draft + calculated, awaiting approval"
          icon="⏳"
          trend={{
            direction: pendingPayouts > 0 ? "down" : "neutral",
            label: pendingPayouts > 0 ? "Pending approval" : "None pending",
          }}
        />
      </div>
    </div>
  );
}
