"use client";

import { Disclosure, KeyValue, KeyValueGrid, Notice, Position, PositionFigure, SectionHeader, TableScroll } from "@/components/ui";
import type { MoneyMetric, ProjectSummary } from "@/lib/api/portfolio";
import type { BoardPack, Comparison, Movement, Snapshot } from "@/lib/api/reporting";
import { businessDate, eventTime, money } from "@/lib/format";

const label = (value: string) => value.replaceAll("_", " ");
const moneyValue = (amount: string | null, currency: string | null) => amount === null ? "Unavailable" : currency ? money(amount,currency) : amount;

function DevelopmentFacts({ snapshot }: { snapshot: Snapshot }) {
  return <section className="reporting-section">
    <SectionHeader title="Captured permit and design records" />
    <TableScroll label="Immutable development records">
      <thead><tr><th scope="col">Project / record</th><th scope="col">Captured status</th><th scope="col">Dates</th></tr></thead>
      <tbody>{snapshot.payload.development.map(f => <tr key={`${f.kind}:${f.source_id}`}>
        <th scope="row" className="cell-prose">{snapshot.payload.projects.find(p => p.project_id === f.project_id)?.code} · {f.label}<p>{label(f.kind)}</p></th>
        <td className="cell-prose">{label(f.status)}{f.blocking !== null ? <p>{f.blocking ? "Blocking permit" : "Non-blocking permit"}</p> : null}</td>
        <td className="cell-prose">Due {businessDate(f.due_date)}<p>Planned {businessDate(f.planned_date)}</p><p>Forecast {businessDate(f.forecast_date)}</p><p>Actual {businessDate(f.actual_date)}</p></td>
      </tr>)}</tbody>
    </TableScroll>
    {!snapshot.payload.development.length ? <p>No development records were present at capture.</p> : null}
  </section>;
}

function FrozenMoney({ rows, title }: { rows: MoneyMetric[]; title: string }) {
  return <TableScroll label={title}><thead><tr><th scope="col">Position</th><th scope="col">Captured amount</th><th scope="col">Coverage / basis</th></tr></thead><tbody>{rows.map(m=><tr key={`${m.metric_code}:${m.currency}`}><th scope="row">{label(m.metric_code)}</th><td className="figure">{moneyValue(m.amount,m.currency)}</td><td className="cell-prose">{m.availability} · {m.contributing_project_count} contributing / {m.missing_project_count} missing<p>{m.reason}</p><p className="muted">{m.source_basis}</p>{m.source_version_id ? <p className="mono">Version {m.source_version_id}</p> : null}</td></tr>)}</tbody></TableScroll>;
}

function Executive({ snapshot }: { snapshot: Snapshot }) {
  const p=snapshot.payload.overview, a=snapshot.payload.action_counts;
  return <section className="reporting-executive"><SectionHeader title="Executive position" /><Position compact><PositionFigure lead label="Projects" value={snapshot.project_count} /><PositionFigure label="Committed / eligible" value={`${p.committed_units} / ${p.eligible_units}`} /><PositionFigure label="Active sold" value={p.active_sold_units} /><PositionFigure label="Source risks" value={p.risk_count} /><PositionFigure label="Overdue actions" value={a.overdue} /></Position><p>Sales penetration: {p.sales_penetration.percentage === null ? "Unavailable" : `${p.sales_penetration.percentage}%`} · {p.sales_penetration.availability}</p><p>{snapshot.incomplete_project_count} projects have incomplete source coverage. Unknown is not healthy.</p></section>;
}

function Projects({ snapshot }: { snapshot: Snapshot }) {
  return <section className="reporting-section"><SectionHeader title="Projects requiring attention" /><TableScroll label="Captured project attention"><thead><tr>{["Project", "Commercial", "Cash / funding", "Risk / coverage"].map(x=><th scope="col" key={x}>{x}</th>)}</tr></thead><tbody>{snapshot.payload.projects.map(p=>{const cash=p.money.find(m=>m.metric_code==="unrestricted_cash");return <tr key={p.project_id}><th scope="row" className="cell-prose">{p.code}<p>{p.name}</p></th><td>{p.committed_units} / {p.eligible_units} committed<p>{p.sales_penetration.percentage ?? "Unavailable"}{p.sales_penetration.percentage===null?"":"%"}</p></td><td className="cell-prose">{cash?moneyValue(cash.amount,cash.currency):"Unavailable"}<p>{cash?.reason}</p></td><td>{p.risk_count} source risks<p>{p.coverage}</p></td></tr>;})}</tbody></TableScroll></section>;
}

