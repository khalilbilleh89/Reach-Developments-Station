"use client";

/**
 * PortfolioExecutionPackagesPanel.tsx
 *
 * Portfolio Execution Packages panel (PR-V7-07).
 *
 * Shows:
 *  - Portfolio execution package summary KPIs
 *  - Top 5 projects ready for review
 *  - Top 5 blocked projects (dependency resolution needed)
 *  - Top 5 high-risk packages (caution required)
 *  - All project execution package cards
 *
 * Design principles:
 *  - All values are sourced from the backend; no recomputation here.
 *  - Renders a safe empty state when no data exists.
 *  - Read-only: no mutation controls.
 *
 * PR-V7-07 — Strategy Execution Package Generator
 */

import React from "react";
import type {
  ExecutionReadiness,
  PortfolioExecutionPackageResponse,
  PortfolioExecutionPackageSummary,
  PortfolioPackagedInterventionCard,
} from "@/lib/strategy-execution-package-types";
import styles from "@/styles/portfolio.module.css";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function readinessLabel(readiness: ExecutionReadiness): string {
  switch (readiness) {
    case "ready_for_review":
      return "Ready";
    case "blocked_by_dependency":
      return "Blocked";
    case "caution_required":
      return "Caution";
    case "insufficient_data":
      return "No Data";
  }
}

function readinessBadgeClass(readiness: ExecutionReadiness): string {
  switch (readiness) {
    case "ready_for_review":
      return styles.badgeSaving;
    case "blocked_by_dependency":
      return styles.badgeOverrun;
    case "caution_required":
      return styles.badgeNeedsAttention;
    case "insufficient_data":
      return styles.badgeNeutral;
  }
}

// ---------------------------------------------------------------------------
// Summary strip
// ---------------------------------------------------------------------------

