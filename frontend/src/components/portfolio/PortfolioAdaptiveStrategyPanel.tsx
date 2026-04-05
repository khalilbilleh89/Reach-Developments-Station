"use client";

/**
 * PortfolioAdaptiveStrategyPanel.tsx
 *
 * Portfolio-level adaptive strategy panel (PR-V7-12).
 *
 * Shows:
 *  - KPI strip: total projects, high/low confidence counts, adjusted count
 *  - Top confident recommendations list
 *  - Low-confidence projects requiring attention
 *  - Full project table with confidence band, raw vs adaptive strategy,
 *    influence applied indicator, and adjusted reason
 *  - Safe empty states when no projects exist
 *
 * Design principles:
 *  - All values are backend-derived; no client-side ranking or influence logic.
 *  - Renders safe empty states for all scenarios.
 *  - AbortController wired for clean unmount cancellation.
 *
 * PR-V7-12 — Adaptive Strategy Influence Layer
 */

import React, { useEffect, useRef, useState } from "react";
import { getPortfolioAdaptiveStrategy } from "@/lib/adaptive-strategy-api";
import type {
  ConfidenceBand,
  PortfolioAdaptiveStrategyProjectCard,
  PortfolioAdaptiveStrategySummaryResponse,
} from "@/lib/adaptive-strategy-types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtPct(value: number | null): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(0)}%`;
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
      return "High";
    case "medium":
      return "Medium";
    case "low":
      return "Low";
    case "insufficient":
      return "Insufficient";
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function KpiTile({
  label,
  value,
  color,
}: {
  label: string;
  value: number | string;
  color?: string;
}) {
  return (
    <div
      style={{
        background: "#f9fafb",
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        padding: "14px 20px",
        minWidth: 120,
        textAlign: "center",
      }}
    >
      <div
        style={{
          fontSize: "1.6rem",
          fontWeight: 700,
          color: color ?? "#111827",
          lineHeight: 1,
        }}
      >
        {value}
      </div>
      <div style={{ fontSize: "0.72rem", color: "#6b7280", marginTop: 4 }}>{label}</div>
    </div>
  );
}

