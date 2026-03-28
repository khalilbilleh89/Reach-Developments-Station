"use client";

/**
 * PortfolioPhasingInsightsPanel.tsx
 *
 * Portfolio-wide phasing intelligence panel (PR-V7-03).
 *
 * Shows:
 *  - Portfolio phasing summary KPIs
 *  - Top phase opportunities (projects to prepare next phase)
 *  - Top release risks (hold/delay projects)
 *  - Per-project phasing cards with status and urgency
 *
 * Design principles:
 *  - All values are sourced from the backend; no recomputation here.
 *  - Renders a safe empty state when no data exists.
 *  - Color conventions: green = release/prepare opportunity, red = hold/defer risk, blue = maintain.
 *
 * PR-V7-03 — Phasing Optimization Engine (Inventory Release & Stage-Gate Recommendations)
 */

import React from "react";
import type {
  CurrentPhaseRecommendation,
  NextPhaseRecommendation,
  PortfolioPhasingInsightsResponse,
  PortfolioPhasingInsightsSummary,
  PortfolioPhasingProjectCard,
  ReleaseUrgency,
} from "@/lib/phasing-optimization-types";
import styles from "@/styles/portfolio.module.css";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function currentRecLabel(rec: CurrentPhaseRecommendation): string {
  if (rec === "release_more_inventory") return "Release More";
  if (rec === "maintain_current_release") return "Maintain";
  if (rec === "hold_current_inventory") return "Hold";
  if (rec === "delay_further_release") return "Delay Release";
  return "No Data";
}

function nextRecLabel(rec: NextPhaseRecommendation): string {
  if (rec === "prepare_next_phase") return "Prepare Next Phase";
  if (rec === "do_not_open_next_phase") return "Hold Next Phase";
  if (rec === "defer_next_phase") return "Defer Next Phase";
  if (rec === "not_applicable") return "N/A";
  return "Insufficient Data";
}

function currentRecBadgeClass(rec: CurrentPhaseRecommendation): string {
  if (rec === "release_more_inventory") return styles.badgeSaving;
  if (rec === "hold_current_inventory" || rec === "delay_further_release") return styles.badgeOverrun;
  return styles.badgeNeutral;
}

function nextRecBadgeClass(rec: NextPhaseRecommendation): string {
  if (rec === "prepare_next_phase") return styles.badgeSaving;
  if (rec === "defer_next_phase") return styles.badgeOverrun;
  return styles.badgeNeutral;
}

function urgencyLabel(urgency: ReleaseUrgency): string {
  if (urgency === "high") return "High";
  if (urgency === "medium") return "Medium";
  if (urgency === "low") return "Low";
  return "—";
}

