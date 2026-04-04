"use client";

/**
 * StrategyExecutionPackagePanel.tsx
 *
 * Strategy Execution Package panel (PR-V7-07).
 *
 * Displays the backend-generated execution package for a project:
 *  - Execution readiness badge and summary
 *  - Ordered action steps with urgency and review indicators
 *  - Dependency checks (cleared / blocked)
 *  - Caution notes with severity badges
 *  - Supporting metrics strip
 *  - Expected impact summary
 *
 * Design principles:
 *  - All values are sourced from the backend; no recomputation here.
 *  - Execution packages are never persisted.
 *  - Renders a safe null / loading / error state at each phase.
 *  - Read-only: no mutation controls exposed.
 *
 * PR-V7-07 — Strategy Execution Package Generator
 */

import React, { useEffect, useRef, useState } from "react";
import { getProjectStrategyExecutionPackage } from "@/lib/strategy-execution-package-api";
import type {
  CautionSeverity,
  ExecutionReadiness,
  ProjectStrategyExecutionPackageResponse,
  StrategyExecutionActionItem,
  StrategyExecutionCautionItem,
  StrategyExecutionDependencyItem,
} from "@/lib/strategy-execution-package-types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function readinessLabel(readiness: ExecutionReadiness): string {
  switch (readiness) {
    case "ready_for_review":
      return "Ready for Review";
    case "blocked_by_dependency":
      return "Blocked";
    case "caution_required":
      return "Caution Required";
    case "insufficient_data":
      return "Insufficient Data";
  }
}

function readinessBadgeStyle(readiness: ExecutionReadiness): React.CSSProperties {
  switch (readiness) {
    case "ready_for_review":
      return {
        background: "#dcfce7",
        color: "#15803d",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: "0.75rem",
        fontWeight: 600,
      };
    case "blocked_by_dependency":
      return {
        background: "#fee2e2",
        color: "#b91c1c",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: "0.75rem",
        fontWeight: 600,
      };
    case "caution_required":
      return {
        background: "#fef9c3",
        color: "#854d0e",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: "0.75rem",
        fontWeight: 600,
      };
    case "insufficient_data":
      return {
        background: "var(--color-border, #e5e7eb)",
        color: "var(--color-text-muted, #6b7280)",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: "0.75rem",
        fontWeight: 600,
      };
  }
}

function urgencyBadgeStyle(urgency: string): React.CSSProperties {
  if (urgency === "high")
    return { background: "#fee2e2", color: "#b91c1c", padding: "1px 6px", borderRadius: 8, fontSize: "0.7rem", fontWeight: 600 };
  if (urgency === "medium")
    return { background: "#fef9c3", color: "#854d0e", padding: "1px 6px", borderRadius: 8, fontSize: "0.7rem", fontWeight: 600 };
  return { background: "#dcfce7", color: "#15803d", padding: "1px 6px", borderRadius: 8, fontSize: "0.7rem", fontWeight: 600 };
}

function cautionSeverityStyle(severity: CautionSeverity): React.CSSProperties {
  if (severity === "high")
    return { background: "#fee2e2", color: "#b91c1c", padding: "1px 7px", borderRadius: 8, fontSize: "0.7rem", fontWeight: 600 };
  if (severity === "medium")
    return { background: "#fef9c3", color: "#854d0e", padding: "1px 7px", borderRadius: 8, fontSize: "0.7rem", fontWeight: 600 };
  return { background: "#dbeafe", color: "#1d4ed8", padding: "1px 7px", borderRadius: 8, fontSize: "0.7rem", fontWeight: 600 };
}

function depStatusStyle(status: "cleared" | "blocked"): React.CSSProperties {
  if (status === "cleared")
    return { background: "#dcfce7", color: "#15803d", padding: "1px 7px", borderRadius: 8, fontSize: "0.7rem", fontWeight: 600 };
  return { background: "#fee2e2", color: "#b91c1c", padding: "1px 7px", borderRadius: 8, fontSize: "0.7rem", fontWeight: 600 };
}

