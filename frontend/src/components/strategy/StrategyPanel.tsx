"use client";

/**
 * StrategyPanel.tsx
 *
 * Automated Strategy Generator panel (PR-V7-05).
 *
 * Displays the backend-generated recommended strategy for a project:
 *  - Best strategy: price adjustment, phase delay, release strategy
 *  - Simulated IRR and risk score
 *  - Human-readable reason
 *  - Top 3 strategy alternatives
 *
 * Design principles:
 *  - All strategy values are sourced from the backend; no recomputation here.
 *  - Strategy state is never persisted.
 *  - Renders a safe null/loading/error state at each phase.
 *
 * PR-V7-05 — Automated Strategy Generator (Decision Synthesis Layer)
 */

import React, { useEffect, useState } from "react";
import { getRecommendedStrategy } from "@/lib/strategy-api";
import type {
  RecommendedStrategyResponse,
} from "@/lib/strategy-types";
import type { RiskScore, SimulationResult } from "@/lib/release-simulation-types";
import { formatCurrency } from "@/lib/format-utils";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function riskBadgeStyle(risk: RiskScore): React.CSSProperties {
  if (risk === "low")
    return {
      background: "#dcfce7",
      color: "#15803d",
      padding: "2px 8px",
      borderRadius: 12,
      fontSize: "0.75rem",
      fontWeight: 600,
    };
  if (risk === "high")
    return {
      background: "#fee2e2",
      color: "#b91c1c",
      padding: "2px 8px",
      borderRadius: 12,
      fontSize: "0.75rem",
      fontWeight: 600,
    };
  return {
    background: "#fef9c3",
    color: "#854d0e",
    padding: "2px 8px",
    borderRadius: 12,
    fontSize: "0.75rem",
    fontWeight: 600,
  };
}

function riskLabel(risk: RiskScore): string {
  if (risk === "low") return "Low Risk";
  if (risk === "high") return "High Risk";
  return "Medium Risk";
}

function formatIrr(irr: number): string {
  return `${(irr * 100).toFixed(2)}%`;
}

function formatIrrDelta(delta: number | null): string {
  if (delta == null) return "—";
  const pct = (delta * 100).toFixed(2);
  if (delta > 0) return `+${pct}%`;
  if (delta < 0) return `${pct}%`;
  return "0.00%";
}

function irrDeltaColor(delta: number | null): string {
  if (delta == null) return "var(--color-text-muted)";
  if (delta > 0) return "#15803d";
  if (delta < 0) return "#b91c1c";
  return "var(--color-text-muted)";
}

function strategyLabel(s: string): string {
  if (s === "hold") return "Hold";
  if (s === "accelerate") return "Accelerate";
  return "Maintain";
}

function priceDirLabel(pct: number): string {
  if (pct > 0) return `+${pct.toFixed(1)}% price`;
  if (pct < 0) return `${pct.toFixed(1)}% price`;
  return "No price change";
}

function delayLabel(months: number): string {
  if (months === 0) return "No delay";
  if (months > 0) return `+${months}mo delay`;
  return `${Math.abs(months)}mo early`;
}

// ---------------------------------------------------------------------------
// StrategyResultCard
// ---------------------------------------------------------------------------

interface StrategyResultCardProps {
  result: SimulationResult;
  rank?: number;
  highlight?: boolean;
}

