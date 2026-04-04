"use client";

/**
 * PortfolioExecutionTriggerPanel.tsx
 *
 * Portfolio Execution Trigger summary panel (PR-V7-09).
 *
 * Shows:
 *  - Portfolio execution trigger status KPIs
 *  - Active execution handoffs (triggered or in_progress)
 *  - Projects with approved strategies awaiting execution trigger
 *
 * Design principles:
 *  - All values are sourced from the backend; no recomputation here.
 *  - Renders a safe empty state when no data exists.
 *  - Read-only: displays status information only, no mutation controls.
 *
 * PR-V7-09 — Approved Strategy Execution Trigger & Handoff Records
 */

import React, { useEffect, useRef, useState } from "react";
import { getPortfolioExecutionTriggers } from "@/lib/strategy-execution-trigger-api";
import type {
  ExecutionTriggerStatus,
  PortfolioExecutionTriggerSummaryResponse,
  PortfolioProjectEntry,
  PortfolioTriggerEntry,
} from "@/lib/strategy-execution-trigger-types";
import styles from "@/styles/portfolio.module.css";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusLabel(status: ExecutionTriggerStatus): string {
  switch (status) {
    case "triggered":
      return "Triggered";
    case "in_progress":
      return "In Progress";
    case "completed":
      return "Completed";
    case "cancelled":
      return "Cancelled";
  }
}

