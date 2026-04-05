/**
 * PortfolioConstructionScorecardsPanel — portfolio-wide construction health panel.
 *
 * Renders:
 *   - Health status counts (healthy / warning / critical / incomplete)
 *   - Top-risk projects requiring executive attention
 *   - Projects missing an approved baseline
 *
 * All status values are sourced from the backend — no re-scoring here.
 * Renders a safe empty state when no projects exist.
 */

import React from "react";
import type {
  ConstructionPortfolioScorecardItem,
  ConstructionPortfolioScorecardsResponse,
  ConstructionHealthStatus,
} from "@/lib/construction-scorecard-types";
import styles from "@/styles/portfolio.module.css";

interface PortfolioConstructionScorecardsPanelProps {
  data: ConstructionPortfolioScorecardsResponse;
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function fmt(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const num = parseFloat(value);
  if (isNaN(num)) return "—";
  return num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtPct(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const num = parseFloat(value);
  if (isNaN(num)) return "—";
  const sign = num > 0 ? "+" : "";
  return `${sign}${num.toFixed(2)}%`;
}

// ---------------------------------------------------------------------------
// Health status helpers
// ---------------------------------------------------------------------------

function statusLabel(status: ConstructionHealthStatus): string {
  if (status === "healthy") return "Healthy";
  if (status === "warning") return "Warning";
  if (status === "critical") return "Critical";
  return "Incomplete";
}

function statusBadgeClass(status: ConstructionHealthStatus): string {
  if (status === "healthy") return styles.badgeSaving;
  if (status === "warning") return styles.badgeNeutral;
  if (status === "critical") return styles.badgeOverrun;
  return styles.badgeNeutral;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ScorecardProjectRow({
  item,
}: {
  item: ConstructionPortfolioScorecardItem;
}) {
  return (
    <div className={styles.varianceProjectCard}>
      <div className={styles.varianceCardHeader}>
        <span className={styles.projectName}>{item.project_name}</span>
        <span
          className={`${styles.healthBadge} ${statusBadgeClass(item.overall_health_status)}`}
        >
          {statusLabel(item.overall_health_status)}
        </span>
      </div>
      <div className={styles.projectStats}>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Baseline (project currency)</span>
          <span className={styles.statValue}>
            {fmt(item.approved_baseline_amount)}
          </span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Forecast (project currency)</span>
          <span className={styles.statValue}>
            {fmt(item.current_forecast_amount)}
          </span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Variance (project currency)</span>
          <span
            className={`${styles.statValue} ${
              item.cost_variance_amount !== null && parseFloat(item.cost_variance_amount) > 0
                ? styles.varianceOverrun
                : item.cost_variance_amount !== null && parseFloat(item.cost_variance_amount) < 0
                  ? styles.varianceSaving
                  : styles.varianceNeutral
            }`}
          >
            {item.cost_variance_amount !== null
              ? (parseFloat(item.cost_variance_amount) > 0 ? "+" : "") +
                fmt(item.cost_variance_amount)
              : "—"}
          </span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Variance %</span>
          <span
            className={`${styles.statValue} ${
              item.cost_variance_pct !== null && parseFloat(item.cost_variance_pct) > 0
                ? styles.varianceOverrun
                : item.cost_variance_pct !== null && parseFloat(item.cost_variance_pct) < 0
                  ? styles.varianceSaving
                  : styles.varianceNeutral
            }`}
          >
            {fmtPct(item.cost_variance_pct)}
          </span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Contingency (project currency)</span>
          <span className={styles.statValue}>
            {fmt(item.contingency_amount)}
          </span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export function PortfolioConstructionScorecardsPanel({
  data,
}: PortfolioConstructionScorecardsPanelProps) {
  const { summary, top_risk_projects, missing_baseline_projects } = data;

  if (summary.total_projects_scored === 0) {
    return (
      <div className={styles.panelCard}>
        <h2 className={styles.panelTitle}>Construction Health</h2>
        <p className={styles.panelEmpty}>
          No projects found. Add projects with construction cost records and
          approved baselines to see portfolio construction health.
        </p>
      </div>
    );
  }

  return (
    <div className={styles.panelCard}>
      <h2 className={styles.panelTitle}>Construction Health</h2>

      {/* Summary counts */}
      <div
        className={styles.metricsRow}
        aria-label="Construction health summary"
      >
        <div className={styles.metricItem}>
          <span className={styles.metricLabel}>Total Projects</span>
          <span className={styles.metricValue}>{summary.total_projects_scored}</span>
        </div>
        <div className={styles.metricItem}>
          <span className={styles.metricLabel}>Healthy</span>
          <span className={`${styles.metricValue} ${styles.varianceSaving}`}>
            {summary.healthy_count}
          </span>
        </div>
        <div className={styles.metricItem}>
          <span className={styles.metricLabel}>Warning</span>
          <span className={`${styles.metricValue} ${styles.varianceNeutral}`}>
            {summary.warning_count}
          </span>
        </div>
        <div className={styles.metricItem}>
          <span className={styles.metricLabel}>Critical</span>
          <span className={`${styles.metricValue} ${styles.varianceOverrun}`}>
            {summary.critical_count}
          </span>
        </div>
        <div className={styles.metricItem}>
          <span className={styles.metricLabel}>No Baseline</span>
          <span className={styles.metricValue}>{summary.incomplete_count}</span>
        </div>
      </div>

      {/* Top risk projects */}
      {top_risk_projects.length > 0 && (
        <section className={styles.varianceSection}>
          <h3 className={styles.varianceSectionTitle}>
            Projects Requiring Attention
          </h3>
          <div className={styles.varianceCardGrid}>
            {top_risk_projects.map((item) => (
              <ScorecardProjectRow key={item.project_id} item={item} />
            ))}
          </div>
        </section>
      )}

      {/* Missing baseline projects */}
      {missing_baseline_projects.length > 0 && (
        <section className={styles.varianceSection}>
          <h3 className={styles.varianceSectionTitle}>
            Missing Approved Baseline
          </h3>
          <ul className={styles.riskFlagList} aria-label="Projects missing approved baseline">
            {missing_baseline_projects.map((item) => (
              <li
                key={item.project_id}
                className={styles.riskFlagItem}
              >
                <span
                  className={`${styles.riskSeverityBadge} ${styles.severityWarning}`}
                >
                  Incomplete
                </span>
                <div className={styles.riskFlagBody}>
                  <span className={styles.riskFlagDescription}>
                    {item.project_name}
                  </span>
                  <span className={styles.riskFlagProject}>
                    No approved baseline — scorecard unavailable
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
