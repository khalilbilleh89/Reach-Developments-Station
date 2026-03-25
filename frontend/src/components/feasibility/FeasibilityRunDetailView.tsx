"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import {
  getFeasibilityRun,
  getFeasibilityAssumptions,
  upsertFeasibilityAssumptions,
  calculateFeasibility,
  getFeasibilityResults,
} from "@/lib/feasibility-api";
import { ApiError } from "@/lib/api-client";
import { formatCurrency } from "@/lib/format-utils";
import type {
  FeasibilityAssumptions,
  FeasibilityAssumptionsCreate,
  FeasibilityDecision,
  FeasibilityResult,
  FeasibilityRiskLevel,
  FeasibilityRun,
  FeasibilityScenarioType,
  FeasibilityViabilityStatus,
} from "@/lib/feasibility-types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatScenarioType(type: FeasibilityScenarioType): string {
  const map: Record<FeasibilityScenarioType, string> = {
    base: "Base",
    upside: "Upside",
    downside: "Downside",
    investor: "Investor",
  };
  return map[type] ?? type;
}

function formatPercent(value: number | null): string {
  if (value === null) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

function formatNumber(value: number | null, decimals = 2): string {
  if (value === null) return "—";
  return value.toFixed(decimals);
}

function viabilityBadgeStyle(
  status: FeasibilityViabilityStatus | null,
): React.CSSProperties {
  if (status === "VIABLE")
    return { background: "#dcfce7", color: "#15803d", padding: "3px 10px", borderRadius: 12, fontWeight: 600, fontSize: "0.8rem" };
  if (status === "MARGINAL")
    return { background: "#fef9c3", color: "#854d0e", padding: "3px 10px", borderRadius: 12, fontWeight: 600, fontSize: "0.8rem" };
  if (status === "NOT_VIABLE")
    return { background: "#fee2e2", color: "#b91c1c", padding: "3px 10px", borderRadius: 12, fontWeight: 600, fontSize: "0.8rem" };
  return { background: "#f1f5f9", color: "#475569", padding: "3px 10px", borderRadius: 12, fontWeight: 600, fontSize: "0.8rem" };
}

function riskBadgeStyle(
  risk: FeasibilityRiskLevel | null,
): React.CSSProperties {
  if (risk === "LOW")
    return { background: "#dcfce7", color: "#15803d", padding: "3px 10px", borderRadius: 12, fontWeight: 600, fontSize: "0.8rem" };
  if (risk === "MEDIUM")
    return { background: "#fef9c3", color: "#854d0e", padding: "3px 10px", borderRadius: 12, fontWeight: 600, fontSize: "0.8rem" };
  if (risk === "HIGH")
    return { background: "#fee2e2", color: "#b91c1c", padding: "3px 10px", borderRadius: 12, fontWeight: 600, fontSize: "0.8rem" };
  return { background: "#f1f5f9", color: "#475569", padding: "3px 10px", borderRadius: 12, fontWeight: 600, fontSize: "0.8rem" };
}

function decisionLabel(decision: FeasibilityDecision | null): string {
  if (decision === "VIABLE") return "Proceed";
  if (decision === "MARGINAL") return "Review";
  if (decision === "NOT_VIABLE") return "Do Not Proceed";
  return "—";
}

// ---------------------------------------------------------------------------
// Source summary panel
// ---------------------------------------------------------------------------

interface SourceSummaryProps {
  run: FeasibilityRun;
}

function FeasibilitySourceSummary({ run }: SourceSummaryProps) {
  return (
    <div
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
        Run Source
      </h3>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
          gap: "12px 24px",
        }}
      >
        <div>
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 4 }}>
            Scenario Name
          </div>
          <div style={{ fontWeight: 500, fontSize: "0.875rem" }}>{run.scenario_name}</div>
        </div>
        <div>
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 4 }}>
            Scenario Type
          </div>
          <div style={{ fontWeight: 500, fontSize: "0.875rem" }}>
            {formatScenarioType(run.scenario_type)}
          </div>
        </div>
        <div>
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 4 }}>
            Scenario ID
          </div>
          <div
            style={{
              fontFamily: "monospace",
              fontSize: "0.8rem",
              color: run.scenario_id ? "var(--color-text)" : "var(--color-text-muted)",
            }}
          >
            {run.scenario_id ? run.scenario_id.substring(0, 12) + "…" : <em>None</em>}
          </div>
        </div>
        <div>
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 4 }}>
            Project ID
          </div>
          <div
            style={{
              fontFamily: "monospace",
              fontSize: "0.8rem",
              color: run.project_id ? "var(--color-text)" : "var(--color-text-muted)",
            }}
          >
            {run.project_id ? run.project_id.substring(0, 12) + "…" : <em>Unlinked</em>}
          </div>
        </div>
        {run.notes && (
          <div style={{ gridColumn: "1 / -1" }}>
            <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 4 }}>
              Notes
            </div>
            <div style={{ fontSize: "0.875rem" }}>{run.notes}</div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Assumptions form
