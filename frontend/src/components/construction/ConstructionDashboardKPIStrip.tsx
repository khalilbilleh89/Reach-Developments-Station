/**
 * ConstructionDashboardKPIStrip — displays aggregated project-level construction KPIs.
 */

"use client";

import React from "react";
import { MetricCard } from "@/components/dashboard/MetricCard";
import type { ConstructionDashboardResponse } from "@/lib/construction-types";
import styles from "@/styles/construction.module.css";

interface ConstructionDashboardKPIStripProps {
  dashboard: ConstructionDashboardResponse;
}

function _fmt(value: string): string {
  const n = parseFloat(value);
  if (isNaN(n)) return value;
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(n);
}

export function ConstructionDashboardKPIStrip({
  dashboard,
}: ConstructionDashboardKPIStripProps) {
  const varianceBudget = parseFloat(dashboard.variance_to_budget);
  const varianceIcon = varianceBudget > 0 ? "🔴" : varianceBudget < 0 ? "🟢" : "⚖️";

  return (
    <div className={styles.kpiGrid}>
      <MetricCard
        title="Total Scopes"
        value={dashboard.scopes_total}
        subtitle="All scopes"
        icon="🏗️"
      />
      <MetricCard
        title="Active Scopes"
        value={dashboard.scopes_active}
        subtitle="In progress"
        icon="⚙️"
      />
      <MetricCard
        title="Open Engineering Items"
        value={dashboard.engineering_items_open_total}
        subtitle="Pending / in progress"
        icon="📐"
      />
      <MetricCard
        title="Overdue Milestones"
        value={dashboard.milestones_overdue_total}
        subtitle="Past target date"
        icon={dashboard.milestones_overdue_total > 0 ? "🔴" : "✅"}
      />
      <MetricCard
        title="Total Budget"
        value={_fmt(dashboard.total_budget)}
        subtitle="AED"
        icon="💰"
      />
      <MetricCard
        title="Total Committed"
        value={_fmt(dashboard.total_committed)}
        subtitle="AED"
        icon="📋"
      />
      <MetricCard
        title="Total Actual"
        value={_fmt(dashboard.total_actual)}
        subtitle="AED"
        icon="💸"
      />
      <MetricCard
        title="Variance to Budget"
        value={_fmt(dashboard.variance_to_budget)}
        subtitle="Actual − Budget (AED)"
        icon={varianceIcon}
      />
    </div>
  );
}
