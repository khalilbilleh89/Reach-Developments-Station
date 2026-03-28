"use client";

/**
 * ProjectPricingRecommendationsPanel.tsx
 *
 * Per-project demand-responsive pricing recommendations panel (PR-V7-02).
 *
 * Displays:
 *  - Demand context note (absorption vs plan)
 *  - Per-unit-type recommendation cards with:
 *    - Demand status badge (high_demand / balanced / low_demand / no_data)
 *    - Recommended price adjustment with direction color indicator
 *    - Inventory stats (total / sold / available)
 *    - Confidence level
 *    - Human-readable reason
 *
 * Design principles:
 *  - All recommendation values are sourced from the backend; no recomputation here.
 *  - Renders a safe null/loading/error state at each phase.
 *  - Color indicators are display-only (green = increase, red = decrease, gray = hold).
 *
 * PR-V7-02 — Pricing Optimization Engine (Demand-Responsive Pricing Layer)
 */

import React, { useEffect, useRef, useState } from "react";
import { getProjectPricingRecommendations } from "@/lib/pricing-optimization-api";
import type {
  ProjectPricingRecommendationsResponse,
  UnitTypePricingRecommendation,
} from "@/lib/pricing-optimization-types";
import { formatCurrency } from "@/lib/format-utils";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function demandLabel(status: UnitTypePricingRecommendation["demand_status"]): string {
  if (status === "high_demand") return "High Demand";
  if (status === "balanced") return "On Plan";
  if (status === "low_demand") return "Low Demand";
  return "No Data";
}

function demandBadgeStyle(
  status: UnitTypePricingRecommendation["demand_status"],
): React.CSSProperties {
  if (status === "high_demand")
    return {
      background: "#dcfce7",
      color: "#15803d",
      padding: "2px 8px",
      borderRadius: 12,
      fontSize: "0.75rem",
      fontWeight: 600,
    };
  if (status === "low_demand")
    return {
      background: "#fee2e2",
      color: "#b91c1c",
      padding: "2px 8px",
      borderRadius: 12,
      fontSize: "0.75rem",
      fontWeight: 600,
    };
  if (status === "balanced")
    return {
      background: "#e0f2fe",
      color: "#0369a1",
      padding: "2px 8px",
      borderRadius: 12,
      fontSize: "0.75rem",
      fontWeight: 600,
    };
  return {
    background: "var(--color-border)",
    color: "var(--color-text-muted)",
    padding: "2px 8px",
    borderRadius: 12,
    fontSize: "0.75rem",
    fontWeight: 600,
  };
}

function changeIndicatorStyle(change_pct: number | null): React.CSSProperties {
  if (change_pct == null) return { color: "var(--color-text-muted)" };
  if (change_pct > 0) return { color: "#15803d", fontWeight: 700 };
  if (change_pct < 0) return { color: "#b91c1c", fontWeight: 700 };
  return { color: "var(--color-text-muted)", fontWeight: 700 };
}

function formatChangePct(change_pct: number | null): string {
  if (change_pct == null) return "—";
  if (change_pct > 0) return `+${change_pct.toFixed(1)}%`;
  if (change_pct < 0) return `${change_pct.toFixed(1)}%`;
  return "Hold";
}

