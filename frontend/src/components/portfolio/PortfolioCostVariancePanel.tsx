/**
 * PortfolioCostVariancePanel — portfolio cost variance roll-up section.
 *
 * Renders the portfolio-wide cost variance summary, per-project variance
 * cards, top overrun/saving lists, and cost variance flags.
 *
 * Sign/color conventions (backend-owned, never recomputed here):
 *   overrun  (variance_amount > 0) → red
 *   saving   (variance_amount < 0) → green
 *   neutral  (variance_amount = 0) → muted
 *
 * Renders a safe empty state when no active comparison sets exist.
 */

import React from "react";
import type {
  PortfolioCostVarianceProjectCard,
  PortfolioCostVarianceResponse,
  PortfolioVarianceStatus,
} from "@/lib/portfolio-variance-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/portfolio.module.css";

interface PortfolioCostVariancePanelProps {
  data: PortfolioCostVarianceResponse;
}

// ---------------------------------------------------------------------------
// Variance status helpers — display-only, values sourced from backend
// ---------------------------------------------------------------------------

function varianceStatusLabel(status: PortfolioVarianceStatus): string {
  if (status === "overrun") return "Overrun";
  if (status === "saving") return "Saving";
  return "Neutral";
}

function varianceAmountClass(status: PortfolioVarianceStatus): string {
  if (status === "overrun") return styles.varianceOverrun;
  if (status === "saving") return styles.varianceSaving;
  return styles.varianceNeutral;
}

function varianceStatusBadgeClass(status: PortfolioVarianceStatus): string {
  if (status === "overrun") return styles.badgeOverrun;
  if (status === "saving") return styles.badgeSaving;
  return styles.badgeNeutral;
}

function formatVariancePct(pct: number | null): string {
  if (pct === null) return "—";
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function formatVarianceAmount(amount: number): string {
  const sign = amount > 0 ? "+" : "";
  return `${sign}${formatCurrency(amount)}`;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function VarianceProjectCard({
  card,
}: {
  card: PortfolioCostVarianceProjectCard;
}) {
  return (
    <div className={styles.varianceProjectCard}>
      <div className={styles.varianceCardHeader}>
        <span className={styles.projectName}>{card.project_name}</span>
        <span
          className={`${styles.healthBadge} ${varianceStatusBadgeClass(card.variance_status)}`}
        >
          {varianceStatusLabel(card.variance_status)}
        </span>
      </div>
      <div className={styles.projectStats}>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Baseline</span>
          <span className={styles.statValue}>
            {formatCurrency(card.baseline_total)}
          </span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Comparison</span>
          <span className={styles.statValue}>
            {formatCurrency(card.comparison_total)}
          </span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Variance</span>
          <span
            className={`${styles.statValue} ${varianceAmountClass(card.variance_status)}`}
          >
            {formatVarianceAmount(card.variance_amount)}
          </span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Variance %</span>
          <span
            className={`${styles.statValue} ${varianceAmountClass(card.variance_status)}`}
          >
            {formatVariancePct(card.variance_pct)}
          </span>
        </div>
      </div>
      {card.latest_comparison_stage && (
        <div className={styles.varianceCardStage}>
          Stage: {card.latest_comparison_stage.replace(/_/g, " ")}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export function PortfolioCostVariancePanel({
  data,
}: PortfolioCostVariancePanelProps) {
  const { summary, top_overruns, top_savings, flags } = data;

  if (summary.projects_with_comparison_sets === 0) {
    return (
      <div className={styles.panelCard}>
        <h2 className={styles.panelTitle}>Cost Variance</h2>
        <p className={styles.panelEmpty}>
          No active tender comparison sets found. Add comparison sets to
          projects to see portfolio cost variance.
        </p>
      </div>
    );
  }

  const summaryVarianceStatus: PortfolioVarianceStatus =
    summary.total_variance_amount > 0
      ? "overrun"
      : summary.total_variance_amount < 0
        ? "saving"
        : "neutral";

  return (
    <div className={styles.panelCard}>
      <h2 className={styles.panelTitle}>Cost Variance</h2>

      {/* Portfolio-wide summary strip */}
      <div
        className={styles.metricsRow}
        aria-label="Portfolio cost variance summary"
      >
        <div className={styles.metricItem}>
          <span className={styles.metricLabel}>Projects with Sets</span>
          <span className={styles.metricValue}>
            {summary.projects_with_comparison_sets}
          </span>
        </div>
        <div className={styles.metricItem}>
          <span className={styles.metricLabel}>Total Baseline</span>
          <span className={styles.metricValue}>
            {formatCurrency(summary.total_baseline_amount)}
          </span>
        </div>
        <div className={styles.metricItem}>
          <span className={styles.metricLabel}>Total Comparison</span>
          <span className={styles.metricValue}>
            {formatCurrency(summary.total_comparison_amount)}
          </span>
        </div>
        <div className={styles.metricItem}>
          <span className={styles.metricLabel}>Total Variance</span>
          <span
            className={`${styles.metricValue} ${varianceAmountClass(summaryVarianceStatus)}`}
          >
            {formatVarianceAmount(summary.total_variance_amount)}
          </span>
        </div>
        <div className={styles.metricItem}>
          <span className={styles.metricLabel}>Variance %</span>
          <span
            className={`${styles.metricValue} ${varianceAmountClass(summaryVarianceStatus)}`}
          >
            {formatVariancePct(summary.total_variance_pct)}
          </span>
        </div>
      </div>

      {/* Top overruns */}
      {top_overruns.length > 0 && (
        <section className={styles.varianceSection}>
          <h3 className={styles.varianceSectionTitle}>Top Overruns</h3>
          <div className={styles.varianceCardGrid}>
            {top_overruns.map((card) => (
              <VarianceProjectCard key={card.project_id} card={card} />
            ))}
          </div>
        </section>
      )}

      {/* Top savings */}
      {top_savings.length > 0 && (
        <section className={styles.varianceSection}>
          <h3 className={styles.varianceSectionTitle}>Top Savings</h3>
          <div className={styles.varianceCardGrid}>
            {top_savings.map((card) => (
              <VarianceProjectCard key={card.project_id} card={card} />
            ))}
          </div>
        </section>
      )}

      {/* Cost variance flags */}
      {flags.length > 0 && (
        <section className={styles.varianceSection}>
          <h3 className={styles.varianceSectionTitle}>Variance Flags</h3>
          <ul
            className={styles.riskFlagList}
            aria-label="Cost variance flags"
          >
            {flags.map((flag, idx) => (
              <li
                key={`${flag.flag_type}-${flag.affected_project_id ?? "portfolio"}-${idx}`}
                className={styles.riskFlagItem}
              >
                <span
                  className={`${styles.riskSeverityBadge} ${
                    flag.flag_type === "major_overrun"
                      ? styles.severityCritical
                      : flag.flag_type === "major_saving"
                        ? styles.severityWarning
                        : styles.severityWarning
                  }`}
                >
                  {flag.flag_type === "major_overrun"
                    ? "Overrun"
                    : flag.flag_type === "major_saving"
                      ? "Saving"
                      : "Missing Data"}
                </span>
                <div className={styles.riskFlagBody}>
                  <span className={styles.riskFlagDescription}>
                    {flag.description}
                  </span>
                  {flag.affected_project_name && (
                    <span className={styles.riskFlagProject}>
                      {flag.affected_project_name}
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
