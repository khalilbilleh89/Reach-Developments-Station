"use client";

import { useState } from "react";
import { marketing, type Scenario, type ScenarioFields, type UnitScenario } from "@/lib/api/marketing";
import { useAnswer } from "@/lib/answer";
import { hasAnyRole, MARKETING_READERS, MARKETING_WRITERS } from "@/lib/roles";
import { businessDate, money } from "@/lib/format";
import { useCurrencyCode } from "@/lib/currency";
import { Badge, Button, Card, Disclosure, EmptyState, Field, KeyValue, KeyValueGrid, Loading, Notice, PageHeader, RecordPage, RegisterPagination, SectionHeader, TableScroll } from "@/components/ui";
import { DeleteRecordButton } from "../DeleteRecordButton";
import { MarketIndicators } from "./MarketIndicators";
import { blankScenario, RentalEditor } from "./RentalEditor";

const modeName = (mode: string) => mode === "long_term" ? "Long-term" : "Short-term";
function fields(row: ScenarioFields): ScenarioFields {
  return Object.fromEntries(Object.keys(blankScenario(row.currency_id, row.mode)).map(key => [key, row[key as keyof ScenarioFields]])) as ScenarioFields;
}

export function MarketingEconomicsTab({ projectId, roles, currencyId }: { projectId: string; roles: Set<string>; currencyId: string }) {
  const canRead = hasAnyRole(roles, MARKETING_READERS);
  const canWrite = hasAnyRole(roles, MARKETING_WRITERS);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editor, setEditor] = useState<{ initial: ScenarioFields; row?: Scenario; label: string } | null>(null);
  const scenarios = useAnswer(canRead, () => marketing.scenarios(projectId), [projectId]);
  const units = useAnswer(canRead, () => marketing.units(projectId, search, offset), [projectId, search, offset]);
  const codeOf = useCurrencyCode();
  const refresh = () => { scenarios.retry(); units.retry(); };
  const settings = scenarios.status === "ready" ? scenarios.data : [];
  const selected = units.status === "ready" ? units.data.units.find(row => row.unit_id === selectedId) : undefined;
  const edit = (mode: ScenarioFields["mode"], unitId: string | null, reference: string) => {
    const row = settings.find(s => s.mode === mode && s.unit_id === unitId);
    const base = row ?? settings.find(s => s.mode === mode && s.unit_id === null);
    setEditor({ row, initial: { ...(base ? fields(base) : blankScenario(currencyId, mode)), unit_id: unitId }, label: reference });
  };
  if (editor) return <RentalEditor initial={editor.initial} scopeLabel={editor.label} onClose={() => setEditor(null)} onSave={async values => { await marketing.saveScenario(projectId, values, editor.row); setEditor(null); refresh(); }} />;
  return <div className="stack">
    <PageHeader title="Economics" subtitle="Compare buyer rental returns, capital appreciation and the market behind them." />
    <Notice tone="info">Indicative five-year estimates, not guaranteed returns. Assumptions do not change recorded unit prices, sales, developer costs or cashflow.</Notice>
    <Card><SectionHeader level={2} title="Project Rental Assumptions" description="Set one default for each rental mode. Individual units can override it." />
      {scenarios.status === "loading" ? <Loading label="Loading rental assumptions…" /> : null}
      {scenarios.status === "denied" ? <Notice tone="info">Rental assumptions are not available to your access level.</Notice> : null}
      {scenarios.status === "failed" ? <Notice tone="error">{scenarios.message} <Button onClick={scenarios.retry}>Retry</Button></Notice> : null}
      {scenarios.status === "ready" ? <div className="marketing-comparison">{(["long_term", "short_term"] as const).map(mode => {
        const row = settings.find(s => s.mode === mode && s.unit_id === null);
        return <section key={mode} className="marketing-entry stack"><SectionHeader title={modeName(mode)} actions={canWrite ? <Button variant="default" onClick={() => edit(mode, null, "Project default · all units without an override")}>{row ? "Edit assumptions" : "Set assumptions"}</Button> : undefined} />
          {row ? <><KeyValueGrid><KeyValue label="Annual rent / m²" value={money(row.annual_rent_per_sqm, codeOf(row.currency_id))} /><KeyValue label="Area basis" value={row.area_basis} /><KeyValue label="Vacancy" value={`${row.vacancy_percent}%`} /><KeyValue label="As at" value={businessDate(row.as_of)} /></KeyValueGrid><p className="muted">{row.source}</p><Assumptions row={row} />
            {canWrite ? <DeleteRecordButton label="rental assumptions" recordName={`${modeName(mode)} project default`} confirmLabel="Delete assumptions" description="Units without an override will show unavailable estimates. Individual overrides and audit history remain." onDelete={reason => marketing.remove(projectId, `scenarios/${row.id}`, row.version, reason)} onDeleted={async () => refresh()} /> : null}</> : <p className="muted">No assumptions recorded.</p>}
        </section>;
      })}</div> : null}
    </Card>
    <Card><SectionHeader level={2} title="Unit Rental Returns" description="Open a unit to compare both rental modes and its year-by-year projection." />
      <Field label="Search units"><input className="input" type="search" value={search} onChange={e => { setSearch(e.target.value); setOffset(0); setSelectedId(null); }} /></Field>
      {units.status === "loading" ? <Loading label="Calculating unit projections…" /> : null}
      {units.status === "denied" ? <Notice tone="info">Unit returns are not available to your access level.</Notice> : null}
      {units.status === "failed" ? <Notice tone="error">{units.message} <Button onClick={units.retry}>Retry</Button></Notice> : null}
      {units.status === "ready" ? <>{units.data.units.length ? <TableScroll label="Marketing economics"><table><caption>Indicative year-one net rental yield and five-year return</caption><thead><tr><th scope="col">Unit</th><th scope="col">Long-term net yield</th><th scope="col">Short-term net yield</th><th scope="col">Long-term 5-year ROI</th><th scope="col">Short-term 5-year ROI</th></tr></thead><tbody>{units.data.units.map(unit => <tr key={unit.unit_id}><th scope="row"><Button variant="default" onClick={() => setSelectedId(unit.unit_id)}>{unit.reference}</Button></th>
        {unit.scenarios.map(s => <td key={`${s.mode}-yield`}>{s.projection ? `${s.projection.net_yield_percent}%` : <span className="muted">{s.unavailable}</span>}</td>)}
        {unit.scenarios.map(s => <td key={`${s.mode}-roi`}>{s.projection ? `${s.projection.roi_percent}%` : "Unavailable"}</td>)}
      </tr>)}</tbody></table></TableScroll> : <EmptyState title="No matching units" hint="Units come from the project's Inventory. Adjust your search or record units there." />}
        <RegisterPagination offset={offset} total={units.data.total} pageSize={25} onChange={value => { setOffset(value); setSelectedId(null); }} />
      </> : null}
    </Card>
    {scenarios.status === "ready" && settings.some(row => row.unit_id) ? <Card><Disclosure title="All saved unit overrides" context="Includes overrides for units outside the current page or removed from Inventory.">
      <div className="stack">{settings.filter(row => row.unit_id).map(row => <section className="marketing-entry" key={row.id}><SectionHeader title={`${row.unit_reference || "Unit"} · ${modeName(row.mode)}`} actions={canWrite ? <DeleteRecordButton label="unit override" recordName={`${row.unit_reference || "Unit"} · ${modeName(row.mode)}`} description="Delete this override and retain its history. Project defaults will apply where available." confirmLabel="Delete unit override" onDelete={reason => marketing.remove(projectId, `scenarios/${row.id}`, row.version, reason)} onDeleted={async () => refresh()} /> : undefined} /><Assumptions row={row} /></section>)}</div>
    </Disclosure></Card> : null}
    <MarketIndicators projectId={projectId} roles={roles} />
    {selected ? <RecordPage title={`${selected.reference} · Rental Returns`} onClose={() => setSelectedId(null)}>
      <div className="stack"><Notice tone="info">Year-one net yield is NOI / initial investment. Five-year ROI includes one resale, using the selected exit method.</Notice>
        <div className="marketing-comparison">{selected.scenarios.map(result => {
          const row = settings.find(s => s.id === result.scenario_id);
          const mode = result.mode as ScenarioFields["mode"];
          return <Card key={result.mode}><SectionHeader level={2} title={modeName(result.mode)} actions={canWrite && scenarios.status === "ready" ? <Button variant="default" onClick={() => edit(mode, selected.unit_id, selected.reference)}>{row?.unit_id ? "Edit unit assumptions" : "Customize this unit"}</Button> : undefined} />
            <Badge>{result.source_scope || "No assumptions"}</Badge>
            <RentalProjection result={result} />
            {row ? <Assumptions row={row} /> : null}
            {row?.unit_id && canWrite ? <DeleteRecordButton label="unit assumptions" recordName={`${selected.reference} · ${modeName(mode)}`} confirmLabel="Delete unit override" description="Remove this unit override and return to project defaults where available. Audit history is retained." onDelete={reason => marketing.remove(projectId, `scenarios/${row.id}`, row.version, reason)} onDeleted={async () => refresh()} /> : null}
          </Card>;
        })}</div><ProjectionBasis />
      </div>
    </RecordPage> : null}
  </div>;
}