// ---------------------------------------------------------------------------

interface AssumptionsFormProps {
  runId: string;
  existing: FeasibilityAssumptions | null;
  onSaved: (assumptions: FeasibilityAssumptions) => void;
}

function FeasibilityAssumptionsForm({
  runId,
  existing,
  onSaved,
}: AssumptionsFormProps) {
  const [sellableArea, setSellableArea] = useState(
    existing?.sellable_area_sqm != null ? String(existing.sellable_area_sqm) : "",
  );
  const [avgSalePrice, setAvgSalePrice] = useState(
    existing?.avg_sale_price_per_sqm != null
      ? String(existing.avg_sale_price_per_sqm)
      : "",
  );
  const [constructionCost, setConstructionCost] = useState(
    existing?.construction_cost_per_sqm != null
      ? String(existing.construction_cost_per_sqm)
      : "",
  );
  const [softCostRatio, setSoftCostRatio] = useState(
    existing?.soft_cost_ratio != null
      ? String((existing.soft_cost_ratio * 100).toFixed(2))
      : "",
  );
  const [financeCostRatio, setFinanceCostRatio] = useState(
    existing?.finance_cost_ratio != null
      ? String((existing.finance_cost_ratio * 100).toFixed(2))
      : "",
  );
  const [salesCostRatio, setSalesCostRatio] = useState(
    existing?.sales_cost_ratio != null
      ? String((existing.sales_cost_ratio * 100).toFixed(2))
      : "",
  );
  const [devPeriod, setDevPeriod] = useState(
    existing?.development_period_months != null
      ? String(existing.development_period_months)
      : "",
  );
  const [notes, setNotes] = useState(existing?.notes ?? "");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const allFilled =
    sellableArea.trim() !== "" &&
    avgSalePrice.trim() !== "" &&
    constructionCost.trim() !== "" &&
    softCostRatio.trim() !== "" &&
    financeCostRatio.trim() !== "" &&
    salesCostRatio.trim() !== "" &&
    devPeriod.trim() !== "";

  const handleSave = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setSaveError(null);

      const parsed = {
        sellable_area_sqm: parseFloat(sellableArea),
        avg_sale_price_per_sqm: parseFloat(avgSalePrice),
        construction_cost_per_sqm: parseFloat(constructionCost),
        soft_cost_ratio: parseFloat(softCostRatio) / 100,
        finance_cost_ratio: parseFloat(financeCostRatio) / 100,
        sales_cost_ratio: parseFloat(salesCostRatio) / 100,
        development_period_months: parseInt(devPeriod, 10),
      };

      // Area, price, and cost fields must be > 0; ratio fields allow 0; period must be >= 1.
      const positiveFields = ["sellable_area_sqm", "avg_sale_price_per_sqm", "construction_cost_per_sqm"] as const;
      const nonNegativeRatioFields = ["soft_cost_ratio", "finance_cost_ratio", "sales_cost_ratio"] as const;

      for (const field of positiveFields) {
        if (isNaN(parsed[field]) || parsed[field] <= 0) {
          setSaveError(`Invalid value for ${field.replace(/_/g, " ")}.`);
          return;
        }
      }
      for (const field of nonNegativeRatioFields) {
        if (isNaN(parsed[field]) || parsed[field] < 0) {
          setSaveError(`Invalid value for ${field.replace(/_/g, " ")}.`);
          return;
        }
      }
      if (isNaN(parsed.development_period_months) || parsed.development_period_months < 1) {
        setSaveError("Development period must be at least 1 month.");
        return;
      }

      const payload: FeasibilityAssumptionsCreate = {
        ...parsed,
        notes: notes.trim() || null,
      };

      setSaving(true);
      try {
        const saved = await upsertFeasibilityAssumptions(runId, payload);
        onSaved(saved);
      } catch (err: unknown) {
        setSaveError(
          err instanceof Error ? err.message : "Failed to save assumptions.",
        );
      } finally {
        setSaving(false);
      }
    },
    [
      runId,
      sellableArea,
      avgSalePrice,
      constructionCost,
      softCostRatio,
      financeCostRatio,
      salesCostRatio,
      devPeriod,
      notes,
      onSaved,
    ],
  );

  const fieldStyle: React.CSSProperties = {
    width: "100%",
    padding: "8px 12px",
    border: "1px solid var(--color-border)",
    borderRadius: 6,
    fontSize: "0.875rem",
    boxSizing: "border-box",
    background: "var(--color-surface)",
  };

  const labelStyle: React.CSSProperties = {
    display: "block",
    marginBottom: 4,
    fontSize: "0.8rem",
    fontWeight: 500,
    color: "var(--color-text-muted)",
  };

  return (
    <div
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
          margin: "0 0 20px",
          fontSize: "0.9rem",
          fontWeight: 600,
          color: "var(--color-text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        Assumptions
      </h3>
      <form onSubmit={handleSave}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: "16px",
            marginBottom: 20,
          }}
        >
          <div>
            <label htmlFor="fa-sellable-area" style={labelStyle}>
              Sellable Area (sqm) *
            </label>
            <input
              id="fa-sellable-area"
              type="number"
              min="0.01"
              step="any"
              value={sellableArea}
              onChange={(e) => setSellableArea(e.target.value)}
              style={fieldStyle}
              placeholder="e.g. 5000"
            />
          </div>
          <div>
            <label htmlFor="fa-avg-sale-price" style={labelStyle}>
              Avg Sale Price / sqm (AED) *
            </label>
            <input
              id="fa-avg-sale-price"
              type="number"
              min="0.01"
              step="any"
              value={avgSalePrice}
              onChange={(e) => setAvgSalePrice(e.target.value)}
              style={fieldStyle}
              placeholder="e.g. 3000"
            />
          </div>
          <div>
            <label htmlFor="fa-construction-cost" style={labelStyle}>
              Construction Cost / sqm (AED) *
            </label>
            <input
              id="fa-construction-cost"
              type="number"
              min="0.01"
              step="any"
              value={constructionCost}
              onChange={(e) => setConstructionCost(e.target.value)}
              style={fieldStyle}
              placeholder="e.g. 800"
            />
          </div>
          <div>
            <label htmlFor="fa-soft-cost" style={labelStyle}>
              Soft Cost Ratio (%) *
            </label>
            <input
              id="fa-soft-cost"
              type="number"
              min="0"
              max="100"
              step="any"
              value={softCostRatio}
              onChange={(e) => setSoftCostRatio(e.target.value)}
              style={fieldStyle}
              placeholder="e.g. 10"
            />
          </div>
          <div>
            <label htmlFor="fa-finance-cost" style={labelStyle}>
              Finance Cost Ratio (%) *
            </label>
            <input
              id="fa-finance-cost"
              type="number"
              min="0"
              max="100"
              step="any"
              value={financeCostRatio}
              onChange={(e) => setFinanceCostRatio(e.target.value)}
              style={fieldStyle}
              placeholder="e.g. 5"
            />
          </div>
          <div>
            <label htmlFor="fa-sales-cost" style={labelStyle}>
              Sales Cost Ratio (%) *
            </label>
            <input
              id="fa-sales-cost"
              type="number"
              min="0"
              max="100"
              step="any"
              value={salesCostRatio}
              onChange={(e) => setSalesCostRatio(e.target.value)}
              style={fieldStyle}
              placeholder="e.g. 3"
            />
          </div>
          <div>
            <label htmlFor="fa-dev-period" style={labelStyle}>
              Development Period (months) *
            </label>
            <input
              id="fa-dev-period"
              type="number"
              min="1"
              step="1"
              value={devPeriod}
              onChange={(e) => setDevPeriod(e.target.value)}
              style={fieldStyle}
              placeholder="e.g. 24"
            />
          </div>
        </div>
        <div style={{ marginBottom: 20 }}>
          <label htmlFor="fa-notes" style={labelStyle}>
            Notes
          </label>
          <textarea
            id="fa-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            style={{ ...fieldStyle, resize: "vertical" }}
            placeholder="Optional notes…"
          />
        </div>
        {saveError && (
          <p
            role="alert"
            style={{ color: "#b91c1c", fontSize: "0.875rem", marginBottom: 12 }}
          >
            {saveError}
          </p>
        )}
        <button
          type="submit"
          disabled={saving || !allFilled}
          style={{
            padding: "8px 24px",
            border: "none",
            borderRadius: 6,
            background:
              saving || !allFilled ? "#94a3b8" : "var(--color-primary, #2563eb)",
            color: "#fff",
            cursor: saving || !allFilled ? "not-allowed" : "pointer",
            fontSize: "0.875rem",
            fontWeight: 500,
          }}
        >
          {saving ? "Saving…" : "Save Assumptions"}
        </button>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Results panel
