"use client";

/**
 * FeasibilityUnitEconomicsPanel.tsx
 *
 * Renders per-sqm unit economics derived from feasibility assumptions and
 * the backend-computed result. Values are displayed with full precision
 * (no K/M compacting) because rounding per-sqm amounts would materially
 * distort investment signals.
 *
 * PR-V6-01 — Unit Economics Panel
 * PR-V6-01A — Hardening: precise formatting, extracted component
 */

import React from "react";
import { formatCurrencyPrecise } from "@/lib/format-utils";
import type {
  FeasibilityAssumptions,
  FeasibilityResult,
} from "@/lib/feasibility-types";

interface UnitEconomicsPanelProps {
  result: FeasibilityResult;
  assumptions: FeasibilityAssumptions | null;
}

export default function FeasibilityUnitEconomicsPanel({
  result,
  assumptions,
}: UnitEconomicsPanelProps) {
  const kpiRow = (label: string, value: string) => (
    <div
      key={label}
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "10px 0",
        borderBottom: "1px solid var(--color-border)",
      }}
    >
      <span style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>
        {label}
      </span>
      <span
        style={{
          fontSize: "0.875rem",
          fontWeight: 500,
          color: "var(--color-text)",
        }}
      >
        {value}
      </span>
    </div>
  );

  return (
    <div
      data-testid="unit-economics-panel"
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        padding: "20px 24px",
        marginBottom: 24,
      }}
    >
      <h3
        style={{
          margin: "0 0 16px",
          fontSize: "0.9rem",
          fontWeight: 600,
          color: "var(--color-text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        Unit Economics
      </h3>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
          gap: "0 32px",
        }}
      >
        <div>
          {kpiRow(
            "Sale Price / sqm",
            assumptions?.avg_sale_price_per_sqm != null
              ? formatCurrencyPrecise(assumptions.avg_sale_price_per_sqm)
              : "—",
          )}
          {kpiRow(
            "Construction Cost / sqm",
            assumptions?.construction_cost_per_sqm != null
              ? formatCurrencyPrecise(assumptions.construction_cost_per_sqm)
              : "—",
          )}
        </div>
        <div>
          {kpiRow(
            "Profit / sqm",
            result.profit_per_sqm != null
              ? formatCurrencyPrecise(result.profit_per_sqm)
              : "—",
          )}
          {kpiRow(
            "Break-Even Price / sqm",
            result.break_even_price != null
              ? formatCurrencyPrecise(result.break_even_price)
              : "—",
          )}
        </div>
      </div>
    </div>
  );
}
