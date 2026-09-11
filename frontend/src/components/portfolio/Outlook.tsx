"use client";



import Link from "next/link";

import { pageOffset, useRegisterFields } from "@/components/shell/registerState";

import { Badge, Button, ButtonRow, Card, DataToolbar, Disclosure, Drawer, EmptyState, IdentityCell, KeyValue, KeyValueGrid, Metric, MetricGroup, Notice, Position, PositionFigure, SectionHeader, TableScroll, ToolbarFilter } from "@/components/ui";

import { ReadState } from "./ReadState";
import { useAnswer } from "@/lib/answer";

import { management } from "@/lib/api/management";

import type { OutlookItem } from "@/lib/api/management";

import { businessDate, money } from "@/lib/format";

import { ProjectChoice } from "./ActionRecord";
import { SourceAction } from "./Actions";



const groups = [

  ["cashflow_forecast", "Cash and funding outlook"], ["scheduled_collection_due", "Contractual collections due"],

  ["commercial_sellout", "Commercial run-rate"], ["construction_eac", "Construction EAC"],

  ["permit_due", "Permit deadlines"], ["consultant_stage_due", "Design stage dates"],

  ["consultant_deliverable_due", "Design deliverables"], ["management_action_due", "Management commitments"],

];



function Observation({ item }: { item: OutlookItem }) {

  return <section className="stack" aria-label={`${item.project_code} ${item.title}`}>

    <SectionHeader title={`${item.project_code} · ${item.title}`} />

    <p className="muted">{item.project_name} · Observed {businessDate(item.observation_date)} {item.due_date ? `· Due ${businessDate(item.due_date)}` : ""}</p>

    {item.availability !== "available" ? <Notice tone="info">{item.availability} · {item.reason}</Notice> : null}

    {item.item_type === "cashflow_forecast" ? <Card tone="command" title="FORECAST · Unrestricted cash" description="Governed monthly positions; full boundary months.">

      <Position compact><PositionFigure lead label="Lowest projected position" value={item.amount !== null && item.currency ? money(item.amount, item.currency) : "Unavailable"} note={item.lowpoint_month ? `Low point · ${businessDate(item.lowpoint_month)}` : item.reason} />

        <PositionFigure label="Peak forecast deficit" value={item.peak_deficit !== null && item.currency ? money(item.peak_deficit, item.currency) : "Unavailable"} note={item.first_deficit_month ? `First deficit · ${businessDate(item.first_deficit_month)}` : item.availability === "available" ? "No deficit in reported months" : "Unavailable"} /></Position>

      <p>Forecast as of {item.source_as_of ? businessDate(item.source_as_of) : "Unavailable"} · Covers through {item.forecast_end_month ? businessDate(item.forecast_end_month) : "Unavailable"}</p>

    </Card> : item.commercial ? <Position compact><PositionFigure lead label="Estimated months to sell" value={item.commercial.estimated_months_to_sell ?? "Indeterminate"} note="Run-rate estimate · no predictive certainty" /><PositionFigure label="Remaining eligible units" value={item.commercial.remaining_units ?? "Unavailable"} /><PositionFigure label="Average monthly net absorption" value={item.commercial.average_monthly_absorption ?? "Unavailable"} note={`${item.commercial.observed_months} complete observed months`} /></Position>

      : item.item_type === "construction_eac" ? <Position compact><PositionFigure lead label="EAC · excluding tax" value={item.amount !== null && item.currency ? money(item.amount, item.currency) : "Unavailable"} /><PositionFigure label="Control budget · excluding tax" value={item.control_budget !== null && item.currency ? money(item.control_budget, item.currency) : "Unavailable"} /></Position>

        : item.currency && item.amount !== null ? <Metric label="SCHEDULED / CONTRACTUAL DUE" value={money(item.amount, item.currency)} note="Outstanding governing installment · not expected or actual cash" /> : <KeyValueGrid>

          {item.status ? <KeyValue label="Source status" value={item.status.replaceAll("_", " ")} /> : null}{item.blocking !== null ? <KeyValue label="Recorded blocker" value={item.blocking ? "Yes" : "No"} /> : null}

          {item.owner_display_name ? <KeyValue label="Owner" value={item.owner_display_name} /> : null}{item.planned_date ? <KeyValue label="Planned" value={businessDate(item.planned_date)} /> : null}{item.forecast_date ? <KeyValue label="Forecast date" value={businessDate(item.forecast_date)} /> : null}{item.actual_date ? <KeyValue label="Actual completion" value={businessDate(item.actual_date)} /> : null}

        </KeyValueGrid>}

    <Disclosure title="Source basis"><p>{item.basis}</p>{item.source_version_id ? <p className="cell-prose">Governing version {item.source_version_id}</p> : null}{item.commercial ? <p>Observation window {businessDate(item.commercial.window_from)}–{businessDate(item.commercial.window_to)} · Monthly net counts {item.commercial.monthly_net_absorption.join(", ")}</p> : null}</Disclosure>

    <ButtonRow><Link className="button button-small" href={item.drilldown}>Open source</Link>{item.availability !== "unavailable" && item.item_type !== "management_action_due" ? <SourceAction project={item.project_id} source={{ source_type: "portfolio_outlook", source_code: item.item_type, source_key: item.source_key, source_observation_date: item.observation_date }} /> : null}</ButtonRow>

  </section>;

}



