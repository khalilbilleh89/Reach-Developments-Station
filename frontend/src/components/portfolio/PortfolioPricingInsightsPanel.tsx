"use client";

/**
 * PortfolioPricingInsightsPanel.tsx
 *
 * Portfolio-wide pricing intelligence panel (PR-V7-02).
 *
 * Shows:
 *  - Portfolio pricing summary KPIs
 *  - Top pricing opportunities (underpriced projects)
 *  - Pricing risk zones (overpriced projects)
 *  - Per-project pricing cards with status and adjustment direction
 *
 * Design principles:
 *  - All values are sourced from the backend; no recomputation here.
 *  - Renders a safe empty state when no data exists.
 *  - Color conventions: green = underpriced (opportunity), red = overpriced (risk), gray = balanced.
 *
 * PR-V7-02 — Pricing Optimization Engine (Demand-Responsive Pricing Layer)
 */

import React from "react";
import type {
  PortfolioPricingInsightsResponse,
  PortfolioPricingInsightsSummary,
  PortfolioPricingProjectCard,
} from "@/lib/pricing-optimization-types";
import styles from "@/styles/portfolio.module.css";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type PricingStatus = "underpriced" | "overpriced" | "balanced" | "no_data";

function pricingStatusLabel(status: PricingStatus): string {
  if (status === "underpriced") return "Underpriced";
  if (status === "overpriced") return "Overpriced";
  if (status === "balanced") return "Balanced";
  return "No Data";
}

function pricingStatusBadgeClass(status: PricingStatus): string {
  if (status === "underpriced") return styles.badgeSaving;
  if (status === "overpriced") return styles.badgeOverrun;
  return styles.badgeNeutral;
}

function fmtAdjPct(n: number | null): string {
  if (n == null) return "—";
  if (n > 0) return `+${n.toFixed(1)}%`;
  if (n < 0) return `${n.toFixed(1)}%`;
  return "Hold";
}

function adjPctColor(n: number | null): string {
  if (n == null) return "var(--color-text-muted)";
  if (n > 0) return "#15803d";
  if (n < 0) return "#b91c1c";
  return "var(--color-text-muted)";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function PricingSummaryStrip({
  summary,
}: {
  summary: PortfolioPricingInsightsSummary;
}) {
  const kpis = [
    {
      label: "Total Projects",
      value: String(summary.total_projects),
      testId: "pricing-total-projects",
    },
    {
      label: "With Pricing Data",
      value: String(summary.projects_with_pricing_data),
      testId: "pricing-with-data",
    },
    {
      label: "Avg Adj.",
      value: fmtAdjPct(summary.avg_recommended_adjustment_pct),
      color: adjPctColor(summary.avg_recommended_adjustment_pct),
      testId: "pricing-avg-adj",
    },
    {
      label: "Underpriced",
      value: String(summary.projects_underpriced),
      color: "#15803d",
      testId: "pricing-underpriced-count",
    },
    {
      label: "Overpriced",
      value: String(summary.projects_overpriced),
      color: "#b91c1c",
      testId: "pricing-overpriced-count",
    },
    {
      label: "Balanced",
      value: String(summary.projects_balanced),
      color: "var(--color-text)",
    },
  ];

  return (
    <div className={styles.summaryStrip}>
      {kpis.map((kpi) => (
        <div key={kpi.label} className={styles.summaryCard} data-testid={kpi.testId}>
          <span className={styles.summaryValue} style={{ color: kpi.color }}>
            {kpi.value}
          </span>
          <span className={styles.summaryLabel}>{kpi.label}</span>
        </div>
      ))}
    </div>
  );
}

function PricingProjectCard({ card }: { card: PortfolioPricingProjectCard }) {
  return (
    <div className={styles.varianceProjectCard} data-testid={`pricing-card-${card.project_id}`}>
      <div className={styles.varianceCardHeader}>
        <span className={styles.projectName}>{card.project_name}</span>
        <span
          className={`${styles.healthBadge} ${pricingStatusBadgeClass(card.pricing_status)}`}
        >
          {pricingStatusLabel(card.pricing_status)}
        </span>
      </div>
      <div className={styles.projectStats}>
        {card.avg_recommended_adjustment_pct != null && (
          <span
            style={{
              color: adjPctColor(card.avg_recommended_adjustment_pct),
              fontWeight: 600,
            }}
          >
            {fmtAdjPct(card.avg_recommended_adjustment_pct)} avg adj.
          </span>
        )}
        {card.recommendation_count > 0 && (
          <span>{card.recommendation_count} actionable recommendation(s)</span>
        )}
        {card.high_demand_unit_types.length > 0 && (
          <span style={{ color: "#15803d" }}>
            High demand: {card.high_demand_unit_types.join(", ")}
          </span>
        )}
        {card.low_demand_unit_types.length > 0 && (
          <span style={{ color: "#b91c1c" }}>
            Low demand: {card.low_demand_unit_types.join(", ")}
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
  cards: PortfolioPricingProjectCard[];
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
            <PricingProjectCard key={card.project_id} card={card} />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface PortfolioPricingInsightsPanelProps {
  data: PortfolioPricingInsightsResponse;
}

export function PortfolioPricingInsightsPanel({
  data,
}: PortfolioPricingInsightsPanelProps) {
  if (data.projects.length === 0) {
    return (
      <section data-testid="portfolio-pricing-panel">
        <h3
          style={{
            fontSize: "1.0625rem",
            fontWeight: 600,
            margin: "0 0 8px",
            color: "var(--color-text)",
          }}
        >
          Pricing Intelligence
        </h3>
        <p
          style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}
          data-testid="pricing-empty-state"
        >
          No projects found. Add projects and unit data to see pricing intelligence.
        </p>
      </section>
    );
  }

  return (
    <section data-testid="portfolio-pricing-panel">
      <h3
        style={{
          fontSize: "1.0625rem",
          fontWeight: 600,
          margin: "0 0 4px",
          color: "var(--color-text)",
        }}
      >
        Pricing Intelligence
      </h3>
      <p
        style={{
          fontSize: "0.8125rem",
          color: "var(--color-text-muted)",
          margin: "0 0 16px",
        }}
      >
        Demand-responsive pricing recommendations — recommendations only, no price changes applied
      </p>

      <PricingSummaryStrip summary={data.summary} />

      {data.top_opportunities.length > 0 && (
        <ProjectCardList
          title="Top Pricing Opportunities (Underpriced)"
          cards={data.top_opportunities}
          emptyNote="No underpriced projects identified."
          testId="top-opportunities"
        />
      )}

      {data.pricing_risk_zones.length > 0 && (
        <ProjectCardList
          title="Pricing Risk Zones (Overpriced)"
          cards={data.pricing_risk_zones}
          emptyNote="No overpriced projects identified."
          testId="pricing-risk-zones"
        />
      )}

      {data.projects.length > 0 && (
        <ProjectCardList
          title="All Projects"
          cards={data.projects}
          emptyNote="No projects with pricing data."
          testId="all-pricing-projects"
        />
      )}
    </section>
  );
}
