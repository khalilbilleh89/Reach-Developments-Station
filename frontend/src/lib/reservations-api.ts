/**
 * reservations-api.ts — frontend API helpers for the unit reservation module.
 *
 * Covers the full reservation lifecycle:
 *   POST   /reservations                        → create
 *   GET    /reservations/{id}                   → get by ID
 *   PATCH  /reservations/{id}                   → update (notes, expires_at)
 *   POST   /reservations/{id}/cancel            → cancel
 *   POST   /reservations/{id}/convert           → convert to contract
 *   PATCH  /reservations/{id}/status            → generic state-machine transition
 *   GET    /projects/{projectId}/reservations   → list by project
 *
 * All helpers call the backend via apiFetch.  Errors propagate as ApiError.
 * Note: apiFetch BASE_URL already includes /api/v1; paths here must NOT
 * repeat the /api/v1 prefix.
 */

import { apiFetch } from "./api-client";
import type {
  Reservation,
  ReservationCreate,
  ReservationListResponse,
  ReservationStatus,
} from "./units-types";

// ---------------------------------------------------------------------------
// Create
// ---------------------------------------------------------------------------

/**
 * Create a new unit reservation.
 *
 * POST /api/v1/reservations
 *
 * Returns 404 if the unit does not exist.
 * Returns 409 if the unit already has an active reservation.
 */
export async function createReservation(
  data: ReservationCreate,
): Promise<Reservation> {
  return apiFetch<Reservation>("/reservations", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Read
// ---------------------------------------------------------------------------

/**
 * Fetch a single reservation by ID.
 *
 * GET /api/v1/reservations/{reservationId}
 *
 * Returns 404 if the reservation does not exist.
 */
export async function getReservation(reservationId: string): Promise<Reservation> {
  return apiFetch<Reservation>(`/reservations/${reservationId}`);
}

/**
 * List all reservations for a project.
 *
 * GET /api/v1/projects/{projectId}/reservations
 */
export async function listProjectReservations(
  projectId: string,
): Promise<ReservationListResponse> {
  return apiFetch<ReservationListResponse>(
    `/projects/${projectId}/reservations`,
  );
}

// ---------------------------------------------------------------------------
// Update
// ---------------------------------------------------------------------------

/**
 * Partially update an active reservation (notes, expires_at).
 *
 * PATCH /api/v1/reservations/{reservationId}
 *
 * Returns 404 if the reservation does not exist.
 * Returns 409 if the reservation is not in ACTIVE status.
 */
export async function updateReservation(
  reservationId: string,
  data: { notes?: string | null; expires_at?: string | null },
): Promise<Reservation> {
  return apiFetch<Reservation>(`/reservations/${reservationId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Status transitions
// ---------------------------------------------------------------------------

/**
 * Transition a reservation to a new lifecycle status via the state machine.
 *
 * PATCH /api/v1/reservations/{reservationId}/status
 *
 * Valid transitions:
 *   draft     → active, cancelled
 *   active    → expired, cancelled, converted
 *   expired   → cancelled
 *   cancelled → (terminal)
 *   converted → (terminal)
 *
 * Returns 422 if the transition is not permitted.
 * Returns 409 if activating would create a duplicate active reservation.
 * Returns 404 if the reservation does not exist.
 */
export async function transitionReservationStatus(
  reservationId: string,
  status: ReservationStatus,
): Promise<Reservation> {
  return apiFetch<Reservation>(`/reservations/${reservationId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

/**
 * Cancel a reservation.
 *
 * POST /api/v1/reservations/{reservationId}/cancel
 *
 * Returns 422 if the reservation is not in a cancellable state.
 * Returns 404 if the reservation does not exist.
 */
export async function cancelReservation(
  reservationId: string,
): Promise<Reservation> {
  return apiFetch<Reservation>(`/reservations/${reservationId}/cancel`, {
    method: "POST",
  });
}

/**
 * Convert a reservation to a formal sales contract.
 *
 * POST /api/v1/reservations/{reservationId}/convert
 *
 * Returns 422 if the reservation is not in ACTIVE status.
 * Returns 404 if the reservation does not exist.
 */
export async function convertReservation(
  reservationId: string,
): Promise<Reservation> {
  return apiFetch<Reservation>(`/reservations/${reservationId}/convert`, {
    method: "POST",
  });
}
