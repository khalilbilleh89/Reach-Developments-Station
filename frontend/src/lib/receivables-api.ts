/**
 * receivables-api.ts — frontend API helpers for the receivables module.
 *
 * All helpers call the backend via apiFetch. Errors propagate to the caller
 * as ApiError instances (see api-client.ts).
 *
 * Note: apiFetch BASE_URL already includes /api/v1; paths here must NOT
 * repeat the /api/v1 prefix.
 */

import { apiFetch } from "./api-client";
import type {
  GenerateReceivablesResponse,
  Receivable,
  ReceivableListResponse,
  ReceivablePaymentUpdate,
} from "./receivables-types";

/**
 * Generate one receivable per payment installment for a contract.
 *
 * POST /api/v1/contracts/{contractId}/receivables/generate
 *
 * Raises 404 if the contract has no payment plan.
 * Raises 409 if receivables already exist for the contract.
 */
export async function generateReceivables(
  contractId: string,
): Promise<GenerateReceivablesResponse> {
  return apiFetch<GenerateReceivablesResponse>(
    `/contracts/${contractId}/receivables/generate`,
    { method: "POST" },
  );
}

/**
 * List all receivables for a contract.
 *
 * GET /api/v1/contracts/{contractId}/receivables
 */
export async function listContractReceivables(
  contractId: string,
): Promise<ReceivableListResponse> {
  return apiFetch<ReceivableListResponse>(
    `/contracts/${contractId}/receivables`,
  );
}

/**
 * List all receivables for a project (across all contracts).
 *
 * GET /api/v1/projects/{projectId}/receivables
 */
export async function listProjectReceivables(
  projectId: string,
): Promise<ReceivableListResponse> {
  return apiFetch<ReceivableListResponse>(
    `/projects/${projectId}/receivables`,
  );
}

/**
 * Get a single receivable by ID.
 *
 * GET /api/v1/receivables/{receivableId}
 */
export async function getReceivable(receivableId: string): Promise<Receivable> {
  return apiFetch<Receivable>(`/receivables/${receivableId}`);
}

/**
 * Record a manual payment update for a receivable.
 *
 * PATCH /api/v1/receivables/{receivableId}
 *
 * amount_paid is the new cumulative total (not an incremental delta).
 * Balance and status are recalculated by the backend.
 */
export async function updateReceivable(
  receivableId: string,
  payload: ReceivablePaymentUpdate,
): Promise<Receivable> {
  return apiFetch<Receivable>(`/receivables/${receivableId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}
