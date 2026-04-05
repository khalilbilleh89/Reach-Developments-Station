"use client";

/**
 * PortfolioLearningPanel.tsx
 *
 * Portfolio-level strategy learning & confidence panel (PR-V7-11).
 *
 * Shows:
 *  - Portfolio-wide confidence KPIs (average, high/low counts, trends)
 *  - Top performing strategy patterns (highest confidence)
 *  - Weak-area projects (lowest confidence)
 *  - All project learning entries
 *
 * Design principles:
 *  - All values are backend-derived; no client-side computation.
 *  - Renders safe empty states when no data exists.
 *  - AbortController wired for clean unmount cancellation.
 *
 * PR-V7-11 — Strategy Learning & Confidence Recalibration Engine
 */

import React, { useEffect, useRef, useState } from "react";
import { getPortfolioStrategyLearning } from "@/lib/strategy-learning-api";
import type {
  PortfolioLearningProjectEntry,
  PortfolioLearningSummaryResponse,
  TrendDirection,
} from "@/lib/strategy-learning-types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtConfidence(score: number | null): string {
  if (score == null) return "—";
  return `${(score * 100).toFixed(0)}%`;
}

function fmtPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function trendLabel(trend: TrendDirection): string {
  switch (trend) {
    case "improving":
      return "↑ Improving";
    case "declining":
      return "↓ Declining";
    case "stable":
      return "→ Stable";
    case "insufficient_data":
      return "—";
  }
}

function trendColor(trend: TrendDirection): string {
  switch (trend) {
    case "improving":
      return "#15803d";
    case "declining":
      return "#b91c1c";
    case "stable":
      return "#1d4ed8";
    case "insufficient_data":
      return "#6b7280";
  }
}

function confidenceColor(score: number): string {
  if (score >= 0.7) return "#15803d";
  if (score >= 0.4) return "#854d0e";
  return "#b91c1c";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function KpiCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}): React.ReactElement {
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        padding: "14px 16px",
        textAlign: "center",
      }}
    >
      <p style={{ fontSize: "0.72rem", color: "#6b7280", marginBottom: 4 }}>
        {label}
      </p>
      <p
        style={{
          fontSize: "1.4rem",
          fontWeight: 700,
          color: color ?? "#111827",
        }}
      >
        {value}
      </p>
    </div>
  );
}

function ProjectRow({
  entry,
}: {
  entry: PortfolioLearningProjectEntry;
}): React.ReactElement {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "10px 14px",
        border: "1px solid #e5e7eb",
        borderRadius: 7,
        marginBottom: 8,
        background: "#fff",
      }}
    >
      <div>
        <p style={{ fontWeight: 600, color: "#111827", fontSize: "0.9rem" }}>
          {entry.project_name}
        </p>
        <p style={{ fontSize: "0.72rem", color: "#6b7280" }}>
          Accuracy: {fmtPct(entry.overall_strategy_accuracy)} · Samples:{" "}
          {entry.sample_size}
        </p>
      </div>
      <div style={{ textAlign: "right" }}>
        <p
          style={{
            fontSize: "1.1rem",
            fontWeight: 700,
            color: confidenceColor(entry.confidence_score),
          }}
        >
          {fmtConfidence(entry.confidence_score)}
        </p>
        <p
          style={{
            fontSize: "0.72rem",
            fontWeight: 600,
            color: trendColor(entry.trend_direction),
          }}
        >
          {trendLabel(entry.trend_direction)}
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export function PortfolioLearningPanel(): React.ReactElement {
  const [data, setData] = useState<PortfolioLearningSummaryResponse | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await getPortfolioStrategyLearning(ctrl.signal);
        if (!ctrl.signal.aborted) {
          setData(result);
        }
      } catch (err: unknown) {
        if (!ctrl.signal.aborted) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load portfolio learning data.",
          );
        }
      } finally {
        if (!ctrl.signal.aborted) {
          setLoading(false);
        }
      }
    })();
    return () => ctrl.abort();
  }, []);

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 16 }}>
      <h2
        style={{
          fontSize: "1.1rem",
          fontWeight: 700,
          color: "#111827",
          marginBottom: 16,
        }}
      >
        Portfolio Strategy Learning
      </h2>

      {loading && (
        <p style={{ color: "#6b7280", fontSize: "0.9rem" }}>
          Loading portfolio learning data…
        </p>
      )}

      {!loading && error && (
        <p style={{ color: "#b91c1c", fontSize: "0.9rem" }}>{error}</p>
      )}

      {!loading && !error && data && data.total_projects_with_data === 0 && (
        <div
          style={{
            background: "#f9fafb",
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            padding: "20px 16px",
            textAlign: "center",
            color: "#6b7280",
            fontSize: "0.9rem",
          }}
        >
          <p style={{ fontWeight: 600, marginBottom: 6 }}>
            No portfolio learning data yet
          </p>
          <p>
            Record execution outcomes for projects and run recalibration to
            populate portfolio confidence insights.
          </p>
        </div>
      )}

      {!loading && !error && data && data.total_projects_with_data > 0 && (
        <>
          {/* KPI grid */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
              gap: 12,
              marginBottom: 20,
            }}
          >
            <KpiCard
              label="Projects with Data"
              value={String(data.total_projects_with_data)}
            />
            <KpiCard
              label="Avg Confidence"
              value={fmtConfidence(data.average_confidence_score)}
              color={
                data.average_confidence_score != null
                  ? confidenceColor(data.average_confidence_score)
                  : undefined
              }
            />
            <KpiCard
              label="High Confidence"
              value={String(data.high_confidence_count)}
              color="#15803d"
            />
            <KpiCard
              label="Low Confidence"
              value={String(data.low_confidence_count)}
              color="#b91c1c"
            />
            <KpiCard
              label="Improving"
              value={String(data.improving_count)}
              color="#15803d"
            />
            <KpiCard
              label="Declining"
              value={String(data.declining_count)}
              color="#b91c1c"
            />
          </div>

          {/* Top performing */}
          {data.top_performing_projects.length > 0 && (
            <section style={{ marginBottom: 20 }}>
              <h3
                style={{
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  color: "#374151",
                  marginBottom: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                Top Performing Projects
              </h3>
              {data.top_performing_projects.map((e) => (
                <ProjectRow key={e.project_id} entry={e} />
              ))}
            </section>
          )}

          {/* Weak areas */}
          {data.weak_area_projects.length > 0 && (
            <section style={{ marginBottom: 20 }}>
              <h3
                style={{
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  color: "#b91c1c",
                  marginBottom: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                Weak Areas
              </h3>
              {data.weak_area_projects.map((e) => (
                <ProjectRow key={e.project_id} entry={e} />
              ))}
            </section>
          )}

          {/* All projects */}
          {data.all_project_entries.length > 0 && (
            <section>
              <h3
                style={{
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  color: "#374151",
                  marginBottom: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                All Projects
              </h3>
              {data.all_project_entries.map((e) => (
                <ProjectRow key={e.project_id} entry={e} />
              ))}
            </section>
          )}
        </>
      )}
    </div>
  );
}

export default PortfolioLearningPanel;
