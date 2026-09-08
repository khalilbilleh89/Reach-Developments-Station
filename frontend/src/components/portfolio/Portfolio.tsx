"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge, Button, ButtonRow, Card, EmptyState, KeyValue, KeyValueGrid, Loading, Metric, MetricGroup, Notice, SectionHeader, TableScroll } from "@/components/ui";
import { useAnswer } from "@/lib/answer";
import type { Answer } from "@/lib/answer";
import { portfolio } from "@/lib/api/portfolio";
import type { MoneyMetric, ProjectSummary, Risk } from "@/lib/api/portfolio";
import { money, businessDate } from "@/lib/format";

const labels: Record<string, string> = {
  contracted_value: "Contracted value", confirmed_receipts: "Confirmed receipts", refunds: "Refunds",
  unapplied_cash: "Unapplied confirmed cash", overdue_outstanding: "Overdue outstanding",
  total_cash: "Total actual cash", restricted_cash: "Restricted cash", unrestricted_cash: "Unrestricted cash",
  forecast_peak_deficit: "Forecast peak deficit", construction_control_budget: "Construction control budget",
  construction_eac: "Construction EAC", construction_commitment: "Construction commitment (ex tax)",
  construction_paid: "Construction paid (gross)", land_acquisition: "Land acquisition",
  commission_released: "Released commissions (non-cash)",
};

function Pending({ answer }: { answer: Answer<unknown> }) {
  if (answer.status === "denied" || answer.status === "off") return <Notice tone="info">Portfolio is not available to your role.</Notice>;
  if (answer.status === "failed") return <Notice tone="error">{answer.message}</Notice>;
  return <Loading label="Reading authorized portfolio…" shape="page" />;
}

function MetricValue({ row }: { row: MoneyMetric }) {
  return <><span className="figure">{row.amount === null ? `${row.currency} · Unavailable` : money(row.amount, row.currency)}</span>{row.availability !== "available" ? <p className="muted">{row.availability}: {row.reason}</p> : null}</>;
}

export function MoneyRegister({ rows }: { rows: MoneyMetric[] }) {
  return <TableScroll label="Portfolio monetary facts and source coverage"><thead><tr><th scope="col">Position</th><th scope="col">Amount</th><th scope="col">Coverage</th><th scope="col">Source</th></tr></thead><tbody>{rows.map((row) => <tr key={`${row.metric_code}:${row.currency}`}><th scope="row" className="cell-prose cell-prose-tight">{labels[row.metric_code] ?? row.metric_code}</th><td className="cell-prose"><MetricValue row={row} /></td><td>{row.contributing_project_count} contributing · {row.missing_project_count} missing</td><td className="cell-prose"><Link href={row.drilldown}>Inspect source</Link><p className="muted">{row.source_basis}</p>{row.source_version_id ? <p className="muted">Version {row.source_version_id}</p> : null}</td></tr>)}</tbody></TableScroll>;
}

export function RiskRegister({ rows }: { rows: Risk[] }) {
  if (!rows.length) return <Notice tone="info">No triggered risks in the available sources. Missing coverage is not a health assessment.</Notice>;
  return <TableScroll label="Deterministic portfolio risks"><thead><tr><th scope="col">Project / risk</th><th scope="col">Severity</th><th scope="col">Why it appears</th><th scope="col">Source</th></tr></thead><tbody>{rows.map((risk) => <tr key={risk.risk_id}><th scope="row" className="cell-prose cell-prose-tight"><Link href={`/portfolio/?project=${risk.project_id}`}>{risk.project_code} · {risk.project_name}</Link><p>{risk.title}</p></th><td><Badge tone={risk.severity === "high" ? "danger" : "warning"}>{risk.severity}</Badge></td><td className="cell-prose">{risk.reason}<p className="figure">{risk.currency ? `${risk.currency} ` : ""}{risk.source_value}</p><p className="muted">Observed {businessDate(risk.observation_date)}</p></td><td className="cell-prose"><Link href={risk.drilldown}>Open source</Link><p className="muted">{risk.basis}</p></td></tr>)}</tbody></TableScroll>;
}

export function PortfolioOverview() {
  const answer = useAnswer(true, portfolio.overview, []);
  if (answer.status !== "ready") return <Pending answer={answer} />;
  const data = answer.data;
  if (!data.project_count) return <EmptyState title="No whole-project access" hint="Portfolio includes only projects you can read in full. Selected-phase memberships do not contribute." />;
  return <>
    <Card tone="command" title="Portfolio position" description={`Current authorized state · ${businessDate(data.as_of)}`}><MetricGroup><Metric size="lg" label="Projects requiring attention" value={data.projects_requiring_attention} note={`${data.project_count} authorized projects`} /><Metric label="Eligible inventory" value={data.eligible_units} /><Metric label="Committed units" value={data.committed_units} /><Metric label="Active sold units" value={data.active_sold_units} /><Metric label="Sales penetration" value={data.sales_penetration.percentage === null ? "Unavailable" : `${data.sales_penetration.percentage}%`} note={`${data.sales_penetration.numerator} / ${data.sales_penetration.denominator} eligible units`} /></MetricGroup></Card>
    <Notice tone="info">{data.projects_with_incomplete_coverage} projects have incomplete source coverage. Amounts remain in their original currencies; partial sums exclude unavailable project amounts.</Notice>
    <Card title="Priority risks" flush><RiskRegister rows={data.priority_risks} /></Card>
    <Card title="Commercial, cash and development position" description="Source currency and coverage accompany every figure." flush><MoneyRegister rows={data.money} /></Card>
    <Card title="Risk evaluation coverage"><KeyValueGrid>{Object.entries(data.unavailable_risk_evaluations).map(([key, count]) => <KeyValue key={key} label={key.replaceAll("_", " ")} value={`${count} projects not fully evaluable`} />)}</KeyValueGrid></Card>
  </>;
}