export function RentalProjection({ result }: { result: UnitScenario }) {
  const codeOf = useCurrencyCode();
  const code = codeOf(result.currency_id);
  const p = result.projection;
  if (!p) return <Notice tone="info">{result.unavailable || "Projection unavailable."}</Notice>;
  const first = p.years[0];
  return <div className="stack">
    <div className="marketing-lead"><span>Year-one net rental yield</span><strong>{p.net_yield_percent}%</strong><span>NOI / initial investment</span></div>
    <KeyValueGrid>
      <KeyValue label="Purchase price basis" value={result.price_basis} /><KeyValue label="Purchase price" value={money(result.price, code)} />
      <KeyValue label="Selected area (m²)" value={money(result.area_sqm)} /><KeyValue label="Initial investment (including costs)" value={money(p.initial_investment, code)} />
      <KeyValue label="Gross potential revenue / year 1" value={money(first.gross_revenue, code)} /><KeyValue label="Monthly potential revenue" value={money(p.monthly_potential_revenue, code)} />
      <KeyValue label="Vacancy deduction / year 1" value={money(first.vacancy_amount, code)} /><KeyValue label="Effective gross revenue / year 1" value={money(first.effective_revenue, code)} />
      <KeyValue label="Operating expenses / year 1" value={money(first.expenses, code)} /><KeyValue label="NOI / year 1" value={money(first.noi, code)} />
      <KeyValue label="Gross rental yield / price" value={`${p.gross_yield_percent}%`} /><KeyValue label="ROI / five years including sale" value={`${p.roi_percent}%`} />
      <KeyValue label="IRR / annual" value={p.irr_percent === null ? p.irr_reason : `${p.irr_percent}%`} /><KeyValue label="Net present value" value={money(p.npv, code)} />
      <KeyValue label="Appreciation-based value / year 5" value={money(p.appreciation_value, code)} /><KeyValue label="Cap-rate value / year 5 (year-six NOI)" value={money(p.cap_value, code)} />
      <KeyValue label="Capital gain / selected exit method" value={money(p.capital_gain, code)} /><KeyValue label="Net sale proceeds / selected exit method" value={money(p.sale_proceeds, code)} />
      <KeyValue label="Simple payback / constant year-one NOI" value={p.simple_payback_years === null ? "Unavailable: non-positive NOI" : `${p.simple_payback_years} years`} />
      <KeyValue label="Rental-only payback" value={p.rental_payback_years === null ? "Not reached within five years" : `${p.rental_payback_years} years`} /><KeyValue label="Payback including sale" value={p.total_payback_year === null ? "Not reached within five years" : `Year ${p.total_payback_year}`} />
    </KeyValueGrid>
    <TableScroll label="Marketing economics"><table><caption>Five-year annual projection ({code || "currency unavailable"})</caption><thead><tr><th scope="col">Year</th><th scope="col">Rent after vacancy</th><th scope="col">Expenses</th><th scope="col">NOI</th><th scope="col">Cash flow*</th></tr></thead><tbody>{p.years.map(row => <tr key={row.year}><th scope="row">{row.year}</th><td>{money(row.effective_revenue, code)}</td><td>{money(row.expenses, code)}</td><td>{money(row.noi, code)}</td><td>{money(row.cashflow, code)}</td></tr>)}</tbody></table></TableScroll>
    <p className="muted">*Year five includes net sale proceeds. Year zero is the initial investment outflow.</p>
  </div>;
}

