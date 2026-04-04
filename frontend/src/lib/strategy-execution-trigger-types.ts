/**
 * strategy-execution-trigger-types.ts — TypeScript types for the Strategy
 * Execution Trigger module endpoints (PR-V7-09).
 *
 * Backend endpoints:
 *   POST /api/v1/projects/{id}/strategy-execution-trigger
 *   GET  /api/v1/projects/{id}/strategy-execution-trigger
 *   POST /api/v1/execution-triggers/{id}/start
 *   POST /api/v1/execution-triggers/{id}/complete
 *   POST /api/v1/execution-triggers/{id}/cancel
 *   GET  /api/v1/portfolio/execution-triggers
 */

// ---------------------------------------------------------------------------
// Classification literals
// ---------------------------------------------------------------------------

export type ExecutionTriggerStatus =
  | "triggered"
  | "in_progress"
  | "completed"
  | "cancelled";

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

export interface CancelExecutionTriggerRequest {
  cancellation_reason: string;
}

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

export interface StrategyExecutionTriggerResponse {
  id: string;
  project_id: string;
  approval_id: string | null;
  status: ExecutionTriggerStatus;
  triggered_by_user_id: string;
  triggered_at: string;
  completed_at: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  strategy_snapshot: Record<string, unknown> | null;
  execution_package_snapshot: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface PortfolioTriggerEntry {
  project_id: string;
  project_name: string;
  trigger: StrategyExecutionTriggerResponse;
}

export interface PortfolioProjectEntry {
  project_id: string;
  project_name: string;
}

export interface PortfolioExecutionTriggerSummaryResponse {
  triggered_count: number;
  in_progress_count: number;
  completed_count: number;
  cancelled_count: number;
  awaiting_trigger_count: number;
  active_triggers: PortfolioTriggerEntry[];
  awaiting_trigger_projects: PortfolioProjectEntry[];
}
