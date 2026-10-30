"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { type ScenarioFields } from "@/lib/api/marketing";
import { useCurrencyCode } from "@/lib/currency";
import { Button, DraftBoundary, Field, FieldRow, FormActions, FormSection, MoneyInput, Notice, RateInput, RecordPage } from "@/components/ui";

const rates = [
  ["vacancy_percent", "Vacancy / unoccupied time"], ["income_growth_percent", "Annual rent growth"],
  ["expense_growth_percent", "Annual expense growth"], ["appreciation_percent", "Annual capital appreciation"],
  ["exit_cap_percent", "Exit cap rate"], ["discount_percent", "Discount rate"],
  ["acquisition_cost_percent", "Acquisition costs / taxes (% of price)"], ["selling_cost_percent", "Selling costs (% of exit value)"],
] as const;

export function blankScenario(currencyId: string, mode: ScenarioFields["mode"]): ScenarioFields {
  return { unit_id: null, mode, currency_id: currencyId, area_basis: "net", annual_rent_per_sqm: "", annual_expense_per_sqm: "", vacancy_percent: "", income_growth_percent: "", expense_growth_percent: "", appreciation_percent: "", exit_cap_percent: "", discount_percent: "", acquisition_cost_percent: "", selling_cost_percent: "", setup_cost: "", rental_delay_months: 0, current_value: null, valuation_source: null, valuation_as_of: null, price_override: null, exit_method: "appreciation", source: "", as_of: "" };
}

export function RentalEditor({ initial, scopeLabel, onSave, onClose }: { initial: ScenarioFields; scopeLabel: string; onSave: (values: ScenarioFields) => Promise<void>; onClose: () => void }) {
  const [values, setValues] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const codeOf = useCurrencyCode();
  const code = codeOf(values.currency_id);
  const set = <K extends keyof ScenarioFields>(key: K, value: ScenarioFields[K]) => setValues({ ...values, [key]: value });
  return <RecordPage title={`${values.mode === "long_term" ? "Long-term" : "Short-term"} rental assumptions`} subtitle={scopeLabel} onClose={onClose}>
    <DraftBoundary dirty={JSON.stringify(values) !== JSON.stringify(initial)} busy={busy}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault(); if (busy) return; setBusy(true); setError(null);
        try { await onSave(values); } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save. Your entries have been kept."); } finally { setBusy(false); }
      }}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <Notice tone="info">Five-year, unlevered estimates in {code || "the recorded currency"}. Enter annual rent and operating costs per m² for both rental modes. For short-term lets, annual rent means full-occupancy annual potential; vacancy accounts for unoccupied nights. Enter 0 only where you intend a zero assumption.</Notice>
        <fieldset disabled={busy} className="marketing-fieldset stack">
          <FormSection title="Rental Basis"><FieldRow>
            <Field label="Area basis"><select className="input" value={values.area_basis} onChange={e => set("area_basis", e.target.value as ScenarioFields["area_basis"])}><option value="net">Net area (internal + balcony)</option><option value="gross">Gross area (includes recorded outdoor areas)</option></select></Field>
            <Field label="Months before rent starts" hint="Five years from the analysis start. Operating costs apply during the delay; enter 0 for an income-ready unit."><select className="input" value={values.rental_delay_months} onChange={e => set("rental_delay_months", Number(e.target.value))}>{Array.from({ length: 61 }, (_, months) => <option key={months} value={months}>{months} months</option>)}</select></Field>
            <Field label="Currency"><input className="input" readOnly value={code || "Currency unavailable"} /></Field>
            <Field label="Annual rent per m²"><MoneyInput required code={code} value={values.annual_rent_per_sqm} onChange={value => set("annual_rent_per_sqm", value)} /></Field>
            <Field label="Annual operating expenses per m²"><MoneyInput required code={code} value={values.annual_expense_per_sqm} onChange={value => set("annual_expense_per_sqm", value)} /></Field>
          </FieldRow></FormSection>
          <FormSection title="Growth, Costs and Valuation"><FieldRow>{rates.map(([key, label]) => <Field key={key} label={label}><RateInput required value={values[key]} onChange={value => set(key, value)} /></Field>)}</FieldRow>
            <Field label="Initial setup / furnishing cost"><MoneyInput required code={code} value={values.setup_cost} onChange={value => set("setup_cost", value)} /></Field>
            <Field label="Resale method"><select className="input" value={values.exit_method} onChange={e => set("exit_method", e.target.value as ScenarioFields["exit_method"])}><option value="appreciation">Compound capital appreciation</option><option value="cap_rate">Year-six NOI / exit cap rate</option></select></Field>
            {values.unit_id ? <Field label="Assumed purchase price" optional hint="Leave blank to use the unit's current asking price excluding tax. Enter acquisition taxes and fees above."><MoneyInput code={code} value={values.price_override ?? ""} onChange={value => set("price_override", value || null)} /></Field> : null}
          </FormSection>
          {values.unit_id ? <FormSection title="Current Unit Valuation"><Notice tone="info">Optional independently sourced value at the analysis start, in the same currency. If absent, appreciation uses purchase price as a proxy. Source entry does not certify a valuation.</Notice>
            <Field label="Current valuation" optional><MoneyInput code={code} value={values.current_value ?? ""} onChange={value => setValues({ ...values, current_value: value || null, ...(!value ? { valuation_source: null, valuation_as_of: null } : {}) })} /></Field>
            {values.current_value ? <><Field label="Valuation evidence / report reference"><input required className="input" maxLength={320} value={values.valuation_source ?? ""} onChange={e => set("valuation_source", e.target.value || null)} /></Field><Field label="Valuation as-at date"><input required className="input" type="date" value={values.valuation_as_of ?? ""} onChange={e => set("valuation_as_of", e.target.value || null)} /></Field></> : null}
          </FormSection> : null}
          <FormSection title="Assumption Source"><Field label="Source / evidence"><input className="input" required maxLength={320} value={values.source} onChange={e => set("source", e.target.value)} /></Field><Field label="As-at date"><input className="input" required type="date" value={values.as_of} onChange={e => set("as_of", e.target.value)} /></Field></FormSection>
        </fieldset>
        <FormActions><Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save assumptions"}</Button><Button variant="default" data-leaves-editor disabled={busy} onClick={onClose}>Cancel</Button></FormActions>
      </form>
    </DraftBoundary>
  </RecordPage>;
}
