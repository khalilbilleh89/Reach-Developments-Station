"use client";

/**
 * ProjectAbsorptionPanel.tsx
 *
 * Read-only absorption metrics panel for a project.
 *
 * Displays actual vs planned absorption rate, sell-through progress,
 * IRR comparison, and revenue timing vs plan derived from live sales
 * and feasibility data.
 *
 * Design principles:
 *  - All metric values are sourced from the backend; no recomputation here.
 *  - Renders a safe null state when data is unavailable.
 *  - Trend indicators are purely visual — no additional calculations.
 *
 * PR-V7-01 — Sales Absorption Feedback Loop → Feasibility Engine
 */

import React, { useEffect, useRef, useState } from "react";
import { getProjectAbsorptionMetrics } from "@/lib/absorption-api";
import type { ProjectAbsorptionMetrics } from "@/lib/absorption-types";
import { formatCurrency } from "@/lib/format-utils";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(n: number | null | undefined, decimals = 1): string {
  if (n == null) return "—";
  return n.toFixed(decimals);
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${n.toFixed(1)}%`;
}

function fmtIrr(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${(n * 100).toFixed(2)}%`;
}

function fmtIrrDelta(n: number | null | undefined): string {
  if (n == null) return "—";
  const sign = n >= 0 ? "+" : "";
  return `${sign}${(n * 100).toFixed(2)}pp`;
}

function absorptionVsPlanColor(pct: number | null): string {
  if (pct == null) return "var(--color-text-muted)";
  if (pct >= 100) return "#15803d";
  if (pct >= 80) return "#92400e";
  return "#b91c1c";
}

