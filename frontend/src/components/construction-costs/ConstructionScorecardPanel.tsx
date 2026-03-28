/**
 * ConstructionScorecardPanel — project construction health scorecard.
 *
 * Displays baseline-vs-actual cost variance, contingency pressure, and
 * overall construction health status for a single project.
 *
 * Design principles:
 *   - All status values are sourced from the backend; no re-scoring here.
 *   - Renders an explicit incomplete state when has_approved_baseline is false.
 *   - Uses construction.module.css + portfolio.module.css class patterns.
 */

"use client";

import React, { useEffect, useState } from "react";
import { getProjectConstructionScorecard } from "@/lib/construction-scorecard-api";
import type { ConstructionProjectScorecard, ConstructionHealthStatus } from "@/lib/construction-scorecard-types";
import styles from "@/styles/construction.module.css";
import portfolioStyles from "@/styles/portfolio.module.css";

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

function fmtVariance(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const num = parseFloat(value);
  if (isNaN(num)) return "—";
  const sign = num > 0 ? "+" : "";
  return `${sign}${num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
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
  if (status === "healthy") return portfolioStyles.badgeSaving;
  if (status === "warning") return portfolioStyles.badgeNeutral;
  if (status === "critical") return portfolioStyles.badgeOverrun;
  return portfolioStyles.badgeNeutral;
}

function statusSeverityClass(status: ConstructionHealthStatus): string {
  if (status === "critical") return portfolioStyles.severityCritical;
  if (status === "warning") return portfolioStyles.severityWarning;
  return portfolioStyles.severityWarning;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface MetricRowProps {
  label: string;
  value: string;
  className?: string;
}

function MetricRow({ label, value, className }: MetricRowProps) {
  return (
    <div className={portfolioStyles.statItem}>
      <span className={portfolioStyles.statLabel}>{label}</span>
      <span className={`${portfolioStyles.statValue}${className ? ` ${className}` : ""}`}>
        {value}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

interface ConstructionScorecardPanelProps {
  projectId: string;
}

export function ConstructionScorecardPanel({
  projectId,
}: ConstructionScorecardPanelProps) {
  const [scorecard, setScorecard] = useState<ConstructionProjectScorecard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId || projectId === "_") {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    const controller = new AbortController();
    getProjectConstructionScorecard(projectId)
      .then((data) => {
        if (controller.signal.aborted) return;
        setScorecard(data);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load construction scorecard.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [projectId]);

  return (
    <div className={portfolioStyles.panelCard}>
      <h2 className={portfolioStyles.panelTitle}>Construction Health Scorecard</h2>

      {loading ? (
        <p className={styles.summaryEmpty}>Loading scorecard…</p>
      ) : error ? (
        <p className={styles.summaryEmpty} role="alert">
          {error}
        </p>
      ) : !scorecard ? null : !scorecard.has_approved_baseline ? (
        <div data-testid="scorecard-incomplete">
          <p className={portfolioStyles.panelEmpty}>
            No approved baseline found for this project. Approve a tender
            comparison baseline to unlock the construction health scorecard.
          </p>
          <div className={portfolioStyles.metricsRow}>
            <MetricRow
              label="Current Forecast (AED)"
              value={fmt(scorecard.current_forecast_amount)}
            />
            <MetricRow
              label="Contingency (AED)"
              value={fmt(scorecard.contingency_amount)}
            />
          </div>
        </div>
      ) : (
        <div data-testid="scorecard-full">
          {/* Overall health badge */}
          <div className={portfolioStyles.varianceCardHeader} style={{ marginBottom: 16 }}>
            <span className={portfolioStyles.projectName}>Overall Health</span>
            <span
              className={`${portfolioStyles.healthBadge} ${statusBadgeClass(scorecard.overall_health_status)}`}
            >
              {statusLabel(scorecard.overall_health_status)}
            </span>
          </div>

          {/* Cost metrics */}
          <section className={portfolioStyles.varianceSection}>
            <h3 className={portfolioStyles.varianceSectionTitle}>Cost</h3>
            <div className={portfolioStyles.metricsRow} aria-label="Cost metrics">
              <MetricRow
                label="Approved Baseline (AED)"
                value={fmt(scorecard.approved_baseline_amount)}
              />
              <MetricRow
                label="Current Forecast (AED)"
                value={fmt(scorecard.current_forecast_amount)}
              />
              <MetricRow
                label="Variance (AED)"
                value={fmtVariance(scorecard.cost_variance_amount)}
                className={
                  scorecard.cost_variance_amount !== null && parseFloat(scorecard.cost_variance_amount) > 0
                    ? portfolioStyles.varianceOverrun
                    : scorecard.cost_variance_amount !== null && parseFloat(scorecard.cost_variance_amount) < 0
                      ? portfolioStyles.varianceSaving
                      : portfolioStyles.varianceNeutral
                }
              />
              <MetricRow
                label="Variance %"
                value={fmtPct(scorecard.cost_variance_pct)}
                className={
                  scorecard.cost_variance_amount !== null && parseFloat(scorecard.cost_variance_amount) > 0
                    ? portfolioStyles.varianceOverrun
                    : scorecard.cost_variance_amount !== null && parseFloat(scorecard.cost_variance_amount) < 0
                      ? portfolioStyles.varianceSaving
                      : portfolioStyles.varianceNeutral
                }
              />
            </div>
            <div style={{ marginTop: 8 }}>
              <span
                className={`${portfolioStyles.riskSeverityBadge} ${statusSeverityClass(scorecard.cost_status)}`}
                aria-label={`Cost status: ${statusLabel(scorecard.cost_status)}`}
              >
                {statusLabel(scorecard.cost_status)}
              </span>
            </div>
          </section>

          {/* Contingency metrics */}
          <section className={portfolioStyles.varianceSection}>
            <h3 className={portfolioStyles.varianceSectionTitle}>Contingency</h3>
            <div className={portfolioStyles.metricsRow} aria-label="Contingency metrics">
              <MetricRow
                label="Contingency (AED)"
                value={fmt(scorecard.contingency_amount)}
              />
              <MetricRow
                label="Contingency Pressure"
                value={fmtPct(scorecard.contingency_pressure_pct)}
              />
            </div>
            <div style={{ marginTop: 8 }}>
              <span
                className={`${portfolioStyles.riskSeverityBadge} ${statusSeverityClass(scorecard.contingency_status)}`}
                aria-label={`Contingency status: ${statusLabel(scorecard.contingency_status)}`}
              >
                {statusLabel(scorecard.contingency_status)}
              </span>
            </div>
          </section>

          {/* Baseline metadata */}
          {scorecard.approved_at && (
            <p className={styles.summaryEmpty} style={{ fontSize: "0.75rem", marginTop: 8 }}>
              Baseline approved:{" "}
              {new Date(scorecard.approved_at).toLocaleDateString()}
              {scorecard.last_updated_at &&
                ` · Last updated: ${new Date(scorecard.last_updated_at).toLocaleDateString()}`}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
