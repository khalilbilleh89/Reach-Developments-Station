"use client";

/**
 * PortfolioExecutionOutcomesPanel.tsx
 *
 * Portfolio Execution Outcomes summary panel (PR-V7-10).
 *
 * Shows:
 *  - Portfolio outcome result KPI counts
 *  - Projects with completed triggers awaiting outcome recording
 *  - Recent recorded outcomes with project names and comparison badges
 *
 * Design principles:
 *  - All values are sourced from the backend; no recomputation here.
 *  - Renders a safe empty state when no data exists.
 *  - Read-only: displays outcome information only, no mutation controls.
 *
 * PR-V7-10 — Execution Outcome Capture & Feedback Loop Closure
 */

import React, { useEffect, useRef, useState } from "react";
import { getPortfolioExecutionOutcomes } from "@/lib/strategy-execution-outcome-api";
import type {
  MatchStatus,
  OutcomeResult,
  PortfolioExecutionOutcomeSummaryResponse,
  PortfolioOutcomeEntry,
  PortfolioOutcomeProjectEntry,
} from "@/lib/strategy-execution-outcome-types";
import styles from "@/styles/portfolio.module.css";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function outcomeResultLabel(result: OutcomeResult): string {
  switch (result) {
    case "matched_strategy":
      return "Matched";
    case "partially_matched":
      return "Partial";
    case "diverged":
      return "Diverged";
    case "cancelled_execution":
      return "Cancelled";
    case "insufficient_data":
      return "No Data";
  }
}

function outcomeResultBadgeClass(result: OutcomeResult): string {
  switch (result) {
    case "matched_strategy":
      return styles.badgeSaving;
    case "partially_matched":
      return styles.badgeNeedsAttention;
    case "diverged":
      return styles.badgeOverrun;
    case "cancelled_execution":
      return styles.badgeNeutral;
    case "insufficient_data":
      return styles.badgeNeutral;
  }
}

function matchStatusBadgeClass(status: MatchStatus): string {
  switch (status) {
    case "exact_match":
      return styles.badgeSaving;
    case "minor_variance":
      return styles.badgeNeedsAttention;
    case "major_variance":
      return styles.badgeOverrun;
    case "no_comparable_strategy":
      return styles.badgeNeutral;
  }
}

function matchStatusLabel(status: MatchStatus): string {
  switch (status) {
    case "exact_match":
      return "Exact Match";
    case "minor_variance":
      return "Minor Variance";
    case "major_variance":
      return "Major Variance";
    case "no_comparable_strategy":
      return "No Comparable";
  }
}

function fmtDatetime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// KPI summary strip
// ---------------------------------------------------------------------------

interface KpiItem {
  label: string;
  value: string;
  testId: string;
}