function Development({ projects }: { projects: ProjectSummary[] }) {
  return <section className="reporting-section"><SectionHeader title="Development, permits and design" /><TableScroll label="Captured development position"><thead><tr><th scope="col">Project</th><th scope="col">Permits</th><th scope="col">Active design programme</th><th scope="col">Source exceptions</th></tr></thead><tbody>{projects.map(p=><tr key={p.project_id}><th scope="row">{p.code}</th><td>{p.permit_count} recorded</td><td className="cell-prose">{p.design.consultant_name ?? "Unavailable"}<p>{p.design.current_stage} · {p.design.stage_status}</p><p>Planned {businessDate(p.design.planned_date)} · Forecast {businessDate(p.design.forecast_date)}</p><p>{p.design.availability} · {p.design.reason}</p></td><td className="cell-prose">{p.risks.filter(r=>r.category==="permits"||r.category==="design").map(r=><p key={r.risk_id}>{r.title}: {r.source_value}</p>)}</td></tr>)}</tbody></TableScroll></section>;
}

function Forward({ snapshot }: { snapshot: Snapshot }) {
  return <section className="reporting-section"><SectionHeader title="Forward outlook" description="What the forecast and contractual schedule said at capture; not later outcomes." />{snapshot.payload.outlooks.map(o=><Disclosure key={o.horizon_days} title={`${o.horizon_days}-day captured outlook`} context={`Through ${businessDate(o.horizon_end)} · ${o.total} observations`} open={o.horizon_days===90}>
    <p>{o.cashflow_basis}</p><TableScroll label={`${o.horizon_days}-day contractual currency positions`}><thead><tr><th scope="col">Original currency</th><th scope="col">Scheduled outstanding due</th><th scope="col">Coverage</th></tr></thead><tbody>{o.currency_buckets.map(b=><tr key={b.currency}><th scope="row">{b.currency}</th><td>{moneyValue(b.scheduled_outstanding_due,b.currency)}</td><td>{b.availability} · {b.unavailable_project_count} unavailable projects</td></tr>)}</tbody></TableScroll>
    <TableScroll label={`${o.horizon_days}-day historical observations`}><thead><tr><th scope="col">Project / observation</th><th scope="col">Date / period</th><th scope="col">Captured fact</th><th scope="col">Basis / coverage</th></tr></thead><tbody>{o.items.map(i=><tr key={i.source_key}><th scope="row" className="cell-prose">{i.project_code}<p>{i.title}</p></th><td>{businessDate(i.due_date ?? i.lowpoint_month)}{i.first_deficit_month?<p>First deficit {businessDate(i.first_deficit_month)}</p>:null}</td><td className="cell-prose">{i.currency?moneyValue(i.amount,i.currency):i.commercial?`${i.commercial.estimated_months_to_sell ?? "Unavailable"} months to sell`:i.status ?? i.availability}{i.peak_deficit!==null?<p>Peak deficit {moneyValue(i.peak_deficit,i.currency)}</p>:null}{i.control_budget!==null?<p>Control budget {moneyValue(i.control_budget,i.currency)}</p>:null}</td><td className="cell-prose">{i.availability}<p>{i.reason ?? i.basis}</p>{i.source_version_id?<p className="mono">Version {i.source_version_id}</p>:null}</td></tr>)}</tbody></TableScroll>
  </Disclosure>)}</section>;
}

function Actions({ snapshot }: { snapshot: Snapshot }) {
  const counts=snapshot.payload.action_counts;
  return <section className="reporting-section"><SectionHeader title="Management actions" /><p>{counts.open} open · {counts.in_progress} in progress · {counts.overdue} overdue · {counts.completed} completed at capture</p><p className="muted">Action completion and source-risk resolution are independent facts.</p><TableScroll label="Captured management action position"><thead><tr><th scope="col">Action / project</th><th scope="col">Owner</th><th scope="col">Due / state</th><th scope="col">Origin</th></tr></thead><tbody>{snapshot.payload.actions.filter(a=>a.status==="open"||a.status==="in_progress").map(a=><tr key={a.id}><th scope="row" className="cell-prose">{a.title}<p>{snapshot.payload.projects.find(p=>p.project_id===a.project_id)?.code}</p></th><td>{a.owner.display_name}</td><td>{businessDate(a.due_date)}<p>{label(a.status)}</p></td><td>{label(a.source_type)}<p>{a.source_code}</p></td></tr>)}</tbody></TableScroll></section>;
}

