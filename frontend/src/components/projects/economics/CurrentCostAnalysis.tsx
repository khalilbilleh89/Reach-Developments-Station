"use client";

import { useState } from "react";
import { inventory, unitEconomics } from "@/lib/api";
import type { AreaType, CurrentCostAnalysis as Analysis, CurrentCostSettings, CurrentCostFigures, CurrentUnitCost } from "@/lib/api";
import { useAnswer } from "@/lib/answer";
import { ECONOMICS_READERS, hasAnyRole } from "@/lib/roles";
import { businessDate, fractionFromPercent, money, percent, percentInput } from "@/lib/format";
import { Button, ButtonRow, Card, DraftBoundary, EmptyState, Field, FieldRow, KeyValue, KeyValueGrid, Loading, MoneyInput, Notice, RateInput, RecordPage, TableScroll, Tabs } from "@/components/ui";
import { DeleteRecordButton } from "../DeleteRecordButton";

const COST_LINES = [
  ["hard_cost", "Construction / hard cost"], ["land_cost", "Land and acquisition charges"],
  ["soft_cost", "Soft costs"], ["additional_cost", "Additional shared costs"],
  ["finance_cost", "Shared finance costs"], ["direct_cost", "Recorded unit costs"],
  ["seller_cost", "Seller-borne deal costs"], ["commission_cost", "Commissions"],
  ["total_cost", "Total unit cost"], ["revenue", "Sale / asking price excluding VAT"],
  ["profit_before_tax", "Profit before tax"], ["tax_amount", "Estimated profit tax"],
  ["net_profit", "Estimated net profit"],
] as const;

/** A single server answer shared by Construction and Unit Economics. */
export function CurrentCostAnalysis({ projectId, roles }: { projectId: string; roles: Set<string> }) {
  const answer = useAnswer(hasAnyRole(roles, ECONOMICS_READERS), () => unitEconomics.currentCosts(projectId), [projectId]);
  if (answer.status === "off" || answer.status === "denied") return <EmptyState title="Current cost analysis unavailable" hint="This analysis requires an economics reader role and access to the whole project." />;
  if (answer.status === "loading") return <Loading label="Calculating current unit costs" shape="metrics" />;
  if (answer.status === "failed") return <><Notice tone="error">{answer.message}</Notice><Button onClick={answer.retry}>Retry current cost analysis</Button></>;
  return <AnalysisView key={projectId} report={answer.data} projectId={projectId} canWrite={hasAnyRole(roles, new Set(["finance"]))} onRefresh={answer.retry} />;
}

