/**
 * format-utils.ts — shared formatting helpers for the dashboard.
 */

/**
 * Format a number as a compact AED currency string.
 *
 * Compacting is applied symmetrically for positive and negative values so
 * that e.g. both `1_500_000` and `-1_500_000` render consistently:
 *   1_500_000  → "AED 1.5M"
 *  -1_500_000  → "AED -1.5M"
 */
export function formatCurrency(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1_000_000) {
    return `AED ${sign}${(abs / 1_000_000).toFixed(1)}M`;
  }
  if (abs >= 1_000) {
    return `AED ${sign}${(abs / 1_000).toFixed(0)}K`;
  }
  return `AED ${value.toLocaleString()}`;
}
