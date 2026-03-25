"use client";

/**
 * Feasibility Run Detail — client component.
 *
 * Sections
 * --------
 *  1. Source Summary   — run metadata: scenario name, type, project, scenario, notes
 *  2. Assumptions Form — load / edit / save assumption inputs
 *  3. Calculate Action — POST /feasibility/runs/{id}/calculate
 *  4. Results Panel    — display backend-computed KPIs after calculation
 *
 * This component does not calculate any financial outputs locally.
 * All KPIs are derived and returned by the backend calculation engine.
 *
 * PR-W5.2
 */

import React, { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import { MetricCard } from "@/components/dashboard/MetricCard";
import {
  getFeasibilityRun,
  getFeasibilityAssumptions,
  upsertFeasibilityAssumptions,
  calculateFeasibility,
  getFeasibilityResults,
} from "@/lib/feasibility-api";
import type {
  FeasibilityAssumptions,
  FeasibilityAssumptionsCreate,
  FeasibilityResult,
  FeasibilityRun,
  FeasibilityScenarioType,
} from "@/lib/feasibility-types";
import styles from "@/styles/demo-shell.module.css";

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

function scenarioBadgeClass(type: FeasibilityScenarioType): string {
  const map: Record<FeasibilityScenarioType, string> = {
    base: styles.badgeBlue,
    upside: styles.badgeGreen,
    downside: styles.badgeRed,
    investor: styles.badgePurple,
  };
  return map[type] ?? styles.badgeGray;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatCurrency(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-AE", {
    style: "currency",
    currency: "AED",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatPercent(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

function formatDecimal(value: number | null | undefined, decimals = 2): string {
  if (value == null) return "—";
  return value.toFixed(decimals);
}

function viabilityBadgeClass(status: string | null | undefined): string {
  if (!status) return styles.badgeGray;
  if (status === "viable") return styles.badgeGreen;
  if (status === "marginal") return styles.badgeYellow;
  return styles.badgeRed;
}

function truncateId(id: string, length = 8): string {
  return id.length > length ? `${id.substring(0, length)}…` : id;
}

function viabilityLabel(status: string | null | undefined): string {
  if (!status) return "—";
  const map: Record<string, string> = {
    viable: "Viable",
    marginal: "Marginal",
    not_viable: "Not Viable",
  };
  return map[status] ?? status;
}

function riskBadgeClass(level: string | null | undefined): string {
  if (!level) return styles.badgeGray;
  if (level === "low") return styles.badgeGreen;
  if (level === "medium") return styles.badgeYellow;
  return styles.badgeRed;
}

function decisionBadgeClass(decision: string | null | undefined): string {
  if (!decision) return styles.badgeGray;
  if (decision === "proceed") return styles.badgeGreen;
  if (decision === "review") return styles.badgeYellow;
  return styles.badgeRed;
}

// ---------------------------------------------------------------------------
// Form state helpers
// ---------------------------------------------------------------------------

interface AssumptionsFormState {
  sellable_area_sqm: string;
  avg_sale_price_per_sqm: string;
  construction_cost_per_sqm: string;
  soft_cost_ratio: string;
  finance_cost_ratio: string;
  sales_cost_ratio: string;
  development_period_months: string;
  notes: string;
}

function assumptionsToFormState(a: FeasibilityAssumptions | null): AssumptionsFormState {
  if (!a) {
    return {
      sellable_area_sqm: "",
      avg_sale_price_per_sqm: "",
      construction_cost_per_sqm: "",
      soft_cost_ratio: "",
      finance_cost_ratio: "",
      sales_cost_ratio: "",
      development_period_months: "",
      notes: "",
    };
  }
  return {
    sellable_area_sqm: a.sellable_area_sqm != null ? String(a.sellable_area_sqm) : "",
    avg_sale_price_per_sqm: a.avg_sale_price_per_sqm != null ? String(a.avg_sale_price_per_sqm) : "",
    construction_cost_per_sqm: a.construction_cost_per_sqm != null ? String(a.construction_cost_per_sqm) : "",
    soft_cost_ratio: a.soft_cost_ratio != null ? String(a.soft_cost_ratio) : "",
    finance_cost_ratio: a.finance_cost_ratio != null ? String(a.finance_cost_ratio) : "",
    sales_cost_ratio: a.sales_cost_ratio != null ? String(a.sales_cost_ratio) : "",
    development_period_months: a.development_period_months != null ? String(a.development_period_months) : "",
    notes: a.notes ?? "",
  };
}

function parseAssumptionsForm(form: AssumptionsFormState): FeasibilityAssumptionsCreate | null {
  const sellable = parseFloat(form.sellable_area_sqm);
  const price = parseFloat(form.avg_sale_price_per_sqm);
  const construction = parseFloat(form.construction_cost_per_sqm);
  const soft = parseFloat(form.soft_cost_ratio);
  const finance = parseFloat(form.finance_cost_ratio);
  const sales = parseFloat(form.sales_cost_ratio);
  const months = parseInt(form.development_period_months, 10);

  if (
    !isFinite(sellable) || sellable <= 0 ||
    !isFinite(price) || price <= 0 ||
    !isFinite(construction) || construction <= 0 ||
    !isFinite(soft) || soft < 0 || soft > 1 ||
    !isFinite(finance) || finance < 0 || finance > 1 ||
    !isFinite(sales) || sales < 0 || sales > 1 ||
    !isFinite(months) || months < 1
  ) {
    return null;
  }

  return {
    sellable_area_sqm: sellable,
    avg_sale_price_per_sqm: price,
    construction_cost_per_sqm: construction,
    soft_cost_ratio: soft,
    finance_cost_ratio: finance,
    sales_cost_ratio: sales,
    development_period_months: months,
    notes: form.notes.trim() || null,
  };
}

// ---------------------------------------------------------------------------
// Section: Source Summary
// ---------------------------------------------------------------------------

const sourceLabelStyle: React.CSSProperties = {
  fontSize: "0.75rem",
  color: "var(--color-text-muted)",
  fontWeight: 500,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  marginBottom: 4,
};

interface SourceSummaryProps {
  run: FeasibilityRun;
}

function SourceSummary({ run }: SourceSummaryProps) {
  return (
    <section aria-labelledby="source-summary-heading" style={{ marginBottom: "var(--space-8)" }}>
      <h2
        id="source-summary-heading"
        style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "var(--space-4)" }}
      >
        Run Source
      </h2>
      <div
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--card-radius, 8px)",
          padding: "var(--card-padding, 20px)",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
          gap: "var(--space-4)",
        }}
      >
        <div>
          <div style={sourceLabelStyle}>Scenario Name</div>
          <div style={{ fontWeight: 600 }}>{run.scenario_name}</div>
        </div>
        <div>
          <div style={sourceLabelStyle}>Scenario Type</div>
          <span className={`${styles.badge} ${scenarioBadgeClass(run.scenario_type)}`}>
            {formatScenarioType(run.scenario_type)}
          </span>
        </div>
        <div>
          <div style={sourceLabelStyle}>Project</div>
          <div style={{ fontSize: "0.875rem" }}>
            {run.project_id ? (
              <span style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>
                {truncateId(run.project_id)}
              </span>
            ) : (
              <em style={{ color: "var(--color-text-muted)" }}>Unlinked</em>
            )}
          </div>
        </div>
        <div>
          <div style={sourceLabelStyle}>Scenario</div>
          <div style={{ fontSize: "0.875rem" }}>
            {run.scenario_id ? (
              <span style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>
                {truncateId(run.scenario_id)}
              </span>
            ) : (
              <em style={{ color: "var(--color-text-muted)" }}>None</em>
            )}
          </div>
        </div>
        <div>
          <div style={sourceLabelStyle}>Created</div>
          <div style={{ fontSize: "0.875rem" }}>{formatDate(run.created_at)}</div>
        </div>
        {run.notes && (
          <div style={{ gridColumn: "1 / -1" }}>
            <div style={sourceLabelStyle}>Notes</div>
            <div style={{ fontSize: "0.875rem" }}>{run.notes}</div>
          </div>
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section: Assumptions Form
// ---------------------------------------------------------------------------

interface AssumptionsFormProps {
  form: AssumptionsFormState;
  onChange: (field: keyof AssumptionsFormState, value: string) => void;
  onSave: () => void;
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  hasExisting: boolean;
}

function labelStyle(): React.CSSProperties {
  return {
    display: "block",
    marginBottom: 4,
    fontSize: "0.8125rem",
    fontWeight: 500,
    color: "var(--color-text-muted)",
    textTransform: "uppercase" as const,
    letterSpacing: "0.04em",
  };
}

function inputStyle(): React.CSSProperties {
  return {
    width: "100%",
    padding: "8px 12px",
    border: "1px solid var(--color-border)",
    borderRadius: 6,
    fontSize: "0.875rem",
    boxSizing: "border-box" as const,
    background: "var(--color-surface)",
  };
}

function AssumptionsForm({
  form,
  onChange,
  onSave,
  saving,
  saveError,
  saveSuccess,
  hasExisting,
}: AssumptionsFormProps) {
  const fields: {
    key: keyof AssumptionsFormState;
    label: string;
    hint: string;
    type: "number" | "integer";
  }[] = [
    { key: "sellable_area_sqm", label: "Sellable Area (sqm)", hint: "> 0", type: "number" },
    { key: "avg_sale_price_per_sqm", label: "Avg Sale Price / sqm (AED)", hint: "> 0", type: "number" },
    { key: "construction_cost_per_sqm", label: "Construction Cost / sqm (AED)", hint: "> 0", type: "number" },
    { key: "soft_cost_ratio", label: "Soft Cost Ratio", hint: "0 – 1 (e.g. 0.10 = 10%)", type: "number" },
    { key: "finance_cost_ratio", label: "Finance Cost Ratio", hint: "0 – 1", type: "number" },
    { key: "sales_cost_ratio", label: "Sales Cost Ratio", hint: "0 – 1", type: "number" },
    { key: "development_period_months", label: "Development Period (months)", hint: "≥ 1", type: "integer" },
  ];

  const isValid = parseAssumptionsForm(form) !== null;

  return (
    <section aria-labelledby="assumptions-heading" style={{ marginBottom: "var(--space-8)" }}>
      <div className={styles.sectionHeader}>
        <h2 id="assumptions-heading" className={styles.sectionTitle}>
          Assumptions
        </h2>
        {hasExisting && (
          <span style={{ fontSize: "0.8125rem", color: "var(--color-text-muted)" }}>
            Editing existing assumptions
          </span>
        )}
      </div>
      <div
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--card-radius, 8px)",
          padding: "var(--card-padding, 20px)",
        }}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
            gap: "var(--space-4)",
            marginBottom: "var(--space-4)",
          }}
        >
          {fields.map(({ key, label, hint, type }) => (
            <div key={key}>
              <label htmlFor={`assumption-${key}`} style={labelStyle()}>
                {label}
              </label>
              <input
                id={`assumption-${key}`}
                type="number"
                step={type === "integer" ? "1" : "any"}
                min={type === "integer" ? "1" : "0"}
                value={form[key]}
                onChange={(e) => onChange(key, e.target.value)}
                placeholder={hint}
                style={inputStyle()}
              />
            </div>
          ))}
        </div>
        <div style={{ marginBottom: "var(--space-4)" }}>
          <label htmlFor="assumption-notes" style={labelStyle()}>
            Notes
          </label>
          <textarea
            id="assumption-notes"
            value={form.notes}
            onChange={(e) => onChange("notes", e.target.value)}
            placeholder="Optional notes about these assumptions…"
            rows={2}
            style={{ ...inputStyle(), resize: "vertical" }}
          />
        </div>
        {saveError && (
          <p role="alert" style={{ color: "#b91c1c", fontSize: "0.875rem", marginBottom: 12 }}>
            {saveError}
          </p>
        )}
        {saveSuccess && (
          <p role="status" style={{ color: "#15803d", fontSize: "0.875rem", marginBottom: 12 }}>
            Assumptions saved.
          </p>
        )}
        <button
          type="button"
          onClick={onSave}
          disabled={saving || !isValid}
          style={{
            padding: "8px 24px",
            border: "none",
            borderRadius: 6,
            background: saving || !isValid ? "#94a3b8" : "var(--color-primary, #2563eb)",
            color: "#fff",
            cursor: saving || !isValid ? "not-allowed" : "pointer",
            fontSize: "0.875rem",
            fontWeight: 500,
          }}
        >
          {saving ? "Saving…" : hasExisting ? "Update Assumptions" : "Save Assumptions"}
        </button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section: Calculate
