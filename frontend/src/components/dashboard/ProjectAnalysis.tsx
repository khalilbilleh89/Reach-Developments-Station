"use client";

import { useState } from "react";
import { useAnswer } from "@/lib/answer";
import { projectAnalysis } from "@/lib/api/analysis";
import type { Availability, Context, Demand, Fundamental, Financial, Technical, Money, Ranking, Ratio, Section } from "@/lib/api/analysis";
import { ANALYSIS_FINANCIAL_READERS, ANALYSIS_FUNDAMENTAL_READERS, ANALYSIS_TECHNICAL_READERS, hasAnyRole } from "@/lib/roles";
import type { Roles } from "@/lib/roles";
import { businessDate, money } from "@/lib/format";
import { Button, ButtonRow, Card, Loading, Notice, TableScroll } from "@/components/ui";

const labels = { fundamental: "Fundamental", financial: "Financial", technical: "Technical" };
const readers = { fundamental: ANALYSIS_FUNDAMENTAL_READERS, financial: ANALYSIS_FINANCIAL_READERS, technical: ANALYSIS_TECHNICAL_READERS };
const display = (value: string) => value.replaceAll("_", " ");
const percentage = (value: Ratio) => value.percentage === null ? "Unavailable" : `${value.percentage}% (${value.numerator} / ${value.denominator})`;
const amounts = (values: Money[]) => values.length ? values.map((value) => money(value.amount, value.currency)).join(" · ") : "No sale activations";

