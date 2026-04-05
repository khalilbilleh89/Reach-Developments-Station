/**
 * currency-constants.ts — frontend currency constants.
 *
 * Mirrors the backend constants in app/core/constants/currency.py so that the
 * frontend has a single source of truth for currency identifiers.  Import
 * DEFAULT_CURRENCY instead of hardcoding the string "AED" anywhere in UI code.
 */

/** The platform default ISO 4217 currency code. */
export const DEFAULT_CURRENCY = "AED";

/** All ISO 4217 currency codes accepted by the platform. */
export const SUPPORTED_CURRENCIES = ["AED", "JOD", "USD"] as const;

/** Union type of all supported currency codes. */
export type SupportedCurrency = (typeof SUPPORTED_CURRENCIES)[number];