function ProjectCardList({
  cards,
  title,
  emptyMessage,
}: {
  cards: PortfolioAdaptiveStrategyProjectCard[];
  title: string;
  emptyMessage?: string;
}) {
  if (cards.length === 0) {
    return (
      <div style={{ marginBottom: 24 }}>
        <h4 style={{ fontSize: "0.88rem", fontWeight: 700, color: "#374151", marginBottom: 8 }}>
          {title}
        </h4>
        <div style={{ color: "#9ca3af", fontSize: "0.82rem" }}>
          {emptyMessage ?? "No projects."}
        </div>
      </div>
    );
  }
  return (
    <div style={{ marginBottom: 24 }}>
      <h4 style={{ fontSize: "0.88rem", fontWeight: 700, color: "#374151", marginBottom: 8 }}>
        {title}
      </h4>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {cards.map((c) => (
          <div
            key={c.project_id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              background: "#fafafa",
              border: "1px solid #e5e7eb",
              borderRadius: 8,
              padding: "10px 14px",
              flexWrap: "wrap",
            }}
          >
            <span style={{ fontWeight: 600, fontSize: "0.88rem", color: "#111827", flex: 1 }}>
              {c.project_name}
            </span>
            <span
              style={{
                padding: "2px 10px",
                borderRadius: 12,
                fontSize: "0.72rem",
                fontWeight: 700,
                background: bandBg(c.confidence_band),
                color: bandColor(c.confidence_band),
              }}
            >
              {bandLabel(c.confidence_band)}
            </span>
            <span style={{ fontSize: "0.82rem", color: "#374151" }}>
              Confidence: <strong>{fmtPct(c.confidence_score)}</strong>
            </span>
            <span style={{ fontSize: "0.82rem", color: "#374151" }}>
              Adaptive: <strong>{fmtStrategy(c.adaptive_best_strategy)}</strong>
            </span>
            {c.confidence_influence_applied && c.raw_best_strategy !== c.adaptive_best_strategy && (
              <span
                style={{
                  padding: "2px 8px",
                  borderRadius: 12,
                  fontSize: "0.7rem",
                  fontWeight: 700,
                  background: "#dbeafe",
                  color: "#1d4ed8",
                }}
              >
                ✦ Changed
              </span>
            )}
            {c.low_confidence_flag && (
              <span
                style={{
                  padding: "2px 8px",
                  borderRadius: 12,
                  fontSize: "0.7rem",
                  fontWeight: 700,
                  background: "#fee2e2",
                  color: "#b91c1c",
                }}
              >
                ⚠ Caution
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function FullProjectTable({
  cards,
}: {
  cards: PortfolioAdaptiveStrategyProjectCard[];
}) {
  if (cards.length === 0) {
    return (
      <div style={{ color: "#9ca3af", fontSize: "0.82rem", padding: "12px 0" }}>
        No projects to display.
      </div>
    );
  }
  return (
    <div style={{ overflowX: "auto" }}>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: "0.82rem",
          minWidth: 700,
        }}
      >
        <thead>
          <tr
            style={{
              background: "#f9fafb",
              color: "#6b7280",
              borderBottom: "2px solid #e5e7eb",
            }}
          >
            {["Project", "Confidence", "Band", "Raw Strategy", "Adaptive Strategy", "Changed", "Caution", "Outcomes"].map(
              (h) => (
                <th
                  key={h}
                  style={{
                    padding: "8px 10px",
                    textAlign: "left",
                    fontWeight: 600,
                    whiteSpace: "nowrap",
                  }}
                >
                  {h}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {cards.map((c) => (
            <tr
              key={c.project_id}
              style={{ borderBottom: "1px solid #f3f4f6" }}
            >
              <td style={{ padding: "8px 10px", fontWeight: 600, color: "#111827" }}>
                {c.project_name}
              </td>
              <td style={{ padding: "8px 10px", color: bandColor(c.confidence_band) }}>
                <strong>{fmtPct(c.confidence_score)}</strong>
              </td>
              <td style={{ padding: "8px 10px" }}>
                <span
                  style={{
                    padding: "2px 8px",
                    borderRadius: 10,
                    fontSize: "0.7rem",
                    fontWeight: 700,
                    background: bandBg(c.confidence_band),
                    color: bandColor(c.confidence_band),
                  }}
                >
                  {bandLabel(c.confidence_band)}
                </span>
              </td>
              <td style={{ padding: "8px 10px", color: "#374151" }}>
                {fmtStrategy(c.raw_best_strategy)}
              </td>
              <td style={{ padding: "8px 10px", color: "#374151" }}>
                {fmtStrategy(c.adaptive_best_strategy)}
              </td>
              <td style={{ padding: "8px 10px", textAlign: "center" }}>
                {c.confidence_influence_applied &&
                c.raw_best_strategy !== c.adaptive_best_strategy ? (
                  <span style={{ color: "#1d4ed8", fontWeight: 700 }}>✦</span>
                ) : (
                  <span style={{ color: "#d1d5db" }}>—</span>
                )}
              </td>
              <td style={{ padding: "8px 10px", textAlign: "center" }}>
                {c.low_confidence_flag ? (
                  <span style={{ color: "#b91c1c", fontWeight: 700 }}>⚠</span>
                ) : (
                  <span style={{ color: "#d1d5db" }}>—</span>
                )}
              </td>
              <td style={{ padding: "8px 10px", color: "#374151", textAlign: "center" }}>
                {c.sample_size}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function PortfolioAdaptiveStrategyPanel() {
  const [data, setData] =
    useState<PortfolioAdaptiveStrategySummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    getPortfolioAdaptiveStrategy(controller.signal)
      .then(setData)
      .catch((err) => {
        if (err.name !== "AbortError") {
          setError("Failed to load portfolio adaptive strategy.");
        }
      })
      .finally(() => setLoading(false));
    return () => abortRef.current?.abort();
  }, []);

  if (loading) {
    return (
      <div style={{ padding: 24, color: "#6b7280", fontSize: "0.9rem" }}>
        Loading portfolio adaptive strategy…
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

  if (data.total_projects === 0) {
    return (
      <div
        style={{
          padding: 24,
          background: "#f9fafb",
          borderRadius: 8,
          color: "#6b7280",
          fontSize: "0.9rem",
          textAlign: "center",
        }}
      >
        No projects available for adaptive strategy analysis.
      </div>
    );
  }

  return (
    <div style={{ fontFamily: "system-ui, sans-serif" }}>
      {/* Title */}
      <h3
        style={{
          margin: "0 0 16px",
          fontSize: "1rem",
          fontWeight: 700,
          color: "#111827",
        }}
      >
        Portfolio Adaptive Strategy
      </h3>

      {/* KPI strip */}
      <div
        style={{
          display: "flex",
          gap: 12,
          flexWrap: "wrap",
          marginBottom: 24,
        }}
      >
        <KpiTile label="Total Projects" value={data.total_projects} />
        <KpiTile
          label="High Confidence"
          value={data.high_confidence_projects}
          color="#15803d"
        />
        <KpiTile
          label="Low Confidence"
          value={data.low_confidence_projects}
          color="#b91c1c"
        />
        <KpiTile
          label="Recommendation Changed"
          value={data.confidence_adjusted_projects}
          color="#1d4ed8"
        />
        <KpiTile label="Neutral" value={data.neutral_projects} color="#6b7280" />
      </div>

      {/* Top confident */}
      <ProjectCardList
        cards={data.top_confident_recommendations}
        title="Top Confident Recommendations"
        emptyMessage="No high-confidence projects yet."
      />

      {/* Low confidence */}
      <ProjectCardList
        cards={data.top_low_confidence_projects}
        title="Low-Confidence Projects — Treat Recommendations Cautiously"
        emptyMessage="No low-confidence projects."
      />

      {/* Full table */}
      <div>
        <h4
          style={{
            fontSize: "0.88rem",
            fontWeight: 700,
            color: "#374151",
            marginBottom: 10,
          }}
        >
          All Projects
        </h4>
        <FullProjectTable cards={data.project_cards} />
      </div>
    </div>
  );
}
