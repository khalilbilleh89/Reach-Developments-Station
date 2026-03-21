/**
 * contracts-api.ts — frontend API helpers for the sales contract lifecycle.
 *
 * Exposes helpers for these contract-related endpoints:
 *   POST  /sales/contracts                            → create
 *   GET   /sales/contracts/{id}                       → get by ID
 *   GET   /sales/units/{unitId}/contracts             → list by unit (dedicated endpoint)
 *   POST  /sales/contracts/{id}/activate              → activate
 *   POST  /sales/contracts/{id}/cancel                → cancel
 *   POST  /sales/reservations/{id}/convert-to-contract → convert reservation to contract
 *
 * All helpers call the backend via apiFetch.  Errors propagate as ApiError.
 * Note: apiFetch BASE_URL already includes /api/v1; paths here must NOT
 * repeat the /api/v1 prefix.
 */

import { apiFetch } from "./api-client";
import type { ContractStatus } from "./sales-types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SalesContract {
  id: string;
  unit_id: string;
  buyer_id: string;
  reservation_id: string | null;
  contract_number: string;
  contract_date: string;
  contract_price: number;
  status: ContractStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface SalesContractCreate {
  unit_id: string;
  buyer_id: string;
  reservation_id?: string | null;
  contract_number: string;
  contract_date: string;
  contract_price: number;
  notes?: string | null;
}

export interface SalesContractUpdate {
  contract_date?: string | null;
  contract_price?: number | null;
  notes?: string | null;
}

export interface SalesContractListResponse {
  total: number;
  items: SalesContract[];
}

// ---------------------------------------------------------------------------
// Create
// ---------------------------------------------------------------------------

/**
 * Create a new sales contract.
 *
 * POST /api/v1/sales/contracts
 *
 * Returns 404 if the unit or buyer does not exist.
 * Returns 409 if the unit already has an open (draft or active) contract,
 *   or if the contract_number is already in use.
 * Returns 409 if reservation_id is supplied but the reservation is not active.
 */
export async function createContract(
  data: SalesContractCreate,
): Promise<SalesContract> {
  return apiFetch<SalesContract>("/sales/contracts", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Read
// ---------------------------------------------------------------------------

/**
 * Fetch a single contract by ID.
 *
 * GET /api/v1/sales/contracts/{contractId}
 *
 * Returns 404 if the contract does not exist.
 */
export async function getContract(contractId: string): Promise<SalesContract> {
  return apiFetch<SalesContract>(`/sales/contracts/${contractId}`);
}

/**
 * List all contracts for a specific unit.
 *
 * GET /api/v1/sales/units/{unitId}/contracts
 */
export async function getUnitContracts(
  unitId: string,
): Promise<SalesContractListResponse> {
  return apiFetch<SalesContractListResponse>(
    `/sales/units/${unitId}/contracts`,
  );
}

// ---------------------------------------------------------------------------
// Lifecycle transitions
// ---------------------------------------------------------------------------

/**
 * Activate a draft contract.
 *
 * POST /api/v1/sales/contracts/{contractId}/activate
 *
 * Rules enforced by the backend:
 *   - Contract must be in DRAFT status.
 *   - Contract must have a linked reservation.
 *   - The linked reservation must be in CONVERTED status.
 *
 * Returns 404 if the contract does not exist.
 * Returns 422 if the contract has no reservation linkage or transition is invalid.
 * Returns 409 if the reservation is not in CONVERTED status.
 */
export async function activateContract(
  contractId: string,
): Promise<SalesContract> {
  return apiFetch<SalesContract>(`/sales/contracts/${contractId}/activate`, {
    method: "POST",
  });
}

/**
 * Cancel a draft or active contract.
 *
 * POST /api/v1/sales/contracts/{contractId}/cancel
 *
 * Returns 404 if the contract does not exist.
 * Returns 422 if the contract is not in a cancellable state
 *   (i.e., already cancelled or completed).
 */
export async function cancelContract(
  contractId: string,
): Promise<SalesContract> {
  return apiFetch<SalesContract>(`/sales/contracts/${contractId}/cancel`, {
    method: "POST",
  });
}

/**
 * Convert an active reservation directly to a sales contract.
 *
 * POST /api/v1/sales/reservations/{reservationId}/convert-to-contract
 *
 * Returns 404 if the reservation does not exist.
 * Returns 409 if the reservation is not active.
 * Returns 409 if the unit already has an open contract.
 */
export async function convertReservationToContract(
  reservationId: string,
  data: SalesContractCreate,
): Promise<SalesContract> {
  return apiFetch<SalesContract>(
    `/sales/reservations/${reservationId}/convert-to-contract`,
    {
      method: "POST",
      body: JSON.stringify(data),
    },
  );
}