function fmtSellThrough(pct: number | null): string {
  if (pct == null) return "—";
  return `${pct.toFixed(1)}%`;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function PhasingSummaryStrip({
  summary,
}: {
  summary: PortfolioPhasingInsightsSummary;
}) {
  const kpis = [
    {
      label: "Total Projects",
      value: String(summary.total_projects),
      testId: "phasing-total-projects",
    },
    {
      label: "Prepare Next Phase",
      value: String(summary.projects_prepare_next_phase_count),
      color: "#15803d",
      testId: "phasing-prepare-count",
    },
    {
      label: "Hold Inventory",
      value: String(summary.projects_hold_inventory_count),
      color: "#b91c1c",
      testId: "phasing-hold-count",
    },
    {
      label: "Delay Release",
      value: String(summary.projects_delay_release_count),
      color: "#b91c1c",
      testId: "phasing-delay-count",
    },
    {
      label: "Insufficient Data",
      value: String(summary.projects_insufficient_data_count),
      color: "var(--color-text-muted)",
      testId: "phasing-insufficient-count",
    },
  ];

  return (
    <div className={styles.summaryStrip}>
      {kpis.map((kpi) => (
        <div key={kpi.label} className={styles.kpiCard} data-testid={kpi.testId}>
          <span className={styles.kpiValue} style={{ color: kpi.color }}>
            {kpi.value}
          </span>
          <span className={styles.kpiLabel}>{kpi.label}</span>
        </div>
      ))}
    </div>
  );
}

function PhasingProjectCard({ card }: { card: PortfolioPhasingProjectCard }) {
  return (
    <div
      className={styles.varianceProjectCard}
      data-testid={`phasing-card-${card.project_id}`}
    >
      <div className={styles.varianceCardHeader}>
        <span className={styles.projectName}>{card.project_name}</span>
        <span
          className={`${styles.healthBadge} ${currentRecBadgeClass(card.current_phase_recommendation)}`}
          data-testid={`current-rec-badge-${card.project_id}`}
        >
          {currentRecLabel(card.current_phase_recommendation)}
        </span>
      </div>
      <div className={styles.projectStats}>
        {card.sell_through_pct != null && (
          <span>{fmtSellThrough(card.sell_through_pct)} sell-through</span>
        )}
        <span
          className={`${styles.healthBadge} ${nextRecBadgeClass(card.next_phase_recommendation)}`}
          data-testid={`next-rec-badge-${card.project_id}`}
        >
          {nextRecLabel(card.next_phase_recommendation)}
        </span>
        {card.release_urgency !== "none" && (
          <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
            Urgency: {urgencyLabel(card.release_urgency)}
          </span>
        )}
      </div>
    </div>
  );
}

function ProjectCardList({
  title,
  cards,
  emptyNote,
  testId,
}: {
  title: string;
  cards: PortfolioPhasingProjectCard[];
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
        <p
          style={{
            fontSize: "0.875rem",
            color: "var(--color-text-muted)",
            fontStyle: "italic",
          }}
        >
          {emptyNote}
        </p>
      ) : (
        <div className={styles.varianceCardGrid}>
          {cards.map((card) => (
            <PhasingProjectCard key={card.project_id} card={card} />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface PortfolioPhasingInsightsPanelProps {
  data: PortfolioPhasingInsightsResponse;
}

export function PortfolioPhasingInsightsPanel({
  data,
}: PortfolioPhasingInsightsPanelProps) {
  if (data.projects.length === 0) {
    return (
      <section data-testid="portfolio-phasing-panel">
        <h3
          style={{
            fontSize: "1.0625rem",
            fontWeight: 600,
            margin: "0 0 8px",
            color: "var(--color-text)",
          }}
        >
          Phasing Intelligence
        </h3>
        <p
          style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}
          data-testid="phasing-empty-state"
        >
          No projects found. Add projects and phase data to see phasing intelligence.
        </p>
      </section>
    );
  }

  return (
    <section data-testid="portfolio-phasing-panel">
      <h3
        style={{
          fontSize: "1.0625rem",
          fontWeight: 600,
          margin: "0 0 4px",
          color: "var(--color-text)",
        }}
      >
        Phasing Intelligence
      </h3>
      <p
        style={{
          fontSize: "0.8125rem",
          color: "var(--color-text-muted)",
          margin: "0 0 16px",
        }}
      >
        Deterministic release-strategy recommendations — recommendations only, no phase records
        mutated
      </p>

      <PhasingSummaryStrip summary={data.summary} />

      {data.top_phase_opportunities.length > 0 && (
        <ProjectCardList
          title="Phase Opportunities (Prepare Next Phase)"
          cards={data.top_phase_opportunities}
          emptyNote="No projects ready to prepare next phase."
          testId="top-phase-opportunities"
        />
      )}

      {data.top_release_risks.length > 0 && (
        <ProjectCardList
          title="Release Risks (Hold / Delay)"
          cards={data.top_release_risks}
          emptyNote="No release risk projects identified."
          testId="top-release-risks"
        />
      )}

      {data.projects.length > 0 && (
        <ProjectCardList
          title="All Projects"
          cards={data.projects}
          emptyNote="No projects with phasing data."
          testId="all-phasing-projects"
        />
      )}
    </section>
  );
}
