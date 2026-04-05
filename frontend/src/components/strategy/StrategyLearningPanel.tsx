"use client";

/**
 * StrategyLearningPanel.tsx
 *
 * Project-level strategy learning & confidence panel (PR-V7-11).
 *
 * Shows:
 *  - Overall confidence score with trend indicator
 *  - Accuracy breakdown (pricing, phasing, overall)
 *  - Per-strategy-type metrics rows
 *  - Recalibrate button to recompute from latest outcomes
 *  - Safe empty state when no outcomes have been recorded
 *
 * Design principles:
 *  - All values are backend-derived; no client-side computation.
 *  - Renders safe empty states for all scenarios.
 *  - AbortController wired for clean unmount cancellation.
 *
 * PR-V7-11 — Strategy Learning & Confidence Recalibration Engine
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  getProjectStrategyLearning,
  recalibrateProjectLearning,
} from "@/lib/strategy-learning-api";
import type {
  StrategyLearningMetricsResponse,
  StrategyLearningResponse,
  TrendDirection,
} from "@/lib/strategy-learning-types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtPct(value: number | null): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function fmtConfidence(score: number): string {
  return `${(score * 100).toFixed(0)}%`;
}

function fmtDatetime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
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
      return "— Insufficient Data";
  }
}

function trendStyle(trend: TrendDirection): React.CSSProperties {
  const base: React.CSSProperties = {
    padding: "2px 10px",
    borderRadius: 12,
    fontSize: "0.75rem",
    fontWeight: 600,
  };
  switch (trend) {
    case "improving":
      return { ...base, background: "#dcfce7", color: "#15803d" };
    case "declining":
      return { ...base, background: "#fee2e2", color: "#b91c1c" };
    case "stable":
      return { ...base, background: "#dbeafe", color: "#1d4ed8" };
    case "insufficient_data":
      return { ...base, background: "#f3f4f6", color: "#6b7280" };
  }
}

function confidenceColor(score: number): string {
  if (score >= 0.7) return "#15803d";
  if (score >= 0.4) return "#854d0e";
  return "#b91c1c";
}

function strategyTypeLabel(stype: string): string {
  if (stype === "_all_") return "All Strategies";
  return stype.charAt(0).toUpperCase() + stype.slice(1);
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MetricsRow({
  row,
}: {
  row: StrategyLearningMetricsResponse;
}): React.ReactElement {
  return (
    <div
      style={{
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        padding: "14px 16px",
        marginBottom: 10,
        background: "#fff",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <span style={{ fontWeight: 600, color: "#111827", fontSize: "0.95rem" }}>
          {strategyTypeLabel(row.strategy_type)}
        </span>
        <span style={trendStyle(row.trend_direction)}>
          {trendLabel(row.trend_direction)}
        </span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
          gap: 10,
          marginBottom: 8,
        }}
      >
        <StatCard
          label="Confidence"
          value={fmtConfidence(row.confidence_score)}
          color={confidenceColor(row.confidence_score)}
        />
        <StatCard label="Sample Size" value={String(row.sample_size)} />
        <StatCard label="Match Rate" value={fmtPct(row.match_rate)} />
        <StatCard label="Divergence Rate" value={fmtPct(row.divergence_rate)} />
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: 10,
        }}
      >
        <StatCard
          label="Pricing Accuracy"
          value={fmtPct(row.accuracy_breakdown.pricing_accuracy_score)}
        />
        <StatCard
          label="Phasing Accuracy"
          value={fmtPct(row.accuracy_breakdown.phasing_accuracy_score)}
        />
        <StatCard
          label="Overall Accuracy"
          value={fmtPct(row.accuracy_breakdown.overall_strategy_accuracy)}
        />
      </div>

      {row.last_updated && (
        <p
          style={{ fontSize: "0.7rem", color: "#9ca3af", marginTop: 8 }}
        >
          Last updated: {fmtDatetime(row.last_updated)}
        </p>
      )}
    </div>
  );
}

function StatCard({
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
        background: "#f9fafb",
        borderRadius: 6,
        padding: "8px 12px",
      }}
    >
      <p style={{ fontSize: "0.7rem", color: "#6b7280", marginBottom: 2 }}>
        {label}
      </p>
      <p
        style={{
          fontSize: "1rem",
          fontWeight: 700,
          color: color ?? "#111827",
        }}
      >
        {value}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

interface StrategyLearningPanelProps {
  projectId: string;
}

export function StrategyLearningPanel({
  projectId,
}: StrategyLearningPanelProps): React.ReactElement {
  const [data, setData] = useState<StrategyLearningResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recalibrating, setRecalibrating] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(
    async (signal: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        const result = await getProjectStrategyLearning(projectId, signal);
        if (!signal.aborted) {
          setData(result);
        }
      } catch (err: unknown) {
        if (!signal.aborted) {
          setError(
            err instanceof Error ? err.message : "Failed to load learning data.",
          );
        }
      } finally {
        if (!signal.aborted) {
          setLoading(false);
        }
      }
    },
    [projectId],
  );

  useEffect(() => {
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  const handleRecalibrate = async () => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setRecalibrating(true);
    setError(null);
    try {
      const result = await recalibrateProjectLearning(projectId, ctrl.signal);
      if (!ctrl.signal.aborted) {
        setData(result);
      }
    } catch (err: unknown) {
      if (!ctrl.signal.aborted) {
        setError(
          err instanceof Error ? err.message : "Recalibration failed.",
        );
      }
    } finally {
      if (!ctrl.signal.aborted) {
        setRecalibrating(false);
      }
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: 16 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <h2 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#111827" }}>
          Strategy Learning & Confidence
        </h2>
        <button
          onClick={handleRecalibrate}
          disabled={recalibrating}
          style={{
            background: recalibrating ? "#9ca3af" : "#1d4ed8",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            padding: "7px 18px",
            fontSize: "0.85rem",
            fontWeight: 600,
            cursor: recalibrating ? "not-allowed" : "pointer",
          }}
        >
          {recalibrating ? "Recalibrating…" : "Recalibrate"}
        </button>
      </div>

      {loading && (
        <p style={{ color: "#6b7280", fontSize: "0.9rem" }}>
          Loading learning data…
        </p>
      )}

      {!loading && error && (
        <p style={{ color: "#b91c1c", fontSize: "0.9rem" }}>{error}</p>
      )}

      {!loading && !error && data && !data.has_sufficient_data && (
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
            No learning data yet
          </p>
          <p>
            Record execution outcomes for this project, then click{" "}
            <strong>Recalibrate</strong> to compute confidence metrics.
          </p>
        </div>
      )}

      {!loading && !error && data?.has_sufficient_data && (
        <>
          {data.overall_metrics && (
            <section style={{ marginBottom: 20 }}>
              <h3
                style={{
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  color: "#374151",
                  marginBottom: 8,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                Overall
              </h3>
              <MetricsRow row={data.overall_metrics} />
            </section>
          )}

          {data.strategy_breakdowns.length > 0 && (
            <section>
              <h3
                style={{
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  color: "#374151",
                  marginBottom: 8,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                By Strategy Type
              </h3>
              {data.strategy_breakdowns.map((row) => (
                <MetricsRow key={row.strategy_type} row={row} />
              ))}
            </section>
          )}
        </>
      )}
    </div>
  );
}

export default StrategyLearningPanel;
