/**
 * ReservationTransitionButtons
 *
 * Renders action buttons for valid reservation lifecycle transitions.
 *
 * Allowed transitions (mirrors the backend state machine):
 *   draft     → Activate, Cancel
 *   active    → Cancel, Convert
 *   expired   → Cancel
 *   cancelled → (terminal — no actions)
 *   converted → (terminal — no actions)
 */

import type { ReservationStatus } from "@/lib/units-types";

interface TransitionButton {
  label: string;
  targetStatus: ReservationStatus;
  variant: "primary" | "danger" | "secondary";
}

const TRANSITIONS: Record<string, TransitionButton[]> = {
  draft: [
    { label: "Activate", targetStatus: "active", variant: "primary" },
    { label: "Cancel", targetStatus: "cancelled", variant: "danger" },
  ],
  active: [
    { label: "Cancel", targetStatus: "cancelled", variant: "danger" },
    { label: "Convert", targetStatus: "converted", variant: "primary" },
  ],
  expired: [
    { label: "Cancel", targetStatus: "cancelled", variant: "danger" },
  ],
  cancelled: [],
  converted: [],
};

const VARIANT_STYLES: Record<string, string> = {
  primary:
    "bg-blue-600 hover:bg-blue-700 text-white border-blue-600 disabled:opacity-50",
  danger:
    "bg-red-600 hover:bg-red-700 text-white border-red-600 disabled:opacity-50",
  secondary:
    "bg-white hover:bg-gray-50 text-gray-700 border-gray-300 disabled:opacity-50",
};

interface ReservationTransitionButtonsProps {
  reservationId: string;
  currentStatus: ReservationStatus | string;
  onTransition: (reservationId: string, newStatus: ReservationStatus) => void;
  loading?: boolean;
  className?: string;
}

export function ReservationTransitionButtons({
  reservationId,
  currentStatus,
  onTransition,
  loading = false,
  className = "",
}: ReservationTransitionButtonsProps) {
  const buttons = TRANSITIONS[currentStatus] ?? [];

  if (buttons.length === 0) {
    return null;
  }

  return (
    <div className={`flex gap-2 ${className}`}>
      {buttons.map((btn) => (
        <button
          key={btn.targetStatus}
          type="button"
          onClick={() => onTransition(reservationId, btn.targetStatus)}
          disabled={loading}
          className={`inline-flex items-center rounded border px-3 py-1.5 text-sm font-medium transition-colors ${VARIANT_STYLES[btn.variant]}`}
        >
          {btn.label}
        </button>
      ))}
    </div>
  );
}