function Assumptions({ row }: { row: Scenario }) {
  const codeOf = useCurrencyCode();
  return <Disclosure title="Assumptions and source"><KeyValueGrid>
    <KeyValue label="Area basis" value={row.area_basis} /><KeyValue label="Annual rent per m²" value={money(row.annual_rent_per_sqm, codeOf(row.currency_id))} /><KeyValue label="Annual expenses per m²" value={money(row.annual_expense_per_sqm, codeOf(row.currency_id))} />
    <KeyValue label="Vacancy" value={`${row.vacancy_percent}%`} /><KeyValue label="Income growth / year" value={`${row.income_growth_percent}%`} /><KeyValue label="Expense growth / year" value={`${row.expense_growth_percent}%`} />
    <KeyValue label="Capital appreciation / year" value={`${row.appreciation_percent}%`} /><KeyValue label="Exit cap rate" value={`${row.exit_cap_percent}%`} /><KeyValue label="Discount rate" value={`${row.discount_percent}%`} />
    <KeyValue label="Acquisition costs" value={`${row.acquisition_cost_percent}%`} /><KeyValue label="Selling costs" value={`${row.selling_cost_percent}%`} /><KeyValue label="Setup / furnishing" value={money(row.setup_cost, codeOf(row.currency_id))} />
    <KeyValue label="Exit method" value={row.exit_method === "appreciation" ? "Compound capital appreciation" : "Year-six NOI / cap rate"} /><KeyValue label="Source" value={row.source} /><KeyValue label="As at" value={businessDate(row.as_of)} />
  </KeyValueGrid></Disclosure>;
}

function ProjectionBasis() {
  return <Disclosure title="Calculation basis and limitations"><div className="stack">
    <p>Annual potential rent = selected approved area × annual rent per m². Vacancy reduces rent, while operating expenses apply to the full selected area. Income and expenses grow independently each year.</p>
    <p>Initial investment = purchase price + acquisition costs + setup costs. Rental yield uses year-one NOI. Five-year ROI = (five annual NOIs + net sale proceeds − initial investment) / initial investment. NPV discounts end-year cash flows and subtracts the year-zero investment. IRR uses the same cash flows.</p>
    <p>The selected resale method uses either compounded appreciation or year-six NOI divided by the exit cap rate, less selling costs. Negative terminal NOI produces a zero cap-based value. The two valuations are alternatives and are never added together.</p>
    <p>Rental payback interpolates within the first five years; no extrapolated payback is implied. This is an unlevered model before personal income and capital gains tax. Include all expected operating costs, acquisition taxes and disposal costs in the assumptions. Current asking price is a reference, not an executed purchase price.</p>
  </div></Disclosure>;
}
