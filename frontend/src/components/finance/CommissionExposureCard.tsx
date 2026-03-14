"use client";

import React, { useEffect, useState } from "react";
import { getProjectCommissionSummary } from "@/lib/finance-dashboard-api";
import type { CommissionExposure } from "@/lib/finance-dashboard-types";
import { formatCurrency } from "@/lib/format-utils";
import { MetricCard } from "@/components/dashboard/MetricCard";
import styles from "@/styles/finance-dashboard.module.css";

interface CommissionExposureCardProps {
  projectId: string;
}

/**
 * CommissionExposureCard — commission burden and payout exposure.
 *
 * Fetches /commission/projects/{id}/summary and renders the payout and
 * value metrics. No commission math is performed in the browser.
 */
export function CommissionExposureCard({
  projectId,
}: CommissionExposureCardProps) {
  const [commission, setCommission] = useState<CommissionExposure | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getProjectCommissionSummary(projectId)
      .then(setCommission)
      .catch((err: unknown) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load commission data.",
        );
      })
      .finally(() => setLoading(false));
  }, [projectId]);

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

  const pendingPayouts =
    // Payouts not yet approved = total minus approved (includes draft + calculated)
    commission.total_payouts - commission.approved_payouts;

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
          subtitle="Payouts awaiting approval"
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
