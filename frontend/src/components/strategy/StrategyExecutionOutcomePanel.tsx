"use client";

/**
 * StrategyExecutionOutcomePanel.tsx
 *
 * Project-level execution outcome capture and display panel (PR-V7-10).
 *
 * Shows:
 *  - Latest trigger context and eligibility state
 *  - Record outcome form when the trigger is eligible (in_progress or completed)
 *  - Actual executed values from the latest recorded outcome
 *  - Intended vs realized comparison block with match/divergence badges
 *  - Recorded-by metadata
 *  - Safe no-trigger / no-outcome / ineligible states
 *
 * Design principles:
 *  - All comparison logic is backend-derived; no recomputation here.
 *  - Renders safe empty states for each possible scenario.
 *  - AbortController wired for clean unmount cancellation.
 *
 * PR-V7-10 — Execution Outcome Capture & Feedback Loop Closure
 */

import React, { useEffect, useRef, useState } from "react";
import {
  getProjectStrategyExecutionOutcome,
  recordStrategyExecutionOutcome,
} from "@/lib/strategy-execution-outcome-api";
import type {
  ExecutionOutcomeComparisonBlock,
  ExecutionQuality,
  MatchStatus,
  OutcomeResult,
  ProjectExecutionOutcomeResponse,
  RecordExecutionOutcomeRequest,
  StrategyExecutionOutcomeResponse,
} from "@/lib/strategy-execution-outcome-types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function outcomeResultLabel(result: OutcomeResult): string {
  switch (result) {
    case "matched_strategy":
      return "Matched Strategy";
    case "partially_matched":
      return "Partially Matched";
    case "diverged":
      return "Diverged";
    case "cancelled_execution":
      return "Cancelled Execution";
    case "insufficient_data":
      return "Insufficient Data";
  }
}

function matchStatusLabel(status: MatchStatus): string {
  switch (status) {
    case "exact_match":
      return "Exact Match";
    case "minor_variance":
      return "Minor Variance";
    case "major_variance":
      return "Major Variance";
    case "no_comparable_strategy":
      return "No Comparable Strategy";
  }
}

function matchStatusStyle(status: MatchStatus): React.CSSProperties {
  switch (status) {
    case "exact_match":
      return {
        background: "#dcfce7",
        color: "#15803d",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: "0.75rem",
        fontWeight: 600,
      };
    case "minor_variance":
      return {
        background: "#fef9c3",
        color: "#854d0e",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: "0.75rem",
        fontWeight: 600,
      };
    case "major_variance":
      return {
        background: "#fee2e2",
        color: "#b91c1c",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: "0.75rem",
        fontWeight: 600,
      };
    case "no_comparable_strategy":
      return {
        background: "#f3f4f6",
        color: "#6b7280",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: "0.75rem",
        fontWeight: 600,
      };
  }
}

function outcomeResultStyle(result: OutcomeResult): React.CSSProperties {
  switch (result) {
    case "matched_strategy":
      return { background: "#dcfce7", color: "#15803d" };
    case "partially_matched":
      return { background: "#fef9c3", color: "#854d0e" };
    case "diverged":
      return { background: "#fee2e2", color: "#b91c1c" };
    case "cancelled_execution":
      return { background: "#f3f4f6", color: "#374151" };
    case "insufficient_data":
      return { background: "#f3f4f6", color: "#6b7280" };
  }
}

function qualityLabel(quality: ExecutionQuality): string {
  switch (quality) {
    case "high":
      return "High";
    case "medium":
      return "Medium";
    case "low":
      return "Low";
    case "unknown":
      return "Unknown";
  }
}

function fmtDatetime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function fmtOptionalPct(val: number | null | undefined): string {
  if (val === null || val === undefined) return "—";
  return `${val > 0 ? "+" : ""}${val.toFixed(1)}%`;
}

function fmtOptionalMonths(val: number | null | undefined): string {
  if (val === null || val === undefined) return "—";
  return `${val.toFixed(1)}m`;
}

// ---------------------------------------------------------------------------
// Comparison block display
// ---------------------------------------------------------------------------

