/**
 * format-utils.ts — shared formatting helpers for the dashboard.
 */

/**
 * Format a number as a precise AED currency string (no K/M compacting).
 *
 * Unlike `formatCurrency`, this formatter never rounds values to K or M
 * abbreviations. Use for per-sqm unit economics and other unit-level amounts
 * where compacting would distort the financial meaning.
 *
 *   3_000   → "AED 3,000"
 *   800     → "AED 800"
 *   2_040   → "AED 2,040"
 *  -1_500   → "AED -1,500"
 */
export function formatCurrencyPrecise(value: number): string {
  const sign = value < 0 ? "-" : "";
  const formatted = Math.abs(value).toLocaleString("en-US", {
    maximumFractionDigits: 0,
  });
  return `AED ${sign}${formatted}`;
}

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

/**
 * Format a number with an explicit currency code.
 *
 * For AED uses the compact abbreviated format from `formatCurrency`.
 * For any other currency code delegates to `Intl.NumberFormat` so that
 * the symbol, sign and decimal positions are all locale-correct.
 *
 * Examples:
 *   formatAmount(525000, "AED")  → "AED 525K"
 *   formatAmount(525000, "USD")  → "$525,000"
 *   formatAmount(-5000, "EUR")   → "-€5,000"
 */
export function formatAmount(value: number, currency: string): string {
  if (currency === "AED") {
    return formatCurrency(value);
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

/**
 * Format a price adjustment (positive or negative delta) with a consistent
 * explicit sign, e.g. `AED +25K` / `AED -5K` / `AED 0`.
 *
 * Sign placement mirrors the currency symbol: the `+` or `-` always
 * appears immediately after the currency prefix so that positive and
 * negative values format symmetrically.
 */
export function formatAdjustment(value: number, currency: string): string {
  if (value === 0) {
    return formatAmount(0, currency);
  }
  const absFormatted = formatAmount(Math.abs(value), currency);
  const sign = value > 0 ? "+" : "-";

  if (currency === "AED") {
    // absFormatted = "AED 25K" — insert sign after "AED "
    return absFormatted.replace("AED ", `AED ${sign}`);
  }
  // For Intl-formatted strings (e.g. "$25,000"), prepend the sign
  return `${sign}${absFormatted}`;
}
