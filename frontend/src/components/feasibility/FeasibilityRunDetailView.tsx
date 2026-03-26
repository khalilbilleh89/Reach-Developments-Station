"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import {
  getFeasibilityRun,
  getFeasibilityAssumptions,
  upsertFeasibilityAssumptions,
  patchFeasibilityAssumptions,
  calculateFeasibility,
  getFeasibilityResults,
  assignProjectToRun,
  getFeasibilityRunLineage,
} from "@/lib/feasibility-api";
import { createConceptFromFeasibility } from "@/lib/concept-design-api";
import { listProjects } from "@/lib/projects-api";
import { ApiError } from "@/lib/api-client";
import { formatCurrency } from "@/lib/format-utils";
import type {
  FeasibilityAssumptions,
  FeasibilityAssumptionsCreate,
  FeasibilityAssumptionsUpdate,
  FeasibilityDecision,
  FeasibilityLineageResponse,
  FeasibilityResult,
  FeasibilityRiskLevel,
  FeasibilityRun,
  FeasibilityRunStatus,
  FeasibilityScenarioType,
  FeasibilityViabilityStatus,
} from "@/lib/feasibility-types";
import type { Project } from "@/lib/projects-types";

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
// Lifecycle status badge — PR-FEAS-03
// ---------------------------------------------------------------------------

function lifecycleStatusLabel(status: FeasibilityRunStatus): string {
  if (status === "assumptions_defined") return "Ready for Calculation";
  if (status === "calculated") return "Calculated";
  return "Draft";
}

function lifecycleStatusBadgeStyle(status: FeasibilityRunStatus): React.CSSProperties {
  const base: React.CSSProperties = { padding: "3px 10px", borderRadius: 12, fontWeight: 600, fontSize: "0.8rem" };
  if (status === "calculated")
    return { ...base, background: "#dcfce7", color: "#15803d" };
  if (status === "assumptions_defined")
    return { ...base, background: "#dbeafe", color: "#1d4ed8" };
  return { ...base, background: "#f1f5f9", color: "#475569" };
}

// ---------------------------------------------------------------------------
// Lifecycle lineage panel — PR-CONCEPT-065
// ---------------------------------------------------------------------------

interface FeasibilityLineagePanelProps {
  lineage: FeasibilityLineageResponse | null | undefined;
}

