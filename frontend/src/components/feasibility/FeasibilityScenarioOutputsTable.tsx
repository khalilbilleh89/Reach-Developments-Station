"use client";

/**
 * FeasibilityScenarioOutputsTable.tsx
 *
 * Renders the scenario_outputs field from a FeasibilityResult as a structured
 * sensitivity-analysis comparison table (Base / Upside / Downside / Investor).
 *
 * Metrics are read-only — no calculations are performed locally.
 * All displayed values come directly from the backend-persisted result.
 *
 * PR-FEAS-07 — Feasibility Scenario Outputs Typed Display
 */

import React from "react";
import { formatCurrency } from "@/lib/format-utils";
import { normalizeFeasibilityScenarioOutputs } from "@/lib/normalizers/feasibility-scenario-outputs";
import type {
  FeasibilityScenarioMetrics,
  FeasibilityScenarioOutputs,
} from "@/lib/feasibility-types";

// ---------------------------------------------------------------------------
// Column / row definitions
// ---------------------------------------------------------------------------

interface ScenarioColumn {
  key: keyof FeasibilityScenarioOutputs;
  label: string;
}

const SCENARIO_COLUMNS: ScenarioColumn[] = [
  { key: "base", label: "Base" },
  { key: "upside", label: "Upside" },
  { key: "downside", label: "Downside" },
  { key: "investor", label: "Investor" },
];

interface MetricRow {
  key: keyof FeasibilityScenarioMetrics;
  label: string;
  format: "currency" | "percent" | "number";
  highlight?: boolean;
}

const METRIC_ROWS: MetricRow[] = [
  { key: "gdv", label: "GDV", format: "currency", highlight: true },
  { key: "total_cost", label: "Total Cost", format: "currency" },
  { key: "construction_cost", label: "Construction Cost", format: "currency" },
  { key: "soft_cost", label: "Soft Cost", format: "currency" },
  { key: "finance_cost", label: "Finance Cost", format: "currency" },
  { key: "sales_cost", label: "Sales Cost", format: "currency" },
  { key: "developer_profit", label: "Developer Profit", format: "currency", highlight: true },
  { key: "profit_margin", label: "Margin", format: "percent", highlight: true },
  { key: "irr_estimate", label: "IRR (Est.)", format: "percent" },
];

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function formatMetricValue(
  value: number | null,
  format: "currency" | "percent" | "number",
): string {
  if (value === null) return "—";
  if (format === "currency") return formatCurrency(value);
  if (format === "percent") return `${(value * 100).toFixed(2)}%`;
  return value.toFixed(2);
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface FeasibilityScenarioOutputsTableProps {
  /**
   * Raw `scenario_outputs` value from FeasibilityResult.
   * May be null, a typed FeasibilityScenarioOutputs, or a raw backend payload.
   * The component normalizes it safely before rendering.
   */
  scenarioOutputs: unknown;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function FeasibilityScenarioOutputsTable({
  scenarioOutputs,
}: FeasibilityScenarioOutputsTableProps) {
  const normalized = normalizeFeasibilityScenarioOutputs(scenarioOutputs);

  // Determine which scenario columns are actually present in this result
  const activeColumns = SCENARIO_COLUMNS.filter(
    (col) => normalized != null && normalized[col.key] != null,
  );

  const panelStyle: React.CSSProperties = {
    background: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    borderRadius: 8,
    padding: "20px 24px",
    marginBottom: 24,
  };

  const headingStyle: React.CSSProperties = {
    margin: "0 0 16px",
    fontSize: "0.9rem",
    fontWeight: 600,
    color: "var(--color-text-muted)",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  };

  if (normalized === null || activeColumns.length === 0) {
    return (
      <div style={panelStyle} data-testid="scenario-outputs-table">
        <h3 style={headingStyle}>Scenario Analysis</h3>
        <p
          style={{
            margin: 0,
            fontSize: "0.875rem",
            color: "var(--color-text-muted)",
          }}
        >
          No scenario analysis data available for this result.
        </p>
      </div>
    );
  }

  const thStyle: React.CSSProperties = {
    textAlign: "right",
    padding: "8px 12px",
    fontSize: "0.8rem",
    fontWeight: 600,
    color: "var(--color-text-muted)",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    borderBottom: "2px solid var(--color-border)",
    whiteSpace: "nowrap",
  };

  const tdLabelStyle: React.CSSProperties = {
    padding: "9px 12px",
    fontSize: "0.875rem",
    color: "var(--color-text-muted)",
    borderBottom: "1px solid var(--color-border)",
    textAlign: "left",
    whiteSpace: "nowrap",
  };

  const tdValueStyle = (highlight: boolean): React.CSSProperties => ({
    padding: "9px 12px",
    fontSize: "0.875rem",
    fontWeight: highlight ? 600 : 400,
    color: "var(--color-text)",
    borderBottom: "1px solid var(--color-border)",
    textAlign: "right",
    whiteSpace: "nowrap",
  });

  return (
    <div style={panelStyle} data-testid="scenario-outputs-table">
      <h3 style={headingStyle}>Scenario Analysis</h3>
      <div style={{ overflowX: "auto" }}>
        <table
          aria-label="Scenario analysis outputs table"
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: "0.875rem",
          }}
        >
          <thead>
            <tr>
              <th
                scope="col"
                style={{
                  ...thStyle,
                  textAlign: "left",
                  borderRight: "1px solid var(--color-border)",
                }}
              >
                Metric
              </th>
              {activeColumns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  style={thStyle}
                  data-testid={`scenario-col-${col.key}`}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {METRIC_ROWS.map((row) => (
              <tr key={row.key}>
                <td
                  style={{
                    ...tdLabelStyle,
                    borderRight: "1px solid var(--color-border)",
                  }}
                >
                  {row.label}
                </td>
                {activeColumns.map((col) => {
                  const metrics = normalized[col.key];
                  const value = metrics != null ? metrics[row.key] : null;
                  return (
                    <td
                      key={col.key}
                      style={tdValueStyle(row.highlight ?? false)}
                      data-testid={`scenario-${col.key}-${row.key}`}
                    >
                      {formatMetricValue(value, row.format)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