function ComparisonBlock({
  comparison,
}: {
  comparison: ExecutionOutcomeComparisonBlock;
}) {
  return (
    <div
      style={{
        marginTop: 16,
        padding: 12,
        border: "1px solid var(--color-border, #e5e7eb)",
        borderRadius: 8,
        background: "var(--color-surface-subtle, #f9fafb)",
      }}
      data-testid="comparison-block"
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 10,
        }}
      >
        <span
          style={{ fontWeight: 700, fontSize: "0.875rem" }}
          data-testid="comparison-title"
        >
          Intended vs Realized
        </span>
        <span
          style={matchStatusStyle(comparison.match_status)}
          data-testid="comparison-match-badge"
        >
          {matchStatusLabel(comparison.match_status)}
        </span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
          gap: 10,
          fontSize: "0.75rem",
          marginBottom: 10,
        }}
      >
        <div data-testid="comparison-price-row">
          <div style={{ color: "var(--color-text-muted, #6b7280)", marginBottom: 2 }}>
            Price Adjustment
          </div>
          <div>
            <span style={{ color: "var(--color-text-muted, #6b7280)" }}>Intended: </span>
            <span
              style={{ fontWeight: 600 }}
              data-testid="comparison-intended-price"
            >
              {fmtOptionalPct(comparison.intended_price_adjustment_pct)}
            </span>
          </div>
          <div>
            <span style={{ color: "var(--color-text-muted, #6b7280)" }}>Actual: </span>
            <span
              style={{ fontWeight: 600 }}
              data-testid="comparison-actual-price"
            >
              {fmtOptionalPct(comparison.actual_price_adjustment_pct)}
            </span>
          </div>
        </div>

        <div data-testid="comparison-phase-row">
          <div style={{ color: "var(--color-text-muted, #6b7280)", marginBottom: 2 }}>
            Phase Delay
          </div>
          <div>
            <span style={{ color: "var(--color-text-muted, #6b7280)" }}>Intended: </span>
            <span
              style={{ fontWeight: 600 }}
              data-testid="comparison-intended-phase"
            >
              {fmtOptionalMonths(comparison.intended_phase_delay_months)}
            </span>
          </div>
          <div>
            <span style={{ color: "var(--color-text-muted, #6b7280)" }}>Actual: </span>
            <span
              style={{ fontWeight: 600 }}
              data-testid="comparison-actual-phase"
            >
              {fmtOptionalMonths(comparison.actual_phase_delay_months)}
            </span>
          </div>
        </div>

        <div data-testid="comparison-release-row">
          <div style={{ color: "var(--color-text-muted, #6b7280)", marginBottom: 2 }}>
            Release Strategy
          </div>
          <div>
            <span style={{ color: "var(--color-text-muted, #6b7280)" }}>Intended: </span>
            <span
              style={{ fontWeight: 600 }}
              data-testid="comparison-intended-release"
            >
              {comparison.intended_release_strategy ?? "—"}
            </span>
          </div>
          <div>
            <span style={{ color: "var(--color-text-muted, #6b7280)" }}>Actual: </span>
            <span
              style={{ fontWeight: 600 }}
              data-testid="comparison-actual-release"
            >
              {comparison.actual_release_strategy ?? "—"}
            </span>
          </div>
        </div>
      </div>

      <div
        style={{
          fontSize: "0.75rem",
          color: "var(--color-text-muted, #6b7280)",
          marginBottom: 4,
        }}
        data-testid="comparison-divergence-summary"
      >
        {comparison.divergence_summary}
      </div>

      <div style={{ display: "flex", gap: 12, fontSize: "0.75rem", flexWrap: "wrap" }}>
        <span data-testid="comparison-quality">
          <span style={{ color: "var(--color-text-muted, #6b7280)" }}>
            Execution quality:{" "}
          </span>
          <span style={{ fontWeight: 600 }}>
            {qualityLabel(comparison.execution_quality)}
          </span>
        </span>
        {comparison.has_material_divergence && (
          <span
            style={{
              background: "#fee2e2",
              color: "#b91c1c",
              padding: "1px 8px",
              borderRadius: 10,
              fontWeight: 600,
              fontSize: "0.7rem",
            }}
            data-testid="material-divergence-badge"
          >
            Material Divergence
          </span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Recorded outcome display
// ---------------------------------------------------------------------------

function RecordedOutcomeDisplay({
  outcome,
}: {
  outcome: StrategyExecutionOutcomeResponse;
}) {
  const resultStyle: React.CSSProperties = {
    display: "inline-block",
    padding: "2px 10px",
    borderRadius: 12,
    fontSize: "0.75rem",
    fontWeight: 600,
    ...outcomeResultStyle(outcome.outcome_result),
  };

  return (
    <div data-testid="recorded-outcome-display">
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 10,
        }}
      >
        <span style={{ fontWeight: 700, fontSize: "0.875rem" }}>
          Recorded Outcome
        </span>
        <span style={resultStyle} data-testid="outcome-result-badge">
          {outcomeResultLabel(outcome.outcome_result)}
        </span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
          gap: 8,
          fontSize: "0.75rem",
          marginBottom: 10,
        }}
      >
        <div>
          <span style={{ color: "var(--color-text-muted, #6b7280)" }}>
            Actual Price Adj.{" "}
          </span>
          <span style={{ fontWeight: 600 }} data-testid="actual-price-value">
            {fmtOptionalPct(outcome.actual_price_adjustment_pct)}
          </span>
        </div>
        <div>
          <span style={{ color: "var(--color-text-muted, #6b7280)" }}>
            Actual Phase Delay{" "}
          </span>
          <span style={{ fontWeight: 600 }} data-testid="actual-phase-value">
            {fmtOptionalMonths(outcome.actual_phase_delay_months)}
          </span>
        </div>
        <div>
          <span style={{ color: "var(--color-text-muted, #6b7280)" }}>
            Release Strategy{" "}
          </span>
          <span style={{ fontWeight: 600 }} data-testid="actual-release-value">
            {outcome.actual_release_strategy ?? "—"}
          </span>
        </div>
      </div>

      {outcome.execution_summary && (
        <div
          style={{
            fontSize: "0.75rem",
            color: "var(--color-text, #111827)",
            marginBottom: 6,
            padding: 8,
            background: "var(--color-surface-subtle, #f9fafb)",
            borderRadius: 6,
          }}
          data-testid="execution-summary-text"
        >
          {outcome.execution_summary}
        </div>
      )}

      {outcome.outcome_notes && (
        <div
          style={{
            fontSize: "0.75rem",
            color: "var(--color-text-muted, #6b7280)",
            marginBottom: 6,
          }}
          data-testid="outcome-notes-text"
        >
          Notes: {outcome.outcome_notes}
        </div>
      )}

      <div
        style={{
          fontSize: "0.7rem",
          color: "var(--color-text-muted, #6b7280)",
          marginTop: 4,
        }}
        data-testid="outcome-metadata"
      >
        Recorded by {outcome.recorded_by_user_id} on{" "}
        {fmtDatetime(outcome.recorded_at)}
      </div>

      <ComparisonBlock comparison={outcome.comparison} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Record outcome form
