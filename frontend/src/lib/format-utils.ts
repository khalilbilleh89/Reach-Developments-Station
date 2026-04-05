/**
 * format-utils.ts — shared formatting helpers for the dashboard.
 */

import { DEFAULT_CURRENCY } from "./currency-constants";

/**
 * Format a number as a precise currency string (no K/M compacting).
 *
 * Unlike `formatCurrency`, this formatter never rounds values to K or M
 * abbreviations. Use for per-sqm unit economics and other unit-level amounts
 * where compacting would distort the financial meaning.
 *
 * Pass the explicit ISO 4217 `currency` code whenever it is available from
 * the data.  The `currency` parameter defaults to `DEFAULT_CURRENCY` only as
 * a fallback for call-sites that do not yet receive denomination from the API.
 *
 * Examples (AED):
 *   3_000   → "AED 3,000"
 *   800     → "AED 800"
 *   2_040   → "AED 2,040"
 *  -1_500   → "AED -1,500"
 *
 * Examples (non-AED):
 *   formatCurrencyPrecise(3_000, "USD")  → "$3,000"
 *   formatCurrencyPrecise(3_000, "JOD")  → "JD3,000"
 */
export function formatCurrencyPrecise(
  value: number,
  currency: string = DEFAULT_CURRENCY,
): string {
  if (currency === DEFAULT_CURRENCY) {
    const sign = value < 0 ? "-" : "";
    const formatted = Math.abs(value).toLocaleString("en-US", {
      maximumFractionDigits: 0,
    });
    return `${DEFAULT_CURRENCY} ${sign}${formatted}`;
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

/**
 * Format a number as a compact currency string.
 *
 * Pass the explicit ISO 4217 `currency` code whenever it is available from
 * the data.  The `currency` parameter defaults to `DEFAULT_CURRENCY` only as
 * a fallback for call-sites that do not yet receive denomination from the API.
 *
 * Compacting is applied symmetrically for positive and negative values so
 * that e.g. both `1_500_000` and `-1_500_000` render consistently:
 *
 * AED examples:
 *   1_500_000  → "AED 1.5M"
 *  -1_500_000  → "AED -1.5M"
 *
 * Non-AED delegates to `formatAmount` for locale-correct symbol placement.
 */
export function formatCurrency(
  value: number,
  currency: string = DEFAULT_CURRENCY,
): string {
  if (currency !== DEFAULT_CURRENCY) {
    return formatAmount(value, currency);
  }
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1_000_000) {
    return `${DEFAULT_CURRENCY} ${sign}${(abs / 1_000_000).toFixed(1)}M`;
  }
  if (abs >= 1_000) {
    return `${DEFAULT_CURRENCY} ${sign}${(abs / 1_000).toFixed(0)}K`;
  }
  return `${DEFAULT_CURRENCY} ${value.toLocaleString()}`;
}

/**
 * Format a number with an explicit currency code.
 *
 * For AED uses the compact abbreviated format from `formatCurrency`.
 * For any other currency code delegates to `Intl.NumberFormat` so that
 * the symbol, sign and decimal positions are all locale-correct.
 *
 * This is the preferred formatting helper whenever a currency code is
 * available from the data — prefer `formatAmount(value, item.currency)`
 * over `formatCurrency(value)` at every call-site that has denomination.
 *
 * Examples:
 *   formatAmount(525000, "AED")  → "AED 525K"
 *   formatAmount(525000, "USD")  → "$525,000"
 *   formatAmount(-5000, "EUR")   → "-€5,000"
 */
export function formatAmount(value: number, currency: string): string {
  if (currency === DEFAULT_CURRENCY) {
    return formatCurrency(value, DEFAULT_CURRENCY);
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

/**
 * Format a grouped currency map (Record<currency, amount>) as a
 * human-readable string.
 *
 * Use this helper when the backend returns portfolio-wide totals grouped by
 * currency instead of a single scalar.  Each currency bucket is formatted
 * with `formatAmount` and the results are joined with " / ", so non-AED
 * values use locale-correct currency formatting rather than compact K/M
 * abbreviations.
 *
 * Example:
 *   formatCurrencyMap({ AED: 5_000_000, USD: 1_200_000 })
 *   → "AED 5.0M / $1,200,000"
 *
 * Returns "—" when the map is empty.
 */
export function formatCurrencyMap(
  map: Record<string, number>,
  opts: { compact?: boolean } = {},
): string {
  const entries = Object.entries(map).filter(([, v]) => v !== 0);
  if (entries.length === 0) return "—";
  return entries
    .map(([currency, value]) =>
      opts.compact === false
        ? formatCurrencyPrecise(value, currency)
        : formatAmount(value, currency),
    )
    .join(" / ");
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

  if (currency === DEFAULT_CURRENCY) {
    // absFormatted = "AED 25K" — insert sign after "AED "
    return absFormatted.replace(`${DEFAULT_CURRENCY} `, `${DEFAULT_CURRENCY} ${sign}`);
  }
  // For Intl-formatted strings (e.g. "$25,000"), prepend the sign
  return `${sign}${absFormatted}`;
}
