"use client";

import { useState } from "react";
import Link from "next/link";
import { useAnswer } from "@/lib/answer";
import { projectAnalysis } from "@/lib/api/analysis";
import type { Availability, Context, Demand, Fundamental, Financial, Technical, Feasibility, Money, Ranking, Ratio, Section } from "@/lib/api/analysis";
import { ANALYSIS_FINANCIAL_READERS, ANALYSIS_FUNDAMENTAL_READERS, ANALYSIS_TECHNICAL_READERS, hasAnyRole } from "@/lib/roles";
import type { Roles } from "@/lib/roles";
import { businessDate, money } from "@/lib/format";
import { CountComposition, CountSeries, Disclosure, Button, SectionHeader, KeyValueGrid, KeyValue, StatusDot, Field, FieldRow, FormActions, Loading, Notice, Position, PositionFigure, Tabs, TabPanel, TableScroll } from "@/components/ui";
import { statusLabel, statusTone } from "@/components/projects/inventory/statusLabels";

import { FeasibilityView } from "./FeasibilityView";

const labels = { fundamental: "Fundamental", financial: "Financial", technical: "Technical", feasibility: "Feasibility" };
const readers = { fundamental: ANALYSIS_FUNDAMENTAL_READERS, financial: ANALYSIS_FINANCIAL_READERS, technical: ANALYSIS_TECHNICAL_READERS, feasibility: ANALYSIS_TECHNICAL_READERS };
const display = (value: string) => value.replaceAll("_", " ");
const capitalise = (value: string) => value.charAt(0).toUpperCase() + value.slice(1);
const percentage = (value: Ratio) => value.percentage === null ? "Unavailable" : `${value.percentage}% (${value.numerator} / ${value.denominator})`;
const amounts = (values: Money[]) => values.length ? values.map((value) => money(value.amount, value.currency)).join(" · ") : "No sale activations";

/**
 * How far a figure can be trusted, said once and quietly.
 *
 * This appears under nearly every block on every tab. As a bordered panel with
 * its own heading and its own collapsed disclosure it was the single largest
 * source of noise on the page: ten copies of the same furniture per tab,
 * each taller than the finding it qualified. It is now one row — coverage,
 * sample, and the method behind a link that opens in place. Nothing is
 * dropped; the reason and the source basis are still both reachable.
 */
function Basis({ value }: { value: Availability }) {
  return <div className="source-basis">
    <div className="source-basis-status">
      <StatusDot tone={value.availability === "available" ? "success" : value.availability === "partial" ? "warning" : "muted"}>
        {value.availability === "available" ? "Available" : value.availability === "partial" ? "Partial coverage" : "Unavailable"}
      </StatusDot>
      <span>{value.sample_size} records in sample</span>
      {value.availability !== "available" && value.reason ? <span className="source-basis-reason">{value.reason}</span> : null}
    </div>
    <div className="source-basis-detail">
      <Disclosure title="Method">
        {value.availability === "available" && value.reason ? <p>{value.reason}</p> : null}
        <p className="footnote">{value.source_basis}</p>
      </Disclosure>
    </div>
  </div>;
}
/**
 * One dimension of the record population, as a row of small facts.
 *
 * Previously a heading over a wrapping list of 26px figures, which turned
 * three dimensions into a screen and a half of mostly nothing. A status count
 * is a fact to scan, not a headline: the figure is sized to be read beside
 * its neighbours rather than across the room.
 */
