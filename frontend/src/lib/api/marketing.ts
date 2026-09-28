import { get, post, put } from "./client";

export type Narrative = { paragraph: string; bullets: string[] };
export type Nearby = { name: string; duration_minutes: number | null; travel_mode: "drive" | "walk" | "transit" | "cycle"; note: string };
export type Bio = {
  country: Narrative; area: Narrative; project: Narrative; location: Narrative;
  nearby: Nearby[]; amenities: string[]; roi_min_percent: string | null;
  roi_max_percent: string | null; roi_basis: string; source: string; as_of: string | null;
};
export type Branding = {
  project_name: string; name_definition: string;
  colors: { name: string; hex: string; usage: string }[];
  fonts: { family: string; usage: string }[];
  source: string; as_of: string | null;
};
export type SavedContent<T> = { version: number; data: T };
export type ScenarioFields = {
  unit_id: string | null; mode: "long_term" | "short_term"; area_basis: "net" | "gross";
  currency_id: string; annual_rent_per_sqm: string; annual_expense_per_sqm: string;
  vacancy_percent: string; income_growth_percent: string; expense_growth_percent: string;
  appreciation_percent: string; exit_cap_percent: string; discount_percent: string;
  acquisition_cost_percent: string; selling_cost_percent: string; setup_cost: string;
  price_override: string | null; exit_method: "appreciation" | "cap_rate"; source: string; as_of: string;
};
export type Scenario = ScenarioFields & { id: string; version: number; unit_reference: string | null };
export type IndicatorFields = { name: string; geography: string; value: string; unit: string; period: string; as_of: string; source: string; commentary: string };
export type Indicator = IndicatorFields & { id: string; version: number };
export type ProjectionYear = { year: number; gross_revenue: string; vacancy_amount: string; effective_revenue: string; expenses: string; noi: string; property_value: string; cashflow: string };
export type Projection = {
  initial_investment: string; gross_yield_percent: string; net_yield_percent: string;
  monthly_potential_revenue: string; appreciation_value: string; capital_gain: string;
  cap_value: string; sale_proceeds: string; roi_percent: string; irr_percent: string | null;
  irr_reason: string | null; npv: string; simple_payback_years: string | null; rental_payback_years: string | null; total_payback_year: number | null;
  years: ProjectionYear[];
};
export type UnitScenario = { mode: string; scenario_id: string | null; source_scope: string | null; area_sqm: string | null; price: string | null; price_basis: string | null; currency_id: string | null; unavailable: string | null; projection: Projection | null };
export type UnitResult = { unit_id: string; reference: string; scenarios: UnitScenario[] };
export type UnitRegister = { total: number; units: UnitResult[] };
const root = (id: string) => `/projects/${id}/marketing`;
export const marketing = {
  bio: (id: string) => get<SavedContent<Bio>>(`${root(id)}/content/bio`),
  branding: (id: string) => get<SavedContent<Branding>>(`${root(id)}/content/branding`),
  saveContent: (id: string, kind: "bio" | "branding", data: Bio | Branding, version: number) => put<SavedContent<Bio | Branding>>(`${root(id)}/content/${kind}`, { data, expected_version: version }),
  scenarios: (id: string) => get<Scenario[]>(`${root(id)}/scenarios`),
  saveScenario: (id: string, data: ScenarioFields, row?: Scenario) => row
    ? put<Scenario>(`${root(id)}/scenarios/${row.id}`, { ...data, expected_version: row.version })
    : post<Scenario>(`${root(id)}/scenarios`, { ...data, expected_version: 0 }),
  indicators: (id: string) => get<Indicator[]>(`${root(id)}/indicators`),
  saveIndicator: (id: string, data: IndicatorFields, row?: Indicator) => row
    ? put<Indicator>(`${root(id)}/indicators/${row.id}`, { ...data, expected_version: row.version })
    : post<Indicator>(`${root(id)}/indicators`, { ...data, expected_version: 0 }),
  remove: (id: string, path: string, version: number, reason: string) => post<void>(`${root(id)}/${path}/delete`, { expected_version: version, reason }),
  units: (id: string, search: string, offset: number) => get<UnitRegister>(`${root(id)}/units?${new URLSearchParams({ search, offset: String(offset), limit: "25" })}`),
};
