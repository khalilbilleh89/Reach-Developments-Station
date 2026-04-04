"use client";

/**
 * StrategyApprovalPanel.tsx
 *
 * Strategy Approval Workflow panel (PR-V7-08).
 *
 * Displays the current approval state for a project strategy and allows
 * authorised users to:
 *  - Request a new approval (from the current execution package snapshot)
 *  - Approve a pending strategy request
 *  - Reject a pending strategy request with a required reason
 *
 * Design principles:
 *  - All state is backend-owned; no approval logic computed client-side.
 *  - Governance only: no execution, no pricing/phasing mutations.
 *  - Renders safe loading / error / null states at each phase.
 *  - AbortController wired for clean unmount cancellation.
 *
 * PR-V7-08 — Strategy Review & Approval Workflow
 */

import React, { useEffect, useRef, useState } from "react";
import {
  approveStrategy,
  createStrategyApproval,
  getLatestStrategyApproval,
  rejectStrategy,
} from "@/lib/strategy-approval-api";
import type {
  ApprovalStatus,
  StrategyApprovalResponse,
} from "@/lib/strategy-approval-types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusLabel(status: ApprovalStatus): string {
  switch (status) {
    case "pending":
      return "Pending Review";
    case "approved":
      return "Approved";
    case "rejected":
      return "Rejected";
  }
}

