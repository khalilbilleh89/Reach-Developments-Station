"use client";

/**
 * AdaptiveStrategyPanel.tsx
 *
 * Project-level adaptive strategy panel (PR-V7-12).
 *
 * Shows:
 *  - Confidence score and band with low-confidence warning
 *  - Raw simulation-best strategy (always visible)
 *  - Confidence-adjusted best strategy
 *  - Whether confidence changed the recommendation
 *  - Adjusted reason explanation
 *  - Raw vs adaptive comparison block
 *  - Safe empty states for no-data and no-learning scenarios
 *
 * Design principles:
 *  - All values are backend-derived; no client-side computation or ranking.
 *  - Renders safe empty states for all scenarios.
 *  - AbortController wired for clean unmount cancellation.
 *
 * PR-V7-12 — Adaptive Strategy Influence Layer
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { getProjectAdaptiveStrategy } from "@/lib/adaptive-strategy-api";
import type {
  AdaptiveStrategyComparisonBlock,
  AdaptiveStrategyResponse,
  ConfidenceBand,
} from "@/lib/adaptive-strategy-types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtPct(value: number | null, decimals = 2): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(decimals)}%`;
}

function fmtAdjPct(value: number | null): string {
  if (value == null) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function fmtMonths(value: number | null): string {
  if (value == null) return "—";
  return `${value}mo`;
}

function fmtStrategy(value: string | null): string {
  if (!value) return "—";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function bandColor(band: ConfidenceBand): string {
  switch (band) {
    case "high":
      return "#15803d";
    case "medium":
      return "#b45309";
    case "low":
      return "#b91c1c";
    case "insufficient":
      return "#6b7280";
  }
}

function bandBg(band: ConfidenceBand): string {
  switch (band) {
    case "high":
      return "#dcfce7";
    case "medium":
      return "#fef3c7";
    case "low":
      return "#fee2e2";
    case "insufficient":
      return "#f3f4f6";
  }
}

function bandLabel(band: ConfidenceBand): string {
  switch (band) {
    case "high":
      return "High Confidence";
    case "medium":
      return "Medium Confidence";
    case "low":
      return "Low Confidence";
    case "insufficient":
      return "Insufficient Data";
  }
}

function riskColor(risk: string | null): string {
  switch (risk) {
    case "low":
      return "#15803d";
    case "medium":
      return "#b45309";
    case "high":
      return "#b91c1c";
    default:
      return "#6b7280";
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StrategyCard({
  label,
  strategy,
  irr,
  risk,
  priceAdj,
  phaseDelay,
  highlight,
}: {
  label: string;
  strategy: string | null;
  irr: number | null;
  risk: string | null;
  priceAdj: number | null;
  phaseDelay: number | null;
  highlight?: boolean;
}) {
  return (
    <div
      style={{
        border: highlight ? "2px solid #2563eb" : "1px solid #e5e7eb",
        borderRadius: 8,
        padding: "12px 16px",
        background: highlight ? "#eff6ff" : "#fafafa",
        flex: 1,
        minWidth: 200,
      }}
    >
      <div
        style={{
          fontSize: "0.7rem",
          fontWeight: 700,
          color: highlight ? "#1d4ed8" : "#6b7280",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: 8,
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#111827", marginBottom: 4 }}>
        {fmtStrategy(strategy)}
      </div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 4 }}>
        <span style={{ fontSize: "0.82rem", color: "#374151" }}>
          IRR: <strong>{fmtPct(irr)}</strong>
        </span>
        <span style={{ fontSize: "0.82rem", color: riskColor(risk) }}>
          Risk: <strong>{risk ?? "—"}</strong>
        </span>
        <span style={{ fontSize: "0.82rem", color: "#374151" }}>
          Price: <strong>{fmtAdjPct(priceAdj)}</strong>
        </span>
        <span style={{ fontSize: "0.82rem", color: "#374151" }}>
          Delay: <strong>{fmtMonths(phaseDelay)}</strong>
        </span>
      </div>
    </div>
  );
}

function ComparisonBlock({ cmp }: { cmp: AdaptiveStrategyComparisonBlock }) {
  const changed = cmp.changed_by_confidence;
  return (
    <div
      style={{
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        padding: "12px 16px",
        background: "#fff",
        marginTop: 12,
      }}
    >
      <div style={{ fontWeight: 600, fontSize: "0.85rem", color: "#374151", marginBottom: 10 }}>
        Raw vs Adaptive Comparison
        {changed && (
          <span
            style={{
              marginLeft: 10,
              padding: "2px 8px",
              background: "#dbeafe",
              color: "#1d4ed8",
              borderRadius: 12,
              fontSize: "0.72rem",
              fontWeight: 700,
            }}
          >
            Changed by Confidence
          </span>
        )}
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
        <thead>
          <tr style={{ color: "#6b7280", borderBottom: "1px solid #e5e7eb" }}>
            <th style={{ textAlign: "left", padding: "4px 8px 4px 0" }}>Metric</th>
            <th style={{ textAlign: "right", padding: "4px 8px" }}>Raw</th>
            <th style={{ textAlign: "right", padding: "4px 0 4px 8px" }}>Adaptive</th>
          </tr>
        </thead>
        <tbody>
          {[
            ["Strategy", fmtStrategy(cmp.raw_release_strategy), fmtStrategy(cmp.adaptive_release_strategy)],
            ["IRR", fmtPct(cmp.raw_irr), fmtPct(cmp.adaptive_irr)],
            ["Risk", cmp.raw_risk_score ?? "—", cmp.adaptive_risk_score ?? "—"],
            ["Price Adj.", fmtAdjPct(cmp.raw_price_adjustment_pct), fmtAdjPct(cmp.adaptive_price_adjustment_pct)],
            ["Phase Delay", fmtMonths(cmp.raw_phase_delay_months), fmtMonths(cmp.adaptive_phase_delay_months)],
          ].map(([label, raw, adp]) => {
            const differs = raw !== adp;
            return (
              <tr
                key={label}
                style={{
                  borderBottom: "1px solid #f3f4f6",
                  background: differs && changed ? "#eff6ff" : undefined,
                }}
              >
                <td style={{ padding: "5px 8px 5px 0", color: "#374151" }}>{label}</td>
                <td style={{ padding: "5px 8px", textAlign: "right", color: "#374151" }}>{raw}</td>
                <td
                  style={{
                    padding: "5px 0 5px 8px",
                    textAlign: "right",
                    fontWeight: differs && changed ? 700 : undefined,
                    color: differs && changed ? "#1d4ed8" : "#374151",
                  }}
                >
                  {adp}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface Props {
  projectId: string;
}

export default function AdaptiveStrategyPanel({ projectId }: Props) {
  const [data, setData] = useState<AdaptiveStrategyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    getProjectAdaptiveStrategy(projectId, controller.signal)
      .then(setData)
      .catch((err) => {
        if (err.name !== "AbortError") {
          setError("Failed to load adaptive strategy.");
        }
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  useEffect(() => {
    load();
    return () => abortRef.current?.abort();
  }, [load]);

  if (loading) {
    return (
      <div style={{ padding: 24, color: "#6b7280", fontSize: "0.9rem" }}>
        Loading adaptive strategy…
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          padding: 16,
          background: "#fee2e2",
          color: "#b91c1c",
          borderRadius: 8,
          fontSize: "0.9rem",
        }}
      >
        {error}
      </div>
    );
  }

  if (!data) return null;

  const band = data.confidence_band;

  return (
    <div style={{ fontFamily: "system-ui, sans-serif" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          marginBottom: 16,
          flexWrap: "wrap",
        }}
      >
        <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 700, color: "#111827" }}>
          Adaptive Strategy
        </h3>
        <span
          style={{
            padding: "3px 12px",
            borderRadius: 12,
            fontSize: "0.75rem",
            fontWeight: 700,
            background: bandBg(band),
            color: bandColor(band),
          }}
        >
          {bandLabel(band)}
        </span>
        {data.low_confidence_flag && (
          <span
            style={{
              padding: "3px 10px",
              borderRadius: 12,
              fontSize: "0.72rem",
              fontWeight: 700,
              background: "#fee2e2",
              color: "#b91c1c",
            }}
          >
            ⚠ Low Confidence
          </span>
        )}
        {data.comparison.changed_by_confidence && (
          <span
            style={{
              padding: "3px 10px",
              borderRadius: 12,
              fontSize: "0.72rem",
              fontWeight: 700,
              background: "#dbeafe",
              color: "#1d4ed8",
            }}
          >
            ✦ Recommendation Changed
          </span>
        )}
      </div>

      {/* Confidence metadata row */}
      <div
        style={{
          display: "flex",
          gap: 24,
          flexWrap: "wrap",
          marginBottom: 16,
          background: "#f9fafb",
          borderRadius: 8,
          padding: "10px 16px",
          fontSize: "0.83rem",
          color: "#374151",
        }}
      >
        <span>
          Confidence:{" "}
          <strong style={{ color: bandColor(band) }}>
            {data.confidence_score != null
              ? `${(data.confidence_score * 100).toFixed(0)}%`
              : "—"}
          </strong>
        </span>
        <span>
          Outcomes: <strong>{data.sample_size}</strong>
        </span>
        <span>
          Trend:{" "}
          <strong>
            {data.trend_direction === "improving"
              ? "↑ Improving"
              : data.trend_direction === "declining"
                ? "↓ Declining"
                : data.trend_direction === "stable"
                  ? "→ Stable"
                  : "— Insufficient Data"}
          </strong>
        </span>
        <span>
          Influence Applied:{" "}
          <strong>{data.confidence_influence_applied ? "Yes" : "No"}</strong>
        </span>
      </div>

      {/* Strategy cards */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
        <StrategyCard
          label="Raw Simulation Best"
          strategy={data.raw_best_strategy}
          irr={data.raw_best_irr}
          risk={data.raw_best_risk_score}
          priceAdj={data.raw_best_price_adjustment_pct}
          phaseDelay={data.raw_best_phase_delay_months}
        />
        <StrategyCard
          label="Confidence-Adjusted Best"
          strategy={data.adaptive_best_strategy}
          irr={data.adaptive_best_irr}
          risk={data.adaptive_best_risk_score}
          priceAdj={data.adaptive_best_price_adjustment_pct}
          phaseDelay={data.adaptive_best_phase_delay_months}
          highlight
        />
      </div>

      {/* Adjusted reason */}
      <div
        style={{
          background: "#f9fafb",
          border: "1px solid #e5e7eb",
          borderRadius: 8,
          padding: "10px 14px",
          fontSize: "0.82rem",
          color: "#374151",
          marginBottom: 12,
        }}
      >
        <span style={{ fontWeight: 600 }}>Influence Explanation: </span>
        {data.adjusted_reason}
      </div>

      {/* Comparison block */}
      <ComparisonBlock cmp={data.comparison} />
    </div>
  );
}
