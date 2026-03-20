/**
 * cashflow-api.ts — API wrapper for the Cashflow Forecasting domain.
 *
 * All cashflow data fetching is centralised here.
 *
 * Paths are relative to the API prefix already embedded in BASE_URL
 * (e.g. /api/v1) — do NOT include /api/v1 here.
 *
 * Backend endpoints used:
 *
 * Project-scoped:
 *   GET  /cashflow/projects/{project_id}/forecasts         → list forecasts
 *   GET  /cashflow/projects/{project_id}/cashflow-summary  → aggregate summary
 *
 * Forecast detail:
 *   GET  /cashflow/forecasts/{forecast_id}                 → single forecast
 *   GET  /cashflow/forecasts/{forecast_id}/periods         → forecast periods
 */

import { apiFetch } from "./api-client";
import type {
  CashflowForecast,
  CashflowForecastList,
  CashflowForecastPeriod,
  CashflowSummary,
} from "./cashflow-types";

// ---------------------------------------------------------------------------
// Project-scoped views
// ---------------------------------------------------------------------------

/**
 * List all cashflow forecasts for a project.
 *
 * Backend endpoint: GET /cashflow/projects/{projectId}/forecasts
 */
export async function listProjectCashflowForecasts(
  projectId: string,
  params?: { skip?: number; limit?: number },
): Promise<CashflowForecastList> {
  const query = new URLSearchParams();
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiFetch<CashflowForecastList>(
    `/cashflow/projects/${encodeURIComponent(projectId)}/forecasts${qs ? `?${qs}` : ""}`,
  );
}

/**
 * Retrieve the project-level cashflow summary based on the latest forecast.
 *
 * Backend endpoint: GET /cashflow/projects/{projectId}/cashflow-summary
 */
export async function getProjectCashflowSummary(
  projectId: string,
): Promise<CashflowSummary> {
  return apiFetch<CashflowSummary>(
    `/cashflow/projects/${encodeURIComponent(projectId)}/cashflow-summary`,
  );
}

// ---------------------------------------------------------------------------
// Forecast detail
// ---------------------------------------------------------------------------

/**
 * Retrieve a single cashflow forecast by ID.
 *
 * Backend endpoint: GET /cashflow/forecasts/{forecastId}
 */
export async function getCashflowForecast(
  forecastId: string,
): Promise<CashflowForecast> {
  return apiFetch<CashflowForecast>(
    `/cashflow/forecasts/${encodeURIComponent(forecastId)}`,
  );
}

/**
 * List all time-bucket periods for a forecast, ordered by sequence.
 *
 * Backend endpoint: GET /cashflow/forecasts/{forecastId}/periods
 */
export async function listCashflowForecastPeriods(
  forecastId: string,
): Promise<CashflowForecastPeriod[]> {
  return apiFetch<CashflowForecastPeriod[]>(
    `/cashflow/forecasts/${encodeURIComponent(forecastId)}/periods`,
  );
}