function Coverage({ snapshot }: { snapshot: Snapshot }) {
  return <section className="reporting-section"><SectionHeader title="Coverage and data limitations" description="These limitations are frozen. A later source correction does not repair an earlier snapshot." /><TableScroll label="Historical source coverage"><thead><tr><th scope="col">Project</th><th scope="col">Source check</th><th scope="col">Availability / reason</th></tr></thead><tbody>{snapshot.payload.projects.flatMap(p=>p.risk_evaluations.filter(e=>e.availability!=="available").map(e=><tr key={`${p.project_id}:${e.risk_code}`}><th scope="row">{p.code}</th><td>{label(e.risk_code)}</td><td className="cell-prose">{e.availability}: {e.reason}</td></tr>))}</tbody></TableScroll>{snapshot.payload.outlooks.map(o=><p key={o.horizon_days}>{o.horizon_days} days: {o.coverage.filter(c=>c.unavailable_project_count||c.undated_item_count).map(c=>`${label(c.source)} — ${c.unavailable_project_count} unavailable projects; ${c.undated_item_count} undated items. ${c.reason}`).join(" ") || "No additional horizon coverage gaps."}</p>)}</section>;
}

export function HistoricalPosition({ snapshot }: { snapshot: Snapshot }) {
  return <div className="reporting-document"><Executive snapshot={snapshot} /><Projects snapshot={snapshot} /><section className="reporting-section"><SectionHeader title="Captured financial position" /><FrozenMoney title="Historical monetary position" rows={snapshot.payload.overview.money} /></section><Development projects={snapshot.payload.projects} /><DevelopmentFacts snapshot={snapshot} /><Forward snapshot={snapshot} /><Actions snapshot={snapshot} /><Coverage snapshot={snapshot} /></div>;
}

function movementValue(row: Movement, value: string | null, currency = row.currency) {
  if (value===null) return "Unavailable";
  return row.unit==="money" ? moneyValue(value,currency) : `${value}${row.unit==="percentage_points"?" pp":row.unit==="count"?"":` ${label(row.unit)}`}`;
}

export function ComparisonReport({ comparison: c }: { comparison: Comparison }) {
  return <section className="reporting-section"><SectionHeader title="Changes since prior snapshot" description={`${eventTime(c.prior.captured_at)} → ${eventTime(c.current.captured_at)}`} /><Notice tone="info">{c.composition_changed?"Portfolio composition changed. Portfolio financial/count deltas are withheld; compare common projects below.":"Same captured project scope. Numeric deltas still require compatible currency, basis and source coverage."}</Notice><KeyValueGrid><KeyValue label="Added to scope" value={c.added_projects.map(p=>`${p.code} · ${p.name}`).join(", ")||"None"} /><KeyValue label="Removed from scope" value={c.removed_projects.map(p=>`${p.code} · ${p.name}`).join(", ")||"None"} /></KeyValueGrid>
    <TableScroll label="Authoritative snapshot movements"><thead><tr><th scope="col">Project / measure</th><th scope="col">Prior</th><th scope="col">Current</th><th scope="col">Change / comparability</th></tr></thead><tbody>{c.movements.map((m,i)=><tr key={i}><th scope="row" className="cell-prose">{m.project_code ?? "Portfolio"}<p>{label(m.metric)}</p></th><td>{movementValue(m,m.prior,m.prior_currency)}<p className="muted">{m.prior_availability}</p></td><td>{movementValue(m,m.current,m.current_currency)}<p className="muted">{m.current_availability}</p></td><td className="cell-prose">{m.comparable?movementValue(m,m.delta):"Not comparable"}<p>{m.reason}</p><p className="muted">{m.basis}</p></td></tr>)}</tbody></TableScroll>
    <SectionHeader title="Exceptions: new, resolved and continuing" /><TableScroll label="Historical risk changes"><thead><tr><th scope="col">Source exception</th><th scope="col">Classification</th><th scope="col">Prior evidence</th><th scope="col">Current evidence</th></tr></thead><tbody>{c.risks.map((r,i)=><tr key={i}><th scope="row" className="cell-prose">{(r.current??r.prior)?.project_code} · {(r.current??r.prior)?.title}</th><td>{r.classification==="resolved"?"Resolved source exception":label(r.classification)}<p>{r.reason}</p></td><td className="cell-prose">{r.prior?.reason ?? "Not observed"}</td><td className="cell-prose">{r.current?.reason ?? "Not observed"}</td></tr>)}</tbody></TableScroll>
    <SectionHeader title="Management execution in the interval" /><p>{c.execution.created} created · {c.execution.started} started · {c.execution.completed} completed · {c.execution.reopened} reopened · {c.execution.cancelled} cancelled</p><p>Overdue: {c.execution.prior_overdue} prior → {c.execution.current_overdue} current</p><p className="footnote">{c.execution.basis}</p>
    <Disclosure title="Source versions, dates and coverage changes" open><TableScroll label="Captured source fact comparison"><thead><tr><th scope="col">Project / fact</th><th scope="col">Prior</th><th scope="col">Current</th></tr></thead><tbody>{c.facts.filter(f=>f.prior!==f.current).map((f,i)=><tr key={i}><th scope="row" className="cell-prose">{f.project_code} · {label(f.fact)}</th><td className="cell-prose">{f.prior ?? "Unavailable"}</td><td className="cell-prose">{f.current ?? "Unavailable"}</td></tr>)}</tbody></TableScroll></Disclosure>
  </section>;
}