function KpiStrip({ items }: { items: KpiItem[] }) {
  return (
    <div className={styles.kpiCard} data-testid="outcome-kpi-strip">
      {items.map((kpi) => (
        <div key={kpi.label}>
          <div className={styles.kpiLabel}>{kpi.label}</div>
          <div className={styles.kpiValue} data-testid={kpi.testId}>
            {kpi.value}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Recent outcome card
// ---------------------------------------------------------------------------

function RecentOutcomeCard({ entry }: { entry: PortfolioOutcomeEntry }) {
  const { outcome } = entry;
  return (
    <div
      style={{
        padding: 12,
        border: "1px solid var(--color-border, #e5e7eb)",
        borderRadius: 8,
        background: "var(--color-surface, #ffffff)",
        marginBottom: 8,
      }}
      data-testid="recent-outcome-card"
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 6,
        }}
      >
        <span
          style={{ fontWeight: 700, fontSize: "0.875rem" }}
          data-testid="outcome-project-name"
        >
          {entry.project_name}
        </span>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <span
            className={outcomeResultBadgeClass(outcome.outcome_result)}
            data-testid="outcome-result-badge"
          >
            {outcomeResultLabel(outcome.outcome_result)}
          </span>
          <span
            className={matchStatusBadgeClass(outcome.comparison.match_status)}
            data-testid="outcome-match-badge"
          >
            {matchStatusLabel(outcome.comparison.match_status)}
          </span>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
          gap: 6,
          fontSize: "0.75rem",
        }}
      >
        <div>
          <span style={{ color: "var(--color-text-muted, #6b7280)" }}>
            Recorded{" "}
          </span>
          <span style={{ fontWeight: 600 }} data-testid="outcome-recorded-at">
            {fmtDatetime(outcome.recorded_at)}
          </span>
        </div>
        <div>
          <span style={{ color: "var(--color-text-muted, #6b7280)" }}>
            By{" "}
          </span>
          <span style={{ fontWeight: 600 }} data-testid="outcome-recorded-by">
            {outcome.recorded_by_user_id}
          </span>
        </div>
        {outcome.has_material_divergence && (
          <div>
            <span
              style={{
                background: "#fee2e2",
                color: "#b91c1c",
                padding: "1px 8px",
                borderRadius: 10,
                fontWeight: 600,
                fontSize: "0.7rem",
              }}
              data-testid="material-divergence-badge"
            >
              Material Divergence
            </span>
          </div>
        )}
      </div>

      {outcome.comparison.divergence_summary &&
        outcome.comparison.match_status !== "exact_match" &&
        outcome.comparison.match_status !== "no_comparable_strategy" && (
          <div
            style={{
              marginTop: 6,
              fontSize: "0.7rem",
              color: "var(--color-text-muted, #6b7280)",
            }}
            data-testid="outcome-divergence-summary"
          >
            {outcome.comparison.divergence_summary}
          </div>
        )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Awaiting outcome card
// ---------------------------------------------------------------------------

function AwaitingOutcomeCard({ entry }: { entry: PortfolioOutcomeProjectEntry }) {
  return (
    <div
      style={{
        padding: 10,
        border: "1px solid var(--color-border, #e5e7eb)",
        borderRadius: 6,
        background: "var(--color-surface-subtle, #f9fafb)",
        marginBottom: 6,
        fontSize: "0.875rem",
        display: "flex",
        alignItems: "center",
        gap: 8,
      }}
      data-testid="awaiting-outcome-card"
    >
      <span
        style={{ fontWeight: 600 }}
        data-testid="awaiting-outcome-project-name"
      >
        {entry.project_name}
      </span>
      <span
        className={styles.badgeNeedsAttention}
        style={{ fontSize: "0.7rem" }}
      >
        Awaiting Outcome
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function PortfolioExecutionOutcomesPanel() {
  const [summary, setSummary] =
    useState<PortfolioExecutionOutcomeSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    getPortfolioExecutionOutcomes(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setSummary(data);
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load portfolio execution outcomes.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, []);

  // ------------------------------------------------------------------
  // Render states
  // ------------------------------------------------------------------

  if (loading) {
    return (
      <section
        aria-label="Portfolio Execution Outcomes"
        style={{
          padding: 16,
          color: "var(--color-text-muted, #6b7280)",
          fontSize: "0.875rem",
        }}
        data-testid="portfolio-outcome-loading"
      >
        Loading portfolio execution outcomes…
      </section>
    );
  }

  if (error) {
    return (
      <section
        aria-label="Portfolio Execution Outcomes"
        style={{ padding: 16, color: "#b91c1c", fontSize: "0.875rem" }}
        data-testid="portfolio-outcome-error"
      >
        {error}
      </section>
    );
  }

  if (!summary) {
    return null;
  }

  const kpis: KpiItem[] = [
    {
      label: "Matched",
      value: String(summary.matched_strategy_count),
      testId: "kpi-matched",
    },
    {
      label: "Partial",
      value: String(summary.partially_matched_count),
      testId: "kpi-partial",
    },
    {
      label: "Diverged",
      value: String(summary.diverged_count),
      testId: "kpi-diverged",
    },
    {
      label: "Cancelled",
      value: String(summary.cancelled_execution_count),
      testId: "kpi-cancelled",
    },
    {
      label: "Awaiting Outcome",
      value: String(summary.awaiting_outcome_count),
      testId: "kpi-awaiting",
    },
  ];

  return (
    <section
      aria-label="Portfolio Execution Outcomes"
      style={{
        padding: 16,
        border: "1px solid var(--color-border, #e5e7eb)",
        borderRadius: 8,
        background: "var(--color-surface, #ffffff)",
      }}
      data-testid="portfolio-outcomes-panel"
    >
      <h3
        style={{
          fontSize: "1rem",
          fontWeight: 700,
          margin: "0 0 16px",
          color: "var(--color-text)",
        }}
      >
        Portfolio Execution Outcomes
      </h3>

      {/* KPI counts */}
      <KpiStrip items={kpis} />

      {/* Projects awaiting outcome recording */}
      {summary.awaiting_outcome_count > 0 && (
        <div style={{ marginTop: 20 }} data-testid="awaiting-outcomes-section">
          <h4
            style={{
              fontSize: "0.875rem",
              fontWeight: 700,
              margin: "0 0 10px",
              color: "var(--color-text)",
            }}
          >
            Awaiting Outcome Recording
            <span
              style={{
                marginLeft: 8,
                fontSize: "0.75rem",
                color: "var(--color-text-muted, #6b7280)",
                fontWeight: 400,
              }}
            >
              ({summary.awaiting_outcome_count})
            </span>
          </h4>
          <div>
            {summary.awaiting_outcome_projects.map((entry) => (
              <AwaitingOutcomeCard
                key={entry.trigger_id}
                entry={entry}
              />
            ))}
          </div>
        </div>
      )}

      {/* Recent recorded outcomes */}
      <div style={{ marginTop: 20 }} data-testid="recent-outcomes-section">
        <h4
          style={{
            fontSize: "0.875rem",
            fontWeight: 700,
            margin: "0 0 10px",
            color: "var(--color-text)",
          }}
        >
          Recent Outcomes
          {summary.recent_outcomes.length > 0 && (
            <span
              style={{
                marginLeft: 8,
                fontSize: "0.75rem",
                color: "var(--color-text-muted, #6b7280)",
                fontWeight: 400,
              }}
            >
              ({summary.recent_outcomes.length})
            </span>
          )}
        </h4>
        {summary.recent_outcomes.length === 0 ? (
          <p
            style={{
              fontSize: "0.875rem",
              color: "var(--color-text-muted, #6b7280)",
              margin: 0,
            }}
            data-testid="no-recent-outcomes"
          >
            No execution outcomes have been recorded yet.
          </p>
        ) : (
          <div>
            {summary.recent_outcomes.map((entry) => (
              <RecentOutcomeCard key={entry.outcome.id} entry={entry} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
