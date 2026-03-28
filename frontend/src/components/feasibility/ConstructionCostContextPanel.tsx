"use client";

/**
 * ConstructionCostContextPanel.tsx
 *
 * Read-only construction cost context panel for the feasibility run detail view.
 *
 * Displays recorded project construction cost totals alongside the
 * feasibility-side assumed construction cost so reviewers can compare
 * both in the same surface.
 *
 * This component:
 *  - is fully read-only and never mutates feasibility or construction records
 *  - is null-safe for all data states (no project, no records, no assumptions)
 *  - clearly labels comparison values as context, not formula outputs
 *  - formats Decimal string fields from the backend before display
 *
 * PR-V6-10 — Feasibility Detail Integration with Construction Cost Records
 */

import React from "react";
import { formatCurrencyPrecise } from "@/lib/format-utils";
import type { FeasibilityConstructionCostContext } from "@/lib/feasibility-types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Parse a Decimal string returned by the backend into a float for display. */
function parseDecimalStr(value: string | null | undefined): number | null {
  if (value == null) return null;
  const parsed = parseFloat(value);
  return isNaN(parsed) ? null : parsed;
}

function formatDecimalStr(value: string | null | undefined): string {
  const n = parseDecimalStr(value);
  if (n === null) return "—";
  return formatCurrencyPrecise(n);
}