function Counts({ values, label }: { values: Record<string, number>; label: string }) {
  const entries = Object.entries(values);
  return <section className="analysis-counts">
    <h4 className="analysis-counts-label">{label}</h4>
    {entries.length ? <ul className="analysis-count-list">{entries.map(([name, count]) => <li key={name} className="analysis-count">
      <span className="analysis-count-name">{display(name)}</span>
      <span className="analysis-count-figure num">{count}</span>
    </li>)}</ul> : <p className="footnote">No records reported.</p>}
  </section>;
}
function ContextNote({ context }: { context: Context }) {
  return <div className="analysis-context">
    <KeyValueGrid columns={3}>
      <KeyValue label="Observation period" value={`${businessDate(context.period_from)} — ${businessDate(context.period_to)}`} />
      <KeyValue label="As of" value={businessDate(context.as_of)} />
      <KeyValue label="Scope" value={`Whole project · ${context.currency}`} />
    </KeyValueGrid>
    <p className="footnote">Current record snapshot {businessDate(context.snapshot_as_of)}. Transaction currencies shown separately.</p>
  </div>;
}
function DemandTable({ rows, title }: { rows: Demand[]; title: string }) {
  return <Disclosure title={<> {title} </>}><TableScroll fixedFirst label={title}><thead><tr><th scope="col">Classification</th><th scope="col" className="num">Inventory</th><th scope="col" className="num">Standing period sales</th><th scope="col" className="num">Demand share</th><th scope="col" className="num">Penetration within group</th></tr></thead><tbody>{rows.map((row) => <tr key={row.label}><th scope="row">{row.label}</th><td className="num">{row.inventory_count}</td><td className="num">{row.sales_count}</td><td className="num">{percentage(row.demand_share)}</td><td className="num">{percentage(row.penetration)}</td></tr>)}</tbody></TableScroll><p className="muted">Demand share uses standing period sales on eligible inventory. Penetration uses eligible inventory within each group. Unknown classifications remain in the population.</p></Disclosure>;
}
function RankingTable({ rows, title }: { rows: Ranking[]; title: string }) {
  return <Disclosure title={<> {title} </>}><p className="muted">Ranked by standing activated sales count within the selected period, then contracted value only when currencies are comparable. Unassigned sales remain visible.</p><TableScroll fixedFirst label={title}><thead><tr><th scope="col">{title}</th><th scope="col" className="num">Sales / sample</th><th scope="col" className="num">Contracted value</th><th scope="col" className="num">Share</th></tr></thead><tbody>{rows.map((row) => <tr key={row.source_key ?? "unassigned"}><th scope="row">{row.label}</th><td className="num">{row.sales_count}</td><td className="num">{amounts(row.contracted_value)}</td><td className="num">{percentage(row.share)}</td></tr>)}</tbody></TableScroll></Disclosure>;
}
function FundamentalView({ data }: { data: Fundamental }) {
  const p = data.position, f = data.forecast;
  return <div className="stack"><ContextNote context={data.context} />
    <div className="analysis-position"><section className="analysis-primary"><SectionHeader title="Inventory absorption" description="Current eligible inventory and standing contracts." />
    {p.availability === "available" ? <Position compact>
      <PositionFigure lead label="Remaining eligible units" value={p.remaining_units} />
      <PositionFigure label="Commercial penetration" value={p.penetration.percentage === null ? "Unavailable" : `${p.penetration.percentage}%`} note={`${p.penetration.numerator} / ${p.penetration.denominator}`} />
      <PositionFigure label="Available units" value={p.available_units} />
      <PositionFigure label="Active sold units" value={p.active_sold_units} />
    </Position> : <Notice tone="info">{p.reason}</Notice>}
    {p.availability === "available" ? <CountComposition label="Commercial inventory" note={`Current snapshot · ${businessDate(data.context.snapshot_as_of)} · ${p.total_units} total unit records`} rows={Object.entries(p.commercial).map(([status, count]) => ({ label: statusLabel(status), count, tone: statusTone(status) }))} /> : null}
    <Basis value={p} /></section>
    <aside className="analysis-outlook">
      <SectionHeader title="Run-rate sellout estimate" />
      <Position compact><PositionFigure lead label="Estimated time to sell" value={f.estimated_months_to_sell === null ? "Unavailable" : `${f.estimated_months_to_sell} months`} note={`${f.average_monthly_absorption ?? "Unavailable"} net units/month`} /></Position>
      <p className="footnote">{businessDate(f.window_from)} to {businessDate(f.window_to)} · {f.observed_months} complete observed months</p>
      <Disclosure title="Observed absorption"><p>Net absorption: {f.monthly_net_absorption.join(", ")}</p></Disclosure>
      <Basis value={f} />
    </aside></div>
    <section className="analysis-primary">
      {data.sales_basis.availability === "unavailable" ? <Notice tone="info">Monthly sales activity is unavailable. {data.sales_basis.reason}</Notice> : data.monthly_sales.length ? <CountSeries label="Monthly net sales activity" note={`${businessDate(data.context.period_from)} — ${businessDate(data.context.period_to)} · Units · ${data.sales_basis.availability} · Below zero means net cancellations`} rows={data.monthly_sales.map((row) => ({ label: businessDate(row.month).replace(/^1 /, ""), count: row.net_absorption }))} /> : <Notice tone="info">No monthly sales observations returned for this period.</Notice>}
      <Basis value={data.sales_basis} />
      <Disclosure title={<> Monthly selling demand </>}><TableScroll fixedFirst label="Monthly selling demand"><thead><tr><th scope="col">Month</th><th scope="col" className="num">Activations</th><th scope="col" className="num">Cancellations</th><th scope="col" className="num">Net absorption</th><th scope="col" className="num">New contracted value</th></tr></thead><tbody>{data.monthly_sales.map((row) => <tr key={row.month}><th scope="row">{businessDate(row.month)}</th><td className="num">{row.activations}</td><td className="num">{row.cancellations}</td><td className="num">{row.net_absorption}</td><td className="num">{amounts(row.contracted_value)}</td></tr>)}</tbody></TableScroll></Disclosure>
    </section>
    <Disclosure title="Inventory scope & status dimensions" context={`${p.total_units} total records`}><p className="muted">{p.eligible_units} units are eligible for absorption analysis. Eligibility excludes inactive, held, unreleased and withdrawn units. Overview register counts follow your inventory access and filters. These are current record dimensions, not a single combined status.</p><div className="analysis-dimensions"><Counts label="Commercial" values={p.commercial} /><Counts label="Legal" values={p.legal} /><Counts label="Delivery" values={p.delivery} /></div></Disclosure>
    <RankingTable title="Sales branches" rows={data.branches} /><RankingTable title="Salespeople" rows={data.salespeople} /><Basis value={data.ranking_basis} />
    <DemandTable title="Property type demand" rows={data.property_types} /><DemandTable title="View demand" rows={data.views} /><Basis value={data.view_basis} />
    <Disclosure title="Observed view premiums" context={`${data.observed_premiums.length} cohorts`}>{data.observed_premiums.length ? <><TableScroll fixedFirst label="Observed view premiums"><thead><tr><th scope="col">Cohort</th><th scope="col">Coverage</th><th scope="col" className="num">Observed premium</th><th scope="col" className="num">View sample</th><th scope="col" className="num">Baseline sample</th><th scope="col">Comparison</th></tr></thead><tbody>{data.observed_premiums.map((row) => <tr key={`${row.property_type}-${row.view}`}><th scope="row">{display(row.property_type)} · {display(row.view)}</th><td><StatusDot tone={row.availability === "available" ? "success" : row.availability === "partial" ? "warning" : "muted"}>{row.availability === "available" ? "Available" : row.availability === "partial" ? "Partial" : "Unavailable"}</StatusDot></td><td className="num">{row.percentage === null ? "Unavailable" : `${row.percentage}%`}</td><td className="num">{row.sample_size}</td><td className="num">{row.baseline_sample}</td><td>{row.currency && row.area_unit ? `${row.view_price_per_gross_area ?? "Unavailable"} vs ${row.baseline_price_per_gross_area ?? "Unavailable"} ${row.currency}/${row.area_unit}` : row.reason ?? row.baseline}</td></tr>)}</tbody></TableScroll><p className="muted">Every recorded cohort is listed, including those with no comparable sale — an absent premium is a fact about the records, not a gap in the page. The method is identical for every row and is stated once below rather than repeated on each.</p>{data.observed_premiums[0] ? <p className="footnote">{data.observed_premiums[0].source_basis}</p> : null}</> : <p>No comparable structured view cohorts recorded.</p>}</Disclosure>
  </div>;
}
function FinancialView({ data }: { data: Financial }) {
  // Choose an existing month; every amount stays on its returned currency row.
  const months = [...new Set(data.monthly.map((row) => row.month))].sort();
  const [chosenMonth, setChosenMonth] = useState<string | null>(null);
  const month = chosenMonth && months.includes(chosenMonth) ? chosenMonth : months.at(-1);
  const visible = data.monthly.filter((row) => row.month === month);
  return <div className="stack">
    <ContextNote context={data.context} />
    <section className="analysis-primary">
      <SectionHeader title="Monthly cash movement" description="Actual movement in the selected month, with each currency kept separate." actions={months.length ? <Field label="Month"><select className="input" value={month} onChange={(event) => setChosenMonth(event.target.value)}>{months.map((value) => <option key={value} value={value}>{businessDate(value)}</option>)}</select></Field> : undefined} />
      {data.basis.availability === "unavailable" ? <Notice tone="info">Monthly cash movement is unavailable for this period.</Notice> : visible.length ? visible.map((row) => <section className="stack" key={row.currency}>
        <h4>{row.currency} · Month beginning {businessDate(row.month)}</h4>
        <Position compact>
          <PositionFigure lead label="Net actual cash movement" value={money(row.net_actual_cash_movement, row.currency)} note="Includes refunds and financing" />
          <PositionFigure label="Customer cash received" value={money(row.customer_cash_received, row.currency)} />
          <PositionFigure label="Project cash outflow" value={money(row.project_cash_outflow, row.currency)} />
        </Position>
        <KeyValueGrid>
          <KeyValue label="New sales in the month" value={row.new_sales_count} mono />
          <KeyValue label="Contracted sales value · demand, not cash" value={money(row.contracted_sales_value, row.currency)} mono />
        </KeyValueGrid>
      </section>) : <Notice tone="info">No monthly cash records returned for this period.</Notice>}
      <Basis value={data.basis} />
    </section>
    <Notice tone="info">{data.cash_scope} Contracted sales value is demand, not cash. An uncollected contract balance is not automatically overdue.</Notice>
    <Disclosure title="Monthly demand and cash evidence">
      <TableScroll fixedFirst label="Sales demand versus actual cash"><thead><tr><th scope="col">Month / currency</th><th scope="col" className="num">New sales</th><th scope="col" className="num">Contracted value</th><th scope="col" className="num">Customer cash received</th><th scope="col" className="num">Project cash outflow</th><th scope="col" className="num">Net actual cash movement</th></tr></thead><tbody>{data.monthly.map((row) => <tr key={`${row.month}-${row.currency}`}><th scope="row">{businessDate(row.month)} · {row.currency}</th><td className="num">{row.new_sales_count}</td><td className="num">{money(row.contracted_sales_value, row.currency)}</td><td className="num">{money(row.customer_cash_received, row.currency)}</td><td className="num">{money(row.project_cash_outflow, row.currency)}</td><td className="num">{money(row.net_actual_cash_movement, row.currency)}</td></tr>)}</tbody></TableScroll>
    </Disclosure>
    <Disclosure title={<> Refund and financing detail included in net cash </>}><TableScroll fixedFirst label="Refunds and financing"><thead><tr><th scope="col">Month / currency</th><th scope="col" className="num">Customer refunds</th><th scope="col" className="num">Financing in</th><th scope="col" className="num">Financing out</th></tr></thead><tbody>{data.monthly.map((row) => <tr key={`${row.month}-${row.currency}`}><th scope="row">{businessDate(row.month)} · {row.currency}</th><td className="num">{money(row.customer_refunds, row.currency)}</td><td className="num">{money(row.financing_inflow, row.currency)}</td><td className="num">{money(row.financing_outflow, row.currency)}</td></tr>)}</tbody></TableScroll></Disclosure>
  </div>;
}
function TechnicalView({ data, projectId }: { data: Technical; projectId: string }) {
  return <div className="stack"><ContextNote context={data.context} /><div className="analysis-position">
    <section className="analysis-primary"><SectionHeader title="Recorded technical product profile" description="The current product mix recorded for this development." />{Object.keys(data.product_types).length ? <CountComposition label="Property types" note="Current recorded unit classifications" rows={Object.entries(data.product_types).map(([label,count]) => ({label:display(label),count}))} /> : <Notice tone="info">No product mix is recorded. <Link href={`/projects/?project=${encodeURIComponent(projectId)}&section=inventory`}>Open inventory</Link> to review units and their classifications.</Notice>}<Basis value={data.basis} /></section>
    <aside className="analysis-outlook"><SectionHeader title="Features and attachments" /><Position compact><PositionFigure lead label="Recorded feature coverage" value={data.feature_coverage.percentage === null ? "Unavailable" : `${data.feature_coverage.percentage}%`} note={`${data.feature_coverage.numerator ?? "—"} / ${data.feature_coverage.denominator ?? "—"} units`} /></Position><Counts label="Attachments" values={data.attachments} /><Basis value={data.feature_coverage} /></aside>
    </div><Disclosure title="Physical area ranges" context={`${data.areas.length} components`}>{data.areas.length ? <><TableScroll fixedFirst label="Approved physical areas"><thead><tr><th scope="col">Component</th><th scope="col">Measure</th><th scope="col" className="num">Minimum</th><th scope="col" className="num">Maximum</th><th scope="col" className="num">Average</th><th scope="col" className="num">Sample</th></tr></thead><tbody>{data.areas.map((row) => <tr key={`${row.component}-${row.unit_of_measure}`}><th scope="row">{display(row.component)}</th><td>{row.unit_of_measure}</td><td className="num">{row.minimum}</td><td className="num">{row.maximum}</td><td className="num">{row.average}</td><td className="num">{row.sample_size}</td></tr>)}</tbody></TableScroll><p className="muted">Gross uses all six approved physical components. Parking and storage are separate attachments.</p></> : <Notice tone="info">{data.area_coverage.reason ?? "No approved physical areas are recorded."}</Notice>}<Basis value={data.area_coverage} /></Disclosure><Disclosure title="Recorded features"><Counts label="Recorded features" values={data.features} /></Disclosure><Disclosure title={<> Permits · Obtained / Issued </>}><Basis value={data.permit_basis} /><Counts label="Statutory permit status" values={data.permits} /></Disclosure><Disclosure title="Consultant design context"><KeyValueGrid>{Object.entries(data.consultant).map(([key, value]) => <KeyValue key={key} label={capitalise(display(key))} value={value ?? "Not recorded"} />)}</KeyValueGrid><Basis value={data.consultant_basis} /></Disclosure><Disclosure title="Physical construction progress" context={`${data.construction_stages.length} stages`}>{data.construction_stages.length ? <TableScroll fixedFirst label="Construction stages"><thead><tr><th scope="col">Stage</th><th scope="col" className="num">Completed units</th><th scope="col" className="num">Units in scope</th></tr></thead><tbody>{data.construction_stages.map((row) => <tr key={row.name}><th scope="row">{row.name}</th><td className="num">{row.completed_units}</td><td className="num">{row.denominator}</td></tr>)}</tbody></TableScroll> : <Notice tone="info">{data.construction_basis.reason ?? "No construction stages are configured for this development."}</Notice>}<Basis value={data.construction_basis} /></Disclosure></div>;
}
function AnalysisAnswer({ projectId, section, query }: { projectId: string; section: Section; query: string }) {
  const answer = useAnswer<Fundamental | Financial | Technical | Feasibility>(true, () => projectAnalysis[section](projectId, query), [projectId, section, query]);
  if (answer.status === "denied") return <Notice tone="info">Not authorized: whole-project access and the appropriate Analysis role are required.</Notice>;
  if (answer.status === "failed") return <Notice tone="info">Analysis could not be loaded. {answer.message}</Notice>;
  if (answer.status !== "ready") return <Loading label="Loading analysis" />;
  return section === "feasibility" ? <FeasibilityView data={answer.data as Feasibility} projectId={projectId} /> : section === "fundamental" ? <FundamentalView data={answer.data as Fundamental} /> : section === "financial" ? <FinancialView data={answer.data as Financial} /> : <TechnicalView data={answer.data as Technical} projectId={projectId} />;
}
export function ProjectAnalysis({ projectId, roles }: { projectId: string; roles: Roles }) {
  const enabled = (Object.keys(labels) as Section[]).filter((key) => hasAnyRole(roles, readers[key]));
  const [chosen, setChosen] = useState<Section | null>(null);
  const [from, setFrom] = useState(""); const [to, setTo] = useState(""); const [asOf, setAsOf] = useState("");
  const [query, setQuery] = useState("");
  const section = chosen && enabled.includes(chosen) ? chosen : enabled[0];
  if (!section) return null;
  // What the reader has actually asked for, in words, on the control that sets
  // it. "Observation period" alone said nothing about which period was in
  // force, so the only way to learn it was to open the panel.
  const period = from || to || asOf
    ? [from ? `from ${businessDate(from)}` : null, to ? `to ${businessDate(to)}` : null, asOf ? `as of ${businessDate(asOf)}` : null].filter(Boolean).join(" · ")
    : "Last 12 months";

  return <section className="analysis-workspace">
    <header className="analysis-head">
      <div className="analysis-head-title">
        <h2 className="analysis-head-heading">Project Analysis</h2>
        <p className="analysis-head-note">Demand, capital movement and the recorded product.</p>
      </div>
      <Tabs variant="analysis" label="Project analysis sections" tabs={enabled.map((key) => ({ key, label: labels[key] }))} active={section} onSelect={(key) => setChosen(key as Section)} />
    </header>
    <div className="analysis-period">
      <Disclosure title="Observation period" context={period}>
        <form onSubmit={(event) => { event.preventDefault(); const params = new URLSearchParams(); if (from) params.set("period_from", from); if (to) params.set("period_to", to); if (asOf) params.set("as_of", asOf); setQuery(params.size ? `?${params}` : ""); }}>
          <FieldRow columns={3}>
            <Field label="From" optional><input className="input" type="date" value={from} onChange={(event) => setFrom(event.target.value)} /></Field>
            <Field label="To" optional><input className="input" type="date" value={to} onChange={(event) => setTo(event.target.value)} /></Field>
            <Field label="As of" optional><input className="input" type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} /></Field>
          </FieldRow>
          <FormActions><Button type="submit">Apply period</Button></FormActions>
          <p className="muted">Default: last 12 calendar months including the current partial month. Maximum 732 days. Inventory and technical facts are current snapshots.</p>
        </form>
      </Disclosure>
    </div>
    <TabPanel group="Project analysis sections" tab={section}><AnalysisAnswer key={`${projectId}:${section}:${query}`} projectId={projectId} section={section} query={query} /></TabPanel>
  </section>;
}
