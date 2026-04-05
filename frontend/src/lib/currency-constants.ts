/**
 * currency-constants.ts — frontend currency constants.
 *
 * The canonical currency configuration is served by the backend at
 * GET /api/v1/system/currencies.  The constants below mirror those
 * values for use in components that need synchronous access (e.g. type
 * guards, form validation) without an async fetch.
 *
 * These values must stay in sync with app/core/constants/currency.py.
 * When the backend SUPPORTED_CURRENCIES list changes, update this file
 * in the same PR.
 */

/** The platform default ISO 4217 currency code. */
export const DEFAULT_CURRENCY = "AED";

/** All ISO 4217 currency codes accepted by the platform. */
export const SUPPORTED_CURRENCIES = ["AED", "JOD", "USD", "EUR"] as const;

/** Union type of all supported currency codes. */
export type SupportedCurrency = (typeof SUPPORTED_CURRENCIES)[number];
