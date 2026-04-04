"use client";

/**
 * PortfolioAutoStrategyPanel.tsx
 *
 * Portfolio Auto-Strategy & Intervention Prioritization panel (PR-V7-06).
 *
 * Shows:
 *  - Portfolio intervention summary KPIs
 *  - Top 5 portfolio actions by urgency
 *  - Top 5 high-risk projects
 *  - Top 5 upside opportunities by best IRR
 *  - All project intervention cards
 *
 * Design principles:
 *  - All values are sourced from the backend; no recomputation here.
 *  - Renders a safe empty state when no data exists.
 *  - Intervention priority badges: red = urgent, orange = recommended,
 *    yellow = monitor, green = stable, grey = no data.
 *
 * PR-V7-06 — Portfolio Auto-Strategy & Intervention Prioritization
 */

import React from "react";
import type {
  InterventionPriority,
  InterventionType,
  PortfolioAutoStrategyResponse,
  PortfolioInterventionProjectCard,
  PortfolioInterventionSummary,
  PortfolioTopActionItem,
} from "@/lib/portfolio-auto-strategy-types";
import styles from "@/styles/portfolio.module.css";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtIrr(irr: number | null): string {
  if (irr == null) return "—";
  return `${(irr * 100).toFixed(2)}%`;
}

function priorityLabel(priority: InterventionPriority): string {
  switch (priority) {
    case "urgent_intervention":
      return "Urgent";
    case "recommended_intervention":
      return "Recommended";
    case "monitor_closely":
      return "Monitor";
    case "stable":
      return "Stable";
    case "insufficient_data":
      return "No Data";
  }
}

function priorityBadgeClass(priority: InterventionPriority): string {
  switch (priority) {
    case "urgent_intervention":
      return styles.badgeOverrun;
    case "recommended_intervention":
      return styles.badgeNeedsAttention;
    case "monitor_closely":
      return styles.badgeNeutral;
    case "stable":
      return styles.badgeSaving;
    case "insufficient_data":
      return styles.badgeNeutral;
  }
}

function interventionTypeLabel(type: InterventionType): string {
  switch (type) {
    case "pricing_intervention":
      return "Pricing";
    case "phasing_intervention":
      return "Phasing";
    case "mixed_intervention":
      return "Mixed";
    case "monitor_only":
      return "Monitor";
    case "insufficient_data":
      return "No Data";
  }
}

// ---------------------------------------------------------------------------
// AutoStrategySummaryStrip
// ---------------------------------------------------------------------------

