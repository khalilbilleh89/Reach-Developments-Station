"use client";

/**
 * FeasibilityDecisionSummary.tsx
 *
 * Top-level investment decision block for a feasibility run.
 *
 * Surfaces the backend-derived `decision`, `viability_status`, and `risk_level`
 * fields as a prominent, colour-coded summary block that leads the results
 * view.  No calculations are performed locally — all values come directly
 * from the persisted FeasibilityResult.
 *
 * PR-FEAS-08 — Feasibility Decision Summary & Investment Signal
 */

import React from "react";
import type {
  FeasibilityDecision,
  FeasibilityResult,
} from "@/lib/feasibility-types";
import {
  decisionLabel,
  viabilityLabel,
  riskLabel,
} from "@/lib/feasibility-decision-display";

// ---------------------------------------------------------------------------
// Colour tokens per decision value
// ---------------------------------------------------------------------------

interface DecisionTheme {
  background: string;
  border: string;
  color: string;
  icon: string;
}

function decisionTheme(decision: FeasibilityDecision | null): DecisionTheme {
  if (decision === "VIABLE")
    return {
      background: "#f0fdf4",
      border: "#86efac",
      color: "#15803d",
      icon: "✔",
    };
  if (decision === "MARGINAL")
    return {
      background: "#fefce8",
      border: "#fde047",
      color: "#854d0e",
      icon: "⚠",
    };
  if (decision === "NOT_VIABLE")
    return {
      background: "#fff1f2",
      border: "#fca5a5",
      color: "#b91c1c",
      icon: "✖",
    };
  return {
    background: "var(--color-surface)",
    border: "var(--color-border)",
    color: "var(--color-text-muted)",
    icon: "—",
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface FeasibilityDecisionSummaryProps {
  result: Pick<
    FeasibilityResult,
    "decision" | "viability_status" | "risk_level"
  >;
}

/**
 * FeasibilityDecisionSummary renders the investment decision as a prominent
 * colour-coded block above the KPI panel.
 *
 * When all three decision fields are null the component renders a neutral
 * "Decision not available" placeholder instead of empty content.
 */
export default function FeasibilityDecisionSummary({
  result,
}: FeasibilityDecisionSummaryProps): React.ReactElement {
  const { decision, viability_status, risk_level } = result;
  const theme = decisionTheme(decision);
  const hasData = decision !== null || viability_status !== null || risk_level !== null;

  if (!hasData) {
    return (
      <div
        role="region"
        aria-label="Investment decision summary"
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: 8,
          padding: "16px 24px",
          marginBottom: 16,
          color: "var(--color-text-muted)",
          fontSize: "0.875rem",
        }}
      >
        Decision not available
      </div>
    );
  }

  const rowStyle: React.CSSProperties = {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "6px 0",
  };

  const labelStyle: React.CSSProperties = {
    fontSize: "0.875rem",
    color: theme.color,
    fontWeight: 500,
    opacity: 0.8,
  };

  const valueStyle: React.CSSProperties = {
    fontSize: "0.875rem",
    fontWeight: 600,
    color: theme.color,
  };

  return (
    <div
      role="region"
      aria-label="Investment decision summary"
      style={{
        background: theme.background,
        border: `1px solid ${theme.border}`,
        borderRadius: 8,
        padding: "16px 24px",
        marginBottom: 16,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 12,
        }}
      >
        <span style={{ fontSize: "1rem", lineHeight: 1 }} aria-hidden="true">
          {theme.icon}
        </span>
        <span
          style={{
            fontSize: "0.75rem",
            fontWeight: 600,
            color: theme.color,
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          Investment Decision
        </span>
      </div>

      {/* Rows */}
      <div style={rowStyle}>
        <span style={labelStyle}>Decision</span>
        <span
          data-testid="decision-value"
          style={{ ...valueStyle, fontSize: "1rem" }}
        >
          {decisionLabel(decision)}
        </span>
      </div>
      <div style={rowStyle}>
        <span style={labelStyle}>Viability</span>
        <span data-testid="viability-value" style={valueStyle}>
          {viabilityLabel(viability_status)}
        </span>
      </div>
      <div style={rowStyle}>
        <span style={labelStyle}>Risk Level</span>
        <span data-testid="risk-value" style={valueStyle}>
          {riskLabel(risk_level)}
        </span>
      </div>
    </div>
  );
}
