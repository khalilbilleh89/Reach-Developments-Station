/**
 * registry-types.ts — TypeScript types for the Registry/Conveyancing domain.
 *
 * These types mirror the Pydantic schemas defined in
 * app/modules/registry/schemas.py and the enumerations in
 * app/shared/enums/registration.py (the enum file uses the legacy name
 * "registration" while the router/module uses the canonical name "registry").
 *
 * CaseStatus values (from CaseStatus enum):
 *   "draft" | "in_progress" | "awaiting_documents" | "submitted"
 *   | "under_review" | "completed" | "cancelled"
 *
 * MilestoneStatus values (from MilestoneStatus enum):
 *   "pending" | "in_progress" | "completed" | "skipped"
 */

// ---------------------------------------------------------------------------
// Enum-like string literals
// ---------------------------------------------------------------------------

export type CaseStatus =
  | "draft"
  | "in_progress"
  | "awaiting_documents"
  | "submitted"
  | "under_review"
  | "completed"
  | "cancelled";

export type MilestoneStatus = "pending" | "in_progress" | "completed" | "skipped";

// ---------------------------------------------------------------------------
// Milestone
// ---------------------------------------------------------------------------

/** Mirrors RegistrationMilestoneResponse */
export interface RegistrationMilestone {
  id: string;
  registration_case_id: string;
  step_code: string;
  step_name: string;
  sequence: number;
  status: MilestoneStatus;
  due_date: string | null;
  completed_at: string | null;
  remarks: string | null;
  created_at: string;
  updated_at: string;
}

export interface RegistrationMilestoneUpdate {
  status?: MilestoneStatus;
  due_date?: string | null;
  completed_at?: string | null;
  remarks?: string | null;
}

// ---------------------------------------------------------------------------
// Document
// ---------------------------------------------------------------------------

/** Mirrors RegistrationDocumentResponse */
export interface RegistrationDocument {
  id: string;
  registration_case_id: string;
  document_type: string;
  is_required: boolean;
  is_received: boolean;
  received_at: string | null;
  reference_number: string | null;
  remarks: string | null;
  created_at: string;
  updated_at: string;
}

export interface RegistrationDocumentUpdate {
  is_received?: boolean;
  received_at?: string | null;
  reference_number?: string | null;
  remarks?: string | null;
}

// ---------------------------------------------------------------------------
// Registration Case
// ---------------------------------------------------------------------------

/** Mirrors RegistrationCaseCreate */
export interface RegistrationCaseCreate {
  project_id: string;
  unit_id: string;
  sale_contract_id: string;
  buyer_name: string;
  buyer_identifier?: string | null;
  jurisdiction?: string | null;
  opened_at?: string | null;
  notes?: string | null;
}

/** Mirrors RegistrationCaseUpdate */
export interface RegistrationCaseUpdate {
  status?: CaseStatus;
  buyer_identifier?: string | null;
  jurisdiction?: string | null;
  opened_at?: string | null;
  submitted_at?: string | null;
  completed_at?: string | null;
  notes?: string | null;
}

/** Mirrors RegistrationCaseResponse */
export interface RegistrationCase {
  id: string;
  project_id: string;
  unit_id: string;
  sale_contract_id: string;
  buyer_name: string;
  buyer_identifier: string | null;
  jurisdiction: string | null;
  status: CaseStatus;
  opened_at: string | null;
  submitted_at: string | null;
  completed_at: string | null;
  notes: string | null;
  milestones: RegistrationMilestone[];
  documents: RegistrationDocument[];
  created_at: string;
  updated_at: string;
}

/** Mirrors RegistrationCaseListResponse */
export interface RegistrationCaseListResponse {
  total: number;
  items: RegistrationCase[];
}

// ---------------------------------------------------------------------------
// Project registry summary
// ---------------------------------------------------------------------------

/** Mirrors RegistrationSummaryResponse */
export interface RegistrationSummaryResponse {
  project_id: string;
  total_sold_units: number;
  registration_cases_open: number;
  registration_cases_completed: number;
  sold_not_registered: number;
  /** Completion ratio as a value between 0 and 1. */
  registration_completion_ratio: number;
}
