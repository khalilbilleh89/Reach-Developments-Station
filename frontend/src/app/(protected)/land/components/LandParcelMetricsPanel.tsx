"use client";

/**
 * LandParcelMetricsPanel
 *
 * Displays server-computed underwriting basis metrics for a land parcel.
 * All values are read-only — they are derived by the backend Calculation Engine
 * and must never be treated as editable inputs.
 */

import React from "react";
import type { LandParcel } from "@/lib/land-types";

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function fmt(value: number | null, prefix?: string): string {
  if (value === null || value === undefined) return "—";
  const p = prefix ? `${prefix} ` : "";
  if (Math.abs(value) >= 1_000_000) {
    return `${p}${(value / 1_000_000).toFixed(2)}M`;
  }
  if (Math.abs(value) >= 1_000) {
    return `${p}${(value / 1_000).toFixed(1)}K`;
  }
  return `${p}${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function fmtPerSqm(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 }) + " /m²";
}

function fmtPct(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return (value * 100).toFixed(1) + "%";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface MetricRowProps {
  label: string;
  value: string;
  highlight?: boolean;
}

function MetricRow({ label, value, highlight }: MetricRowProps) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "6px 0",
        borderBottom: "1px solid var(--color-border)",
      }}
    >
      <span
        style={{
          fontSize: "0.8rem",
          color: "var(--color-text-muted)",
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: "0.875rem",
          fontWeight: highlight ? 600 : 500,
          color: value === "—" ? "var(--color-text-muted)" : "var(--color-text)",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {value}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface LandParcelMetricsPanelProps {
  parcel: LandParcel;
}

export function LandParcelMetricsPanel({ parcel }: LandParcelMetricsPanelProps) {
  const currency = parcel.currency ?? undefined;

  const hasBasisMetrics =
    parcel.effective_land_basis !== null ||
    parcel.gross_land_price_per_sqm !== null ||
    parcel.effective_land_price_per_gross_sqm !== null ||
    parcel.effective_land_price_per_buildable_sqm !== null ||
    parcel.effective_land_price_per_sellable_sqm !== null;

  const hasResidualMetrics =
    parcel.supported_acquisition_price !== null ||
    parcel.residual_land_value !== null ||
    parcel.margin_impact !== null;

  if (!hasBasisMetrics && !hasResidualMetrics) {
    return (
      <div
        style={{
          padding: "16px",
          background: "var(--color-surface-alt, #f9fafb)",
          borderRadius: 8,
          border: "1px solid var(--color-border)",
          fontSize: "0.8rem",
          color: "var(--color-text-muted)",
          textAlign: "center",
        }}
      >
        Computed metrics will appear once an acquisition price is entered.
      </div>
    );
  }

  return (
    <div
      style={{
        background: "var(--color-surface-alt, #f9fafb)",
        borderRadius: 8,
        border: "1px solid var(--color-border)",
        padding: "16px",
      }}
    >
      <p
        style={{
          margin: "0 0 12px",
          fontSize: "0.75rem",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          color: "var(--color-text-muted)",
        }}
      >
        Computed Underwriting Metrics
      </p>
      <p
        style={{
          margin: "0 0 12px",
          fontSize: "0.75rem",
          color: "var(--color-text-muted)",
          fontStyle: "italic",
        }}
      >
        Server-derived — read-only
      </p>

      {hasBasisMetrics && (
        <>
          <MetricRow
            label="Effective Land Basis"
            value={fmt(parcel.effective_land_basis, currency)}
            highlight
          />
          <MetricRow
            label="Gross Land Price / m²"
            value={fmtPerSqm(parcel.gross_land_price_per_sqm)}
          />
          <MetricRow
            label="Effective Price / Gross m²"
            value={fmtPerSqm(parcel.effective_land_price_per_gross_sqm)}
          />
          <MetricRow
            label="Effective Price / Buildable m²"
            value={fmtPerSqm(parcel.effective_land_price_per_buildable_sqm)}
          />
          <MetricRow
            label="Effective Price / Sellable m²"
            value={fmtPerSqm(parcel.effective_land_price_per_sellable_sqm)}
          />
        </>
      )}

      {hasResidualMetrics && (
        <div style={{ marginTop: hasBasisMetrics ? 12 : 0 }}>
          <p
            style={{
              margin: "0 0 8px",
              fontSize: "0.75rem",
              fontWeight: 600,
              color: "var(--color-text-muted)",
            }}
          >
            Residual Valuation
          </p>
          <MetricRow
            label="Supported Acquisition Price"
            value={fmt(parcel.supported_acquisition_price, currency)}
            highlight
          />
          <MetricRow
            label="Residual Land Value"
            value={fmt(parcel.residual_land_value, currency)}
          />
          <MetricRow
            label="Margin Impact"
            value={fmtPct(parcel.margin_impact)}
          />
        </div>
      )}
    </div>
  );
}
