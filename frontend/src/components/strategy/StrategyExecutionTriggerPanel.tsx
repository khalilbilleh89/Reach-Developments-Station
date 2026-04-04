"use client";

/**
 * StrategyExecutionTriggerPanel.tsx
 *
 * Strategy Execution Trigger panel (PR-V7-09).
 *
 * Displays the current execution trigger state for a project and allows
 * authorised users to:
 *  - Trigger execution handoff (when an approved strategy exists and no active trigger)
 *  - Start execution (move to in_progress)
 *  - Complete execution (move to completed)
 *  - Cancel execution with a required reason
 *
 * Design principles:
 *  - All state is backend-owned; no workflow logic computed client-side.
 *  - Governance only: no execution, no pricing/phasing mutations.
 *  - Renders safe loading / error / null states at each phase.
 *  - AbortController wired for clean unmount cancellation.
 *
 * PR-V7-09 — Approved Strategy Execution Trigger & Handoff Records
 */

import React, { useEffect, useRef, useState } from "react";
import {
  cancelStrategyExecutionTrigger,
  completeStrategyExecutionTrigger,
  createStrategyExecutionTrigger,
  getProjectStrategyExecutionTrigger,
  startStrategyExecutionTrigger,
} from "@/lib/strategy-execution-trigger-api";
import type {
  ExecutionTriggerStatus,
  StrategyExecutionTriggerResponse,
} from "@/lib/strategy-execution-trigger-types";

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

