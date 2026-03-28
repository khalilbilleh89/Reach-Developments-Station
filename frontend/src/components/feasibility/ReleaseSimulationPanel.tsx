"use client";

/**
 * ReleaseSimulationPanel.tsx
 *
 * Release Strategy Simulation Engine panel (PR-V7-04).
 *
 * Allows developers to run what-if simulations by adjusting:
 *  - Price adjustment % (slider + numeric input)
 *  - Phase delay months (slider + numeric input)
 *  - Release strategy (hold / accelerate / maintain)
 *
 * Displays for each simulation:
 *  - Simulated IRR vs baseline
 *  - IRR delta with direction indicator
 *  - NPV
 *  - Cashflow delay months
 *  - Risk score badge
 *
 * Multi-scenario comparison mode shows all scenarios side by side,
 * sorted by IRR descending.
 *
 * Design principles:
 *  - All simulation values are sourced from the backend; no recomputation here.
 *  - Simulation state is never persisted.
 *  - Renders a safe null/loading/error state at each phase.
 *
 * PR-V7-04 — Release Strategy Simulation Engine
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  simulateReleaseStrategies,
  simulateReleaseStrategy,
} from "@/lib/release-simulation-api";
import type {
  ReleaseStrategy,
  RiskScore,
  SimulationResult,
  SimulationScenarioInput,
} from "@/lib/release-simulation-types";
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

function irrDeltaStyle(delta: number | null): React.CSSProperties {
  if (delta == null) return { color: "var(--color-text-muted)" };
  if (delta > 0) return { color: "#15803d", fontWeight: 700 };
  if (delta < 0) return { color: "#b91c1c", fontWeight: 700 };
  return { color: "var(--color-text-muted)", fontWeight: 700 };
}

function formatIrrDelta(delta: number | null): string {
  if (delta == null) return "—";
  const pct = (delta * 100).toFixed(2);
  if (delta > 0) return `+${pct}%`;
  if (delta < 0) return `${pct}%`;
  return "0.00%";
}

function formatIrr(irr: number): string {
  return `${(irr * 100).toFixed(2)}%`;
}

function strategyLabel(strategy: ReleaseStrategy): string {
  if (strategy === "hold") return "Hold";
  if (strategy === "accelerate") return "Accelerate";
  return "Maintain";
}

function cashflowDelayLabel(months: number): string {
  if (months === 0) return "On Plan";
  if (months > 0) return `+${months}mo delayed`;
  return `${Math.abs(months)}mo early`;
}

// ---------------------------------------------------------------------------
// Default scenario
// ---------------------------------------------------------------------------

const DEFAULT_SCENARIO: SimulationScenarioInput = {
  price_adjustment_pct: 0,
  phase_delay_months: 0,
  release_strategy: "maintain",
  label: undefined,
};

const EMPTY_COMPARISON: SimulationScenarioInput[] = [
  { price_adjustment_pct: 0, phase_delay_months: 0, release_strategy: "maintain", label: "Base" },
  { price_adjustment_pct: 5, phase_delay_months: 0, release_strategy: "maintain", label: "+5% Price" },
  { price_adjustment_pct: -5, phase_delay_months: 3, release_strategy: "hold", label: "-5% + Delay" },
];

// ---------------------------------------------------------------------------
// ScenarioInputForm
// ---------------------------------------------------------------------------

interface ScenarioInputFormProps {
  scenario: SimulationScenarioInput;
  onChange: (updated: SimulationScenarioInput) => void;
  disabled?: boolean;
}

function ScenarioInputForm({ scenario, onChange, disabled }: ScenarioInputFormProps) {
  return (
    <div
      style={{ display: "flex", flexDirection: "column", gap: 16 }}
      data-testid="scenario-input-form"
    >
      {/* Price Adjustment */}
      <div>
        <label
          style={{
            display: "block",
            fontSize: "0.8125rem",
            fontWeight: 600,
            color: "var(--color-text)",
            marginBottom: 6,
          }}
        >
          Price Adjustment:{" "}
          <span
            style={{ color: scenario.price_adjustment_pct >= 0 ? "#15803d" : "#b91c1c" }}
            data-testid="price-pct-display"
          >
            {scenario.price_adjustment_pct >= 0 ? "+" : ""}
            {scenario.price_adjustment_pct.toFixed(1)}%
          </span>
        </label>
        <input
          type="range"
          min={-50}
          max={50}
          step={0.5}
          value={scenario.price_adjustment_pct}
          disabled={disabled}
          onChange={(e) =>
            onChange({ ...scenario, price_adjustment_pct: parseFloat(e.target.value) })
          }
          style={{ width: "100%" }}
          data-testid="price-pct-slider"
          aria-label="Price adjustment percentage"
        />
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: "0.6875rem",
            color: "var(--color-text-muted)",
            marginTop: 2,
          }}
        >
          <span>-50%</span>
          <span>0%</span>
          <span>+50%</span>
        </div>
      </div>

      {/* Phase Delay */}
      <div>
        <label
          style={{
            display: "block",
            fontSize: "0.8125rem",
            fontWeight: 600,
            color: "var(--color-text)",
            marginBottom: 6,
          }}
        >
          Phase Delay:{" "}
          <span data-testid="delay-months-display">
            {scenario.phase_delay_months >= 0 ? "+" : ""}
            {scenario.phase_delay_months} months
          </span>
        </label>
        <input
          type="range"
          min={-24}
          max={60}
          step={1}
          value={scenario.phase_delay_months}
          disabled={disabled}
          onChange={(e) =>
            onChange({ ...scenario, phase_delay_months: parseInt(e.target.value, 10) })
          }
          style={{ width: "100%" }}
          data-testid="delay-months-slider"
          aria-label="Phase delay months"
        />
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: "0.6875rem",
            color: "var(--color-text-muted)",
            marginTop: 2,
          }}
        >
          <span>-24mo</span>
          <span>0</span>
          <span>+60mo</span>
        </div>
      </div>

      {/* Release Strategy */}
      <div>
        <label
          style={{
            display: "block",
            fontSize: "0.8125rem",
            fontWeight: 600,
            color: "var(--color-text)",
            marginBottom: 6,
          }}
        >
          Release Strategy
        </label>
        <div style={{ display: "flex", gap: 8 }}>
          {(["maintain", "accelerate", "hold"] as ReleaseStrategy[]).map((s) => (
            <button
              key={s}
              disabled={disabled}
              onClick={() => onChange({ ...scenario, release_strategy: s })}
              data-testid={`strategy-btn-${s}`}
              style={{
                padding: "6px 14px",
                borderRadius: 6,
                fontSize: "0.8125rem",
                fontWeight: scenario.release_strategy === s ? 700 : 400,
                border:
                  scenario.release_strategy === s
                    ? "2px solid var(--color-primary)"
                    : "1px solid var(--color-border)",
                background:
                  scenario.release_strategy === s
                    ? "var(--color-primary-light, #e0f2fe)"
                    : "var(--color-surface)",
                color:
                  scenario.release_strategy === s
                    ? "var(--color-primary)"
                    : "var(--color-text)",
                cursor: disabled ? "not-allowed" : "pointer",
                opacity: disabled ? 0.6 : 1,
              }}
            >
              {strategyLabel(s)}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SimulationResultCard
// ---------------------------------------------------------------------------

interface SimulationResultCardProps {
  result: SimulationResult;
  isTop?: boolean;
}

function SimulationResultCard({ result, isTop }: SimulationResultCardProps) {
  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: isTop
          ? "2px solid var(--color-primary, #0369a1)"
          : "1px solid var(--color-border)",
        borderRadius: 8,
        padding: "14px 16px",
        display: "flex",
        flexDirection: "column",
        gap: 10,
        flex: 1,
        minWidth: 200,
      }}
      data-testid={`simulation-result-card${result.label ? `-${result.label.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}` : ""}`}
    >
      {/* Header */}
      <div
        style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}
      >
        <span
          style={{ fontWeight: 700, fontSize: "0.9375rem", color: "var(--color-text)" }}
          data-testid="result-label"
        >
          {result.label ?? "Scenario"}
        </span>
        <span style={riskBadgeStyle(result.risk_score)} data-testid="risk-score-badge">
          {riskLabel(result.risk_score)}
        </span>
      </div>

      {/* IRR row */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <span
          style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--color-text)" }}
          data-testid="result-irr"
        >
          {formatIrr(result.irr)}
        </span>
        <span
          style={{ fontSize: "0.875rem", ...irrDeltaStyle(result.irr_delta) }}
          data-testid="result-irr-delta"
        >
          {formatIrrDelta(result.irr_delta)} vs baseline
        </span>
      </div>

      {/* KPI grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "6px 12px",
          fontSize: "0.8125rem",
        }}
      >
        <div>
          <span style={{ color: "var(--color-text-muted)" }}>NPV</span>
          <div style={{ fontWeight: 600, color: "var(--color-text)" }} data-testid="result-npv">
            {formatCurrency(result.npv)}
          </div>
        </div>
        <div>
          <span style={{ color: "var(--color-text-muted)" }}>Cashflow Timing</span>
          <div
            style={{ fontWeight: 600, color: "var(--color-text)" }}
            data-testid="result-cashflow-delay"
          >
            {cashflowDelayLabel(result.cashflow_delay_months)}
          </div>
        </div>
        <div>
          <span style={{ color: "var(--color-text-muted)" }}>Simulated GDV</span>
          <div style={{ fontWeight: 600, color: "var(--color-text)" }} data-testid="result-gdv">
            {formatCurrency(result.simulated_gdv)}
          </div>
        </div>
        <div>
          <span style={{ color: "var(--color-text-muted)" }}>Dev Period</span>
          <div
            style={{ fontWeight: 600, color: "var(--color-text)" }}
            data-testid="result-dev-period"
          >
            {result.simulated_dev_period_months}mo
          </div>
        </div>
      </div>

      {/* Inputs echoed */}
      <div
        style={{
          fontSize: "0.75rem",
          color: "var(--color-text-muted)",
          borderTop: "1px solid var(--color-border)",
          paddingTop: 8,
          display: "flex",
          gap: 8,
          flexWrap: "wrap",
        }}
      >
        <span>
          Price:{" "}
          {result.price_adjustment_pct >= 0 ? "+" : ""}
          {result.price_adjustment_pct.toFixed(1)}%
        </span>
        <span>·</span>
        <span>
          Delay: {result.phase_delay_months >= 0 ? "+" : ""}
          {result.phase_delay_months}mo
        </span>
        <span>·</span>
        <span>Strategy: {strategyLabel(result.release_strategy as ReleaseStrategy)}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

interface ReleaseSimulationPanelProps {
  projectId: string;
}

export function ReleaseSimulationPanel({ projectId }: ReleaseSimulationPanelProps) {
  // Single scenario state
  const [scenario, setScenario] = useState<SimulationScenarioInput>(DEFAULT_SCENARIO);
  const [singleResult, setSingleResult] = useState<SimulationResult | null>(null);
  const [singleLoading, setSingleLoading] = useState(false);
  const [singleError, setSingleError] = useState<string | null>(null);
  const [hasBaseline, setHasBaseline] = useState<boolean | null>(null);

  // Comparison state
  const [showComparison, setShowComparison] = useState(false);
  const [compareScenarios] = useState<SimulationScenarioInput[]>(EMPTY_COMPARISON);
  const [compareResults, setCompareResults] = useState<SimulationResult[]>([]);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  // Abort any in-flight request when the component unmounts.
  useEffect(() => {
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
  }, []);

  // ----- Run single simulation -----
  const runSimulation = useCallback(async () => {
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setSingleLoading(true);
    setSingleError(null);
    setSingleResult(null);

    try {
      const resp = await simulateReleaseStrategy(
        projectId,
        { scenario },
        controller.signal,
      );
      setSingleResult(resp.result);
      setHasBaseline(resp.has_feasibility_baseline);
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return;
      setSingleError("Simulation failed. Please try again.");
    } finally {
      setSingleLoading(false);
    }
  }, [projectId, scenario]);

  // ----- Run comparison -----
  const runComparison = useCallback(async () => {
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setCompareLoading(true);
    setCompareError(null);
    setCompareResults([]);

    try {
      const resp = await simulateReleaseStrategies(
        projectId,
        { scenarios: compareScenarios },
        controller.signal,
      );
      setCompareResults(resp.results);
      setHasBaseline(resp.has_feasibility_baseline);
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return;
      setCompareError("Comparison failed. Please try again.");
    } finally {
      setCompareLoading(false);
    }
  }, [projectId, compareScenarios]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 24,
        padding: "20px 0",
      }}
      data-testid="release-simulation-panel"
    >
      {/* Header */}
      <div>
        <h3
          style={{
            margin: 0,
            fontSize: "1rem",
            fontWeight: 700,
            color: "var(--color-text)",
          }}
        >
          Release Strategy Simulation
        </h3>
        <p
          style={{
            margin: "4px 0 0",
            fontSize: "0.875rem",
            color: "var(--color-text-muted)",
          }}
        >
          Model the impact of pricing and phasing decisions on IRR and cashflow.
          All simulations are read-only — no project data is modified.
        </p>
        {hasBaseline === false && (
          <p
            style={{
              marginTop: 8,
              fontSize: "0.8125rem",
              color: "#854d0e",
              background: "#fef9c3",
              padding: "6px 10px",
              borderRadius: 6,
            }}
            data-testid="no-baseline-notice"
          >
            No feasibility baseline found. Results use default assumptions and are indicative only.
          </p>
        )}
      </div>

      {/* Mode toggle */}
      <div style={{ display: "flex", gap: 8 }}>
        <button
          onClick={() => setShowComparison(false)}
          data-testid="mode-single"
          style={{
            padding: "6px 16px",
            borderRadius: 6,
            fontSize: "0.875rem",
            fontWeight: !showComparison ? 700 : 400,
            border: !showComparison
              ? "2px solid var(--color-primary)"
              : "1px solid var(--color-border)",
            background: !showComparison
              ? "var(--color-primary-light, #e0f2fe)"
              : "var(--color-surface)",
            color: !showComparison ? "var(--color-primary)" : "var(--color-text)",
            cursor: "pointer",
          }}
        >
          Single Scenario
        </button>
        <button
          onClick={() => setShowComparison(true)}
          data-testid="mode-compare"
          style={{
            padding: "6px 16px",
            borderRadius: 6,
            fontSize: "0.875rem",
            fontWeight: showComparison ? 700 : 400,
            border: showComparison
              ? "2px solid var(--color-primary)"
              : "1px solid var(--color-border)",
            background: showComparison
              ? "var(--color-primary-light, #e0f2fe)"
              : "var(--color-surface)",
            color: showComparison ? "var(--color-primary)" : "var(--color-text)",
            cursor: "pointer",
          }}
        >
          Compare Scenarios
        </button>
      </div>

      {/* Single scenario mode */}
      {!showComparison && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Input form */}
          <div
            style={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: 8,
              padding: "16px",
            }}
          >
            <ScenarioInputForm
              scenario={scenario}
              onChange={setScenario}
              disabled={singleLoading}
            />
            <button
              onClick={runSimulation}
              disabled={singleLoading}
              data-testid="run-simulation-btn"
              style={{
                marginTop: 16,
                padding: "8px 20px",
                background: "var(--color-primary, #0369a1)",
                color: "#fff",
                border: "none",
                borderRadius: 6,
                fontSize: "0.875rem",
                fontWeight: 600,
                cursor: singleLoading ? "not-allowed" : "pointer",
                opacity: singleLoading ? 0.7 : 1,
              }}
            >
              {singleLoading ? "Running…" : "Run Simulation"}
            </button>
          </div>

          {/* Single result */}
          {singleError && (
            <p
              style={{ fontSize: "0.875rem", color: "#b91c1c" }}
              data-testid="single-error"
            >
              {singleError}
            </p>
          )}
          {singleResult && (
            <div data-testid="single-result">
              <SimulationResultCard result={singleResult} />
            </div>
          )}
        </div>
      )}

      {/* Comparison mode */}
      {showComparison && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--color-text-muted)" }}>
            Compare {compareScenarios.length} pre-configured scenarios side by side.
            Results are ranked by IRR (highest first).
          </p>
          <button
            onClick={runComparison}
            disabled={compareLoading}
            data-testid="run-comparison-btn"
            style={{
              alignSelf: "flex-start",
              padding: "8px 20px",
              background: "var(--color-primary, #0369a1)",
              color: "#fff",
              border: "none",
              borderRadius: 6,
              fontSize: "0.875rem",
              fontWeight: 600,
              cursor: compareLoading ? "not-allowed" : "pointer",
              opacity: compareLoading ? 0.7 : 1,
            }}
          >
            {compareLoading ? "Running…" : "Run Comparison"}
          </button>

          {compareError && (
            <p
              style={{ fontSize: "0.875rem", color: "#b91c1c" }}
              data-testid="compare-error"
            >
              {compareError}
            </p>
          )}

          {compareResults.length > 0 && (
            <div
              style={{ display: "flex", gap: 12, flexWrap: "wrap" }}
              data-testid="comparison-results"
            >
              {compareResults.map((result, idx) => (
                <SimulationResultCard
                  key={`${result.price_adjustment_pct}|${result.phase_delay_months}|${result.release_strategy}|${result.label ?? idx}`}
                  result={result}
                  isTop={idx === 0}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