// ---------------------------------------------------------------------------

interface CalculateSectionProps {
  canCalculate: boolean;
  calculating: boolean;
  calcError: string | null;
  onCalculate: () => void;
}

function CalculateSection({
  canCalculate,
  calculating,
  calcError,
  onCalculate,
}: CalculateSectionProps) {
  return (
    <section aria-labelledby="calculate-heading" style={{ marginBottom: "var(--space-8)" }}>
      <h2
        id="calculate-heading"
        style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "var(--space-4)" }}
      >
        Calculate
      </h2>
      <div
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--card-radius, 8px)",
          padding: "var(--card-padding, 20px)",
          display: "flex",
          alignItems: "center",
          gap: "var(--space-4)",
          flexWrap: "wrap",
        }}
      >
        <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--color-text-muted)", flex: "1 1 auto" }}>
          {canCalculate
            ? "Assumptions are saved. Run the calculation to produce financial results."
            : "Save complete assumptions above before running the calculation."}
        </p>
        {calcError && (
          <p role="alert" style={{ color: "#b91c1c", fontSize: "0.875rem", width: "100%" }}>
            {calcError}
          </p>
        )}
        <button
          type="button"
          onClick={onCalculate}
          disabled={!canCalculate || calculating}
          style={{
            padding: "10px 28px",
            border: "none",
            borderRadius: 6,
            background: !canCalculate || calculating ? "#94a3b8" : "#16a34a",
            color: "#fff",
            cursor: !canCalculate || calculating ? "not-allowed" : "pointer",
            fontSize: "0.875rem",
            fontWeight: 600,
            whiteSpace: "nowrap",
          }}
        >
          {calculating ? "Calculating…" : "Run Calculation"}
        </button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section: Results Panel