function PageControls({ offset, total, count, onChange }: { offset: number; total: number; count: number; onChange: (value: number) => void }) {
  return <ButtonRow><Button variant="default" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - 20))}>Previous</Button><span>{count} shown · {total} total</span><Button variant="default" disabled={offset + 20 >= total} onClick={() => onChange(offset + 20)}>Next</Button></ButtonRow>;
}

function ProjectMoney({ project, code }: { project: ProjectSummary; code: string }) {
  return <>{project.money.filter((row) => row.metric_code === code).map((row) => <div key={row.currency}><MetricValue row={row} /></div>)}</>;
}

function ProjectRows({ offset, onChange }: { offset: number; onChange: (value: number) => void }) {
  const answer = useAnswer(true, () => portfolio.projects(offset), [offset]);
  if (answer.status !== "ready") return <Pending answer={answer} />;
  const data = answer.data;
  return <Card title="Authorized projects" flush><TableScroll label="Portfolio projects"><thead><tr>{["Project", "Inventory", "Commercial", "Confirmed receipts", "Unrestricted cash", "Construction EAC", "Risks / coverage"].map((label) => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{data.items.map((project) => <tr key={project.project_id}><th scope="row" className="cell-prose cell-prose-tight"><Link href={`/portfolio/?project=${project.project_id}`}>{project.code} · {project.name}</Link><p>{project.status} · {project.currency}</p></th><td>{project.eligible_units} eligible<p>{project.committed_units} committed</p><p>{project.active_sold_units} active sold</p></td><td>{project.sales_penetration.percentage === null ? "Unavailable" : `${project.sales_penetration.percentage}%`}<p>{project.sales_penetration.numerator} / {project.sales_penetration.denominator}</p></td><td><ProjectMoney project={project} code="confirmed_receipts" /></td><td><ProjectMoney project={project} code="unrestricted_cash" /></td><td><ProjectMoney project={project} code="construction_eac" /></td><td>{project.risk_count} risks · {project.highest_risk ?? "No triggered risk"}<p>Coverage: {project.coverage}</p><Link href={project.drilldown}>Open project</Link></td></tr>)}</tbody></TableScroll>{!data.items.length ? <Notice tone="info">No authorized whole-project records on this page.</Notice> : null}<PageControls offset={offset} total={data.total} count={data.items.length} onChange={onChange} /></Card>;
}

export function PortfolioProjects() {
  const [offset, setOffset] = useState(0);
  return <ProjectRows key={offset} offset={offset} onChange={setOffset} />;
}

function RiskRows({ offset, onChange }: { offset: number; onChange: (value: number) => void }) {
  const answer = useAnswer(true, () => portfolio.risks(offset), [offset]);
  if (answer.status !== "ready") return <Pending answer={answer} />;
  const data = answer.data;
  return <><Notice tone="info">{data.unavailable_project_count} projects have risk evaluations with unavailable coverage.</Notice><Card title="Management risks" flush><RiskRegister rows={data.items} /><PageControls offset={offset} total={data.total} count={data.items.length} onChange={onChange} /></Card></>;
}

export function PortfolioRisks() {
  const [offset, setOffset] = useState(0);
  return <RiskRows key={offset} offset={offset} onChange={setOffset} />;
}

export function PortfolioProject({ id }: { id: string }) {
  const answer = useAnswer(true, () => portfolio.project(id), [id]);
  if (answer.status !== "ready") return <Pending answer={answer} />;
  const project = answer.data;
  return <><SectionHeader title={`${project.code} · ${project.name}`} /><p>{project.status} · {project.currency} · {businessDate(project.as_of)} · Coverage: {project.coverage}</p><Link href={project.drilldown}>Open project workspace</Link>
    {project.cashflow_reason_code ? <Notice tone="warning">Cashflow unavailable: source currency mismatch. Observed currencies: {project.cashflow_observed_currencies.join(", ")}. No partial cash balance is reported.</Notice> : null}
    <Card tone="command" title="Commercial position"><MetricGroup><Metric label="Eligible units" value={project.eligible_units} /><Metric label="Committed" value={project.committed_units} /><Metric label="Active sold" value={project.active_sold_units} /><Metric label="Sales penetration" value={project.sales_penetration.percentage === null ? "Unavailable" : `${project.sales_penetration.percentage}%`} /><Metric label="Net sales / month" value={project.sales_run_rate.average_monthly_absorption ?? "Unavailable"} note="Three complete UTC months" /></MetricGroup></Card>
    <Card title="Project risks" flush><RiskRegister rows={project.risks} /></Card><Card title="Source positions" flush><MoneyRegister rows={project.money} /></Card>
    <Card title="Design and permits"><KeyValueGrid><KeyValue label="Permits recorded" value={project.permit_count} /><KeyValue label="Consultant" value={project.design.consultant_name ?? "Unavailable"} /><KeyValue label="Current stage" value={project.design.current_stage ?? "Unavailable"} /><KeyValue label="Stage status" value={project.design.stage_status} /><KeyValue label="Planned / forecast date" value={`${businessDate(project.design.planned_date)} / ${businessDate(project.design.forecast_date)}`} /><KeyValue label="Design coverage" value={`${project.design.availability}: ${project.design.reason ?? "Recorded programme"}`} /></KeyValueGrid></Card>
    <Card title="Risk evaluation basis"><KeyValueGrid>{project.risk_evaluations.map((row) => <KeyValue key={row.risk_code} label={row.risk_code.replaceAll("_", " ")} value={`${row.availability}${row.reason ? ` · ${row.reason}` : ""}`} />)}</KeyValueGrid></Card>
  </>;
}