function StrategyResultCard({ result, rank, highlight }: StrategyResultCardProps) {
  return (
    <div
      data-testid={highlight ? "best-strategy-card" : `strategy-card-${rank}`}
      style={{
        border: highlight ? "2px solid #2563eb" : "1px solid var(--color-border)",
        borderRadius: 8,
        padding: 16,
        background: highlight ? "#eff6ff" : "var(--color-surface)",
      }}
    >
      {rank !== undefined && (
        <div
          style={{
            fontSize: "0.6875rem",
            fontWeight: 700,
            color: highlight ? "#2563eb" : "var(--color-text-muted)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            marginBottom: 8,
          }}
        >
          {highlight ? "★ Best Strategy" : `#${rank}`}
        </div>
      )}

      {/* Primary metrics row */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 16, marginBottom: 12 }}>
        <div>
          <div
            style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 2 }}
          >
            Price Adjustment
          </div>
          <div
            data-testid="price-adjustment"
            style={{
              fontWeight: 700,
              color:
                result.price_adjustment_pct > 0
                  ? "#15803d"
                  : result.price_adjustment_pct < 0
                  ? "#b91c1c"
                  : "var(--color-text)",
            }}
          >
            {priceDirLabel(result.price_adjustment_pct)}
          </div>
        </div>
        <div>
          <div
            style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 2 }}
          >
            Phase Delay
          </div>
          <div data-testid="phase-delay" style={{ fontWeight: 700 }}>
            {delayLabel(result.phase_delay_months)}
          </div>
        </div>
        <div>
          <div
            style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 2 }}
          >
            Release Strategy
          </div>
          <div data-testid="release-strategy" style={{ fontWeight: 700 }}>
            {strategyLabel(result.release_strategy)}
          </div>
        </div>
      </div>

      {/* IRR + risk row */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 16, marginBottom: 12 }}>
        <div>
          <div
            style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 2 }}
          >
            Simulated IRR
          </div>
          <div data-testid="simulated-irr" style={{ fontWeight: 700, fontSize: "1.1rem" }}>
            {formatIrr(result.irr)}
          </div>
        </div>
        <div>
          <div
            style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 2 }}
          >
            IRR Delta
          </div>
          <div
            data-testid="irr-delta"
            style={{ fontWeight: 700, color: irrDeltaColor(result.irr_delta) }}
          >
            {formatIrrDelta(result.irr_delta)}
          </div>
        </div>
        <div>
          <div
            style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 2 }}
          >
            NPV
          </div>
          <div data-testid="npv" style={{ fontWeight: 700 }}>
            {formatCurrency(result.npv)}
          </div>
        </div>
        <div>
          <div
            style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 2 }}
          >
            Risk
          </div>
          <span data-testid="risk-score" style={riskBadgeStyle(result.risk_score)}>
            {riskLabel(result.risk_score)}
          </span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// StrategyPanel
// ---------------------------------------------------------------------------

export interface StrategyPanelProps {
  projectId: string;
}

export function StrategyPanel({ projectId }: StrategyPanelProps) {
  const [response, setResponse] = useState<RecommendedStrategyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    getRecommendedStrategy(projectId, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setResponse(data);
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          err instanceof Error ? err.message : "Failed to load recommended strategy.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [projectId]);

  return (
    <div
      data-testid="strategy-panel"
      style={{
        padding: 24,
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        background: "var(--color-surface)",
      }}
    >
      <h3
        style={{
          margin: "0 0 16px",
          fontSize: "1rem",
          fontWeight: 700,
          color: "var(--color-text)",
        }}
      >
        Recommended Strategy
      </h3>

      {loading && (
        <div data-testid="strategy-loading" style={{ color: "var(--color-text-muted)" }}>
          Generating strategies…
        </div>
      )}

      {!loading && error && (
        <div
          data-testid="strategy-error"
          style={{ color: "#b91c1c", fontSize: "0.875rem" }}
        >
          {error}
        </div>
      )}

      {!loading && !error && response && (
        <>
          {!response.has_feasibility_baseline && (
            <div
              data-testid="no-baseline-notice"
              style={{
                background: "#fef9c3",
                border: "1px solid #fde047",
                borderRadius: 6,
                padding: "8px 12px",
                fontSize: "0.8125rem",
                color: "#854d0e",
                marginBottom: 16,
              }}
            >
              No feasibility baseline found. Strategies are indicative only.
            </div>
          )}

          {/* Best strategy */}
          {response.best_strategy ? (
            <div style={{ marginBottom: 20 }}>
              <StrategyResultCard
                result={response.best_strategy}
                highlight
              />
              <div
                data-testid="strategy-reason"
                style={{
                  marginTop: 12,
                  padding: "10px 14px",
                  background: "#f0f9ff",
                  border: "1px solid #bae6fd",
                  borderRadius: 6,
                  fontSize: "0.8125rem",
                  color: "#0369a1",
                }}
              >
                {response.reason}
              </div>
            </div>
          ) : (
            <div
              data-testid="no-strategy-available"
              style={{ color: "var(--color-text-muted)", fontSize: "0.875rem" }}
            >
              No strategy could be generated.
            </div>
          )}

          {/* Top 3 strategies */}
          {response.top_strategies.length > 0 && (
            <div>
              <h4
                style={{
                  margin: "0 0 12px",
                  fontSize: "0.875rem",
                  fontWeight: 600,
                  color: "var(--color-text)",
                }}
              >
                Top Strategies
              </h4>
              <div
                data-testid="top-strategies-list"
                style={{ display: "flex", flexDirection: "column", gap: 10 }}
              >
                {response.top_strategies.map((result, idx) => (
                  <StrategyResultCard
                    key={`${result.price_adjustment_pct}-${result.phase_delay_months}-${result.release_strategy}-${idx}`}
                    result={result}
                    rank={idx + 1}
                  />
                ))}
              </div>
            </div>
          )}

          <div
            style={{
              marginTop: 16,
              fontSize: "0.75rem",
              color: "var(--color-text-muted)",
            }}
          >
            {response.generated_scenario_count} scenarios evaluated
          </div>
        </>
      )}
    </div>
  );
}
