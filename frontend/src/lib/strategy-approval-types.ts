/**
 * strategy-approval-types.ts — TypeScript types for the Strategy Approval
 * Workflow endpoints (PR-V7-08).
 *
 * Backend endpoints:
 *   POST /api/v1/projects/{id}/strategy-approval
 *   POST /api/v1/approvals/{id}/approve
 *   POST /api/v1/approvals/{id}/reject
 *   GET  /api/v1/projects/{id}/strategy-approval
 */

// ---------------------------------------------------------------------------
// Classification literals
// ---------------------------------------------------------------------------

export type ApprovalStatus = "pending" | "approved" | "rejected";

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

export interface StrategyApprovalCreateRequest {
  strategy_snapshot: Record<string, unknown>;
  execution_package_snapshot: Record<string, unknown>;
}

export interface ApproveStrategyRequest {
  notes?: string | null;
}

export interface RejectStrategyRequest {
  rejection_reason: string;
}

// ---------------------------------------------------------------------------
// Response type
// ---------------------------------------------------------------------------

export interface StrategyApprovalResponse {
  id: string;
  project_id: string;
  status: ApprovalStatus;
  strategy_snapshot: Record<string, unknown> | null;
  execution_package_snapshot: Record<string, unknown> | null;
  approved_by_user_id: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
  created_at: string;
  updated_at: string;
}
