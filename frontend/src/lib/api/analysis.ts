import { get } from "./client";

export type Availability = { availability: "available" | "partial" | "unavailable"; reason: string | null; source_basis: string; sample_size: number };
export type Ratio = Availability & { numerator: number | null; denominator: number | null; percentage: string | null };
export type Money = { currency: string; amount: string };
export type Context = { project_id: string; as_of: string; period_from: string; period_to: string; filters: Record<string, string | null>; currency: string; source_basis: string; snapshot_as_of: string };
export type Demand = Availability & { label: string; inventory_count: number; sales_count: number; demand_share: Ratio; penetration: Ratio };
export type Ranking = Availability & { source_key: string | null; label: string; sales_count: number; contracted_value: Money[]; share: Ratio };
export type Fundamental = {
  context: Context;
  position: Availability & { total_units: number; eligible_units: number; available_units: number; committed_units: number; active_sold_units: number; remaining_units: number; commercial: Record<string, number>; legal: Record<string, number>; delivery: Record<string, number>; penetration: Ratio };
  monthly_sales: { month: string; activations: number; cancellations: number; net_absorption: number; contracted_value: Money[] }[];
  sales_basis: Availability;
  branches: Ranking[]; salespeople: Ranking[]; ranking_basis: Availability;
  forecast: Availability & { window_from: string; window_to: string; observed_months: number; monthly_net_absorption: number[]; remaining_units: number | null; average_monthly_absorption: string | null; estimated_months_to_sell: string | null };
  property_types: Demand[]; views: Demand[]; view_basis: Availability;
  observed_premiums: (Availability & { property_type: string; view: string; baseline: string; currency: string | null; area_unit: string | null; baseline_sample: number; view_price_per_gross_area: string | null; baseline_price_per_gross_area: string | null; percentage: string | null })[];
};
export type Financial = { context: Context; basis: Availability; cash_scope: string; monthly: { month: string; currency: string; new_sales_count: number; contracted_sales_value: string; customer_cash_received: string; project_cash_outflow: string; customer_refunds: string; financing_inflow: string; financing_outflow: string; net_actual_cash_movement: string }[] };
export type Technical = { context: Context; basis: Availability; product_types: Record<string, number>; areas: (Availability & { component: string; unit_of_measure: string; minimum: string; maximum: string; average: string })[]; area_coverage: Availability; features: Record<string, number>; feature_coverage: Ratio; attachments: Record<string, number>; permits: Record<string, number>; permit_basis: Availability; consultant: Record<string, string | number | null>; consultant_basis: Availability; construction_stages: { name: string; completed_units: number; denominator: number }[]; construction_basis: Availability };
export type AreaMeasure = { value: string | null; measured_count: number; expected_count: number; reason: string | null; formula: string };
export type Feasibility = { context: Context; apartments: number; other_units: number; totals: Record<string, AreaMeasure>; averages: Record<string, AreaMeasure>; groups: {unit_type: string; bedrooms: number | null; apartments: number; areas: Record<string, AreaMeasure>}[]; efficiencies: {label:string;percentage:string|null;numerator:string|null;denominator:string|null;formula:string;reason:string|null}[]; notes:string[] };
export type Section = "fundamental" | "financial" | "technical" | "feasibility";
export const projectAnalysis = {
  feasibility: (id: string, query: string) => get<Feasibility>(`/projects/${id}/analysis/feasibility${query}`),
  fundamental: (id: string, query: string) => get<Fundamental>(`/projects/${id}/analysis/fundamental${query}`),
  financial: (id: string, query: string) => get<Financial>(`/projects/${id}/analysis/financial${query}`),
  technical: (id: string, query: string) => get<Technical>(`/projects/${id}/analysis/technical${query}`),
};
