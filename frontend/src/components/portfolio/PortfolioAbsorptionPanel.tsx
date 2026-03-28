"use client";

/**
 * PortfolioAbsorptionPanel.tsx
 *
 * Portfolio-wide absorption intelligence panel (PR-V7-01).
 *
 * Shows:
 *  - Portfolio absorption summary KPIs
 *  - Fastest and slowest selling projects
 *  - Projects performing below plan threshold
 *  - Per-project absorption cards with status badges
 *
 * Design principles:
 *  - All metric values are sourced from the backend; no recomputation here.
 *  - Renders a safe empty state when no data exists.
 *  - Absorption status badges and colors are display-only.
 *
 * PR-V7-01 — Sales Absorption Feedback Loop → Feasibility Engine
 */

import React from "react";
import type {
  PortfolioAbsorptionProjectCard,
  PortfolioAbsorptionResponse,
  PortfolioAbsorptionSummary,
} from "@/lib/portfolio-absorption-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/portfolio.module.css";

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

type AbsorptionStatus =
  | "ahead_of_plan"
  | "on_plan"
  | "behind_plan"
  | "no_data"
  | null;

function statusLabel(status: AbsorptionStatus): string {
  if (status === "ahead_of_plan") return "Ahead";
  if (status === "on_plan") return "On Plan";
  if (status === "behind_plan") return "Behind";
  if (status === "no_data") return "No Data";
  if (status === null) return "No Units";
  return "No Data";
}

function statusBadgeClass(status: AbsorptionStatus): string {
  if (status === "ahead_of_plan") return styles.badgeSaving;
  if (status === "on_plan") return styles.badgeNeutral;
  if (status === "behind_plan") return styles.badgeOverrun;
  return styles.badgeNeutral;
}

function fmtRate(n: number | null): string {
  if (n == null) return "—";
  return `${n.toFixed(2)}/mo`;
}

function fmtPct(n: number | null): string {
  if (n == null) return "—";
  return `${n.toFixed(1)}%`;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function AbsorptionSummaryStrip({
  summary,
}: {
  summary: PortfolioAbsorptionSummary;
}) {
  const kpis = [
    {
      label: "Total Projects",
      value: String(summary.total_projects),
      testId: "absorption-total-projects",
    },
    {
      label: "Avg Sell-Through",
      value: fmtPct(summary.portfolio_avg_sell_through_pct),
      testId: "absorption-avg-sell-through",
    },
    {
      label: "Avg Rate (units/mo)",
      value: summary.portfolio_avg_absorption_rate != null
        ? summary.portfolio_avg_absorption_rate.toFixed(2)
        : "—",
      testId: "absorption-avg-rate",
    },
    {
      label: "Ahead of Plan",
      value: String(summary.projects_ahead_of_plan),
      color: "#15803d",
    },
    {
      label: "On Plan",
      value: String(summary.projects_on_plan),
      color: "var(--color-text)",
    },
    {
      label: "Behind Plan",
      value: String(summary.projects_behind_plan),
      color: "#b91c1c",
    },
  ];

  return (
    <div className={styles.summaryStrip}>
      {kpis.map((kpi) => (
        <div
          key={kpi.label}
          className={styles.summaryCard}
          data-testid={kpi.testId}
        >
          <span className={styles.summaryValue} style={{ color: kpi.color }}>
            {kpi.value}
          </span>
          <span className={styles.summaryLabel}>{kpi.label}</span>
        </div>
      ))}
    </div>
  );
}

function AbsorptionProjectCard({
  card,
}: {
  card: PortfolioAbsorptionProjectCard;
}) {
  return (
    <div className={styles.varianceProjectCard}>
      <div className={styles.varianceCardHeader}>
        <span className={styles.projectName}>{card.project_name}</span>
        <span
          className={`${styles.healthBadge} ${statusBadgeClass(card.absorption_status)}`}
        >
          {statusLabel(card.absorption_status)}
        </span>
      </div>
      <div className={styles.projectStats}>
        <span>
          {card.sold_units}/{card.total_units} sold
          {card.sell_through_pct != null
            ? ` (${card.sell_through_pct.toFixed(1)}%)`
            : ""}
        </span>
        <span>Rate: {fmtRate(card.absorption_rate_per_month)}</span>
        {card.absorption_vs_plan_pct != null && (
          <span
            style={{
              color:
                card.absorption_vs_plan_pct >= 100
                  ? "#15803d"
                  : card.absorption_vs_plan_pct >= 80
                    ? "#92400e"
                    : "#b91c1c",
              fontWeight: 500,
            }}
          >
            {card.absorption_vs_plan_pct.toFixed(1)}% of plan
          </span>
        )}
        <span>{formatCurrency(card.contracted_revenue)} contracted</span>
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
  cards: PortfolioAbsorptionProjectCard[];
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
        <div className={styles.varianceProjectList}>
          {cards.map((card) => (
            <AbsorptionProjectCard key={card.project_id} card={card} />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface PortfolioAbsorptionPanelProps {
  data: PortfolioAbsorptionResponse;
}

export function PortfolioAbsorptionPanel({
  data,
}: PortfolioAbsorptionPanelProps) {
  if (data.projects.length === 0) {
    return (
      <section data-testid="portfolio-absorption-panel">
        <h3
          style={{
            fontSize: "1.0625rem",
            fontWeight: 600,
            margin: "0 0 8px",
            color: "var(--color-text)",
          }}
        >
          Portfolio Absorption
        </h3>
        <p
          style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}
          data-testid="absorption-empty-state"
        >
          No projects found. Add projects to see absorption intelligence.
        </p>
      </section>
    );
  }

  return (
    <section data-testid="portfolio-absorption-panel">
      <h3
        style={{
          fontSize: "1.0625rem",
          fontWeight: 600,
          margin: "0 0 4px",
          color: "var(--color-text)",
        }}
      >
        Portfolio Absorption
      </h3>
      <p
        style={{
          fontSize: "0.8125rem",
          color: "var(--color-text-muted)",
          margin: "0 0 16px",
        }}
      >
        Actual sales velocity vs feasibility plan across all projects
      </p>

      <AbsorptionSummaryStrip summary={data.summary} />

      {data.fastest_projects.length > 0 && (
        <ProjectCardList
          title="Fastest Selling"
          cards={data.fastest_projects}
          emptyNote="No absorption data available."
          testId="fastest-projects"
        />
      )}

      {data.below_plan_projects.length > 0 && (
        <ProjectCardList
          title="Below Plan — Requires Attention"
          cards={data.below_plan_projects}
          emptyNote="All projects are on or ahead of plan."
          testId="below-plan-projects"
        />
      )}

      {data.slowest_projects.length > 0 &&
        data.slowest_projects.some(
          (p) => p.project_id !== data.fastest_projects[0]?.project_id,
        ) && (
          <ProjectCardList
            title="Slowest Selling"
            cards={data.slowest_projects}
            emptyNote="No absorption data available."
            testId="slowest-projects"
          />
        )}
    </section>
  );
}