function statusBadgeClass(status: ExecutionTriggerStatus): string {
  switch (status) {
    case "triggered":
      return styles.badgeNeutral;
    case "in_progress":
      return styles.badgeNeedsAttention;
    case "completed":
      return styles.badgeSaving;
    case "cancelled":
      return styles.badgeOverrun;
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

// ---------------------------------------------------------------------------
// KPI summary strip
// ---------------------------------------------------------------------------

interface KpiItem {
  label: string;
  value: string;
  testId: string;
}

function KpiStrip({ items }: { items: KpiItem[] }) {
  return (
    <div className={styles.kpiCard} data-testid="trigger-kpi-strip">
      {items.map((kpi) => (
        <div key={kpi.label}>
          <div className={styles.kpiLabel}>{kpi.label}</div>
          <div className={styles.kpiValue} data-testid={kpi.testId}>
            {kpi.value}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Active trigger card
// ---------------------------------------------------------------------------

function ActiveTriggerCard({ entry }: { entry: PortfolioTriggerEntry }) {
  const { trigger } = entry;
  return (
    <div
      style={{
        padding: 12,
        border: "1px solid var(--color-border, #e5e7eb)",
        borderRadius: 8,
        background: "var(--color-surface, #ffffff)",
        marginBottom: 8,
      }}
      data-testid="active-trigger-card"
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 6,
        }}
      >
        <span
          style={{ fontWeight: 700, fontSize: "0.875rem" }}
          data-testid="active-trigger-project-name"
        >
          {entry.project_name}
        </span>
        <span
          className={statusBadgeClass(trigger.status)}
          data-testid="active-trigger-status-badge"
        >
          {statusLabel(trigger.status)}
        </span>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
          gap: 6,
          fontSize: "0.75rem",
        }}
      >
        <div>
          <span style={{ color: "var(--color-text-muted, #6b7280)" }}>Triggered </span>
          <span style={{ fontWeight: 600 }} data-testid="active-trigger-triggered-at">
            {fmtDatetime(trigger.triggered_at)}
          </span>
        </div>
        <div>
          <span style={{ color: "var(--color-text-muted, #6b7280)" }}>By </span>
          <span
            style={{ fontWeight: 600 }}
            data-testid="active-trigger-triggered-by"
          >
            {trigger.triggered_by_user_id}
          </span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Awaiting trigger card
// ---------------------------------------------------------------------------

function AwaitingTriggerCard({ entry }: { entry: PortfolioProjectEntry }) {
  return (
    <div
      style={{
        padding: 10,
        border: "1px solid var(--color-border, #e5e7eb)",
        borderRadius: 6,
        background: "var(--color-surface-subtle, #f9fafb)",
        marginBottom: 6,
        fontSize: "0.875rem",
        display: "flex",
        alignItems: "center",
        gap: 8,
      }}
      data-testid="awaiting-trigger-card"
    >
      <span style={{ fontWeight: 600 }} data-testid="awaiting-trigger-project-name">
        {entry.project_name}
      </span>
      <span className={styles.badgeNeutral} style={{ fontSize: "0.7rem" }}>
        Awaiting Trigger
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function PortfolioExecutionTriggerPanel() {
  const [summary, setSummary] =
    useState<PortfolioExecutionTriggerSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    getPortfolioExecutionTriggers(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setSummary(data);
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load portfolio execution triggers.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, []);

  // ------------------------------------------------------------------
  // Render states
  // ------------------------------------------------------------------

  if (loading) {
    return (
      <section
        aria-label="Portfolio Execution Triggers"
        style={{
          padding: 16,
          color: "var(--color-text-muted, #6b7280)",
          fontSize: "0.875rem",
        }}
        data-testid="portfolio-trigger-loading"
      >
        Loading portfolio execution triggers…
      </section>
    );
  }

  if (error) {
    return (
      <section
        aria-label="Portfolio Execution Triggers"
        style={{ padding: 16, color: "#b91c1c", fontSize: "0.875rem" }}
        data-testid="portfolio-trigger-error"
      >
        {error}
      </section>
    );
  }

  if (!summary) {
    return null;
  }

  const kpis: KpiItem[] = [
    {
      label: "Triggered",
      value: String(summary.triggered_count),
      testId: "kpi-triggered",
    },
    {
      label: "In Progress",
      value: String(summary.in_progress_count),
      testId: "kpi-in-progress",
    },
    {
      label: "Completed",
      value: String(summary.completed_count),
      testId: "kpi-completed",
    },
    {
      label: "Cancelled",
      value: String(summary.cancelled_count),
      testId: "kpi-cancelled",
    },
    {
      label: "Awaiting Trigger",
      value: String(summary.awaiting_trigger_count),
      testId: "kpi-awaiting",
    },
  ];

  return (
    <section
      aria-label="Portfolio Execution Triggers"
      style={{
        padding: 16,
        border: "1px solid var(--color-border, #e5e7eb)",
        borderRadius: 8,
        background: "var(--color-surface, #ffffff)",
      }}
      data-testid="portfolio-trigger-panel"
    >
      <h3
        style={{
          fontSize: "1rem",
          fontWeight: 700,
          margin: "0 0 16px",
          color: "var(--color-text)",
        }}
      >
        Portfolio Execution Triggers
      </h3>

      {/* KPI counts */}
      <KpiStrip items={kpis} />

      {/* Active execution handoffs */}
      <div style={{ marginTop: 20 }} data-testid="active-triggers-section">
        <h4
          style={{
            fontSize: "0.875rem",
            fontWeight: 700,
            margin: "0 0 10px",
            color: "var(--color-text)",
          }}
        >
          Active Execution Handoffs
          {summary.active_triggers.length > 0 && (
            <span
              style={{
                marginLeft: 8,
                fontSize: "0.75rem",
                color: "var(--color-text-muted, #6b7280)",
                fontWeight: 400,
              }}
            >
              ({summary.active_triggers.length})
            </span>
          )}
        </h4>
        {summary.active_triggers.length === 0 ? (
          <p
            style={{
              fontSize: "0.875rem",
              color: "var(--color-text-muted, #6b7280)",
              margin: 0,
            }}
            data-testid="no-active-triggers"
          >
            No active execution handoffs.
          </p>
        ) : (
          <div>
            {summary.active_triggers.map((entry) => (
              <ActiveTriggerCard
                key={entry.trigger.id}
                entry={entry}
              />
            ))}
          </div>
        )}
      </div>

      {/* Projects awaiting execution trigger */}
      <div style={{ marginTop: 20 }} data-testid="awaiting-triggers-section">
        <h4
          style={{
            fontSize: "0.875rem",
            fontWeight: 700,
            margin: "0 0 10px",
            color: "var(--color-text)",
          }}
        >
          Awaiting Execution Trigger
          {summary.awaiting_trigger_projects.length > 0 && (
            <span
              style={{
                marginLeft: 8,
                fontSize: "0.75rem",
                color: "var(--color-text-muted, #6b7280)",
                fontWeight: 400,
              }}
            >
              ({summary.awaiting_trigger_projects.length})
            </span>
          )}
        </h4>
        {summary.awaiting_trigger_count === 0 ? (
          <p
            style={{
              fontSize: "0.875rem",
              color: "var(--color-text-muted, #6b7280)",
              margin: 0,
            }}
            data-testid="no-awaiting-triggers"
          >
            No approved projects awaiting execution trigger.
          </p>
        ) : (
          <div>
            {summary.awaiting_trigger_projects.map((entry) => (
              <AwaitingTriggerCard key={entry.project_id} entry={entry} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