function formatVariancePct(value: number | null | undefined): string {
  if (value == null) return "—";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(2)}%`;
}

function varianceColor(value: number | null | undefined): string {
  if (value == null) return "var(--color-text-muted)";
  if (value > 0) return "#b91c1c"; // recorded exceeds assumed — cost overrun
  if (value < 0) return "#15803d"; // recorded below assumed — cost saving
  return "var(--color-text)";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function PanelRow({
  label,
  value,
  testId,
  valueStyle,
}: {
  label: string;
  value: string;
  testId?: string;
  valueStyle?: React.CSSProperties;
}) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "8px 0",
        borderBottom: "1px solid var(--color-border)",
      }}
    >
      <span style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>
        {label}
      </span>
      <span
        data-testid={testId}
        style={{
          fontSize: "0.875rem",
          fontWeight: 500,
          ...valueStyle,
        }}
      >
        {value}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

function LoadingState() {
  return (
    <div
      data-testid="construction-cost-context-loading"
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        padding: "16px 24px",
        marginTop: 24,
      }}
    >
      <h3
        style={{
          margin: "0 0 12px",
          fontSize: "0.9rem",
          fontWeight: 600,
          color: "var(--color-text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        Construction Cost Context
      </h3>
      <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--color-text-muted)" }}>
        Loading construction cost context…
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

function ErrorState({ message }: { message: string }) {
  return (
    <div
      role="alert"
      data-testid="construction-cost-context-error"
      style={{
        background: "#fef2f2",
        border: "1px solid #fecaca",
        borderRadius: 8,
        padding: "12px 16px",
        marginTop: 24,
        color: "#b91c1c",
        fontSize: "0.875rem",
      }}
    >
      {message}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface ConstructionCostContextPanelProps {
  /** When undefined, the panel renders a loading state. */
  context: FeasibilityConstructionCostContext | null | undefined;
  /** When true, the panel renders a loading state regardless of context. */
  loading?: boolean;
  /** When provided, the panel renders an error state. */
  error?: string | null;
}

/**
 * ConstructionCostContextPanel
 *
 * Renders a read-only comparison panel showing recorded construction cost
 * totals alongside the feasibility-side assumed construction cost.
 *
 * State matrix:
 *  - loading=true OR context=undefined          → loading state
 *  - error provided                             → error state
 *  - context=null                               → error/unavailable state
 *  - context.project_id=null                   → no-project empty state
 *  - context.has_cost_records=false             → no-records empty state
 *  - both sides present                         → full comparison with variance
 *  - only one side present                      → partial comparison
 */
export default function ConstructionCostContextPanel({
  context,
  loading = false,
  error,
}: ConstructionCostContextPanelProps): React.ReactElement {
  if (loading || context === undefined) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  if (context === null) {
    return (
      <ErrorState message="Construction cost context is currently unavailable." />
    );
  }

  const headingStyle: React.CSSProperties = {
    margin: "0 0 4px",
    fontSize: "0.9rem",
    fontWeight: 600,
    color: "var(--color-text-muted)",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  };

  const subtitleStyle: React.CSSProperties = {
    margin: "0 0 16px",
    fontSize: "0.75rem",
    color: "var(--color-text-muted)",
    fontStyle: "italic",
  };

  const hasRecorded = context.has_cost_records;
  const hasAssumed = context.assumed_construction_cost != null;
  const hasVariance = context.variance_amount != null;

  const variancePctColor = varianceColor(context.variance_pct);

  return (
    <div
      data-testid="construction-cost-context-panel"
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        padding: "20px 24px",
        marginTop: 24,
      }}
    >
      <h3 style={headingStyle}>Construction Cost Context</h3>
      <p style={subtitleStyle}>
        Read-only comparison — recorded cost totals vs. feasibility assumption.
        This panel does not update feasibility results.
      </p>

      {/* Note / empty state */}
      <div
        data-testid="construction-cost-context-note"
        style={{
          padding: "8px 12px",
          background: "#f8fafc",
          border: "1px solid var(--color-border)",
          borderRadius: 6,
          fontSize: "0.8rem",
          color: "var(--color-text-muted)",
          marginBottom: 16,
        }}
      >
        {context.note}
      </div>

      {/* Core comparison rows */}
      <div>
        {/* Recorded total */}
        <PanelRow
          label="Recorded Construction Cost (active records)"
          value={hasRecorded ? formatDecimalStr(context.recorded_construction_cost_total) : "No cost records"}
          testId="recorded-construction-cost"
          valueStyle={hasRecorded ? { fontWeight: 600 } : { color: "var(--color-text-muted)", fontStyle: "italic" }}
        />

        {/* Record count */}
        <PanelRow
          label="Active Record Count"
          value={String(context.active_record_count)}
          testId="active-record-count"
        />

        {/* Assumed construction cost */}
        <PanelRow
          label="Assumed Construction Cost (cost/sqm × area)"
          value={
            hasAssumed
              ? formatCurrencyPrecise(context.assumed_construction_cost!)
              : "Assumptions not yet defined"
          }
          testId="assumed-construction-cost"
          valueStyle={hasAssumed ? { fontWeight: 600 } : { color: "var(--color-text-muted)", fontStyle: "italic" }}
        />

        {/* Variance — only when both sides exist */}
        {hasVariance && (
          <>
            <PanelRow
              label="Variance Amount (recorded − assumed)"
              value={formatDecimalStr(context.variance_amount)}
              testId="variance-amount"
              valueStyle={{ color: variancePctColor, fontWeight: 600 }}
            />
            <PanelRow
              label="Variance %"
              value={formatVariancePct(context.variance_pct)}
              testId="variance-pct"
              valueStyle={{ color: variancePctColor, fontWeight: 600 }}
            />
          </>
        )}
      </div>

      {/* Grouped breakdowns — only when cost records exist */}
      {hasRecorded && context.by_category && Object.keys(context.by_category).length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div
            style={{
              fontSize: "0.75rem",
              fontWeight: 600,
              color: "var(--color-text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 8,
              paddingBottom: 4,
              borderBottom: "2px solid var(--color-border)",
            }}
          >
            By Category
          </div>
          <div data-testid="by-category-breakdown">
            {Object.entries(context.by_category).map(([cat, total]) => (
              <PanelRow
                key={cat}
                label={cat.replace(/_/g, " ")}
                value={formatDecimalStr(total)}
              />
            ))}
          </div>
        </div>
      )}

      {hasRecorded && context.by_stage && Object.keys(context.by_stage).length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div
            style={{
              fontSize: "0.75rem",
              fontWeight: 600,
              color: "var(--color-text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 8,
              paddingBottom: 4,
              borderBottom: "2px solid var(--color-border)",
            }}
          >
            By Stage
          </div>
          <div data-testid="by-stage-breakdown">
            {Object.entries(context.by_stage).map(([stage, total]) => (
              <PanelRow
                key={stage}
                label={stage.replace(/_/g, " ")}
                value={formatDecimalStr(total)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