// ---------------------------------------------------------------------------

const OUTCOME_RESULT_OPTIONS: { value: OutcomeResult; label: string }[] = [
  { value: "matched_strategy", label: "Matched Strategy" },
  { value: "partially_matched", label: "Partially Matched" },
  { value: "diverged", label: "Diverged" },
  { value: "cancelled_execution", label: "Cancelled Execution" },
  { value: "insufficient_data", label: "Insufficient Data" },
];

interface RecordFormProps {
  triggerId: string;
  onRecorded: (outcome: StrategyExecutionOutcomeResponse) => void;
}

function RecordOutcomeForm({ triggerId, onRecorded }: RecordFormProps) {
  const [outcomeResult, setOutcomeResult] =
    useState<OutcomeResult>("matched_strategy");
  const [priceAdj, setPriceAdj] = useState("");
  const [phaseDelay, setPhaseDelay] = useState("");
  const [releaseStrategy, setReleaseStrategy] = useState("");
  const [summary, setSummary] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const body: RecordExecutionOutcomeRequest = {
      outcome_result: outcomeResult,
      actual_price_adjustment_pct:
        priceAdj !== "" ? parseFloat(priceAdj) : null,
      actual_phase_delay_months:
        phaseDelay !== "" ? parseFloat(phaseDelay) : null,
      actual_release_strategy: releaseStrategy || null,
      execution_summary: summary || null,
      outcome_notes: notes || null,
    };

    try {
      const recorded = await recordStrategyExecutionOutcome(triggerId, body);
      onRecorded(recorded);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to record outcome.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "6px 10px",
    border: "1px solid var(--color-border, #d1d5db)",
    borderRadius: 6,
    fontSize: "0.875rem",
    boxSizing: "border-box",
    background: "var(--color-surface, #ffffff)",
    color: "var(--color-text, #111827)",
  };

  const labelStyle: React.CSSProperties = {
    display: "block",
    fontSize: "0.75rem",
    fontWeight: 600,
    color: "var(--color-text-muted, #6b7280)",
    marginBottom: 4,
  };

  return (
    <form
      onSubmit={handleSubmit}
      style={{ marginTop: 16 }}
      data-testid="record-outcome-form"
    >
      <div style={{ fontWeight: 700, fontSize: "0.875rem", marginBottom: 12 }}>
        Record Execution Outcome
      </div>

      {error && (
        <div
          style={{
            color: "#b91c1c",
            fontSize: "0.75rem",
            marginBottom: 10,
          }}
          data-testid="record-outcome-error"
        >
          {error}
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
          gap: 10,
          marginBottom: 10,
        }}
      >
        <div>
          <label style={labelStyle} htmlFor="outcome-result">
            Outcome Result *
          </label>
          <select
            id="outcome-result"
            value={outcomeResult}
            onChange={(e) => setOutcomeResult(e.target.value as OutcomeResult)}
            style={inputStyle}
            required
            data-testid="outcome-result-select"
          >
            {OUTCOME_RESULT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label style={labelStyle} htmlFor="price-adj">
            Actual Price Adjustment (%)
          </label>
          <input
            id="price-adj"
            type="number"
            step="0.1"
            value={priceAdj}
            onChange={(e) => setPriceAdj(e.target.value)}
            placeholder="e.g. 5.0"
            style={inputStyle}
            data-testid="price-adj-input"
          />
        </div>

        <div>
          <label style={labelStyle} htmlFor="phase-delay">
            Actual Phase Delay (months)
          </label>
          <input
            id="phase-delay"
            type="number"
            step="0.5"
            min="0"
            value={phaseDelay}
            onChange={(e) => setPhaseDelay(e.target.value)}
            placeholder="e.g. 2"
            style={inputStyle}
            data-testid="phase-delay-input"
          />
        </div>

        <div>
          <label style={labelStyle} htmlFor="release-strategy">
            Actual Release Strategy
          </label>
          <input
            id="release-strategy"
            type="text"
            value={releaseStrategy}
            onChange={(e) => setReleaseStrategy(e.target.value)}
            placeholder="e.g. maintain"
            style={inputStyle}
            data-testid="release-strategy-input"
          />
        </div>
      </div>

      <div style={{ marginBottom: 10 }}>
        <label style={labelStyle} htmlFor="execution-summary">
          Execution Summary
        </label>
        <textarea
          id="execution-summary"
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          rows={3}
          placeholder="Describe what was executed…"
          style={{ ...inputStyle, resize: "vertical" }}
          data-testid="execution-summary-input"
        />
      </div>

      <div style={{ marginBottom: 12 }}>
        <label style={labelStyle} htmlFor="outcome-notes">
          Outcome Notes
        </label>
        <textarea
          id="outcome-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          placeholder="Additional notes or deviations…"
          style={{ ...inputStyle, resize: "vertical" }}
          data-testid="outcome-notes-input"
        />
      </div>

      <button
        type="submit"
        disabled={submitting}
        style={{
          padding: "8px 20px",
          background: submitting ? "#9ca3af" : "#2563eb",
          color: "#ffffff",
          border: "none",
          borderRadius: 6,
          fontSize: "0.875rem",
          fontWeight: 600,
          cursor: submitting ? "not-allowed" : "pointer",
        }}
        data-testid="record-outcome-submit"
      >
        {submitting ? "Recording…" : "Record Outcome"}
      </button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface StrategyExecutionOutcomePanelProps {
  projectId: string;
}

export function StrategyExecutionOutcomePanel({
  projectId,
}: StrategyExecutionOutcomePanelProps) {
  const [data, setData] = useState<ProjectExecutionOutcomeResponse | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  function load() {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    getProjectStrategyExecutionOutcome(projectId, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setData(result);
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load execution outcome.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
  }

  useEffect(() => {
    load();
    return () => abortRef.current?.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  function handleRecorded(outcome: StrategyExecutionOutcomeResponse) {
    if (data) {
      setData({
        ...data,
        latest_outcome: outcome,
      });
    }
  }

  // ------------------------------------------------------------------
  // Render states
  // ------------------------------------------------------------------

  if (loading) {
    return (
      <section
        aria-label="Execution Outcome"
        style={{
          padding: 16,
          color: "var(--color-text-muted, #6b7280)",
          fontSize: "0.875rem",
        }}
        data-testid="outcome-panel-loading"
      >
        Loading execution outcome…
      </section>
    );
  }

  if (error) {
    return (
      <section
        aria-label="Execution Outcome"
        style={{ padding: 16, color: "#b91c1c", fontSize: "0.875rem" }}
        data-testid="outcome-panel-error"
      >
        {error}
      </section>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <section
      aria-label="Execution Outcome"
      style={{
        padding: 16,
        border: "1px solid var(--color-border, #e5e7eb)",
        borderRadius: 8,
        background: "var(--color-surface, #ffffff)",
      }}
      data-testid="outcome-panel"
    >
      <h3
        style={{
          fontSize: "1rem",
          fontWeight: 700,
          margin: "0 0 12px",
          color: "var(--color-text)",
        }}
      >
        Execution Outcome
      </h3>

      {/* Trigger context */}
      {data.execution_trigger_id ? (
        <div
          style={{
            fontSize: "0.75rem",
            color: "var(--color-text-muted, #6b7280)",
            marginBottom: 12,
          }}
          data-testid="trigger-context"
        >
          Trigger:{" "}
          <span style={{ fontWeight: 600 }} data-testid="trigger-id">
            {data.execution_trigger_id}
          </span>
          {data.trigger_status && (
            <>
              {" "}
              — Status:{" "}
              <span
                style={{ fontWeight: 600 }}
                data-testid="trigger-status"
              >
                {data.trigger_status}
              </span>
            </>
          )}
        </div>
      ) : (
        <p
          style={{
            fontSize: "0.875rem",
            color: "var(--color-text-muted, #6b7280)",
            margin: 0,
          }}
          data-testid="no-trigger-message"
        >
          No execution trigger exists for this project yet.
        </p>
      )}

      {/* Recorded outcome */}
      {data.latest_outcome ? (
        <RecordedOutcomeDisplay outcome={data.latest_outcome} />
      ) : data.execution_trigger_id ? (
        <p
          style={{
            fontSize: "0.875rem",
            color: "var(--color-text-muted, #6b7280)",
            margin: "8px 0",
          }}
          data-testid="no-outcome-message"
        >
          No outcome has been recorded for this trigger yet.
        </p>
      ) : null}

      {/* Record outcome form — shown when eligible */}
      {data.outcome_eligible && data.execution_trigger_id ? (
        <RecordOutcomeForm
          triggerId={data.execution_trigger_id}
          onRecorded={handleRecorded}
        />
      ) : data.execution_trigger_id && !data.outcome_eligible ? (
        <p
          style={{
            fontSize: "0.75rem",
            color: "var(--color-text-muted, #6b7280)",
            marginTop: 12,
          }}
          data-testid="outcome-ineligible-message"
        >
          Outcome recording is not available for the current trigger state (
          {data.trigger_status}).
        </p>
      ) : null}
    </section>
  );
}