function fmtIrr(irr: number | null): string {
  if (irr == null) return "—";
  return `${(irr * 100).toFixed(2)}%`;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ActionStep({ action }: { action: StrategyExecutionActionItem }) {
  return (
    <div
      style={{
        display: "flex",
        gap: 12,
        padding: "10px 0",
        borderBottom: "1px solid var(--color-border-subtle, #e5e7eb)",
      }}
      data-testid={`action-step-${action.step_number}`}
    >
      <div
        style={{
          flexShrink: 0,
          width: 28,
          height: 28,
          borderRadius: "50%",
          background: "var(--color-border, #e5e7eb)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontWeight: 700,
          fontSize: "0.8rem",
          color: "var(--color-text-muted, #6b7280)",
        }}
        data-testid={`action-step-number-${action.step_number}`}
      >
        {action.step_number}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{ fontWeight: 600, fontSize: "0.875rem" }} data-testid={`action-title-${action.step_number}`}>
            {action.action_title}
          </span>
          <span style={urgencyBadgeStyle(action.urgency)} data-testid={`action-urgency-${action.step_number}`}>
            {action.urgency}
          </span>
          {action.review_required && (
            <span
              style={{ background: "#e0f2fe", color: "#0369a1", padding: "1px 6px", borderRadius: 8, fontSize: "0.7rem", fontWeight: 600 }}
              data-testid={`action-review-flag-${action.step_number}`}
            >
              Review Required
            </span>
          )}
        </div>
        <p style={{ margin: 0, fontSize: "0.8125rem", color: "var(--color-text-muted, #6b7280)" }}>
          {action.action_description}
        </p>
      </div>
    </div>
  );
}

function DependencyRow({ dep }: { dep: StrategyExecutionDependencyItem }) {
  return (
    <div
      style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "6px 0" }}
      data-testid={`dependency-${dep.dependency_type}`}
    >
      <span style={depStatusStyle(dep.dependency_status)} data-testid={`dep-status-${dep.dependency_type}`}>
        {dep.dependency_status === "cleared" ? "Cleared" : "Blocked"}
      </span>
      <div>
        <div style={{ fontWeight: 600, fontSize: "0.8125rem" }}>{dep.dependency_label}</div>
        {dep.blocking_reason && (
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted, #6b7280)", marginTop: 2 }}>
            {dep.blocking_reason}
          </div>
        )}
      </div>
    </div>
  );
}

