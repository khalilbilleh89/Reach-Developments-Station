/**
 * format-utils.ts — shared formatting helpers for the dashboard.
 */

/** Format a number as a compact AED currency string (e.g. 1 500 000 → AED 1.5M). */
export function formatCurrency(value: number): string {
  if (value >= 1_000_000) {
    return `AED ${(value / 1_000_000).toFixed(1)}M`;
  }
  if (value >= 1_000) {
    return `AED ${(value / 1_000).toFixed(0)}K`;
  }
  return `AED ${value.toLocaleString()}`;
}