export function PortfolioOutlook() {

  const [fields, change] = useRegisterFields({ project: "", horizon: "90", kind: "cashflow_forecast", offset: "", observation: "" });
  const project = fields.project;
  const horizon = [30, 60, 90].includes(Number(fields.horizon)) ? Number(fields.horizon) : 90;
  const kind = groups.some(([key]) => key === fields.kind) || fields.kind === "" ? fields.kind : "cashflow_forecast";
  const offset = pageOffset(fields.offset);
  const setHorizon = (horizon: number) => change({ horizon: String(horizon), observation: "" });
  const setKind = (kind: string) => change({ kind, observation: "" });
  const setOffset = (offset: number) => change({ offset: String(offset), observation: "" });
  const setSelected = (item: OutlookItem | null) => change({ observation: item?.source_key ?? "" });

  const answer = useAnswer(true, () => management.outlook(horizon, offset, kind, project), [horizon, offset, kind, project]);

  const selected = answer.status === "ready" ? answer.data.items.find(item => item.source_key === fields.observation) : null;

  return <div className="stack"><DataToolbar onReset={project || kind || horizon !== 90 || offset ? () => change({ project: "", horizon: "90", kind: "", offset: "", observation: "" }) : undefined} activeSummary={`${project ? "Selected development" : "All authorized developments"} · ${horizon} days · ${groups.find(([key]) => key === kind)?.[1] ?? "Upcoming dates"}`}>

    <ProjectChoice value={project} onChange={project => change({ project, offset: "", observation: "" })} />
    <ToolbarFilter label="Outlook horizon"><select className="input" value={horizon} onChange={(event) => { setHorizon(Number(event.target.value)); setOffset(0); }}>{[30, 60, 90].map((days) => <option key={days} value={days}>{days} days</option>)}</select></ToolbarFilter>

    <ToolbarFilter label="Outlook source"><select className="input" value={kind} onChange={(event) => { setKind(event.target.value); setOffset(0); }}><option value="">All observations · date order</option>{groups.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></ToolbarFilter>

  </DataToolbar>

    {answer.status === "ready" ? <><p>As of {businessDate(answer.data.as_of)} through {businessDate(answer.data.horizon_end)} · {answer.data.authorized_project_count} authorized developments</p>

      <SectionHeader title={groups.find(([key]) => key === kind)?.[1] ?? "Upcoming dates and owner observations"} />

      <Notice tone="info">{kind === "cashflow_forecast" ? answer.data.cashflow_basis : answer.data.date_basis}</Notice>

      {kind === "scheduled_collection_due" ? <Card title="Contractual outstanding due" description="Original currencies · governing schedules · no cash assumption"><MetricGroup>{answer.data.currency_buckets.map((bucket) => <Metric key={bucket.currency} label={`${bucket.currency} · Scheduled due`} value={bucket.scheduled_outstanding_due === null ? "Unavailable" : money(bucket.scheduled_outstanding_due, bucket.currency)} note={`${bucket.availability} · ${bucket.contributing_project_count} contributing · ${bucket.unavailable_project_count} unavailable projects`} />)}</MetricGroup></Card> : null}

      {!answer.data.items.length ? <EmptyState title="No matching observations" hint="Missing sources and undated items remain visible in coverage below." /> : <TableScroll label="Forward outlook source register" stickyHeader fixedFirst><thead><tr><th scope="col">Development / source</th><th scope="col">Reported outlook</th><th scope="col">Date / period</th><th scope="col">Coverage</th><th scope="col">Inspect</th></tr></thead><tbody>{answer.data.items.map((item) => <tr key={item.source_key}>

        <th scope="row" className="cell-prose"><IdentityCell name={`${item.project_code} · ${item.project_name}`} meta={item.title} /></th>

        <td className="cell-prose"><span className="figure">{item.currency && item.amount !== null ? money(item.amount, item.currency) : item.commercial ? `${item.commercial.estimated_months_to_sell ?? "Indeterminate"} ${item.commercial.estimated_months_to_sell !== null ? "estimated months" : ""}` : item.availability === "unavailable" ? "Unavailable" : item.status?.replaceAll("_", " ") ?? "Recorded due date"}</span>{item.item_type === "cashflow_forecast" ? <p className="muted">FORECAST · lowest unrestricted cash</p> : item.item_type === "scheduled_collection_due" ? <p className="muted">SCHEDULED DUE · outstanding, not cash</p> : item.item_type === "construction_eac" ? <p className="muted">EAC · excluding tax</p> : null}{item.owner_display_name ? <p>{item.owner_display_name}</p> : null}</td>

        <td>{item.lowpoint_month ? <>Low point {businessDate(item.lowpoint_month)}<p className="muted">First deficit: {item.first_deficit_month ? businessDate(item.first_deficit_month) : "None"}</p></> : item.due_date ? businessDate(item.due_date) : item.source_as_of ? businessDate(item.source_as_of) : "See source basis"}</td>

        <td className="cell-prose"><Badge>{item.availability}</Badge>{item.reason ? <p className="muted">{item.reason}</p> : null}</td><td><Button small onClick={() => setSelected(item)}>Inspect outlook</Button></td>

      </tr>)}</tbody></TableScroll>}

      <ButtonRow><Button disabled={!offset} onClick={() => setOffset(offset - 20)}>Previous observations</Button><Button disabled={offset + 20 >= answer.data.total} onClick={() => setOffset(offset + 20)}>Next observations</Button><span>{answer.data.total} matching observations</span></ButtonRow>

      <Card title="Coverage and horizon basis"><p>{answer.data.date_basis}</p><p>{answer.data.cashflow_basis}</p><p>Unavailable does not mean zero or healthy. Upcoming dates do not imply new risk severity.</p>

        <Disclosure title="All source observation counts"><KeyValueGrid>{groups.map(([key, label]) => <KeyValue key={key} label={label} value={answer.data.summary_counts[key] ?? 0} />)}</KeyValueGrid></Disclosure>

        <ul>{answer.data.coverage.map((row) => <li key={row.source}><strong>{row.source.replaceAll("_", " ")}</strong> · {row.unavailable_project_count} unavailable projects · {row.undated_item_count} undated items<p>{row.reason}</p></li>)}</ul>

      </Card>

    </> : <ReadState answer={answer} label="Reading the authorized forward outlook…" />}

    {selected ? <Drawer title={selected.title} subtitle={`${selected.project_code} · ${selected.project_name}`} onClose={() => setSelected(null)}><Observation item={selected} /></Drawer> : null}

  </div>;

}