function AutoStrategySummaryStrip({
  summary,
}: {
  summary: PortfolioInterventionSummary;
}) {
  const kpis = [
    {
      label: "Total Projects",
      value: String(summary.total_projects),
      testId: "auto-strategy-total-projects",
    },
    {
      label: "Analyzed",
      value: String(summary.analyzed_projects),
      testId: "auto-strategy-analyzed",
    },
    {
      label: "Urgent",
      value: String(summary.urgent_intervention_count),
      testId: "auto-strategy-urgent",
    },
    {
      label: "Monitor / Stable",
      value: String(summary.monitor_only_count),
      testId: "auto-strategy-monitor",
    },
    {
      label: "No Data",
      value: String(summary.no_data_count),
      testId: "auto-strategy-no-data",
    },
  ];

  return (
    <div
      className={styles.summaryStrip}
      data-testid="auto-strategy-summary-strip"
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
// InterventionProjectCard
// ---------------------------------------------------------------------------

function InterventionProjectCard({
  card,
}: {
  card: PortfolioInterventionProjectCard;
}) {
  return (
    <div
      className={styles.varianceProjectCard}
      data-testid={`auto-strategy-card-${card.project_id}`}
    >
      <div className={styles.varianceCardHeader}>
        <span className={styles.projectName}>{card.project_name}</span>
        <span
          className={`${styles.healthBadge} ${priorityBadgeClass(card.intervention_priority)}`}
          data-testid={`priority-badge-${card.project_id}`}
        >
          {priorityLabel(card.intervention_priority)}
        </span>
      </div>
      <div className={styles.varianceCardGrid}>
        <div>
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
            Best IRR
          </div>
          <div
            data-testid={`auto-strategy-irr-${card.project_id}`}
            style={{ fontWeight: 700 }}
          >
            {fmtIrr(card.best_irr)}
          </div>
        </div>
        <div>
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
            Intervention
          </div>
          <div style={{ fontWeight: 600 }}>
            {interventionTypeLabel(card.intervention_type)}
          </div>
        </div>
        <div>
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
            Urgency
          </div>
          <div
            data-testid={`urgency-score-${card.project_id}`}
            style={{ fontWeight: 600 }}
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
      </div>
      {card.reason && (
        <div
          style={{
            marginTop: 8,
            fontSize: "0.75rem",
            color: "var(--color-text-muted)",
            fontStyle: "italic",
          }}
          data-testid={`auto-strategy-reason-${card.project_id}`}
        >
          {card.reason}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TopActionItem
// ---------------------------------------------------------------------------

function TopActionRow({ action }: { action: PortfolioTopActionItem }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "8px 0",
        borderBottom: "1px solid var(--color-border-subtle, #e5e7eb)",
      }}
      data-testid={`top-action-${action.project_id}`}
    >
      <span
        className={`${styles.healthBadge} ${priorityBadgeClass(action.intervention_priority)}`}
      >
        {priorityLabel(action.intervention_priority)}
      </span>
      <span style={{ fontWeight: 600, flex: 1 }}>{action.project_name}</span>
      <span
        style={{ fontSize: "0.8125rem", color: "var(--color-text-muted)" }}
      >
        {interventionTypeLabel(action.intervention_type)} · {action.urgency_score}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CardList (generic)
// ---------------------------------------------------------------------------

function CardList({
  title,
  cards,
  emptyNote,
  testId,
}: {
  title: string;
  cards: PortfolioInterventionProjectCard[];
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
            <InterventionProjectCard key={card.project_id} card={card} />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface PortfolioAutoStrategyPanelProps {
  data: PortfolioAutoStrategyResponse;
}

export function PortfolioAutoStrategyPanel({
  data,
}: PortfolioAutoStrategyPanelProps) {
  if (data.project_cards.length === 0) {
    return (
      <section data-testid="portfolio-auto-strategy-panel">
        <h3
          style={{
            fontSize: "1.0625rem",
            fontWeight: 600,
            margin: "0 0 8px",
            color: "var(--color-text)",
          }}
        >
          Portfolio Auto-Strategy
        </h3>
        <p
          style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}
          data-testid="auto-strategy-empty-state"
        >
          No projects found. Add projects and feasibility data to see portfolio
          intervention priorities.
        </p>
      </section>
    );
  }

  return (
    <section data-testid="portfolio-auto-strategy-panel">
      <h3
        style={{
          fontSize: "1.0625rem",
          fontWeight: 600,
          margin: "0 0 4px",
          color: "var(--color-text)",
        }}
      >
        Portfolio Auto-Strategy
      </h3>
      <p
        style={{
          fontSize: "0.8125rem",
          color: "var(--color-text-muted)",
          margin: "0 0 16px",
        }}
      >
        Intervention prioritization — ranked portfolio action guidance. Read-only.
      </p>

      <AutoStrategySummaryStrip summary={data.summary} />

      {data.top_actions.length > 0 && (
        <div style={{ marginTop: 20 }} data-testid="top-actions-section">
          <h4
            style={{
              fontSize: "0.9375rem",
              fontWeight: 600,
              margin: "0 0 12px",
              color: "var(--color-text)",
            }}
          >
            Top Portfolio Actions
          </h4>
          {data.top_actions.map((action) => (
            <TopActionRow key={action.project_id} action={action} />
          ))}
        </div>
      )}

      {data.top_risk_projects.length > 0 && (
        <CardList
          title="Highest Risk Projects"
          cards={data.top_risk_projects}
          emptyNote="No high-risk projects."
          testId="top-risk-section"
        />
      )}

      {data.top_upside_projects.length > 0 && (
        <CardList
          title="Top Upside Opportunities"
          cards={data.top_upside_projects}
          emptyNote="No upside data available."
          testId="top-upside-section"
        />
      )}

      {data.project_cards.length > 0 && (
        <CardList
          title="All Projects"
          cards={data.project_cards}
          emptyNote="No project intervention data."
          testId="all-auto-strategy-projects"
        />
      )}
    </section>
  );
}
