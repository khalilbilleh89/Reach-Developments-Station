/**
 * ReservationStatusBadge
 *
 * Renders a coloured pill badge for a reservation lifecycle status.
 *
 * Colour mapping:
 *   draft     → grey
 *   active    → blue
 *   expired   → orange
 *   cancelled → red
 *   converted → green
 */

import type { ReservationStatus } from "@/lib/units-types";
import { reservationStatusLabel } from "@/lib/units-types";

interface ReservationStatusBadgeProps {
  status: ReservationStatus | string;
  className?: string;
}

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700 border-gray-300",
  active: "bg-blue-100 text-blue-700 border-blue-300",
  expired: "bg-orange-100 text-orange-700 border-orange-300",
  cancelled: "bg-red-100 text-red-700 border-red-300",
  converted: "bg-green-100 text-green-700 border-green-300",
};

export function ReservationStatusBadge({
  status,
  className = "",
}: ReservationStatusBadgeProps) {
  const styles =
    STATUS_STYLES[status] ?? "bg-gray-100 text-gray-600 border-gray-300";

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${styles} ${className}`}
    >
      {reservationStatusLabel(status)}
    </span>
  );
}
