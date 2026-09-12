"use client";

import { useEffect, useState } from "react";
import { ApiError, projects } from "@/lib/api";
import type { LandAnalytics as Analytics, LandParcel } from "@/lib/api";
import { fractionFromPercent, money, percent, percentInput } from "@/lib/format";
import { Button, DraftBoundary, Field, FieldRow, FormActions, KeyValue, KeyValueGrid, Loading, Notice, SectionHeader, TableScroll } from "@/components/ui";

export function LandAnalytics({ projectId, parcel, canWrite, onChanged }: {
  projectId: string; parcel: LandParcel; canWrite: boolean; onChanged: () => Promise<void>;
}) {
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [year, setYear] = useState("");
  const [rate, setRate] = useState("");
  const [gdv, setGdv] = useState(parcel.expected_gdv_amount ?? "");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    void projects.landAnalytics(projectId, parcel.id).then(result => {
      if (!cancelled) { setData(result); setError(null); }
    }).catch(caught => {
      if (!cancelled) { setData(null); setError(caught instanceof ApiError ? caught.message : "Could not load land analytics."); }
    });
    return () => { cancelled = true; };
  }, [projectId, parcel, attempt]);
  const price = (value: string | null) => value === null ? "Unavailable" : money(value, parcel.base_currency_code);
  const changedGdv = gdv !== (parcel.expected_gdv_amount ?? "");
  const existingYear = data?.market_years.some(row => String(row.year) === year);
  return <DraftBoundary dirty={Boolean(year || rate || changedGdv)} busy={busy}>
    <div className="stack">
      <SectionHeader title="Analytics" />
      {error ? <Notice tone="error">{error}<Button onClick={() => setAttempt(value => value + 1)}>Retry analytics</Button></Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}
      {!data && !error ? <Loading label="Calculating land analytics…" /> : null}
      {data ? <>
        <KeyValueGrid columns={2}>
          <KeyValue label="Purchase price" value={price(parcel.purchase_price)} />
          <KeyValue label="Total acquisition cost" value={price(parcel.total_acquisition_cost)} />
          <KeyValue label="Total land area (sqm)" value={data.land_area_sqm} />
          <KeyValue label="Max buildable area (sqm)" value={data.max_buildable_area_sqm ?? "Record Maximum GFA in Planning"} />
          <KeyValue label="Land cost per sqm · purchase price / land area" value={price(data.purchase_cost_per_sqm)} />
          <KeyValue label="Land cost per buildable sqm · purchase price / max buildable area" value={price(data.purchase_cost_per_buildable_sqm)} />
          <KeyValue label="All-in cost per sqm · total acquisition cost / land area" value={price(data.acquisition_cost_per_sqm)} />
          <KeyValue label="All-in cost per buildable sqm · total acquisition cost / max buildable area" value={price(data.acquisition_cost_per_buildable_sqm)} />
          <KeyValue label="Purchase land cost as % of GDV" value={percent(data.purchase_cost_to_gdv_fraction)} />
          <KeyValue label="All-in acquisition cost as % of GDV" value={percent(data.acquisition_cost_to_gdv_fraction)} />
        </KeyValueGrid>
        <p className="footnote">GDV means expected Gross Development Value for this parcel, in {parcel.base_currency_code}. Missing or zero GDV/buildable area cannot produce a ratio. Buildable area uses recorded Maximum GFA, not an inferred planning permission. Sqft measurements are converted to sqm.</p>
        {canWrite ? <form onSubmit={async event => {
          event.preventDefault(); if (busy) return;
          setBusy(true); setError(null); setNotice(null);
          try {
            const saved = await projects.updateParcel(projectId, parcel.id, { expected_gdv_amount: gdv.trim() || null });
            setGdv(saved.expected_gdv_amount ?? "");
            await onChanged(); setNotice("Expected GDV saved.");
          } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save GDV."); }
          finally { setBusy(false); }
        }}>
          <Field label="Expected GDV for this parcel" optional hint={parcel.base_currency_code ?? undefined}>
            <input className="input" inputMode="decimal" disabled={busy} value={gdv} onChange={e => setGdv(e.target.value)} />
          </Field>
          <FormActions><Button type="submit" disabled={busy || !changedGdv}>Save GDV</Button></FormActions>
        </form> : <KeyValue label="Expected GDV" value={price(parcel.expected_gdv_amount)} />}
        <SectionHeader title="Annual market value estimates" />
        <p>Each entered year applies its change to the previous calculated value. The first starts from purchase price; acquisition fees do not appreciate. Years without an entry are not estimated. These are your assumptions, not a market valuation.</p>
        {data.market_years.length ? <TableScroll label="Annual land market estimates">
          <thead><tr><th scope="col">Year</th><th scope="col">Market change</th><th scope="col">Opening estimate</th><th scope="col">Closing estimate</th>{canWrite ? <th scope="col">Action</th> : null}</tr></thead>
          <tbody>{data.market_years.map(row => <tr key={row.year}>
            <th scope="row">{row.year}</th><td>{percent(row.change_rate_fraction)}</td>
            <td>{price(row.opening_value)}</td><td>{price(row.estimated_value)}{row.value_basis !== "calculated" ? <span className="cell-secondary">Missing purchase price or estimate outside supported range</span> : null}</td>
            {canWrite ? <td><Button small disabled={busy} data-leaves-editor onClick={() => { setYear(String(row.year)); setRate(percentInput(row.change_rate_fraction)); }}>Edit year</Button></td> : null}
          </tr>)}</tbody>
        </TableScroll> : <p className="subtle">No annual market assumptions recorded yet.</p>}
        {canWrite ? <form onSubmit={async event => {
          event.preventDefault(); if (busy) return;
          setBusy(true); setError(null); setNotice(null);
          try {
            setData(await projects.writeLandMarketYear(projectId, parcel.id, year, fractionFromPercent(rate)));
            setYear(""); setRate(""); setNotice("Annual assumption saved; later estimates recalculated.");
          } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save the market assumption."); }
          finally { setBusy(false); }
        }}>
          <FieldRow columns={2}>
            <Field label="Year"><input className="input" type="number" min={1900} max={2200} step={1} required disabled={busy} value={year} onChange={e => setYear(e.target.value)} /></Field>
            <Field label="Expected increase / decrease (%)" hint="Use a negative value for a decrease; −100% to +1,000%.">
              <input className="input" inputMode="decimal" required disabled={busy} value={rate} onChange={e => setRate(e.target.value)} />
            </Field>
          </FieldRow>
          {existingYear ? <p>This replaces the assumption for {year} and recalculates later recorded years.</p> : null}
          <FormActions><Button variant="primary" type="submit" disabled={busy || !year || !rate.trim()}>{existingYear ? "Update year" : "Add year"}</Button></FormActions>
        </form> : null}
      </> : null}
    </div>
  </DraftBoundary>;
}