function FeasibilityLineagePanel({ lineage }: FeasibilityLineagePanelProps) {
  const panelStyle: React.CSSProperties = {
    background: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    borderRadius: 8,
    padding: "16px 24px",
    marginTop: 24,
  };
  const headingStyle: React.CSSProperties = {
    margin: "0 0 12px",
    fontSize: "0.9rem",
    fontWeight: 600,
    color: "var(--color-text-muted)",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  };
  const labelStyle: React.CSSProperties = {
    fontSize: "0.75rem",
    color: "var(--color-text-muted)",
    marginBottom: 4,
  };
  const monoStyle: React.CSSProperties = {
    fontFamily: "monospace",
    fontSize: "0.8rem",
  };

  if (lineage === undefined) {
    return (
      <div style={panelStyle}>
        <h3 style={headingStyle}>Lifecycle Lineage</h3>
        <p
          style={{
            margin: 0,
            fontSize: "0.875rem",
            color: "var(--color-text-muted)",
          }}
        >
          Loading lineage data…
        </p>
      </div>
    );
  }

  if (lineage === null) {
    return (
      <div style={panelStyle}>
        <h3 style={headingStyle}>Lifecycle Lineage</h3>
        <p
          style={{
            margin: 0,
            fontSize: "0.875rem",
            color: "var(--color-text-muted)",
          }}
        >
          Lineage data unavailable.
        </p>
      </div>
    );
  }

  return (
    <div style={panelStyle} data-testid="feasibility-lineage-panel">
      <h3 style={headingStyle}>Lifecycle Lineage</h3>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: "16px",
        }}
      >
        {/* Upstream */}
        <div>
          <div style={labelStyle}>Seeded From Concept Option</div>
          {lineage.source_concept_option_id ? (
            <span style={monoStyle} data-testid="lineage-source-concept">
              {lineage.source_concept_option_id.substring(0, 12)}…
            </span>
          ) : (
            <em style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
              None — manually created
            </em>
          )}
        </div>

        {/* Downstream */}
        <div>
          <div style={labelStyle}>
            Reverse-Seeded Concept Options ({lineage.reverse_seeded_concept_options.length})
          </div>
          {lineage.reverse_seeded_concept_options.length > 0 ? (
            <ul
              style={{
                margin: 0,
                padding: "0 0 0 16px",
                fontSize: "0.8rem",
              }}
              data-testid="lineage-reverse-seeded-list"
            >
              {lineage.reverse_seeded_concept_options.map((id) => (
                <li key={id} style={monoStyle}>
                  {id.substring(0, 12)}…
                </li>
              ))}
            </ul>
          ) : (
            <em style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
              None yet
            </em>
          )}
        </div>

        {/* Project context */}
        <div>
          <div style={labelStyle}>Project Context</div>
          {lineage.project_id ? (
            <span style={monoStyle} data-testid="lineage-project-id">
              {lineage.project_id.substring(0, 12)}…
            </span>
          ) : (
            <em style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
              Unlinked
            </em>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Source summary panel
// ---------------------------------------------------------------------------

interface SourceSummaryProps {
  run: FeasibilityRun;
}

function formatSeedSourceType(
  seedSourceType: "concept_option" | "manual" | null,
): string {
  if (seedSourceType === "concept_option") return "Concept Option";
  return "Manual";
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
            Project
          </div>
          <div
            style={{
              fontFamily: run.project_id ? undefined : "inherit",
              fontSize: "0.8rem",
              color: run.project_id ? "var(--color-text)" : "var(--color-text-muted)",
            }}
          >
            {run.project_name ? (
              <span style={{ fontWeight: 500 }}>{run.project_name}</span>
            ) : run.project_id ? (
              <span style={{ fontFamily: "monospace" }}>{run.project_id.substring(0, 12)}…</span>
            ) : (
              <em>Unlinked</em>
            )}
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
        <div>
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 4 }}>
            Seed Source
          </div>
          <div
            data-testid="run-seed-source-type"
            style={{
              fontSize: "0.875rem",
              fontWeight: 500,
              color:
                run.seed_source_type === "concept_option"
                  ? "var(--color-accent)"
                  : "var(--color-text-muted)",
            }}
          >
            {formatSeedSourceType(run.seed_source_type)}
          </div>
        </div>
        {run.source_concept_option_id && (
          <div>
            <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 4 }}>
              Source Concept Option
            </div>
            <div
              data-testid="run-source-concept-option-id"
              style={{ fontFamily: "monospace", fontSize: "0.8rem" }}
            >
              {run.source_concept_option_id.substring(0, 12)}…
            </div>
          </div>
        )}
        <div>
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 4 }}>
            Lifecycle Status
          </div>
          <span
            data-testid="run-lifecycle-status"
            style={lifecycleStatusBadgeStyle(run.status)}
          >
            {lifecycleStatusLabel(run.status)}
          </span>
        </div>
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

      // Parse and validate all numeric fields using Number.isFinite() to reject
      // non-finite inputs (Infinity, NaN, scientific notation overflow) before
      // they reach the backend and produce confusing validation errors.

      const sellableAreaVal = Number(sellableArea);
      const avgSalePriceVal = Number(avgSalePrice);
      const constructionCostVal = Number(constructionCost);
      const softCostRawVal = Number(softCostRatio);
      const financeCostRawVal = Number(financeCostRatio);
      const salesCostRawVal = Number(salesCostRatio);
      const devPeriodVal = Number(devPeriod);

      if (!Number.isFinite(sellableAreaVal) || sellableAreaVal <= 0) {
        setSaveError("Invalid value for sellable area sqm.");
        return;
      }
      if (!Number.isFinite(avgSalePriceVal) || avgSalePriceVal <= 0) {
        setSaveError("Invalid value for avg sale price per sqm.");
        return;
      }
      if (!Number.isFinite(constructionCostVal) || constructionCostVal <= 0) {
        setSaveError("Invalid value for construction cost per sqm.");
        return;
      }
      // Ratio fields: percent input must be finite and in [0, 100]; convert to [0, 1] for backend.
      if (!Number.isFinite(softCostRawVal) || softCostRawVal < 0 || softCostRawVal > 100) {
        setSaveError("Soft cost ratio must be between 0 and 100.");
        return;
      }
      if (!Number.isFinite(financeCostRawVal) || financeCostRawVal < 0 || financeCostRawVal > 100) {
        setSaveError("Finance cost ratio must be between 0 and 100.");
        return;
      }
      if (!Number.isFinite(salesCostRawVal) || salesCostRawVal < 0 || salesCostRawVal > 100) {
        setSaveError("Sales cost ratio must be between 0 and 100.");
        return;
      }
      // Development period: must be a finite positive integer (no decimal truncation).
      if (!Number.isFinite(devPeriodVal) || !Number.isInteger(devPeriodVal) || devPeriodVal < 1) {
        setSaveError("Development period must be a whole number of months (≥ 1).");
        return;
      }

      const fullPayload = {
        sellable_area_sqm: sellableAreaVal,
        avg_sale_price_per_sqm: avgSalePriceVal,
        construction_cost_per_sqm: constructionCostVal,
        soft_cost_ratio: softCostRawVal / 100,
        finance_cost_ratio: financeCostRawVal / 100,
        sales_cost_ratio: salesCostRawVal / 100,
        development_period_months: devPeriodVal,
        notes: notes.trim() || null,
      };

      setSaving(true);
      try {
        if (existing) {
          // PATCH: send only fields whose parsed values differ from the persisted record.
          const patchPayload: FeasibilityAssumptionsUpdate = {};
          (Object.keys(fullPayload) as (keyof typeof fullPayload)[]).forEach((key) => {
            if (fullPayload[key] !== existing[key]) {
              (patchPayload as Record<string, unknown>)[key] = fullPayload[key];
            }
          });

          if (Object.keys(patchPayload).length === 0) {
            // Nothing changed — skip the network request and re-confirm saved state.
            onSaved(existing);
            return;
          }

          const saved = await patchFeasibilityAssumptions(runId, patchPayload);
          onSaved(saved);
        } else {
          // POST: first save — send the full create payload.
          const createPayload: FeasibilityAssumptionsCreate = fullPayload;
          const saved = await upsertFeasibilityAssumptions(runId, createPayload);
          onSaved(saved);
        }
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
      existing,
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
      <form onSubmit={handleSave} noValidate>
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
  const router = useRouter();
  const runId = searchParams.get("runId") ?? "";

  const [run, setRun] = useState<FeasibilityRun | null>(null);
  const [assumptions, setAssumptions] = useState<FeasibilityAssumptions | null>(null);
  const [result, setResult] = useState<FeasibilityResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [calcError, setCalcError] = useState<string | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [assigningProject, setAssigningProject] = useState(false);
  const [projectAssignError, setProjectAssignError] = useState<string | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [seedingConcept, setSeedingConcept] = useState(false);
  const [seedConceptError, setSeedConceptError] = useState<string | null>(null);
  const [lineage, setLineage] = useState<FeasibilityLineageResponse | null | undefined>(undefined);

  const load = useCallback(() => {
    if (!runId || runId === "_") {
      setLoading(false);
      return;
    }
    // Reset all run-dependent state so switching between runs never leaks
    // stale data, errors, or calculation results from a prior run.
    setLoading(true);
    setError(null);
    setCalcError(null);
    setProjectAssignError(null);
    setRun(null);
    setAssumptions(null);
    setResult(null);
    setLineage(undefined);

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
        setSelectedProjectId(runData.project_id ?? "");

        // Fetch lineage independently so it does not block core page render.
        getFeasibilityRunLineage(runId)
          .then((lineageData) => setLineage(lineageData))
          .catch(() => setLineage(null));
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Failed to load feasibility run.",
        );
        setLineage(null);
      })
      .finally(() => setLoading(false));
  }, [runId]);

  // Load projects list for assignment dropdown
  useEffect(() => {
    listProjects({ limit: 200 })
      .then((resp) => setProjects(resp.items))
      .catch(() => setProjects([]));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleAssumptionsSaved = useCallback(
    (saved: FeasibilityAssumptions) => {
      setAssumptions(saved);
      // Reload the run to pick up the updated lifecycle status ('assumptions_defined').
      getFeasibilityRun(runId)
        .then((updatedRun) => setRun(updatedRun))
        .catch((err: unknown) => {
          // Non-fatal: status badge may be stale until next full reload.
          console.warn("Failed to reload run after assumptions save:", err);
        });
    },
    [runId],
  );

  const handleCalculate = useCallback(async () => {
    if (!runId) return;
    setCalcError(null);
    setCalculating(true);
    try {
      const res = await calculateFeasibility(runId);
      setResult(res);
      // Reload the run to pick up the updated lifecycle status ('calculated').
      const updatedRun = await getFeasibilityRun(runId);
      setRun(updatedRun);
    } catch (err: unknown) {
      setCalcError(
        err instanceof Error ? err.message : "Calculation failed.",
      );
    } finally {
      setCalculating(false);
    }
  }, [runId]);

  const handleAssignProject = useCallback(async () => {
    if (!runId || !selectedProjectId) return;
    setProjectAssignError(null);
    setAssigningProject(true);
    try {
      const updated = await assignProjectToRun(runId, selectedProjectId);
      setRun(updated);
    } catch (err: unknown) {
      setProjectAssignError(
        err instanceof Error ? err.message : "Failed to assign project.",
      );
    } finally {
      setAssigningProject(false);
    }
  }, [runId, selectedProjectId]);

  const handleUnlinkProject = useCallback(async () => {
    if (!runId) return;
    setProjectAssignError(null);
    setAssigningProject(true);
    try {
      const updated = await assignProjectToRun(runId, null);
      setRun(updated);
      setSelectedProjectId("");
    } catch (err: unknown) {
      setProjectAssignError(
        err instanceof Error ? err.message : "Failed to unlink project.",
      );
    } finally {
      setAssigningProject(false);
    }
  }, [runId]);

  const handleCreateConcept = useCallback(async () => {
    if (!runId) return;
    setSeedConceptError(null);
    setSeedingConcept(true);
    try {
      const result = await createConceptFromFeasibility(runId);
      router.push(
        `/concept-design?concept_option_id=${encodeURIComponent(result.concept_option_id)}`,
      );
    } catch (err: unknown) {
      setSeedConceptError(
        err instanceof Error ? err.message : "Failed to create concept option.",
      );
    } finally {
      setSeedingConcept(false);
    }
  }, [runId, router]);

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

          {/* Project assignment panel */}
          <div
            style={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: 8,
              padding: "16px 24px",
              marginBottom: 24,
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
              Project Context
            </h3>
            {run.project_id ? (
              <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
                <span style={{ fontSize: "0.875rem" }}>
                  Linked to:{" "}
                  <strong data-testid="linked-project-name">
                    {run.project_name ?? run.project_id.substring(0, 12) + "…"}
                  </strong>
                </span>
                <button
                  type="button"
                  onClick={handleUnlinkProject}
                  disabled={assigningProject}
                  style={{
                    padding: "4px 14px",
                    border: "1px solid #fecaca",
                    borderRadius: 4,
                    background: "transparent",
                    color: "#b91c1c",
                    cursor: assigningProject ? "not-allowed" : "pointer",
                    fontSize: "0.8rem",
                  }}
                >
                  {assigningProject ? "Unlinking…" : "Unlink Project"}
                </button>
              </div>
            ) : (
              <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                <span style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>
                  This run is not linked to a project.
                </span>
                {projects.length > 0 && (
                  <>
                    <select
                      aria-label="Select project to assign"
                      value={selectedProjectId}
                      onChange={(e) => setSelectedProjectId(e.target.value)}
                      style={{
                        padding: "6px 10px",
                        border: "1px solid var(--color-border)",
                        borderRadius: 4,
                        fontSize: "0.875rem",
                        background: "var(--color-surface)",
                      }}
                    >
                      <option value="">Select a project…</option>
                      {projects.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={handleAssignProject}
                      disabled={assigningProject || !selectedProjectId}
                      style={{
                        padding: "6px 16px",
                        border: "none",
                        borderRadius: 4,
                        background:
                          assigningProject || !selectedProjectId
                            ? "#94a3b8"
                            : "var(--color-primary, #2563eb)",
                        color: "#fff",
                        cursor:
                          assigningProject || !selectedProjectId
                            ? "not-allowed"
                            : "pointer",
                        fontSize: "0.875rem",
                        fontWeight: 500,
                      }}
                    >
                      {assigningProject ? "Assigning…" : "Assign Project"}
                    </button>
                  </>
                )}
              </div>
            )}
            {projectAssignError && (
              <p
                role="alert"
                style={{
                  color: "#b91c1c",
                  fontSize: "0.875rem",
                  margin: "8px 0 0",
                }}
              >
                {projectAssignError}
              </p>
            )}
          </div>

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

          {/* Reverse-seed: Create Concept Option — PR-CONCEPT-064 */}
          <div
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
              Design Iteration
            </h3>
            <p
              style={{
                margin: "0 0 12px",
                fontSize: "0.875rem",
                color: "var(--color-text-muted)",
              }}
            >
              Create a new concept option from this feasibility run to continue
              the design-finance iteration loop.
            </p>
            <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
              <button
                type="button"
                data-testid="create-concept-btn"
                onClick={handleCreateConcept}
                disabled={seedingConcept}
                style={{
                  padding: "8px 20px",
                  border: "none",
                  borderRadius: 4,
                  background: seedingConcept ? "#94a3b8" : "#16a34a",
                  color: "#fff",
                  cursor: seedingConcept ? "not-allowed" : "pointer",
                  fontSize: "0.875rem",
                  fontWeight: 500,
                }}
              >
                {seedingConcept ? "Creating…" : "Create Concept Option"}
              </button>
              {seedConceptError && (
                <span
                  role="alert"
                  style={{ fontSize: "0.875rem", color: "#b91c1c" }}
                >
                  {seedConceptError}
                </span>
              )}
            </div>
          </div>

          {/* Lifecycle Lineage — PR-CONCEPT-065 */}
          <FeasibilityLineagePanel lineage={lineage} />
        </>
      )}
    </PageContainer>
  );
}