function Basis({ value }: { value: Availability }) {
  return <p className="muted">{value.availability === "available" ? "Available" : value.availability === "partial" ? "Partial coverage" : "Unavailable"} · Sample: {value.sample_size}. {value.reason} {value.source_basis}</p>;
}
function Counts({ values, label }: { values: Record<string, number>; label: string }) {
  return <TableScroll label={label} compact><thead><tr><th>{label}</th><th>Count</th></tr></thead><tbody>{Object.entries(values).map(([name, count]) => <tr key={name}><th scope="row">{display(name)}</th><td>{count}</td></tr>)}</tbody></TableScroll>;
}
function ContextNote({ context }: { context: Context }) {
  return <p className="muted">As of {businessDate(context.as_of)} · Period {businessDate(context.period_from)} to {businessDate(context.period_to)} · Current record snapshot {businessDate(context.snapshot_as_of)} · Whole project · Project currency {context.currency}; transaction currencies shown separately.</p>;
}
function DemandTable({ rows, title }: { rows: Demand[]; title: string }) {
  return <details><summary>{title}</summary><TableScroll label={title}><thead><tr><th>Classification</th><th>Inventory</th><th>Standing period sales</th><th>Demand share</th><th>Penetration within group</th></tr></thead><tbody>{rows.map((row) => <tr key={row.label}><th scope="row">{row.label}</th><td>{row.inventory_count}</td><td>{row.sales_count}</td><td>{percentage(row.demand_share)}</td><td>{percentage(row.penetration)}</td></tr>)}</tbody></TableScroll><p className="muted">Demand share uses standing period sales on eligible inventory. Penetration uses eligible inventory within each group. Unknown classifications remain in the population.</p></details>;
}
function RankingTable({ rows, title }: { rows: Ranking[]; title: string }) {
  return <details><summary>{title}</summary><p className="muted">Ranked by standing activated sales count within the selected period, then contracted value only when currencies are comparable. Unassigned sales remain visible.</p><TableScroll label={title}><thead><tr><th>{title}</th><th>Sales / sample</th><th>Contracted value</th><th>Share</th></tr></thead><tbody>{rows.map((row) => <tr key={row.source_key ?? "unassigned"}><th scope="row">{row.label}</th><td>{row.sales_count}</td><td>{amounts(row.contracted_value)}</td><td>{percentage(row.share)}</td></tr>)}</tbody></TableScroll></details>;
}
function FundamentalView({ data }: { data: Fundamental }) {
  const p = data.position, f = data.forecast;
  return <div className="stack"><ContextNote context={data.context} />
    {p.availability === "available" ? <div className="analysis-headlines"><p><strong>{p.remaining_units}</strong><span>Remaining eligible units</span></p><p><strong>{percentage(p.penetration)}</strong><span>Commercial penetration</span></p><p><strong>{p.available_units}</strong><span>Available units</span></p><p><strong>{p.active_sold_units}</strong><span>Active sold units</span></p></div> : <Notice tone="info">{p.reason}</Notice>}
    <Basis value={p} />
    <section><h3>Run-rate sellout estimate</h3><p>{f.estimated_months_to_sell === null ? "Unavailable" : `${f.estimated_months_to_sell} months`} · {f.average_monthly_absorption ?? "Unavailable"} net units/month</p><p className="muted">{businessDate(f.window_from)} to {businessDate(f.window_to)} · {f.observed_months} complete observed months · Net absorption: {f.monthly_net_absorption.join(", ")}</p><Basis value={f} /></section>
    <details><summary>Monthly selling demand</summary><Basis value={data.sales_basis} /><TableScroll label="Monthly selling demand"><thead><tr><th>Month</th><th>Activations</th><th>Cancellations</th><th>Net absorption</th><th>New contracted value</th></tr></thead><tbody>{data.monthly_sales.map((row) => <tr key={row.month}><th scope="row">{businessDate(row.month)}</th><td>{row.activations}</td><td>{row.cancellations}</td><td>{row.net_absorption}</td><td>{amounts(row.contracted_value)}</td></tr>)}</tbody></TableScroll></details>
    <details><summary>Independent unit status dimensions · {p.total_units} total records</summary><Counts label="Commercial" values={p.commercial} /><Counts label="Legal" values={p.legal} /><Counts label="Delivery" values={p.delivery} /><p>These are current record dimensions, not a single combined status.</p></details>
    <RankingTable title="Sales branches" rows={data.branches} /><RankingTable title="Salespeople" rows={data.salespeople} /><Basis value={data.ranking_basis} />
    <DemandTable title="Property type demand" rows={data.property_types} /><DemandTable title="View demand" rows={data.views} /><Basis value={data.view_basis} />
    <details><summary>Observed view premiums</summary>{data.observed_premiums.length ? data.observed_premiums.map((row) => <section key={`${row.property_type}-${row.view}`}><h4>{row.property_type} · {row.view}</h4><p>{row.percentage === null ? "Unavailable" : `${row.percentage}% observed premium`} · View sample {row.sample_size}, baseline sample {row.baseline_sample}</p><p>{row.baseline} {row.currency && row.area_unit ? `${row.view_price_per_gross_area ?? "Unavailable"} vs ${row.baseline_price_per_gross_area ?? "Unavailable"} ${row.currency}/${row.area_unit}` : null}</p><Basis value={row} /></section>) : <p>No comparable structured view cohorts recorded.</p>}</details>
  </div>;
}
function FinancialView({ data }: { data: Financial }) {
  return <div className="stack"><ContextNote context={data.context} /><p>{data.cash_scope}</p><p>Contracted sales value is demand, not cash. An uncollected contract balance is not automatically overdue.</p><Basis value={data.basis} /><TableScroll label="Sales demand versus actual cash"><thead><tr><th>Month / currency</th><th>New sales</th><th>Contracted value</th><th>Customer cash received</th><th>Project cash outflow</th><th>Net actual cash movement</th></tr></thead><tbody>{data.monthly.map((row) => <tr key={`${row.month}-${row.currency}`}><th scope="row">{businessDate(row.month)} · {row.currency}</th><td>{row.new_sales_count}</td><td>{money(row.contracted_sales_value, row.currency)}</td><td>{money(row.customer_cash_received, row.currency)}</td><td>{money(row.project_cash_outflow, row.currency)}</td><td>{money(row.net_actual_cash_movement, row.currency)}</td></tr>)}</tbody></TableScroll><details><summary>Refund and financing detail included in net cash</summary><TableScroll label="Refunds and financing"><thead><tr><th>Month / currency</th><th>Customer refunds</th><th>Financing in</th><th>Financing out</th></tr></thead><tbody>{data.monthly.map((row) => <tr key={`${row.month}-${row.currency}`}><th scope="row">{businessDate(row.month)} · {row.currency}</th><td>{money(row.customer_refunds, row.currency)}</td><td>{money(row.financing_inflow, row.currency)}</td><td>{money(row.financing_outflow, row.currency)}</td></tr>)}</tbody></TableScroll></details></div>;
}
function TechnicalView({ data }: { data: Technical }) {
  return <div className="stack"><ContextNote context={data.context} /><h3>Recorded technical product profile</h3><Basis value={data.basis} /><Counts values={data.product_types} label="Property types" /><details><summary>Physical area ranges</summary><Basis value={data.area_coverage} /><TableScroll label="Approved physical areas"><thead><tr><th>Component</th><th>Measure</th><th>Minimum</th><th>Maximum</th><th>Average</th><th>Sample</th></tr></thead><tbody>{data.areas.map((row) => <tr key={`${row.component}-${row.unit_of_measure}`}><th scope="row">{display(row.component)}</th><td>{row.unit_of_measure}</td><td>{row.minimum}</td><td>{row.maximum}</td><td>{row.average}</td><td>{row.sample_size}</td></tr>)}</tbody></TableScroll><p>Gross uses all six approved physical components. Parking and storage are separate attachments.</p></details><details><summary>Features and attachments</summary><p>Feature coverage {percentage(data.feature_coverage)}</p><Counts label="Recorded features" values={data.features} /><Counts label="Attachments" values={data.attachments} /></details><details><summary>Permits · Obtained / Issued</summary><Basis value={data.permit_basis} /><Counts label="Statutory permit status" values={data.permits} /></details><details><summary>Consultant design context</summary><Basis value={data.consultant_basis} />{Object.entries(data.consultant).map(([key, value]) => <p key={key}>{display(key)}: {value ?? "Not recorded"}</p>)}</details><details><summary>Physical construction progress</summary><Basis value={data.construction_basis} /><TableScroll label="Construction stages"><thead><tr><th>Stage</th><th>Completed units</th><th>Units in scope</th></tr></thead><tbody>{data.construction_stages.map((row) => <tr key={row.name}><th scope="row">{row.name}</th><td>{row.completed_units}</td><td>{row.denominator}</td></tr>)}</tbody></TableScroll></details></div>;
}
function AnalysisAnswer({ projectId, section, query }: { projectId: string; section: Section; query: string }) {
  const answer = useAnswer<Fundamental | Financial | Technical>(true, () => projectAnalysis[section](projectId, query), [projectId, section, query]);
  if (answer.status === "denied") return <Notice tone="info">Not authorized: whole-project access and the appropriate Analysis role are required.</Notice>;
  if (answer.status === "failed") return <Notice tone="info">Analysis could not be loaded. {answer.message}</Notice>;
  if (answer.status !== "ready") return <Loading label="Loading analysis" />;
  return section === "fundamental" ? <FundamentalView data={answer.data as Fundamental} /> : section === "financial" ? <FinancialView data={answer.data as Financial} /> : <TechnicalView data={answer.data as Technical} />;
}
export function ProjectAnalysis({ projectId, roles }: { projectId: string; roles: Roles }) {
  const enabled = (Object.keys(labels) as Section[]).filter((key) => hasAnyRole(roles, readers[key]));
  const [chosen, setChosen] = useState<Section | null>(null);
  const [from, setFrom] = useState(""); const [to, setTo] = useState(""); const [asOf, setAsOf] = useState("");
  const [query, setQuery] = useState("");
  const section = chosen && enabled.includes(chosen) ? chosen : enabled[0];
  if (!section) return null;
  return <Card title="Project Analysis" description="Fundamental demand, financial cash and recorded technical facts. Derived from the source registers."><div className="stack"><ButtonRow>{enabled.map((key) => <Button key={key} variant={section === key ? "primary" : "default"} aria-pressed={section === key} onClick={() => setChosen(key)}>{labels[key]}</Button>)}</ButtonRow><details><summary>Observation period</summary><form className="analysis-filters" onSubmit={(event) => { event.preventDefault(); const params = new URLSearchParams(); if (from) params.set("period_from", from); if (to) params.set("period_to", to); if (asOf) params.set("as_of", asOf); setQuery(params.size ? `?${params}` : ""); }}><label>From<input type="date" value={from} onChange={(event) => setFrom(event.target.value)} /></label><label>To<input type="date" value={to} onChange={(event) => setTo(event.target.value)} /></label><label>As of<input type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} /></label><Button type="submit">Apply period</Button><p className="muted">Default: last 12 calendar months including the current partial month. Maximum 732 days. Inventory and technical facts are current snapshots.</p></form></details><AnalysisAnswer key={`${projectId}:${section}:${query}`} projectId={projectId} section={section} query={query} /></div></Card>;
}
