"use client";

/**
 * PortfolioStrategyPanel.tsx
 *
 * Portfolio-wide strategy intelligence panel (PR-V7-05).
 *
 * Shows:
 *  - Portfolio strategy summary KPIs (total, with baseline, high/low risk)
 *  - Top 3 strategies by best simulated IRR
 *  - Intervention list (projects with high-risk best strategy)
 *  - All project strategy cards
 *
 * Design principles:
 *  - All values are sourced from the backend; no recomputation here.
 *  - Renders a safe empty state when no data exists.
 *  - Color conventions: blue = best strategy, red = high risk, green = low risk.
 *
 * PR-V7-05 — Automated Strategy Generator (Decision Synthesis Layer)
 */

import React from "react";
import type {
  PortfolioStrategyInsightsResponse,
  PortfolioStrategyInsightsSummary,
  PortfolioStrategyProjectCard,
} from "@/lib/strategy-types";
import styles from "@/styles/portfolio.module.css";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtIrr(irr: number | null): string {
  if (irr == null) return "—";
  return `${(irr * 100).toFixed(2)}%`;
}

function fmtPriceAdj(pct: number | null): string {
  if (pct == null) return "—";
  if (pct > 0) return `+${pct.toFixed(1)}%`;
  if (pct < 0) return `${pct.toFixed(1)}%`;
  return "0.0%";
}

function fmtDelay(months: number | null): string {
  if (months == null) return "—";
  if (months === 0) return "No delay";
  if (months > 0) return `+${months}mo`;
  return `${Math.abs(months)}mo early`;
}

function riskBadgeClass(risk: string | null): string {
  if (risk === "low") return styles.badgeSaving;
  if (risk === "high") return styles.badgeOverrun;
  return styles.badgeNeutral;
}

function riskLabel(risk: string | null): string {
  if (risk === "low") return "Low Risk";
  if (risk === "high") return "High Risk";
  if (risk === "medium") return "Medium Risk";
  return "No Data";
}

function strategyLabel(s: string | null): string {
  if (s === "hold") return "Hold";
  if (s === "accelerate") return "Accelerate";
  if (s === "maintain") return "Maintain";
  return "—";
}

// ---------------------------------------------------------------------------
// StrategySummaryStrip
// ---------------------------------------------------------------------------

function StrategySummaryStrip({
  summary,
}: {
  summary: PortfolioStrategyInsightsSummary;
}) {
  const kpis = [
    {
      label: "Total Projects",
      value: String(summary.total_projects),
      testId: "strategy-total-projects",
    },
    {
      label: "With Baseline",
      value: String(summary.projects_with_baseline),
      testId: "strategy-with-baseline",
    },
    {
      label: "High Risk",
      value: String(summary.projects_high_risk),
      testId: "strategy-high-risk",
    },
    {
      label: "Low Risk",
      value: String(summary.projects_low_risk),
      testId: "strategy-low-risk",
    },
  ];

  return (
    <div className={styles.summaryStrip} data-testid="strategy-summary-strip">
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
// StrategyProjectCard
// ---------------------------------------------------------------------------

function StrategyProjectCard({ card }: { card: PortfolioStrategyProjectCard }) {
  return (
    <div
      className={styles.varianceProjectCard}
      data-testid={`strategy-card-${card.project_id}`}
    >
      <div className={styles.varianceCardHeader}>
        <span className={styles.projectName}>{card.project_name}</span>
        {card.best_risk_score && (
          <span
            className={`${styles.healthBadge} ${riskBadgeClass(card.best_risk_score)}`}
            data-testid={`risk-badge-${card.project_id}`}
          >
            {riskLabel(card.best_risk_score)}
          </span>
        )}
      </div>
      <div className={styles.varianceCardGrid}>
        <div>
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Best IRR</div>
          <div data-testid={`best-irr-${card.project_id}`} style={{ fontWeight: 700 }}>
            {fmtIrr(card.best_irr)}
          </div>
        </div>
        <div>
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
            Price Adj
          </div>
          <div style={{ fontWeight: 600 }}>{fmtPriceAdj(card.best_price_adjustment_pct)}</div>
        </div>
        <div>
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Phase Delay</div>
          <div style={{ fontWeight: 600 }}>{fmtDelay(card.best_phase_delay_months)}</div>
        </div>
        <div>
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Strategy</div>
          <div style={{ fontWeight: 600 }}>{strategyLabel(card.best_release_strategy)}</div>
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
          data-testid={`strategy-reason-${card.project_id}`}
        >
          {card.reason}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ProjectCardList
// ---------------------------------------------------------------------------

function ProjectCardList({
  title,
  cards,
  emptyNote,
  testId,
}: {
  title: string;
  cards: PortfolioStrategyProjectCard[];
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
            <StrategyProjectCard key={card.project_id} card={card} />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface PortfolioStrategyPanelProps {
  data: PortfolioStrategyInsightsResponse;
}

export function PortfolioStrategyPanel({ data }: PortfolioStrategyPanelProps) {
  if (data.projects.length === 0) {
    return (
      <section data-testid="portfolio-strategy-panel">
        <h3
          style={{
            fontSize: "1.0625rem",
            fontWeight: 600,
            margin: "0 0 8px",
            color: "var(--color-text)",
          }}
        >
          Strategy Intelligence
        </h3>
        <p
          style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}
          data-testid="strategy-empty-state"
        >
          No projects found. Add projects and feasibility data to see strategy intelligence.
        </p>
      </section>
    );
  }

  return (
    <section data-testid="portfolio-strategy-panel">
      <h3
        style={{
          fontSize: "1.0625rem",
          fontWeight: 600,
          margin: "0 0 4px",
          color: "var(--color-text)",
        }}
      >
        Strategy Intelligence
      </h3>
      <p
        style={{
          fontSize: "0.8125rem",
          color: "var(--color-text-muted)",
          margin: "0 0 16px",
        }}
      >
        Automated strategy recommendations — synthesis of simulation, pricing, and phasing
        signals. Read-only.
      </p>

      <StrategySummaryStrip summary={data.summary} />

      {data.top_strategies.length > 0 && (
        <ProjectCardList
          title="Top Strategies by IRR"
          cards={data.top_strategies}
          emptyNote="No top strategies available."
          testId="top-strategies-section"
        />
      )}

      {data.intervention_required.length > 0 && (
        <ProjectCardList
          title="Intervention Required (High Risk)"
          cards={data.intervention_required}
          emptyNote="No high-risk projects."
          testId="intervention-required-section"
        />
      )}

      {data.projects.length > 0 && (
        <ProjectCardList
          title="All Projects"
          cards={data.projects}
          emptyNote="No project strategy data."
          testId="all-strategy-projects"
        />
      )}
    </section>
  );
}