function statusBadgeStyle(status: ApprovalStatus): React.CSSProperties {
  switch (status) {
    case "pending":
      return {
        background: "#fef9c3",
        color: "#854d0e",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: "0.75rem",
        fontWeight: 600,
      };
    case "approved":
      return {
        background: "#dcfce7",
        color: "#15803d",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: "0.75rem",
        fontWeight: 600,
      };
    case "rejected":
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

interface ApprovalStatusBadgeProps {
  status: ApprovalStatus;
}

function ApprovalStatusBadge({ status }: ApprovalStatusBadgeProps) {
  return (
    <span style={statusBadgeStyle(status)} data-testid="approval-status-badge">
      {statusLabel(status)}
    </span>
  );
}

interface AuditMetaProps {
  approval: StrategyApprovalResponse;
}

function AuditMeta({ approval }: AuditMetaProps) {
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
      data-testid="approval-audit-meta"
    >
      <div>
        <div style={{ color: "var(--color-text-muted, #6b7280)" }}>Record ID</div>
        <div style={{ fontWeight: 600, wordBreak: "break-all" }} data-testid="approval-id">
          {approval.id}
        </div>
      </div>
      <div>
        <div style={{ color: "var(--color-text-muted, #6b7280)" }}>Requested</div>
        <div style={{ fontWeight: 600 }} data-testid="approval-created-at">
          {fmtDatetime(approval.created_at)}
        </div>
      </div>
      {approval.approved_at && (
        <div>
          <div style={{ color: "var(--color-text-muted, #6b7280)" }}>Decision at</div>
          <div style={{ fontWeight: 600 }} data-testid="approval-approved-at">
            {fmtDatetime(approval.approved_at)}
          </div>
        </div>
      )}
      {approval.approved_by_user_id && (
        <div>
          <div style={{ color: "var(--color-text-muted, #6b7280)" }}>Approved by</div>
          <div style={{ fontWeight: 600 }} data-testid="approval-approved-by">
            {approval.approved_by_user_id}
          </div>
        </div>
      )}
      {approval.rejection_reason && (
        <div style={{ gridColumn: "1 / -1" }}>
          <div style={{ color: "var(--color-text-muted, #6b7280)" }}>Rejection reason</div>
          <div
            style={{ fontWeight: 500, color: "#b91c1c", marginTop: 2 }}
            data-testid="approval-rejection-reason"
          >
            {approval.rejection_reason}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface StrategyApprovalPanelProps {
  projectId: string;
  /** Optional pre-built snapshot payloads from parent panels (PR-V7-07). */
  strategySnapshot?: Record<string, unknown>;
  executionPackageSnapshot?: Record<string, unknown>;
}

export function StrategyApprovalPanel({
  projectId,
  strategySnapshot = {},
  executionPackageSnapshot = {},
}: StrategyApprovalPanelProps) {
  const [approval, setApproval] = useState<StrategyApprovalResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");
  const [showRejectForm, setShowRejectForm] = useState(false);
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
  // Load latest approval on mount / projectId change
  // ------------------------------------------------------------------

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    getLatestStrategyApproval(projectId, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setApproval(data);
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          err instanceof Error ? err.message : "Failed to load approval status.",
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

  async function handleRequestApproval() {
    actionAbortRef.current?.abort();
    const controller = new AbortController();
    actionAbortRef.current = controller;

    setActionLoading(true);
    setActionError(null);
    try {
      const result = await createStrategyApproval(
        projectId,
        {
          strategy_snapshot: strategySnapshot,
          execution_package_snapshot: executionPackageSnapshot,
        },
        controller.signal,
      );
      if (!controller.signal.aborted && mountedRef.current) {
        setApproval(result);
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      if (mountedRef.current) {
        setActionError(
          err instanceof Error ? err.message : "Failed to create approval request.",
        );
      }
    } finally {
      if (!controller.signal.aborted && mountedRef.current) {
        setActionLoading(false);
      }
    }
  }

  async function handleApprove() {
    if (!approval) return;

    actionAbortRef.current?.abort();
    const controller = new AbortController();
    actionAbortRef.current = controller;

    setActionLoading(true);
    setActionError(null);
    try {
      const result = await approveStrategy(approval.id, {}, controller.signal);
      if (!controller.signal.aborted && mountedRef.current) {
        setApproval(result);
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      if (mountedRef.current) {
        setActionError(
          err instanceof Error ? err.message : "Failed to approve strategy.",
        );
      }
    } finally {
      if (!controller.signal.aborted && mountedRef.current) {
        setActionLoading(false);
      }
    }
  }

  async function handleReject() {
    if (!approval || !rejectionReason.trim()) return;

    actionAbortRef.current?.abort();
    const controller = new AbortController();
    actionAbortRef.current = controller;

    setActionLoading(true);
    setActionError(null);
    try {
      const result = await rejectStrategy(
        approval.id,
        { rejection_reason: rejectionReason.trim() },
        controller.signal,
      );
      if (!controller.signal.aborted && mountedRef.current) {
        setApproval(result);
        setShowRejectForm(false);
        setRejectionReason("");
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      if (mountedRef.current) {
        setActionError(
          err instanceof Error ? err.message : "Failed to reject strategy.",
        );
      }
    } finally {
      if (!controller.signal.aborted && mountedRef.current) {
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
        aria-label="Strategy Approval"
        style={{ padding: 16, color: "var(--color-text-muted, #6b7280)", fontSize: "0.875rem" }}
        data-testid="approval-loading"
      >
        Loading approval status…
      </section>
    );
  }

  if (error) {
    return (
      <section
        aria-label="Strategy Approval"
        style={{ padding: 16, color: "#b91c1c", fontSize: "0.875rem" }}
        data-testid="approval-error"
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

  return (
    <section aria-label="Strategy Approval" style={panelStyle} data-testid="approval-panel">
      {/* Header */}
      <div
        style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}
      >
        <h3 style={{ fontSize: "1rem", fontWeight: 700, margin: 0, color: "var(--color-text)" }}>
          Strategy Approval
        </h3>
        {approval && <ApprovalStatusBadge status={approval.status} />}
      </div>

      {/* No approval yet */}
      {!approval && (
        <div data-testid="approval-no-record">
          <p
            style={{ fontSize: "0.875rem", color: "var(--color-text-muted, #6b7280)", margin: "0 0 12px" }}
          >
            No approval request has been made for this project strategy yet.
          </p>
          <button
            style={{ ...btnBase, background: "#2563eb", color: "#ffffff" }}
            onClick={handleRequestApproval}
            disabled={actionLoading}
            data-testid="btn-request-approval"
          >
            {actionLoading ? "Requesting…" : "Request Approval"}
          </button>
        </div>
      )}

      {/* Existing approval record */}
      {approval && (
        <div>
          <AuditMeta approval={approval} />

          {/* Actions for pending approval */}
          {approval.status === "pending" && (
            <div style={{ marginTop: 16 }} data-testid="approval-actions">
              {!showRejectForm ? (
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button
                    style={{ ...btnBase, background: "#16a34a", color: "#ffffff" }}
                    onClick={handleApprove}
                    disabled={actionLoading}
                    data-testid="btn-approve"
                  >
                    {actionLoading ? "Approving…" : "Approve Strategy"}
                  </button>
                  <button
                    style={{ ...btnBase, background: "#dc2626", color: "#ffffff" }}
                    onClick={() => setShowRejectForm(true)}
                    disabled={actionLoading}
                    data-testid="btn-show-reject"
                  >
                    Reject
                  </button>
                </div>
              ) : (
                <div data-testid="rejection-form">
                  <label
                    htmlFor="rejection-reason"
                    style={{ display: "block", fontSize: "0.8125rem", fontWeight: 600, marginBottom: 4 }}
                  >
                    Rejection Reason <span style={{ color: "#b91c1c" }}>*</span>
                  </label>
                  <textarea
                    id="rejection-reason"
                    rows={3}
                    value={rejectionReason}
                    onChange={(e) => setRejectionReason(e.target.value)}
                    placeholder="Describe why this strategy is being rejected…"
                    style={{
                      width: "100%",
                      padding: "6px 8px",
                      borderRadius: 4,
                      border: "1px solid var(--color-border, #d1d5db)",
                      fontSize: "0.8125rem",
                      resize: "vertical",
                      boxSizing: "border-box",
                    }}
                    data-testid="rejection-reason-input"
                  />
                  <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                    <button
                      style={{
                        ...btnBase,
                        background: "#dc2626",
                        color: "#ffffff",
                        opacity: actionLoading || !rejectionReason.trim() ? 0.6 : 1,
                        cursor:
                          actionLoading || !rejectionReason.trim() ? "not-allowed" : "pointer",
                      }}
                      onClick={handleReject}
                      disabled={actionLoading || !rejectionReason.trim()}
                      data-testid="btn-confirm-reject"
                    >
                      {actionLoading ? "Rejecting…" : "Confirm Rejection"}
                    </button>
                    <button
                      style={{ ...btnBase, background: "var(--color-surface-subtle, #f3f4f6)", color: "var(--color-text)" }}
                      onClick={() => {
                        setShowRejectForm(false);
                        setRejectionReason("");
                      }}
                      disabled={actionLoading}
                      data-testid="btn-cancel-reject"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* New approval allowed after resolution */}
          {(approval.status === "approved" || approval.status === "rejected") && (
            <div style={{ marginTop: 16 }} data-testid="approval-new-request">
              <button
                style={{ ...btnBase, background: "#2563eb", color: "#ffffff" }}
                onClick={handleRequestApproval}
                disabled={actionLoading}
                data-testid="btn-request-new-approval"
              >
                {actionLoading ? "Requesting…" : "Request New Approval"}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Action-level error */}
      {actionError && (
        <p
          style={{ marginTop: 10, fontSize: "0.8125rem", color: "#b91c1c" }}
          data-testid="approval-action-error"
        >
          {actionError}
        </p>
      )}
    </section>
  );
}