export function AnalysisView({ report, projectId, canWrite, onRefresh }: { report: Analysis; projectId: string; canWrite: boolean; onRefresh: () => void }) {
  const [level, setLevel] = useState("units");
  const [selected, setSelected] = useState<CurrentUnitCost | null>(null);
  const [editing, setEditing] = useState(false);
  const [building, setBuilding] = useState("");
  const code = report.currency_code || null;
  if (editing) return <SettingsEditor projectId={projectId} settings={report.settings} code={code} onClose={() => setEditing(false)} onSaved={() => { setEditing(false); onRefresh(); }} />;
  if (selected) return <RecordPage title={`Cost of ${selected.unit_reference}`} onClose={() => setSelected(null)}>
    <div className="stack">
      <p>{selected.building_name} / {selected.floor_name} · {selected.gross_area_sqm ?? "Area unavailable"} sqm · {selected.revenue_basis === "sold" ? "Signed sale" : "Unsold forecast"}</p>
      <KeyValueGrid><KeyValue label="Construction cost / sqm" value={money(selected.hard_cost_per_sqm, code)} /><KeyValue label="Total cost / sqm" value={money(selected.total_cost_per_sqm, code)} /></KeyValueGrid>
      <Card title="Unit cost and profit breakdown"><KeyValueGrid>{COST_LINES.map(([key, label]) => <KeyValue key={key} label={label} value={money(selected[key], code)} />)}</KeyValueGrid></Card>
      <p>Commission basis: {selected.commission_basis}. Shared costs follow gross built area. Profit tax applies to positive profit only, with no assumed credit for losses.</p>
      {[...report.issues, ...selected.issues].map((issue, i) => <Notice key={i} tone="warning">{issue}</Notice>)}
    </div>
  </RecordPage>;
  const rows: { key: string; label: string; figures: CurrentCostFigures; unit?: CurrentUnitCost; basis: string }[] = level === "units"
    ? report.units.filter(r => !building || r.building_id === building).map(r => ({ key: r.unit_id, label: r.unit_reference, figures: r, unit: r, basis: r.revenue_basis === "sold" ? "Signed sale" : r.revenue_basis === "asking_price" ? "Asking-price forecast" : "Revenue unavailable" }))
    : (level === "floors" ? report.floors : report.buildings).filter(r => !building || r.building_id === building).map(r => ({ key: r.id, label: r.label, figures: r, basis: `${r.sold_count} sold / ${r.unit_count} units` }));
  return <div className="stack">
    <Card title="Current unit costs and profit" description={`As at ${businessDate(report.as_of_date)} · ${code ?? "Currency unavailable"} · costs and revenue excluding VAT.`} actions={<ButtonRow><Button onClick={onRefresh}>Refresh analysis</Button>{canWrite ? <Button onClick={() => setEditing(true)}>{report.settings ? "Edit cost inputs & tax" : "Set cost inputs & tax"}</Button> : null}</ButtonRow>}>
      <KeyValueGrid>
        <KeyValue label="Construction cost / sqm" value={money(report.project.hard_cost_per_sqm, code)} />
        <KeyValue label="Total project cost" value={money(report.project.total_cost, code)} />
        <KeyValue label="Signed sale revenue" value={money(report.project.sold_revenue, code)} />
        <KeyValue label="Unsold asking-price forecast" value={money(report.project.forecast_revenue, code)} />
        <KeyValue label="Profit before tax · sold + forecast" value={money(report.project.profit_before_tax, code)} />
        <KeyValue label="Estimated net profit · sold + forecast" value={money(report.project.net_profit, code)} />
      </KeyValueGrid>
      <p>Area basis: {report.gross_area_label ?? "Not selected"}. Profit tax: {percent(report.settings?.profit_tax_rate_fraction)}. Commission provision: {percent(report.settings?.commission_rate_fraction)}.</p>
      <p className="footnote">Cost coverage: {report.project.cost_complete_count} of {report.project.unit_count} units. Net profit coverage: {report.project.net_profit_complete_count} of {report.project.unit_count}. Missing inputs remain unavailable. These are current management estimates; approved historical sale allocations remain in the Approved basis view.</p>
    </Card>
    {report.issues.map((issue, i) => <Notice key={i} tone="warning">{issue}</Notice>)}
    <Tabs label="Cost breakdown level" tabs={[{ key: "units", label: "Units" }, { key: "floors", label: "Floors" }, { key: "buildings", label: "Buildings" }]} active={level} onSelect={setLevel} />
    <Field label="Building"><select className="input" value={building} onChange={e => setBuilding(e.target.value)}><option value="">All buildings</option>{report.buildings.map(r => <option key={r.id} value={r.id}>{r.label}</option>)}</select></Field>
    <TableScroll label="Current cost and profit breakdown"><thead><tr>{["Unit / group", "Revenue basis", "Gross built sqm", "Build cost / sqm", "Total cost", "Total cost / sqm", "Sale / forecast", "Pre-tax profit", "Profit tax", "Net profit estimate"].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{rows.map(({ key, label, figures: r, unit, basis }) => <tr key={key}>
      <th scope="row">{unit ? <Button variant="quiet" onClick={() => setSelected(unit)}>{label}</Button> : label}</th><td>{basis}</td><td>{r.gross_area_sqm ?? "Unavailable"}</td>
      {(["hard_cost_per_sqm", "total_cost", "total_cost_per_sqm", "revenue", "profit_before_tax", "tax_amount", "net_profit"] as const).map(field => <td key={field}>{money(r[field], code)}</td>)}
    </tr>)}</tbody></TableScroll>
    {!rows.length ? <EmptyState title="No units in this selection" hint="Add project units and their approved gross-built measurements in Inventory." /> : null}
    <Card title="Shared cost sources" description="Signed contracts include approved additions and reductions. Payments settle those contracts and are never added to cost a second time.">
      <TableScroll label="Shared cost sources"><thead><tr><th scope="col">Source</th><th scope="col">Category</th><th scope="col">Amount excluding VAT</th></tr></thead><tbody>{report.sources.map((source, i) => <tr key={i}><th scope="row">{source.reference}</th><td>{source.category}</td><td>{money(source.amount, code)}</td></tr>)}</tbody></TableScroll>
      <p className="footnote">Gross built area includes covered areas recorded in the chosen approved measurement. Do not include open gardens or plots. Tax is the project’s entered rate applied per profitable unit, separate from sales VAT. This estimate does not calculate statutory tax adjustments or loss offsets.</p>
      {canWrite && report.settings ? <DeleteRecordButton label="cost analysis inputs" description="Removes these editable inputs and the tax rate, retaining their audit history. Contracts, payments, land, unit costs and historical allocations remain recorded." onDelete={reason => unitEconomics.deleteCurrentCostSettings(projectId, report.settings!.revision, reason)} onDeleted={async () => onRefresh()} /> : null}
    </Card>
  </div>;
}

function SettingsEditor({ projectId, settings, code, onClose, onSaved }: { projectId: string; settings: CurrentCostSettings | null; code: string | null; onClose: () => void; onSaved: () => void }) {
  const areas = useAnswer(true, () => inventory.areaTypes(projectId), [projectId]);
  const [form, setForm] = useState({ gross_area_type_id: settings?.gross_area_type_id ?? "", supplemental_soft_cost: settings?.supplemental_soft_cost ?? "", additional_cost: settings?.additional_cost ?? "", finance_cost: settings?.finance_cost ?? "", commission: percentInput(settings?.commission_rate_fraction), tax: percentInput(settings?.profit_tax_rate_fraction), notes: settings?.notes ?? "", reason: "" });
  const [initial] = useState(form);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const change = (key: keyof typeof form, value: string) => setForm(previous => ({ ...previous, [key]: value }));
  const eligible: AreaType[] = areas.status === "ready" ? areas.data.filter(a => a.is_active && a.area_role === "gross" && ["sqm", "sqft"].includes(a.unit_of_measure)) : [];
  async function save() {
    if (busy || areas.status !== "ready") return;
    setBusy(true); setError(null);
    try {
      await unitEconomics.writeCurrentCostSettings(projectId, { gross_area_type_id: form.gross_area_type_id, supplemental_soft_cost: form.supplemental_soft_cost || null, additional_cost: form.additional_cost || null, finance_cost: form.finance_cost || null, commission_rate_fraction: form.commission ? fractionFromPercent(form.commission) : null, profit_tax_rate_fraction: form.tax ? fractionFromPercent(form.tax) : null, notes: form.notes || null, expected_revision: settings?.revision ?? 0, reason: form.reason });
      onSaved();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not save cost inputs."); }
    finally { setBusy(false); }
  }
  return <RecordPage title="Current cost inputs and profit tax" onClose={onClose}><DraftBoundary dirty={JSON.stringify(initial) !== JSON.stringify(form)} busy={busy}><form className="stack" onSubmit={e => { e.preventDefault(); void save(); }}>
    {error ? <Notice tone="error">{error}</Notice> : null}
    <p>Only enter costs outside the signed contracts, land register and individual unit costs. Blank means unknown; enter zero when there is no cost.</p>
    {areas.status === "failed" ? <><Notice tone="error">{areas.message}</Notice><Button onClick={areas.retry}>Retry area types</Button></> : areas.status === "denied" ? <Notice tone="warning">Area configuration is unavailable at your access scope.</Notice> : areas.status === "loading" ? <Loading label="Loading gross area choices" /> : null}
    <Field label="Approved gross-built area" hint="Choose the measurement including internal and covered built areas, excluding open garden and plot area. Record missing measurements in Inventory before allocating costs; use zero pricing weight for a construction-only measurement."><select className="input" required value={form.gross_area_type_id} onChange={e => change("gross_area_type_id", e.target.value)}><option value="">Choose gross-built measurement</option>{eligible.map(a => <option key={a.id} value={a.id}>{a.label} ({a.unit_of_measure})</option>)}</select></Field>
    {areas.status === "ready" && !eligible.length ? <Notice tone="warning">Add an active gross-role area type in Inventory, then record and approve its built/covered measurement for every unit.</Notice> : null}
    <FieldRow>{([["supplemental_soft_cost", "Supplemental soft costs"], ["additional_cost", "Additional project costs"], ["finance_cost", "Shared finance costs"]] as const).map(([key, label]) => <Field key={key} label={label} optional><MoneyInput value={form[key]} code={code} onChange={value => change(key, value)} /></Field>)}</FieldRow>
    <FieldRow><Field label="Commission provision %" optional hint="Used only without a current grant or recorded commission. Enter zero explicitly if none."><RateInput value={form.commission} onChange={value => change("commission", value)} /></Field><Field label="Profit tax %" optional hint="Separate from sales VAT. Blank keeps estimated net profit unavailable."><RateInput value={form.tax} onChange={value => change("tax", value)} /></Field></FieldRow>
    <Field label="Cost basis notes" optional><textarea className="input" maxLength={1000} value={form.notes} onChange={e => change("notes", e.target.value)} /></Field>
    <Field label="Reason for saving"><input className="input" required maxLength={1000} value={form.reason} onChange={e => change("reason", e.target.value)} /></Field>
    <ButtonRow><Button type="submit" variant="primary" disabled={busy || areas.status !== "ready" || !eligible.some(a => a.id === form.gross_area_type_id)}>{busy ? "Saving…" : "Save and calculate"}</Button><Button data-leaves-editor onClick={onClose} disabled={busy}>Cancel</Button></ButtonRow>
  </form></DraftBoundary></RecordPage>;
}