function CautionCard({ caution }: { caution: StrategyExecutionCautionItem }) {
  return (
    <div
      style={{
        padding: "10px 12px",
        borderRadius: 8,
        background: caution.severity === "high" ? "#fff1f2" : caution.severity === "medium" ? "#fefce8" : "#eff6ff",
        border: `1px solid ${caution.severity === "high" ? "#fecdd3" : caution.severity === "medium" ? "#fef08a" : "#bfdbfe"}`,
        marginBottom: 8,
      }}
      data-testid={`caution-${caution.severity}-${caution.caution_title.replace(/\s+/g, "-").toLowerCase()}`}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <span style={cautionSeverityStyle(caution.severity)}>
          {caution.severity.charAt(0).toUpperCase() + caution.severity.slice(1)}
        </span>
        <span style={{ fontWeight: 600, fontSize: "0.8125rem" }}>{caution.caution_title}</span>
      </div>
      <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--color-text-muted, #6b7280)" }}>
        {caution.caution_description}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface StrategyExecutionPackagePanelProps {
  projectId: string;
}

export function StrategyExecutionPackagePanel({
  projectId,
}: StrategyExecutionPackagePanelProps) {
  const [pkg, setPkg] =
    useState<ProjectStrategyExecutionPackageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    getProjectStrategyExecutionPackage(projectId, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setPkg(data);
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          err instanceof Error ? err.message : "Failed to load execution package.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [projectId]);

  if (loading) {
    return (
      <section data-testid="execution-package-panel">
        <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted, #6b7280)" }}>
          Loading execution package…
        </p>
      </section>
    );
  }

  if (error) {
    return (
      <section data-testid="execution-package-panel">
        <p
          style={{ fontSize: "0.875rem", color: "#b91c1c" }}
          data-testid="execution-package-error"
        >
          {error}
        </p>
      </section>
    );
  }

  if (!pkg) {
    return null;
  }

  return (
    <section data-testid="execution-package-panel">
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
        <h3
          style={{
            fontSize: "1.0625rem",
            fontWeight: 600,
            margin: 0,
            color: "var(--color-text)",
          }}
        >
          Strategy Execution Package
        </h3>
        <span style={readinessBadgeStyle(pkg.execution_readiness)} data-testid="execution-readiness-badge">
          {readinessLabel(pkg.execution_readiness)}
        </span>
      </div>
      <p
        style={{ fontSize: "0.8125rem", color: "var(--color-text-muted, #6b7280)", margin: "0 0 16px" }}
        data-testid="execution-package-summary"
      >
        {pkg.summary}
      </p>

      {/* Dependencies */}
      {pkg.dependencies.length > 0 && (
        <div style={{ marginBottom: 16 }} data-testid="execution-dependencies-section">
          <h4 style={{ fontSize: "0.875rem", fontWeight: 600, margin: "0 0 8px", color: "var(--color-text)" }}>
            Dependencies
          </h4>
          {pkg.dependencies.map((dep) => (
            <DependencyRow key={dep.dependency_type} dep={dep} />
          ))}
        </div>
      )}

      {/* Cautions */}
      {pkg.cautions.length > 0 && (
        <div style={{ marginBottom: 16 }} data-testid="execution-cautions-section">
          <h4 style={{ fontSize: "0.875rem", fontWeight: 600, margin: "0 0 8px", color: "var(--color-text)" }}>
            Cautions
          </h4>
          {pkg.cautions.map((caution, i) => (
            <CautionCard key={i} caution={caution} />
          ))}
        </div>
      )}

      {/* Action sequence */}
      {pkg.actions.length > 0 && (
        <div style={{ marginBottom: 16 }} data-testid="execution-actions-section">
          <h4 style={{ fontSize: "0.875rem", fontWeight: 600, margin: "0 0 4px", color: "var(--color-text)" }}>
            Execution Actions
          </h4>
          <p style={{ fontSize: "0.75rem", color: "var(--color-text-muted, #6b7280)", margin: "0 0 8px" }}>
            Complete in order. Review-required steps need sign-off before proceeding.
          </p>
          {pkg.actions.map((action) => (
            <ActionStep key={action.step_number} action={action} />
          ))}
        </div>
      )}

      {/* Supporting metrics */}
      <div style={{ marginBottom: 16 }} data-testid="execution-metrics-section">
        <h4 style={{ fontSize: "0.875rem", fontWeight: 600, margin: "0 0 8px", color: "var(--color-text)" }}>
          Supporting Metrics
        </h4>
        <div
          style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))", gap: 8 }}
          data-testid="execution-metrics-grid"
        >
          <div>
            <div style={{ fontSize: "0.7rem", color: "var(--color-text-muted, #6b7280)" }}>Best IRR</div>
            <div style={{ fontWeight: 700, fontSize: "0.875rem" }} data-testid="execution-best-irr">
              {fmtIrr(pkg.supporting_metrics.best_irr)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: "0.7rem", color: "var(--color-text-muted, #6b7280)" }}>Risk</div>
            <div style={{ fontWeight: 600, fontSize: "0.875rem" }} data-testid="execution-risk-score">
              {pkg.supporting_metrics.risk_score ?? "—"}
            </div>
          </div>
          <div>
            <div style={{ fontSize: "0.7rem", color: "var(--color-text-muted, #6b7280)" }}>Price Adj.</div>
            <div style={{ fontWeight: 600, fontSize: "0.875rem" }} data-testid="execution-price-adj">
              {pkg.supporting_metrics.price_adjustment_pct != null
                ? `${pkg.supporting_metrics.price_adjustment_pct > 0 ? "+" : ""}${pkg.supporting_metrics.price_adjustment_pct}%`
                : "—"}
            </div>
          </div>
          <div>
            <div style={{ fontSize: "0.7rem", color: "var(--color-text-muted, #6b7280)" }}>Phase Delay</div>
            <div style={{ fontWeight: 600, fontSize: "0.875rem" }} data-testid="execution-phase-delay">
              {pkg.supporting_metrics.phase_delay_months != null
                ? `${pkg.supporting_metrics.phase_delay_months}mo`
                : "—"}
            </div>
          </div>
          <div>
            <div style={{ fontSize: "0.7rem", color: "var(--color-text-muted, #6b7280)" }}>Release</div>
            <div style={{ fontWeight: 600, fontSize: "0.875rem" }} data-testid="execution-release-strategy">
              {pkg.supporting_metrics.release_strategy ?? "—"}
            </div>
          </div>
        </div>
      </div>

      {/* Expected impact */}
      <div data-testid="execution-expected-impact">
        <h4 style={{ fontSize: "0.875rem", fontWeight: 600, margin: "0 0 4px", color: "var(--color-text)" }}>
          Expected Impact
        </h4>
        <p style={{ margin: 0, fontSize: "0.8125rem", color: "var(--color-text-muted, #6b7280)", fontStyle: "italic" }}>
          {pkg.expected_impact}
        </p>
      </div>
    </section>
  );
}
