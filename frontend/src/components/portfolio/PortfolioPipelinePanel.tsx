/**
 * PortfolioPipelinePanel — pipeline section for the portfolio dashboard.
 *
 * Renders scenario and feasibility pipeline signals sourced directly from
 * the backend pipeline summary contract. No pipeline logic is derived here.
 */

import React from "react";
import type { PortfolioPipelineSummary } from "@/lib/portfolio-types";
import styles from "@/styles/portfolio.module.css";

interface PortfolioPipelinePanelProps {
  pipeline: PortfolioPipelineSummary;
}

export function PortfolioPipelinePanel({ pipeline }: PortfolioPipelinePanelProps) {
  const metrics: { label: string; value: string }[] = [
    { label: "Total Scenarios", value: String(pipeline.total_scenarios) },
    { label: "Approved Scenarios", value: String(pipeline.approved_scenarios) },
    {
      label: "Total Feasibility Runs",
      value: String(pipeline.total_feasibility_runs),
    },
    {
      label: "Calculated Runs",
      value: String(pipeline.calculated_feasibility_runs),
    },
    {
      label: "Projects with No Feasibility",
      value: String(pipeline.projects_with_no_feasibility),
    },
  ];

  return (
    <div className={styles.panelCard}>
      <h2 className={styles.panelTitle}>Pipeline</h2>
      <div className={styles.metricsRow}>
        {metrics.map((m) => (
          <div key={m.label} className={styles.metricItem}>
            <span className={styles.metricLabel}>{m.label}</span>
            <span className={styles.metricValue}>{m.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
