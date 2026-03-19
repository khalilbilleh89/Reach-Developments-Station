/**
 * construction-types.ts — TypeScript types for the Construction domain.
 *
 * Mirrors the backend ConstructionScopeResponse, ConstructionMilestoneResponse,
 * EngineeringItemResponse, and ConstructionCostItemResponse schemas.
 */

export type ConstructionStatus = "planned" | "in_progress" | "on_hold" | "completed";

export type MilestoneStatus = "pending" | "in_progress" | "completed" | "delayed";

export type EngineeringStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "delayed"
  | "on_hold";

export type CostCategory =
  | "materials"
  | "labor"
  | "equipment"
  | "subcontractor"
  | "consultant"
  | "permits"
  | "utilities"
  | "site_overheads"
  | "other";

export type CostType = "budget" | "commitment" | "actual";

export interface ConstructionScope {
  id: string;
  project_id: string | null;
  phase_id: string | null;
  building_id: string | null;
  name: string;
  description: string | null;
  status: ConstructionStatus;
  start_date: string | null;
  target_end_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConstructionScopeListResponse {
  items: ConstructionScope[];
  total: number;
}

export interface ConstructionScopeCreate {
  project_id?: string | null;
  phase_id?: string | null;
  building_id?: string | null;
  name: string;
  description?: string | null;
  status?: ConstructionStatus;
  start_date?: string | null;
  target_end_date?: string | null;
}

export interface ConstructionScopeUpdate {
  name?: string;
  description?: string | null;
  status?: ConstructionStatus;
  start_date?: string | null;
  target_end_date?: string | null;
}

export interface ConstructionMilestone {
  id: string;
  scope_id: string;
  name: string;
  description: string | null;
  sequence: number;
  status: MilestoneStatus;
  target_date: string | null;
  completion_date: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConstructionMilestoneListResponse {
  items: ConstructionMilestone[];
  total: number;
}

export interface ConstructionMilestoneCreate {
  scope_id: string;
  name: string;
  description?: string | null;
  sequence: number;
  status?: MilestoneStatus;
  target_date?: string | null;
  completion_date?: string | null;
  notes?: string | null;
}

export interface ConstructionMilestoneUpdate {
  name?: string;
  description?: string | null;
  sequence?: number;
  status?: MilestoneStatus;
  target_date?: string | null;
  completion_date?: string | null;
  notes?: string | null;
}

// ── Engineering items ────────────────────────────────────────────────────────

export interface ConstructionEngineeringItem {
  id: string;
  scope_id: string;
  title: string;
  description: string | null;
  status: EngineeringStatus;
  item_type: string | null;
  consultant_name: string | null;
  consultant_cost: string | null;
  target_date: string | null;
  completion_date: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface EngineeringItemListResponse {
  items: ConstructionEngineeringItem[];
  total: number;
}

export interface EngineeringItemCreate {
  title: string;
  description?: string | null;
  status?: EngineeringStatus;
  item_type?: string | null;
  consultant_name?: string | null;
  consultant_cost?: string | null;
  target_date?: string | null;
  completion_date?: string | null;
  notes?: string | null;
}

export interface EngineeringItemUpdate {
  title?: string;
  description?: string | null;
  status?: EngineeringStatus;
  item_type?: string | null;
  consultant_name?: string | null;
  consultant_cost?: string | null;
  target_date?: string | null;
  completion_date?: string | null;
  notes?: string | null;
}

// ── Cost items ───────────────────────────────────────────────────────────────

export interface ConstructionCostItem {
  id: string;
  scope_id: string;
  cost_category: CostCategory;
  cost_type: CostType;
  description: string;
  vendor_name: string | null;
  budget_amount: string;
  committed_amount: string;
  actual_amount: string;
  variance_to_budget: string;
  variance_to_commitment: string;
  currency: string;
  cost_date: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConstructionCostItemListResponse {
  items: ConstructionCostItem[];
  total: number;
}

export interface ConstructionCostItemCreate {
  cost_category: CostCategory;
  cost_type: CostType;
  description: string;
  vendor_name?: string | null;
  budget_amount?: number;
  committed_amount?: number;
  actual_amount?: number;
  currency?: string;
  cost_date?: string | null;
  notes?: string | null;
}

export interface ConstructionCostItemUpdate {
  cost_category?: CostCategory;
  cost_type?: CostType;
  description?: string;
  vendor_name?: string | null;
  budget_amount?: number;
  committed_amount?: number;
  actual_amount?: number;
  currency?: string;
  cost_date?: string | null;
  notes?: string | null;
}

export interface CategoryCostBreakdown {
  budget: string;
  committed: string;
  actual: string;
  variance_to_budget: string;
  variance_to_commitment: string;
}

export interface ConstructionCostSummary {
  scope_id: string;
  total_budget: string;
  total_committed: string;
  total_actual: string;
  total_variance_to_budget: string;
  total_variance_to_commitment: string;
  by_category: Record<string, CategoryCostBreakdown>;
}