// ---------------------------------------------------------------------------

interface ResultsPanelProps {
  result: FeasibilityResult;
}

function FeasibilityResultsPanel({ result }: ResultsPanelProps) {
  const kpiRow = (
    label: string,
    value: string,
    highlight?: boolean,
  ) => (
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
          fontWeight: highlight ? 600 : 400,
          color: highlight ? "var(--color-text)" : "var(--color-text)",
        }}
      >
        {value}
      </span>
    </div>
  );

  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        padding: "20px 24px",
        marginBottom: 24,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 20,
        }}
      >
        <h3
          style={{
            margin: 0,
            fontSize: "0.9rem",
            fontWeight: 600,
            color: "var(--color-text-muted)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          Results
        </h3>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          {result.viability_status && (
            <span style={viabilityBadgeStyle(result.viability_status)}>
              {result.viability_status}
            </span>
          )}
          {result.risk_level && (
            <span style={riskBadgeStyle(result.risk_level)}>
              {result.risk_level} risk
            </span>
          )}
        </div>
      </div>

      {result.decision && (
        <div
          style={{
            padding: "12px 16px",
            background:
              result.decision === "VIABLE"
                ? "#dcfce7"
                : result.decision === "MARGINAL"
                  ? "#fef9c3"
                  : "#fee2e2",
            borderRadius: 6,
            marginBottom: 20,
            fontSize: "0.875rem",
            fontWeight: 500,
            color:
              result.decision === "VIABLE"
                ? "#15803d"
                : result.decision === "MARGINAL"
                  ? "#854d0e"
                  : "#b91c1c",
          }}
        >
          Decision: {decisionLabel(result.decision)}
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: "0 32px",
        }}
      >
        <div>
          <div
            style={{
              fontSize: "0.75rem",
              fontWeight: 600,
              color: "var(--color-text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 4,
              paddingBottom: 4,
              borderBottom: "2px solid var(--color-border)",
            }}
          >
            Revenue
          </div>
          {kpiRow("GDV", result.gdv != null ? formatCurrency(result.gdv) : "—", true)}
          {kpiRow("Developer Profit", result.developer_profit != null ? formatCurrency(result.developer_profit) : "—", true)}
          {kpiRow("Profit Margin", formatPercent(result.profit_margin), true)}
        </div>
        <div>
          <div
            style={{
              fontSize: "0.75rem",
              fontWeight: 600,
              color: "var(--color-text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 4,
              paddingBottom: 4,
              borderBottom: "2px solid var(--color-border)",
            }}
          >
            Costs
          </div>
          {kpiRow("Total Cost", result.total_cost != null ? formatCurrency(result.total_cost) : "—")}
          {kpiRow("Construction", result.construction_cost != null ? formatCurrency(result.construction_cost) : "—")}
          {kpiRow("Soft Cost", result.soft_cost != null ? formatCurrency(result.soft_cost) : "—")}
          {kpiRow("Finance Cost", result.finance_cost != null ? formatCurrency(result.finance_cost) : "—")}
          {kpiRow("Sales Cost", result.sales_cost != null ? formatCurrency(result.sales_cost) : "—")}
        </div>
        <div>
          <div
            style={{
              fontSize: "0.75rem",
              fontWeight: 600,
              color: "var(--color-text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 4,
              paddingBottom: 4,
              borderBottom: "2px solid var(--color-border)",
            }}
          >
            Returns
          </div>
          {kpiRow("IRR", formatPercent(result.irr))}
          {kpiRow("IRR Estimate", formatPercent(result.irr_estimate))}
          {kpiRow("Equity Multiple", result.equity_multiple != null ? formatNumber(result.equity_multiple) + "x" : "—")}
          {kpiRow("Payback Period", result.payback_period != null ? formatNumber(result.payback_period, 1) + " yrs" : "—")}
        </div>
        <div>
          <div
            style={{
              fontSize: "0.75rem",
              fontWeight: 600,
              color: "var(--color-text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 4,
              paddingBottom: 4,
              borderBottom: "2px solid var(--color-border)",
            }}
          >
            Break-Even
          </div>
          {kpiRow("Break-Even Price / sqm", result.break_even_price != null ? formatCurrency(result.break_even_price) : "—")}
          {kpiRow("Break-Even Sellable sqm", result.break_even_units != null ? formatNumber(result.break_even_units, 0) + " sqm" : "—")}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main detail view
// ---------------------------------------------------------------------------

/**
 * FeasibilityRunDetailView — full detail page for a single feasibility run.
 *
 * Reads ?runId= from the URL query string so the view is compatible with
 * Next.js static export (output: "export").
 *
 * Workflow:
 *   1. Load run metadata (source summary)
 *   2. Load existing assumptions (pre-fill form if present)
 *   3. User edits and saves assumptions
 *   4. User triggers calculation
 *   5. Results panel renders backend-derived KPIs
 *
 * All financial outputs are backend-derived. This component never calculates
 * IRR, NPV, margin, or cost totals locally.
 */
export default function FeasibilityRunDetailView() {
  const searchParams = useSearchParams();
  const runId = searchParams.get("runId") ?? "";

  const [run, setRun] = useState<FeasibilityRun | null>(null);
  const [assumptions, setAssumptions] = useState<FeasibilityAssumptions | null>(null);
  const [result, setResult] = useState<FeasibilityResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [calcError, setCalcError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!runId || runId === "_") {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);

    Promise.all([
      getFeasibilityRun(runId),
      getFeasibilityAssumptions(runId).catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }),
      getFeasibilityResults(runId).catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }),
    ])
      .then(([runData, assumptionsData, resultData]) => {
        setRun(runData);
        setAssumptions(assumptionsData);
        setResult(resultData);
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Failed to load feasibility run.",
        );
      })
      .finally(() => setLoading(false));
  }, [runId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleAssumptionsSaved = useCallback(
    (saved: FeasibilityAssumptions) => {
      setAssumptions(saved);
    },
    [],
  );

  const handleCalculate = useCallback(async () => {
    if (!runId) return;
    setCalcError(null);
    setCalculating(true);
    try {
      const res = await calculateFeasibility(runId);
      setResult(res);
    } catch (err: unknown) {
      setCalcError(
        err instanceof Error ? err.message : "Calculation failed.",
      );
    } finally {
      setCalculating(false);
    }
  }, [runId]);

  const title = run ? run.scenario_name : "Feasibility Run";

  if (!runId || runId === "_") {
    return (
      <PageContainer title="Feasibility Run" subtitle="">
        <div
          style={{
            padding: 40,
            textAlign: "center",
            color: "var(--color-text-muted)",
          }}
        >
          No run ID provided.
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer title={title} subtitle="Assumption editing, calculation, and result review.">
      <Link
        href="/feasibility"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
          fontSize: "0.875rem",
          color: "var(--color-primary, #2563eb)",
          textDecoration: "none",
          marginBottom: 24,
        }}
        aria-label="Back to feasibility runs"
      >
        ← Back to Feasibility
      </Link>

      {loading && (
        <div
          style={{
            padding: 40,
            textAlign: "center",
            color: "var(--color-text-muted)",
          }}
        >
          Loading feasibility run…
        </div>
      )}

      {error && (
        <div
          role="alert"
          style={{
            padding: "12px 16px",
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: 8,
            color: "#b91c1c",
            marginBottom: 24,
            fontSize: "0.875rem",
          }}
        >
          {error}
        </div>
      )}

      {!loading && !error && run && (
        <>
          {/* Source summary */}
          <FeasibilitySourceSummary run={run} />

          {/* Assumptions form */}
          <FeasibilityAssumptionsForm
            runId={runId}
            existing={assumptions}
            onSaved={handleAssumptionsSaved}
          />

          {/* Calculate action */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 16,
              marginBottom: 24,
            }}
          >
            <button
              type="button"
              onClick={handleCalculate}
              disabled={calculating || !assumptions}
              style={{
                padding: "10px 28px",
                border: "none",
                borderRadius: 6,
                background:
                  calculating || !assumptions
                    ? "#94a3b8"
                    : "var(--color-primary, #2563eb)",
                color: "#fff",
                cursor: calculating || !assumptions ? "not-allowed" : "pointer",
                fontSize: "0.875rem",
                fontWeight: 600,
              }}
            >
              {calculating ? "Calculating…" : "Calculate"}
            </button>
            {!assumptions && (
              <span
                style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}
              >
                Save assumptions first to enable calculation.
              </span>
            )}
            {calcError && (
              <span
                role="alert"
                style={{ fontSize: "0.875rem", color: "#b91c1c" }}
              >
                {calcError}
              </span>
            )}
          </div>

          {/* Results panel */}
          {result ? (
            <FeasibilityResultsPanel result={result} />
          ) : (
            <div
              style={{
                padding: 40,
                textAlign: "center",
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: 8,
                color: "var(--color-text-muted)",
              }}
            >
              <div style={{ fontSize: "1.5rem", marginBottom: 8 }}>📊</div>
              <p style={{ margin: 0, fontWeight: 500 }}>No results yet</p>
              <p style={{ margin: "6px 0 0", fontSize: "0.875rem" }}>
                Save assumptions and click Calculate to generate results.
              </p>
            </div>
          )}
        </>
      )}
    </PageContainer>
  );
}