export function BoardReport({ pack }: { pack: BoardPack }) {
  const s=pack.snapshot;
  const sections: [string,string[]][] = [["Commercial",["contracted_value"]],["Collections",["confirmed_receipts","refunds","unapplied_cash","overdue_outstanding"]],["Cash and funding",["total_cash","unrestricted_cash","restricted_cash","forecast_peak_deficit"]],["Construction cost control",["construction_control_budget","construction_eac","construction_commitment","construction_paid"]]];
  return <div className="reporting-document"><p className="footnote">{pack.historical_notice}</p><Executive snapshot={s} />{pack.comparison?<ComparisonReport comparison={pack.comparison} />:<section className="reporting-section"><SectionHeader title="Changes since prior snapshot" /><p>No comparator selected. This report presents the captured position only.</p></section>}<Projects snapshot={s} />{sections.map(([title,codes])=><section className="reporting-section" key={title}><SectionHeader title={title} /><FrozenMoney title={`Board ${title}`} rows={s.payload.overview.money.filter(m=>codes.includes(m.metric_code))} />{title==="Commercial"?<TableScroll label="Board commercial run rates"><thead><tr><th scope="col">Project</th><th scope="col">Remaining eligible</th><th scope="col">Average monthly absorption</th><th scope="col">Estimated months to sell</th><th scope="col">Coverage</th></tr></thead><tbody>{s.payload.projects.map(p=><tr key={p.project_id}><th scope="row">{p.code}</th><td>{p.remaining_units}</td><td>{p.sales_run_rate.average_monthly_absorption ?? "Unavailable"}</td><td>{p.sales_run_rate.estimated_months_to_sell ?? "Unavailable"}</td><td className="cell-prose">{p.sales_run_rate.availability}: {p.sales_run_rate.reason}</td></tr>)}</tbody></TableScroll>:null}</section>)}<Development projects={s.payload.projects} /><DevelopmentFacts snapshot={s} /><Forward snapshot={s} /><Actions snapshot={s} /><Coverage snapshot={s} /><section className="reporting-section"><SectionHeader title="Project appendix" />{s.payload.projects.map(p=><Disclosure key={p.project_id} title={`${p.code} · ${p.name}`} context={`${p.status} · ${p.currency} · ${p.coverage}`} open><p>{p.committed_units} committed / {p.eligible_units} eligible · {p.active_sold_units} active sold · {p.risk_count} risks</p><FrozenMoney title={`${p.code} captured capital`} rows={p.money} />{p.risks.map(r=><p key={r.risk_id}>{r.severity}: {r.reason}</p>)}<p>{p.design.current_stage} · Planned {businessDate(p.design.planned_date)} · Forecast {businessDate(p.design.forecast_date)}</p></Disclosure>)}</section></div>;
}