// ---------------------------------------------------------------------------

interface ResultsPanelProps {
  result: FeasibilityResult;
}

function ResultsPanel({ result }: ResultsPanelProps) {
  return (
    <section aria-labelledby="results-heading" style={{ marginBottom: "var(--space-8)" }}>
      <h2
        id="results-heading"
        style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "var(--space-4)" }}
      >
        Results
      </h2>

      {/* KPI strip */}
      <div className={styles.kpiGrid} style={{ marginBottom: "var(--space-6)" }}>
        <MetricCard title="GDV" value={formatCurrency(result.gdv)} />
        <MetricCard title="Total Cost" value={formatCurrency(result.total_cost)} />
        <MetricCard title="Developer Profit" value={formatCurrency(result.developer_profit)} />
        <MetricCard title="Profit Margin" value={formatPercent(result.profit_margin)} />
      </div>

      {/* Detail card */}
      <div
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--card-radius, 8px)",
          padding: "var(--card-padding, 20px)",
        }}
      >
        {/* Viability / decision row */}
        <div
          style={{
            display: "flex",
            gap: "var(--space-4)",
            flexWrap: "wrap",
            marginBottom: "var(--space-6)",
            paddingBottom: "var(--space-4)",
            borderBottom: "1px solid var(--color-border)",
          }}
        >
          <div>
            <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
              Viability
            </div>
            <span className={`${styles.badge} ${viabilityBadgeClass(result.viability_status)}`}>
              {viabilityLabel(result.viability_status)}
            </span>
          </div>
          <div>
            <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
              Risk Level
            </div>
            <span className={`${styles.badge} ${riskBadgeClass(result.risk_level)}`}>
              {result.risk_level ? result.risk_level.charAt(0).toUpperCase() + result.risk_level.slice(1) : "—"}
            </span>
          </div>
          <div>
            <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
              Decision
            </div>
            <span className={`${styles.badge} ${decisionBadgeClass(result.decision)}`}>
              {result.decision ? result.decision.charAt(0).toUpperCase() + result.decision.slice(1) : "—"}
            </span>
          </div>
        </div>

        {/* Cost breakdown */}
        <div style={{ marginBottom: "var(--space-4)" }}>
          <h3 style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: "var(--space-3)" }}>
            Cost Breakdown
          </h3>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
              gap: "var(--space-3)",
            }}
          >
            {[
              { label: "Construction Cost", value: formatCurrency(result.construction_cost) },
              { label: "Soft Cost", value: formatCurrency(result.soft_cost) },
              { label: "Finance Cost", value: formatCurrency(result.finance_cost) },
              { label: "Sales Cost", value: formatCurrency(result.sales_cost) },
            ].map(({ label, value }) => (
              <div
                key={label}
                style={{
                  padding: "var(--space-3)",
                  background: "#f8fafc",
                  borderRadius: 6,
                  border: "1px solid var(--color-border)",
                }}
              >
                <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 2 }}>
                  {label}
                </div>
                <div style={{ fontWeight: 600, fontSize: "0.9375rem" }}>{value}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Return metrics */}
        <div>
          <h3 style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: "var(--space-3)" }}>
            Return Metrics
          </h3>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
              gap: "var(--space-3)",
            }}
          >
            {[
              { label: "IRR (Estimate)", value: result.irr_estimate != null ? formatPercent(result.irr_estimate) : "—" },
              { label: "IRR", value: result.irr != null ? formatPercent(result.irr) : "—" },
              { label: "Equity Multiple", value: result.equity_multiple != null ? `${formatDecimal(result.equity_multiple)}×` : "—" },
              { label: "Payback Period", value: result.payback_period != null ? `${formatDecimal(result.payback_period)} yrs` : "—" },
              { label: "Break-even Price / sqm", value: formatCurrency(result.break_even_price) },
              { label: "Break-even Units", value: result.break_even_units != null ? formatDecimal(result.break_even_units, 0) : "—" },
            ].map(({ label, value }) => (
              <div
                key={label}
                style={{
                  padding: "var(--space-3)",
                  background: "#f8fafc",
                  borderRadius: 6,
                  border: "1px solid var(--color-border)",
                }}
              >
                <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 2 }}>
                  {label}
                </div>
                <div style={{ fontWeight: 600, fontSize: "0.9375rem" }}>{value}</div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ marginTop: "var(--space-4)", fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
          Calculated {formatDate(result.updated_at)}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Main client component
// ---------------------------------------------------------------------------

/**
 * FeasibilityRunDetailClient — full interactive detail view for a single feasibility run.
 *
 * Reads `runId` from the URL via useParams() for client-side navigation.
 * Loads run metadata, assumptions, and any existing results on mount.
 */
export function FeasibilityRunDetailClient() {
  const params = useParams();
  const router = useRouter();
  const runId = typeof params?.runId === "string" ? params.runId : null;

  // Page data
  const [run, setRun] = useState<FeasibilityRun | null>(null);
  const [assumptions, setAssumptions] = useState<FeasibilityAssumptions | null>(null);
  const [result, setResult] = useState<FeasibilityResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Assumptions form state
  const [form, setForm] = useState<AssumptionsFormState>(assumptionsToFormState(null));
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Calculate state
  const [calculating, setCalculating] = useState(false);
  const [calcError, setCalcError] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Load run data
  // ---------------------------------------------------------------------------

  const loadRun = useCallback(async (id: string) => {
    setLoading(true);
    setLoadError(null);
    try {
      const [runData, assumptionsData] = await Promise.all([
        getFeasibilityRun(id),
        getFeasibilityAssumptions(id).catch(() => null),
      ]);
      setRun(runData);
      setAssumptions(assumptionsData);
      setForm(assumptionsToFormState(assumptionsData));

      // Try to load existing results
      getFeasibilityResults(id)
        .then(setResult)
        .catch(() => setResult(null));
    } catch (err: unknown) {
      setLoadError(
        err instanceof Error ? err.message : "Failed to load feasibility run.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (runId && runId !== "_") {
      loadRun(runId);
    } else {
      setLoading(false);
    }
  }, [runId, loadRun]);

  // ---------------------------------------------------------------------------
  // Form field change handler
  // ---------------------------------------------------------------------------

  const handleFormChange = useCallback(
    (field: keyof AssumptionsFormState, value: string) => {
      setForm((prev) => ({ ...prev, [field]: value }));
      setSaveSuccess(false);
    },
    [],
  );

  // ---------------------------------------------------------------------------
  // Save assumptions
  // ---------------------------------------------------------------------------

  const handleSave = useCallback(async () => {
    if (!runId || runId === "_") return;
    const parsed = parseAssumptionsForm(form);
    if (!parsed) {
      setSaveError("Please fill in all required fields with valid values.");
      return;
    }
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);
    try {
      const saved = await upsertFeasibilityAssumptions(runId, parsed);
      setAssumptions(saved);
      setSaveSuccess(true);
    } catch (err: unknown) {
      setSaveError(
        err instanceof Error ? err.message : "Failed to save assumptions.",
      );
    } finally {
      setSaving(false);
    }
  }, [runId, form]);

  // ---------------------------------------------------------------------------
  // Calculate
  // ---------------------------------------------------------------------------

  const handleCalculate = useCallback(async () => {
    if (!runId || runId === "_") return;
    setCalculating(true);
    setCalcError(null);
    try {
      const res = await calculateFeasibility(runId);
      setResult(res);
    } catch (err: unknown) {
      setCalcError(
        err instanceof Error
          ? err.message
          : "Calculation failed. Check assumptions and retry.",
      );
    } finally {
      setCalculating(false);
    }
  }, [runId]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  // Placeholder page for static export stub route
  if (!runId || runId === "_") {
    return (
      <PageContainer title="Feasibility Run" subtitle="Open a run from the Feasibility dashboard.">
        <div
          style={{
            padding: 60,
            textAlign: "center",
            color: "var(--color-text-muted)",
            background: "var(--color-surface)",
            borderRadius: 8,
            border: "1px solid var(--color-border)",
          }}
        >
          <div style={{ fontSize: "2rem", marginBottom: 12 }}>📐</div>
          <p style={{ margin: 0, fontWeight: 500 }}>No run selected</p>
          <p style={{ margin: "8px 0 0", fontSize: "0.875rem" }}>
            Navigate to a specific feasibility run from the dashboard.
          </p>
        </div>
      </PageContainer>
    );
  }

  if (loading) {
    return (
      <PageContainer title="Feasibility Run">
        <div style={{ padding: 40, textAlign: "center", color: "var(--color-text-muted)" }}>
          Loading feasibility run…
        </div>
      </PageContainer>
    );
  }

  if (loadError || !run) {
    return (
      <PageContainer title="Feasibility Run">
        <div
          role="alert"
          style={{
            padding: "12px 16px",
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: 8,
            color: "#b91c1c",
            marginBottom: "var(--space-4)",
            fontSize: "0.875rem",
          }}
        >
          {loadError ?? "Feasibility run not found."}
        </div>
        <button
          type="button"
          onClick={() => router.push("/feasibility")}
          style={{
            padding: "8px 20px",
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            background: "transparent",
            cursor: "pointer",
            fontSize: "0.875rem",
          }}
        >
          ← Back to Feasibility
        </button>
      </PageContainer>
    );
  }

  const hasAssumptions = assumptions !== null;
  const canCalculate = hasAssumptions;

  return (
    <PageContainer
      title={run.scenario_name}
      subtitle="Feasibility Run Detail"
      actions={
        <button
          type="button"
          onClick={() => router.push("/feasibility")}
          style={{
            padding: "8px 20px",
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            background: "transparent",
            cursor: "pointer",
            fontSize: "0.875rem",
          }}
        >
          ← All Runs
        </button>
      }
    >
      <SourceSummary run={run} />

      <AssumptionsForm
        form={form}
        onChange={handleFormChange}
        onSave={handleSave}
        saving={saving}
        saveError={saveError}
        saveSuccess={saveSuccess}
        hasExisting={hasAssumptions}
      />

      <CalculateSection
        canCalculate={canCalculate}
        calculating={calculating}
        calcError={calcError}
        onCalculate={handleCalculate}
      />

      {result && <ResultsPanel result={result} />}
    </PageContainer>
  );
}