function irrDeltaColor(delta: number | null): string {
  if (delta == null) return "var(--color-text-muted)";
  if (delta > 0) return "#15803d";
  if (delta < 0) return "#b91c1c";
  return "var(--color-text)";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MetricRow({
  label,
  value,
  valueStyle,
  testId,
}: {
  label: string;
  value: string;
  valueStyle?: React.CSSProperties;
  testId?: string;
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
        style={{ fontSize: "0.875rem", fontWeight: 500, ...valueStyle }}
        data-testid={testId}
      >
        {value}
      </span>
    </div>
  );
}

function SectionHeader({ title }: { title: string }) {
  return (
    <h4
      style={{
        fontSize: "0.8125rem",
        fontWeight: 600,
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        color: "var(--color-text-muted)",
        margin: "16px 0 4px",
      }}
    >
      {title}
    </h4>
  );
}

function SellThroughBar({ pct }: { pct: number | null }) {
  const value = pct ?? 0;
  const color =
    value >= 50 ? "#15803d" : value >= 20 ? "#92400e" : "#b91c1c";
  return (
    <div
      style={{
        background: "var(--color-border)",
        borderRadius: 4,
        height: 8,
        overflow: "hidden",
        margin: "8px 0",
      }}
    >
      <div
        style={{
          width: `${Math.min(value, 100)}%`,
          height: "100%",
          background: color,
          transition: "width 0.3s ease",
        }}
        data-testid="sell-through-bar"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface ProjectAbsorptionPanelProps {
  projectId: string;
}

export function ProjectAbsorptionPanel({
  projectId,
}: ProjectAbsorptionPanelProps) {
  const [data, setData] = useState<ProjectAbsorptionMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    getProjectAbsorptionMetrics(projectId, controller.signal)
      .then((metrics) => {
        if (!controller.signal.aborted) {
          setData(metrics);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            err instanceof Error ? err.message : "Failed to load absorption metrics.",
          );
          setLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [projectId]);

  if (loading) {
    return (
      <div
        style={{ padding: "16px", color: "var(--color-text-muted)" }}
        data-testid="absorption-panel-loading"
      >
        Loading absorption metrics…
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{ padding: "16px", color: "#b91c1c" }}
        data-testid="absorption-panel-error"
      >
        {error}
      </div>
    );
  }

  if (!data) return null;

  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        padding: "20px",
        marginTop: 16,
      }}
      data-testid="absorption-panel"
    >
      <h3
        style={{
          fontSize: "1rem",
          fontWeight: 600,
          margin: "0 0 4px",
          color: "var(--color-text)",
        }}
      >
        Absorption Metrics
      </h3>
      <p
        style={{
          fontSize: "0.8125rem",
          color: "var(--color-text-muted)",
          margin: "0 0 12px",
        }}
      >
        Actual sales performance vs feasibility plan
      </p>

      {/* Sell-through progress */}
      <SectionHeader title="Inventory & Sell-Through" />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "4px 16px",
          marginBottom: 4,
        }}
      >
        <MetricRow
          label="Total Units"
          value={String(data.total_units)}
          testId="total-units"
        />
        <MetricRow
          label="Sold Units"
          value={String(data.sold_units)}
          testId="sold-units"
        />
        <MetricRow
          label="Reserved"
          value={String(data.reserved_units)}
        />
        <MetricRow
          label="Available"
          value={String(data.available_units)}
        />
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <span style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>
          Sell-Through
        </span>
        <span
          style={{
            fontSize: "0.875rem",
            fontWeight: 600,
            color: absorptionVsPlanColor(data.absorption_vs_plan_pct),
          }}
          data-testid="sell-through-pct"
        >
          {fmtPct(
            data.total_units > 0
              ? (data.sold_units / data.total_units) * 100
              : null,
          )}
        </span>
      </div>
      <SellThroughBar
        pct={
          data.total_units > 0
            ? (data.sold_units / data.total_units) * 100
            : null
        }
      />

      {/* Absorption velocity */}
      <SectionHeader title="Absorption Rate" />
      <MetricRow
        label="Actual (units/month)"
        value={
          data.absorption_rate_per_month != null
            ? fmt(data.absorption_rate_per_month, 2)
            : "—"
        }
        testId="actual-absorption-rate"
      />
      <MetricRow
        label="Planned (units/month)"
        value={
          data.planned_absorption_rate_per_month != null
            ? fmt(data.planned_absorption_rate_per_month, 2)
            : "—"
        }
        testId="planned-absorption-rate"
      />
      <MetricRow
        label="Actual vs Plan"
        value={fmtPct(data.absorption_vs_plan_pct)}
        valueStyle={{
          color: absorptionVsPlanColor(data.absorption_vs_plan_pct),
          fontWeight: 600,
        }}
        testId="absorption-vs-plan"
      />
      {data.avg_selling_time_days != null && (
        <MetricRow
          label="Avg Days Per Unit"
          value={fmt(data.avg_selling_time_days, 0)}
        />
      )}

      {/* Revenue */}
      <SectionHeader title="Revenue" />
      <MetricRow
        label="Contracted Revenue"
        value={formatCurrency(data.contracted_revenue)}
        testId="contracted-revenue"
      />
      {data.projected_revenue != null && (
        <MetricRow
          label="Projected (Feasibility GDV)"
          value={formatCurrency(data.projected_revenue)}
        />
      )}
      {data.revenue_realized_pct != null && (
        <MetricRow
          label="Revenue Realized"
          value={fmtPct(data.revenue_realized_pct)}
          valueStyle={{
            color:
              data.revenue_realized_pct >= 80
                ? "#15803d"
                : data.revenue_realized_pct >= 50
                  ? "#92400e"
                  : "#b91c1c",
          }}
          testId="revenue-realized-pct"
        />
      )}

      {/* IRR comparison */}
      {(data.planned_irr != null || data.actual_irr_estimate != null) && (
        <>
          <SectionHeader title="Feasibility vs Reality" />
          <MetricRow
            label="Planned IRR"
            value={fmtIrr(data.planned_irr)}
            testId="planned-irr"
          />
          <MetricRow
            label="Actual IRR (estimate)"
            value={fmtIrr(data.actual_irr_estimate)}
            testId="actual-irr"
          />
          {data.irr_delta != null && (
            <MetricRow
              label="IRR Delta"
              value={fmtIrrDelta(data.irr_delta)}
              valueStyle={{ color: irrDeltaColor(data.irr_delta), fontWeight: 600 }}
              testId="irr-delta"
            />
          )}
        </>
      )}

      {/* Timing note */}
      <div
        style={{
          marginTop: 16,
          padding: "10px 12px",
          background: "var(--color-background)",
          border: "1px solid var(--color-border)",
          borderRadius: 6,
          fontSize: "0.8125rem",
          color: "var(--color-text-muted)",
        }}
        data-testid="revenue-timing-note"
      >
        {data.revenue_timing_note}
      </div>

      {/* Cashflow delay indicator */}
      {data.cashflow_delay_months != null && data.cashflow_delay_months !== 0 && (
        <div
          style={{
            marginTop: 8,
            padding: "8px 12px",
            background:
              data.cashflow_delay_months > 0 ? "#fef2f2" : "#f0fdf4",
            border: `1px solid ${data.cashflow_delay_months > 0 ? "#fecaca" : "#bbf7d0"}`,
            borderRadius: 6,
            fontSize: "0.8125rem",
            color: data.cashflow_delay_months > 0 ? "#b91c1c" : "#15803d",
            fontWeight: 500,
          }}
          data-testid="cashflow-delay"
        >
          {data.cashflow_delay_months > 0
            ? `⚠ Revenue delayed ~${data.cashflow_delay_months.toFixed(1)} months vs plan`
            : `✓ Revenue arriving ~${Math.abs(data.cashflow_delay_months).toFixed(1)} months ahead of plan`}
        </div>
      )}
    </div>
  );
}