function ExecutionPackageSummaryStrip({
  summary,
}: {
  summary: PortfolioExecutionPackageSummary;
}) {
  const kpis = [
    {
      label: "Total Projects",
      value: String(summary.total_projects),
      testId: "exec-pkg-total",
    },
    {
      label: "Ready for Review",
      value: String(summary.ready_for_review_count),
      testId: "exec-pkg-ready",
    },
    {
      label: "Blocked",
      value: String(summary.blocked_count),
      testId: "exec-pkg-blocked",
    },
    {
      label: "Caution Required",
      value: String(summary.caution_required_count),
      testId: "exec-pkg-caution",
    },
    {
      label: "No Data",
      value: String(summary.insufficient_data_count),
      testId: "exec-pkg-no-data",
    },
  ];

  return (
    <div
      className={styles.summaryStrip}
      data-testid="exec-pkg-summary-strip"
    >
      {kpis.map(({ label, value, testId }) => (
        <div key={label} className={styles.kpiCard}>
          <div className={styles.kpiValue} data-testid={testId}>
            {value}
          </div>
          <div className={styles.kpiLabel}>{label}</div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Package card
// ---------------------------------------------------------------------------

function PackagedInterventionCard({
  card,
}: {
  card: PortfolioPackagedInterventionCard;
}) {
  return (
    <div
      className={styles.varianceProjectCard}
      data-testid={`exec-pkg-card-${card.project_id}`}
    >
      <div className={styles.varianceCardHeader}>
        <span className={styles.projectName}>{card.project_name}</span>
        <span
          className={`${styles.healthBadge} ${readinessBadgeClass(card.execution_readiness)}`}
          data-testid={`exec-pkg-readiness-badge-${card.project_id}`}
        >
          {readinessLabel(card.execution_readiness)}
        </span>
      </div>
      <div className={styles.varianceCardGrid}>
        <div>
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
            Urgency
          </div>
          <div
            data-testid={`exec-pkg-urgency-${card.project_id}`}
            style={{ fontWeight: 700 }}
          >
            {card.urgency_score}
          </div>
        </div>
        <div>
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
            Strategy
          </div>
          <div style={{ fontWeight: 600 }}>
            {card.recommended_strategy ?? "—"}
          </div>
        </div>
        <div>
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
            Review Needed
          </div>
          <div
            data-testid={`exec-pkg-review-${card.project_id}`}
            style={{ fontWeight: 600 }}
          >
            {card.requires_manual_review ? "Yes" : "No"}
          </div>
        </div>
      </div>
      {card.next_best_action && (
        <div
          style={{ marginTop: 8, fontSize: "0.75rem", color: "var(--color-text-muted)", fontStyle: "italic" }}
          data-testid={`exec-pkg-next-action-${card.project_id}`}
        >
          Next: {card.next_best_action}
        </div>
      )}
      {card.blockers.length > 0 && (
        <div
          style={{ marginTop: 4, fontSize: "0.75rem", color: "#b91c1c" }}
          data-testid={`exec-pkg-blockers-${card.project_id}`}
        >
          Blocked by: {card.blockers.join(", ")}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Package card list (generic)
// ---------------------------------------------------------------------------

function PackageCardList({
  title,
  cards,
  emptyNote,
  testId,
}: {
  title: string;
  cards: PortfolioPackagedInterventionCard[];
  emptyNote: string;
  testId?: string;
}) {
  return (
    <div style={{ marginTop: 20 }} data-testid={testId}>
      <h4
        style={{
          fontSize: "0.9375rem",
          fontWeight: 600,
          margin: "0 0 12px",
          color: "var(--color-text)",
        }}
      >
        {title}
      </h4>
      {cards.length === 0 ? (
        <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)", fontStyle: "italic" }}>
          {emptyNote}
        </p>
      ) : (
        <div className={styles.varianceCardGrid}>
          {cards.map((card) => (
            <PackagedInterventionCard key={card.project_id} card={card} />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface PortfolioExecutionPackagesPanelProps {
  data: PortfolioExecutionPackageResponse;
}

export function PortfolioExecutionPackagesPanel({
  data,
}: PortfolioExecutionPackagesPanelProps) {
  if (data.packages.length === 0) {
    return (
      <section data-testid="portfolio-execution-packages-panel">
        <h3
          style={{
            fontSize: "1.0625rem",
            fontWeight: 600,
            margin: "0 0 8px",
            color: "var(--color-text)",
          }}
        >
          Portfolio Execution Packages
        </h3>
        <p
          style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}
          data-testid="exec-pkg-empty-state"
        >
          No projects found. Add projects and feasibility data to see portfolio
          execution packages.
        </p>
      </section>
    );
  }

  return (
    <section data-testid="portfolio-execution-packages-panel">
      <h3
        style={{
          fontSize: "1.0625rem",
          fontWeight: 600,
          margin: "0 0 4px",
          color: "var(--color-text)",
        }}
      >
        Portfolio Execution Packages
      </h3>
      <p
        style={{
          fontSize: "0.8125rem",
          color: "var(--color-text-muted)",
          margin: "0 0 16px",
        }}
      >
        Execution-ready action packaging — ordered by readiness and urgency. Read-only.
      </p>

      <ExecutionPackageSummaryStrip summary={data.summary} />

      {data.top_ready_actions.length > 0 && (
        <PackageCardList
          title="Ready for Review"
          cards={data.top_ready_actions}
          emptyNote="No projects ready for review."
          testId="exec-pkg-top-ready-section"
        />
      )}

      {data.top_high_risk_packages.length > 0 && (
        <PackageCardList
          title="Caution Required"
          cards={data.top_high_risk_packages}
          emptyNote="No caution packages."
          testId="exec-pkg-top-caution-section"
        />
      )}

      {data.top_blocked_actions.length > 0 && (
        <PackageCardList
          title="Blocked Projects"
          cards={data.top_blocked_actions}
          emptyNote="No blocked projects."
          testId="exec-pkg-top-blocked-section"
        />
      )}

      {data.packages.length > 0 && (
        <PackageCardList
          title="All Projects"
          cards={data.packages}
          emptyNote="No execution package data."
          testId="exec-pkg-all-projects"
        />
      )}
    </section>
  );
}
