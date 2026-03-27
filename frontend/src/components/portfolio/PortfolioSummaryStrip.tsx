/**
 * PortfolioSummaryStrip — top-level KPI strip for the portfolio dashboard.
 *
 * Renders headline portfolio metrics sourced directly from the backend
 * summary contract. No values are recomputed or derived here.
 */

import React from "react";
import type { PortfolioSummary } from "@/lib/portfolio-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/portfolio.module.css";

interface PortfolioSummaryStripProps {
  summary: PortfolioSummary;
}

export function PortfolioSummaryStrip({ summary }: PortfolioSummaryStripProps) {
  const kpis: { label: string; value: string }[] = [
    { label: "Total Projects", value: String(summary.total_projects) },
    { label: "Active Projects", value: String(summary.active_projects) },
    { label: "Total Units", value: String(summary.total_units) },
    { label: "Available", value: String(summary.available_units) },
    { label: "Reserved", value: String(summary.reserved_units) },
    { label: "Under Contract", value: String(summary.under_contract_units) },
    { label: "Registered", value: String(summary.registered_units) },
    {
      label: "Contracted Revenue",
      value: formatCurrency(summary.contracted_revenue),
    },
    {
      label: "Collected Cash",
      value: formatCurrency(summary.collected_cash),
    },
    {
      label: "Outstanding Balance",
      value: formatCurrency(summary.outstanding_balance),
    },
  ];

  return (
    <div className={styles.summaryStrip} aria-label="Portfolio KPI summary">
      {kpis.map((kpi) => (
        <div key={kpi.label} className={styles.kpiCard}>
          <span className={styles.kpiLabel}>{kpi.label}</span>
          <span className={styles.kpiValue}>{kpi.value}</span>
        </div>
      ))}
    </div>
  );
}