function confidenceLabel(confidence: UnitTypePricingRecommendation["confidence"]): string {
  if (confidence === "high") return "High confidence";
  if (confidence === "medium") return "Medium confidence";
  if (confidence === "low") return "Low confidence";
  return "Insufficient data";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function RecommendationCard({ rec }: { rec: UnitTypePricingRecommendation }) {
  const hasPricing = rec.current_avg_price != null;

  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        padding: "14px 16px",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
      data-testid={`rec-card-${rec.unit_type}`}
    >
      {/* Header: unit type + demand badge */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
        }}
      >
        <span
          style={{ fontWeight: 600, fontSize: "0.9375rem", color: "var(--color-text)" }}
          data-testid={`rec-unit-type-${rec.unit_type}`}
        >
          {rec.unit_type}
        </span>
        <span style={demandBadgeStyle(rec.demand_status)} data-testid={`rec-demand-${rec.unit_type}`}>
          {demandLabel(rec.demand_status)}
        </span>
      </div>

      {/* Price row */}
      <div
        style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}
      >
        {hasPricing && (
          <span style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>
            Current avg:{" "}
            <strong style={{ color: "var(--color-text)" }}>
              {formatCurrency(rec.current_avg_price!)}
            </strong>
          </span>
        )}
        {hasPricing && rec.recommended_price != null && (
          <span style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>
            Recommended:{" "}
            <strong style={{ color: "var(--color-text)" }}>
              {formatCurrency(rec.recommended_price)}
            </strong>
          </span>
        )}
        <span
          style={{
            fontSize: "1rem",
            ...changeIndicatorStyle(rec.change_pct),
          }}
          data-testid={`rec-change-pct-${rec.unit_type}`}
        >
          {formatChangePct(rec.change_pct)}
        </span>
      </div>

      {/* Inventory stats */}
      <div
        style={{
          display: "flex",
          gap: 16,
          fontSize: "0.8125rem",
          color: "var(--color-text-muted)",
          flexWrap: "wrap",
        }}
      >
        <span>{rec.total_units} total</span>
        <span>{rec.sold_units} sold</span>
        <span>{rec.available_units} available</span>
        {rec.availability_pct != null && (
          <span>
            Availability:{" "}
            <strong style={{ color: "var(--color-text)" }}>
              {rec.availability_pct.toFixed(1)}%
            </strong>
          </span>
        )}
      </div>

      {/* Reason */}
      <div
        style={{
          fontSize: "0.8125rem",
          color: "var(--color-text-muted)",
          fontStyle: "italic",
          borderTop: "1px solid var(--color-border)",
          paddingTop: 8,
        }}
        data-testid={`rec-reason-${rec.unit_type}`}
      >
        {rec.reason}
      </div>

      {/* Confidence */}
      <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
        {confidenceLabel(rec.confidence)}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface ProjectPricingRecommendationsPanelProps {
  projectId: string;
}

export function ProjectPricingRecommendationsPanel({
  projectId,
}: ProjectPricingRecommendationsPanelProps) {
  const [data, setData] =
    useState<ProjectPricingRecommendationsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    getProjectPricingRecommendations(projectId, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setData(result);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load pricing recommendations.",
          );
          setLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [projectId]);

  if (loading) {
    return (
      <div
        style={{ padding: "16px", color: "var(--color-text-muted)" }}
        data-testid="pricing-rec-loading"
      >
        Loading pricing recommendations…
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{ padding: "16px", color: "#b91c1c" }}
        data-testid="pricing-rec-error"
      >
        {error}
      </div>
    );
  }

  if (!data) return null;

  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        padding: "20px",
        marginTop: 16,
      }}
      data-testid="pricing-recommendations-panel"
    >
      <h3
        style={{
          fontSize: "1rem",
          fontWeight: 600,
          margin: "0 0 4px",
          color: "var(--color-text)",
        }}
      >
        Pricing Recommendations
      </h3>
      <p
        style={{
          fontSize: "0.8125rem",
          color: "var(--color-text-muted)",
          margin: "0 0 12px",
        }}
      >
        Demand-responsive pricing guidance — recommendations only, no price changes applied
      </p>

      {/* Demand context */}
      {data.demand_context && (
        <div
          style={{
            padding: "10px 12px",
            background: "var(--color-background)",
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            fontSize: "0.8125rem",
            color: "var(--color-text-muted)",
            marginBottom: 16,
          }}
          data-testid="demand-context-note"
        >
          {data.demand_context}
        </div>
      )}

      {/* No pricing data notice */}
      {!data.has_pricing_data && data.recommendations.length > 0 && (
        <div
          style={{
            padding: "8px 12px",
            background: "#fffbeb",
            border: "1px solid #fde68a",
            borderRadius: 6,
            fontSize: "0.8125rem",
            color: "#92400e",
            marginBottom: 16,
          }}
          data-testid="no-pricing-data-notice"
        >
          No formal pricing records found. Set up pricing engine inputs to see
          recommended price values.
        </div>
      )}

      {/* Empty state */}
      {data.recommendations.length === 0 ? (
        <p
          style={{ fontSize: "0.875rem", color: "var(--color-text-muted)", fontStyle: "italic" }}
          data-testid="pricing-rec-empty"
        >
          No unit types found. Add units to this project to see pricing recommendations.
        </p>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
            gap: 12,
          }}
          data-testid="pricing-rec-grid"
        >
          {data.recommendations.map((rec) => (
            <RecommendationCard key={rec.unit_type} rec={rec} />
          ))}
        </div>
      )}
    </div>
  );
}