function statusBadgeStyle(status: ExecutionTriggerStatus): React.CSSProperties {
  switch (status) {
    case "triggered":
      return {
        background: "#dbeafe",
        color: "#1d4ed8",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: "0.75rem",
        fontWeight: 600,
      };
    case "in_progress":
      return {
        background: "#fef9c3",
        color: "#854d0e",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: "0.75rem",
        fontWeight: 600,
      };
    case "completed":
      return {
        background: "#dcfce7",
        color: "#15803d",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: "0.75rem",
        fontWeight: 600,
      };
    case "cancelled":
      return {
        background: "#fee2e2",
        color: "#b91c1c",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: "0.75rem",
        fontWeight: 600,
      };
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
// Sub-components
// ---------------------------------------------------------------------------

interface TriggerStatusBadgeProps {
  status: ExecutionTriggerStatus;
}

function TriggerStatusBadge({ status }: TriggerStatusBadgeProps) {
  return (
    <span style={statusBadgeStyle(status)} data-testid="trigger-status-badge">
      {statusLabel(status)}
    </span>
  );
}

interface AuditMetaProps {
  trigger: StrategyExecutionTriggerResponse;
}

function AuditMeta({ trigger }: AuditMetaProps) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
        gap: 8,
        marginTop: 12,
        padding: 10,
        background: "var(--color-surface-subtle, #f9fafb)",
        borderRadius: 6,
        fontSize: "0.75rem",
      }}
      data-testid="trigger-audit-meta"
    >
      <div>
        <div style={{ color: "var(--color-text-muted, #6b7280)" }}>Record ID</div>
        <div
          style={{ fontWeight: 600, wordBreak: "break-all" }}
          data-testid="trigger-id"
        >
          {trigger.id}
        </div>
      </div>
      <div>
        <div style={{ color: "var(--color-text-muted, #6b7280)" }}>Triggered</div>
        <div style={{ fontWeight: 600 }} data-testid="trigger-triggered-at">
          {fmtDatetime(trigger.triggered_at)}
        </div>
      </div>
      <div>
        <div style={{ color: "var(--color-text-muted, #6b7280)" }}>Triggered by</div>
        <div style={{ fontWeight: 600 }} data-testid="trigger-triggered-by">
          {trigger.triggered_by_user_id}
        </div>
      </div>
      {trigger.completed_at && (
        <div>
          <div style={{ color: "var(--color-text-muted, #6b7280)" }}>Completed</div>
          <div style={{ fontWeight: 600 }} data-testid="trigger-completed-at">
            {fmtDatetime(trigger.completed_at)}
          </div>
        </div>
      )}
      {trigger.cancelled_at && (
        <div>
          <div style={{ color: "var(--color-text-muted, #6b7280)" }}>Cancelled</div>
          <div style={{ fontWeight: 600 }} data-testid="trigger-cancelled-at">
            {fmtDatetime(trigger.cancelled_at)}
          </div>
        </div>
      )}
      {trigger.cancellation_reason && (
        <div style={{ gridColumn: "1 / -1" }}>
          <div style={{ color: "var(--color-text-muted, #6b7280)" }}>
            Cancellation reason
          </div>
          <div
            style={{ fontWeight: 500, color: "#b91c1c", marginTop: 2 }}
            data-testid="trigger-cancellation-reason"
          >
            {trigger.cancellation_reason}
          </div>
        </div>
      )}
      {trigger.approval_id && (
        <div>
          <div style={{ color: "var(--color-text-muted, #6b7280)" }}>Approval ID</div>
          <div
            style={{ fontWeight: 600, wordBreak: "break-all" }}
            data-testid="trigger-approval-id"
          >
            {trigger.approval_id}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface StrategyExecutionTriggerPanelProps {
  projectId: string;
}

export function StrategyExecutionTriggerPanel({
  projectId,
}: StrategyExecutionTriggerPanelProps) {
  const [trigger, setTrigger] = useState<StrategyExecutionTriggerResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [cancellationReason, setCancellationReason] = useState("");
  const [showCancelForm, setShowCancelForm] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const actionAbortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

  // ------------------------------------------------------------------
  // Track mount state for abort-safe action handlers
  // ------------------------------------------------------------------

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      actionAbortRef.current?.abort();
    };
  }, []);

  // ------------------------------------------------------------------
  // Load latest trigger on mount / projectId change
  // ------------------------------------------------------------------

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    getProjectStrategyExecutionTrigger(projectId, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setTrigger(data);
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load execution trigger status.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [projectId]);

  // ------------------------------------------------------------------
  // Actions — each action gets its own AbortController so unmount
  // or a subsequent action can cancel an in-flight request and
  // prevent setState calls after unmount.
  // ------------------------------------------------------------------

  /** Returns true when the request was aborted or the component has unmounted. */
  function _isStale(signal: AbortSignal): boolean {
    return signal.aborted || !mountedRef.current;
  }

  async function handleTriggerExecution() {
    actionAbortRef.current?.abort();
    const controller = new AbortController();
    actionAbortRef.current = controller;

    setActionLoading(true);
    setActionError(null);
    try {
      const result = await createStrategyExecutionTrigger(
        projectId,
        controller.signal,
      );
      if (!_isStale(controller.signal)) {
        setTrigger(result);
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      if (!_isStale(controller.signal)) {
        setActionError(
          err instanceof Error
            ? err.message
            : "Failed to create execution trigger.",
        );
      }
    } finally {
      if (!_isStale(controller.signal)) {
        setActionLoading(false);
      }
    }
  }

  async function handleStart() {
    if (!trigger) return;

    actionAbortRef.current?.abort();
    const controller = new AbortController();
    actionAbortRef.current = controller;

    setActionLoading(true);
    setActionError(null);
    try {
      const result = await startStrategyExecutionTrigger(
        trigger.id,
        controller.signal,
      );
      if (!_isStale(controller.signal)) {
        setTrigger(result);
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      if (!_isStale(controller.signal)) {
        setActionError(
          err instanceof Error ? err.message : "Failed to start execution.",
        );
      }
    } finally {
      if (!_isStale(controller.signal)) {
        setActionLoading(false);
      }
    }
  }

  async function handleComplete() {
    if (!trigger) return;

    actionAbortRef.current?.abort();
    const controller = new AbortController();
    actionAbortRef.current = controller;

    setActionLoading(true);
    setActionError(null);
    try {
      const result = await completeStrategyExecutionTrigger(
        trigger.id,
        controller.signal,
      );
      if (!_isStale(controller.signal)) {
        setTrigger(result);
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      if (!_isStale(controller.signal)) {
        setActionError(
          err instanceof Error ? err.message : "Failed to complete execution.",
        );
      }
    } finally {
      if (!_isStale(controller.signal)) {
        setActionLoading(false);
      }
    }
  }

  async function handleCancel() {
    if (!trigger || !cancellationReason.trim()) return;

    actionAbortRef.current?.abort();
    const controller = new AbortController();
    actionAbortRef.current = controller;

    setActionLoading(true);
    setActionError(null);
    try {
      const result = await cancelStrategyExecutionTrigger(
        trigger.id,
        { cancellation_reason: cancellationReason.trim() },
        controller.signal,
      );
      if (!_isStale(controller.signal)) {
        setTrigger(result);
        setShowCancelForm(false);
        setCancellationReason("");
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      if (!_isStale(controller.signal)) {
        setActionError(
          err instanceof Error ? err.message : "Failed to cancel execution.",
        );
      }
    } finally {
      if (!_isStale(controller.signal)) {
        setActionLoading(false);
      }
    }
  }

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  if (loading) {
    return (
      <section
        aria-label="Strategy Execution Trigger"
        style={{
          padding: 16,
          color: "var(--color-text-muted, #6b7280)",
          fontSize: "0.875rem",
        }}
        data-testid="trigger-loading"
      >
        Loading execution trigger status…
      </section>
    );
  }

  if (error) {
    return (
      <section
        aria-label="Strategy Execution Trigger"
        style={{ padding: 16, color: "#b91c1c", fontSize: "0.875rem" }}
        data-testid="trigger-error"
      >
        {error}
      </section>
    );
  }

  const panelStyle: React.CSSProperties = {
    padding: 16,
    border: "1px solid var(--color-border, #e5e7eb)",
    borderRadius: 8,
    background: "var(--color-surface, #ffffff)",
  };

  const btnBase: React.CSSProperties = {
    display: "inline-block",
    padding: "6px 14px",
    borderRadius: 6,
    fontSize: "0.8125rem",
    fontWeight: 600,
    cursor: actionLoading ? "not-allowed" : "pointer",
    border: "none",
    opacity: actionLoading ? 0.6 : 1,
  };

  const isActive =
    trigger !== null &&
    (trigger.status === "triggered" || trigger.status === "in_progress");

  return (
    <section
      aria-label="Strategy Execution Trigger"
      style={panelStyle}
      data-testid="trigger-panel"
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 12,
        }}
      >
        <h3
          style={{
            fontSize: "1rem",
            fontWeight: 700,
            margin: 0,
            color: "var(--color-text)",
          }}
        >
          Execution Trigger
        </h3>
        {trigger && <TriggerStatusBadge status={trigger.status} />}
      </div>

      {/* No trigger yet */}
      {!trigger && (
        <div data-testid="trigger-no-record">
          <p
            style={{
              fontSize: "0.875rem",
              color: "var(--color-text-muted, #6b7280)",
              margin: "0 0 12px",
            }}
          >
            No execution trigger has been created for this project yet. Trigger
            execution handoff once the strategy has been approved.
          </p>
          <button
            style={{ ...btnBase, background: "#2563eb", color: "#ffffff" }}
            onClick={handleTriggerExecution}
            disabled={actionLoading}
            data-testid="btn-trigger-execution"
          >
            {actionLoading ? "Triggering…" : "Trigger Execution Handoff"}
          </button>
        </div>
      )}

      {/* Existing trigger record */}
      {trigger && (
        <div>
          <AuditMeta trigger={trigger} />

          {/* Actions for triggered state */}
          {trigger.status === "triggered" && (
            <div style={{ marginTop: 16 }} data-testid="trigger-actions-triggered">
              {!showCancelForm ? (
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button
                    style={{ ...btnBase, background: "#16a34a", color: "#ffffff" }}
                    onClick={handleStart}
                    disabled={actionLoading}
                    data-testid="btn-start"
                  >
                    {actionLoading ? "Starting…" : "Start Execution"}
                  </button>
                  <button
                    style={{ ...btnBase, background: "#dc2626", color: "#ffffff" }}
                    onClick={() => setShowCancelForm(true)}
                    disabled={actionLoading}
                    data-testid="btn-show-cancel"
                  >
                    Cancel Trigger
                  </button>
                </div>
              ) : (
                <CancelForm
                  cancellationReason={cancellationReason}
                  setCancellationReason={setCancellationReason}
                  actionLoading={actionLoading}
                  onConfirm={handleCancel}
                  onDismiss={() => {
                    setShowCancelForm(false);
                    setCancellationReason("");
                  }}
                />
              )}
            </div>
          )}

          {/* Actions for in_progress state */}
          {trigger.status === "in_progress" && (
            <div style={{ marginTop: 16 }} data-testid="trigger-actions-in-progress">
              {!showCancelForm ? (
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button
                    style={{ ...btnBase, background: "#16a34a", color: "#ffffff" }}
                    onClick={handleComplete}
                    disabled={actionLoading}
                    data-testid="btn-complete"
                  >
                    {actionLoading ? "Completing…" : "Mark as Completed"}
                  </button>
                  <button
                    style={{ ...btnBase, background: "#dc2626", color: "#ffffff" }}
                    onClick={() => setShowCancelForm(true)}
                    disabled={actionLoading}
                    data-testid="btn-show-cancel-in-progress"
                  >
                    Cancel Execution
                  </button>
                </div>
              ) : (
                <CancelForm
                  cancellationReason={cancellationReason}
                  setCancellationReason={setCancellationReason}
                  actionLoading={actionLoading}
                  onConfirm={handleCancel}
                  onDismiss={() => {
                    setShowCancelForm(false);
                    setCancellationReason("");
                  }}
                />
              )}
            </div>
          )}

          {/* New trigger allowed after terminal state */}
          {!isActive && (
            <div style={{ marginTop: 16 }} data-testid="trigger-new-request">
              <button
                style={{ ...btnBase, background: "#2563eb", color: "#ffffff" }}
                onClick={handleTriggerExecution}
                disabled={actionLoading}
                data-testid="btn-trigger-new"
              >
                {actionLoading ? "Triggering…" : "Trigger New Execution Handoff"}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Action-level error */}
      {actionError && (
        <p
          style={{ marginTop: 10, fontSize: "0.8125rem", color: "#b91c1c" }}
          data-testid="trigger-action-error"
        >
          {actionError}
        </p>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// CancelForm sub-component
// ---------------------------------------------------------------------------

interface CancelFormProps {
  cancellationReason: string;
  setCancellationReason: (v: string) => void;
  actionLoading: boolean;
  onConfirm: () => void;
  onDismiss: () => void;
}

function CancelForm({
  cancellationReason,
  setCancellationReason,
  actionLoading,
  onConfirm,
  onDismiss,
}: CancelFormProps) {
  return (
    <div data-testid="cancel-form">
      <label
        htmlFor="cancellation-reason"
        style={{
          display: "block",
          fontSize: "0.8125rem",
          fontWeight: 600,
          marginBottom: 4,
        }}
      >
        Cancellation Reason <span style={{ color: "#b91c1c" }}>*</span>
      </label>
      <textarea
        id="cancellation-reason"
        rows={3}
        value={cancellationReason}
        onChange={(e) => setCancellationReason(e.target.value)}
        placeholder="Describe why this execution trigger is being cancelled…"
        style={{
          width: "100%",
          padding: "6px 8px",
          borderRadius: 4,
          border: "1px solid var(--color-border, #d1d5db)",
          fontSize: "0.8125rem",
          resize: "vertical",
          boxSizing: "border-box",
        }}
        data-testid="cancellation-reason-input"
      />
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <button
          style={{
            display: "inline-block",
            padding: "6px 14px",
            borderRadius: 6,
            fontSize: "0.8125rem",
            fontWeight: 600,
            border: "none",
            background: "#dc2626",
            color: "#ffffff",
            opacity: actionLoading || !cancellationReason.trim() ? 0.6 : 1,
            cursor:
              actionLoading || !cancellationReason.trim()
                ? "not-allowed"
                : "pointer",
          }}
          onClick={onConfirm}
          disabled={actionLoading || !cancellationReason.trim()}
          data-testid="btn-confirm-cancel"
        >
          {actionLoading ? "Cancelling…" : "Confirm Cancellation"}
        </button>
        <button
          style={{
            display: "inline-block",
            padding: "6px 14px",
            borderRadius: 6,
            fontSize: "0.8125rem",
            fontWeight: 600,
            border: "none",
            background: "var(--color-surface-subtle, #f3f4f6)",
            color: "var(--color-text)",
            cursor: actionLoading ? "not-allowed" : "pointer",
            opacity: actionLoading ? 0.6 : 1,
          }}
          onClick={onDismiss}
          disabled={actionLoading}
          data-testid="btn-dismiss-cancel"
        >
          Back
        </button>
      </div>
    </div>
  );
}
