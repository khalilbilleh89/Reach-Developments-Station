"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge, Button, ButtonRow, Card, DataToolbar, Disclosure, EmptyState, KeyValue, KeyValueGrid, Loading, Metric, MetricGroup, Notice, Position, PositionFigure, SectionHeader, ToolbarFilter } from "@/components/ui";
import { useAnswer } from "@/lib/answer";
import { management } from "@/lib/api/management";
import type { OutlookItem } from "@/lib/api/management";
import { businessDate, money } from "@/lib/format";
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

export function PortfolioOutlook({ project }: { project?: string }) {
  const [horizon, setHorizon] = useState(90);
  const [kind, setKind] = useState("cashflow_forecast");
  const [offset, setOffset] = useState(0);
  const answer = useAnswer(true, () => management.outlook(horizon, offset, kind, project), [horizon, offset, kind, project]);
  return <div className="stack"><DataToolbar activeSummary={`${horizon} days · ${groups.find(([key]) => key === kind)?.[1] ?? "Upcoming dates"}`}>
    <ToolbarFilter label="Outlook horizon"><select value={horizon} onChange={(event) => { setHorizon(Number(event.target.value)); setOffset(0); }}>{[30, 60, 90].map((days) => <option key={days} value={days}>{days} days</option>)}</select></ToolbarFilter>
    <ToolbarFilter label="Outlook source"><select value={kind} onChange={(event) => { setKind(event.target.value); setOffset(0); }}><option value="">All observations · date order</option>{groups.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></ToolbarFilter>
  </DataToolbar>
    {answer.status === "ready" ? <><p>As of {businessDate(answer.data.as_of)} through {businessDate(answer.data.horizon_end)} · {answer.data.authorized_project_count} authorized developments</p>
      <div className="stack"><SectionHeader title="Forward management view" /><ButtonRow>{groups.map(([key, label]) => <Button key={key} variant={kind === key ? "primary" : "quiet"} onClick={() => { setKind(key); setOffset(0); }}>{label} <Badge>{answer.data.summary_counts[key] ?? 0}</Badge></Button>)}</ButtonRow></div>
      {kind === "scheduled_collection_due" ? <Card title="Contractual outstanding due" description="Original currencies · governing schedules · no cash assumption"><MetricGroup>{answer.data.currency_buckets.map((bucket) => <Metric key={bucket.currency} label={`${bucket.currency} · Scheduled due`} value={money(bucket.scheduled_outstanding_due, bucket.currency)} note={`${bucket.contributing_project_count} contributing · ${bucket.unavailable_project_count} unavailable projects`} />)}</MetricGroup></Card> : null}
      {!answer.data.items.length ? <EmptyState title="No matching observations" hint="Missing sources and undated items remain visible in coverage below." /> : answer.data.items.map((item) => <Observation key={item.source_key} item={item} />)}
      <ButtonRow><Button disabled={!offset} onClick={() => setOffset(offset - 20)}>Previous observations</Button><Button disabled={offset + 20 >= answer.data.total} onClick={() => setOffset(offset + 20)}>Next observations</Button><span>{answer.data.total} matching observations</span></ButtonRow>
      <Card title="Coverage and horizon basis"><p>{answer.data.date_basis}</p><p>{answer.data.cashflow_basis}</p><p>Unavailable does not mean zero or healthy. Upcoming dates do not imply new risk severity.</p>
        <ul>{answer.data.coverage.map((row) => <li key={row.source}><strong>{row.source.replaceAll("_", " ")}</strong> · {row.unavailable_project_count} unavailable projects · {row.undated_item_count} undated items<p>{row.reason}</p></li>)}</ul>
      </Card>
    </> : answer.status === "failed" ? <Notice tone="error">{answer.message}</Notice> : <Loading label="Reading the authorized forward outlook…" />}
  </div>;
}
