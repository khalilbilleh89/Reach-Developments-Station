"use client";

import Link from "next/link";
import { useState } from "react";
import { AttentionList, Badge, Button, ButtonRow, Card, Disclosure, EmptyState, IdentityCell, KeyValue, KeyValueGrid, Loading, Meter, Metric, MetricGroup, Notice, Position, PositionFigure, PositionSupport, PositionSupportItem, SectionHeader, TableScroll } from "@/components/ui";
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
  return <AttentionList detailed items={rows.map((risk) => ({
    key: risk.risk_id,
    title: risk.title,
    reason: risk.reason,
    severity: risk.severity === "high" ? "High" : "Attention",
    tone: risk.severity === "high" ? "danger" : "warning",
    category: risk.category.replaceAll("_", " "),
    context: <Link href={`/portfolio/?project=${risk.project_id}`}>{risk.project_code} · {risk.project_name}</Link>,
    evidence: <><span className={risk.currency ? "figure" : undefined}>{risk.currency ? money(risk.source_value, risk.currency) : risk.source_value}</span><span>Observed {businessDate(risk.observation_date)}</span></>,
    source: <Disclosure title="Source basis"><p>{risk.basis}</p></Disclosure>,
    action: <Link className="button button-small" href={risk.drilldown}>Open source</Link>,
  }))} />;
}

/** Select exact source records by denomination; never total the visible rows. */
function CapitalBands({ rows }: { rows: MoneyMetric[] }) {
  const currencies = [...new Set(rows.map((row) => row.currency))];
  const codes = ["contracted_value", "confirmed_receipts", "unrestricted_cash", "construction_eac"];
  return <div className="capital-bands">{currencies.map((currency) => <section className="capital-band" key={currency} aria-label={`${currency} capital position`}>
    <div className="capital-denomination"><span>{currency}</span><p>Original currency</p></div>
    <MetricGroup>{codes.map((code) => {
      const row = rows.find((entry) => entry.currency === currency && entry.metric_code === code);
      if (!row) return null;
      return <Metric key={code} label={labels[code]} value={row.amount === null ? "Unavailable" : money(row.amount, row.currency)}
        note={<><span>{row.availability === "available" ? `${row.contributing_project_count} contributing projects` : `${row.availability} · ${row.reason}`}</span><Link href={row.drilldown}>Inspect source</Link></>} />;
    })}</MetricGroup>
  </section>)}</div>;
}

export function PortfolioOverview() {
  const answer = useAnswer(true, portfolio.overview, []);
  if (answer.status !== "ready") return <Pending answer={answer} />;
  const data = answer.data;
  if (!data.project_count) return <EmptyState title="No whole-project access" hint="Portfolio includes only projects you can read in full. Selected-phase memberships do not contribute." />;
  return <>
    <Card tone="command" title="Portfolio position" description={`Across authorized developments · ${businessDate(data.as_of)}`}>
      <Position compact>
        <PositionFigure lead label="Developments" value={data.project_count} note="Whole-project access" />
        <PositionFigure label="Requiring attention" value={data.projects_requiring_attention} note={`${data.risk_count} triggered risks`} />
        <PositionFigure label="Eligible inventory" value={data.eligible_units} />
        <PositionFigure label="Active sold units" value={data.active_sold_units} />
      </Position>
      <div className="portfolio-penetration">
        <div><p className="metric-label">Sales penetration</p><p className="metric-note">{data.sales_penetration.numerator} / {data.sales_penetration.denominator} eligible units · {data.sales_penetration.availability}</p></div>
        {data.sales_penetration.percentage === null ? <span>Unavailable · {data.sales_penetration.reason}</span> : <Meter neutral percent={data.sales_penetration.percentage} label={`Sales penetration ${data.sales_penetration.percentage}%`} />}
      </div>
      <PositionSupport>
        <PositionSupportItem label="Committed units" value={data.committed_units} />
        <PositionSupportItem label="Incomplete coverage" value={`${data.projects_with_incomplete_coverage} projects`} />
        <Link href="/portfolio/?section=projects">Explore developments →</Link>
      </PositionSupport>
    </Card>
    <Card title="Needs attention" description="Reported risks, with the reason and a route to the source." actions={<Link href="/portfolio/?section=risks">All risks →</Link>}>
      <RiskRegister rows={data.priority_risks} />
    </Card>
    <section className="stack" aria-label="Commercial and capital position">
      <SectionHeader title="Commercial and capital position" />
      <Notice tone="info">{data.projects_with_incomplete_coverage} projects have incomplete source coverage. Amounts remain in their original currencies; partial sums exclude unavailable project amounts.</Notice>
      <CapitalBands rows={data.money} />
      <Disclosure title="All source positions" context="Commercial · collections · cash · construction · land"><MoneyRegister rows={data.money} /></Disclosure>
    </section>
    <Disclosure title="Risk evaluation coverage" context="Unavailable is not a health assessment">
      <KeyValueGrid>{Object.entries(data.unavailable_risk_evaluations).map(([key, count]) => <KeyValue key={key} label={key.replaceAll("_", " ")} value={`${count} projects not fully evaluable`} />)}</KeyValueGrid>
      <p className="footnote">{data.source_basis}</p>
    </Disclosure>
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
  return <Card title="Authorized projects" flush><TableScroll label="Portfolio projects" fixedFirst stickyHeader><thead><tr>{["Project", "Inventory", "Commercial", "Confirmed receipts", "Unrestricted cash", "Construction EAC", "Risks / coverage"].map((label) => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{data.items.map((project) => <tr key={project.project_id}><th scope="row" className="cell-prose cell-prose-tight"><Link className="button-link" href={`/portfolio/?project=${project.project_id}`}><IdentityCell icon="projects" name={project.name} meta={project.code} /></Link><p><Badge>{project.status.replaceAll("_", " ")}</Badge> · {project.currency}</p></th><td>{project.eligible_units} eligible<p>{project.committed_units} committed</p><p>{project.active_sold_units} active sold</p></td><td>{project.sales_penetration.percentage === null ? "Unavailable" : `${project.sales_penetration.percentage}%`}<p>{project.sales_penetration.numerator} / {project.sales_penetration.denominator}</p></td><td><ProjectMoney project={project} code="confirmed_receipts" /></td><td><ProjectMoney project={project} code="unrestricted_cash" /></td><td><ProjectMoney project={project} code="construction_eac" /></td><td>{project.risk_count} risks · {project.highest_risk ?? "No triggered risk"}<p>Coverage: {project.coverage}</p><Link href={project.drilldown}>Open project</Link></td></tr>)}</tbody></TableScroll>{!data.items.length ? <Notice tone="info">No authorized whole-project records on this page.</Notice> : null}<PageControls offset={offset} total={data.total} count={data.items.length} onChange={onChange} /></Card>;
}

export function PortfolioProjects() {
  const [offset, setOffset] = useState(0);
  return <ProjectRows key={offset} offset={offset} onChange={setOffset} />;
}

function RiskRows({ offset, onChange }: { offset: number; onChange: (value: number) => void }) {
  const answer = useAnswer(true, () => portfolio.risks(offset), [offset]);
  if (answer.status !== "ready") return <Pending answer={answer} />;
  const data = answer.data;
  return <><Notice tone="info">{data.unavailable_project_count} projects have risk evaluations with unavailable coverage.</Notice><Card title="Management risks"><RiskRegister rows={data.items} /><PageControls offset={offset} total={data.total} count={data.items.length} onChange={onChange} /></Card></>;
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
    <Card title="Project risks"><RiskRegister rows={project.risks} /></Card><Card title="Source positions" flush><MoneyRegister rows={project.money} /></Card>
    <Card title="Design and permits"><KeyValueGrid><KeyValue label="Permits recorded" value={project.permit_count} /><KeyValue label="Consultant" value={project.design.consultant_name ?? "Unavailable"} /><KeyValue label="Current stage" value={project.design.current_stage ?? "Unavailable"} /><KeyValue label="Stage status" value={project.design.stage_status} /><KeyValue label="Planned / forecast date" value={`${businessDate(project.design.planned_date)} / ${businessDate(project.design.forecast_date)}`} /><KeyValue label="Design coverage" value={`${project.design.availability}: ${project.design.reason ?? "Recorded programme"}`} /></KeyValueGrid></Card>
    <Card title="Risk evaluation basis"><KeyValueGrid>{project.risk_evaluations.map((row) => <KeyValue key={row.risk_code} label={row.risk_code.replaceAll("_", " ")} value={`${row.availability}${row.reason ? ` · ${row.reason}` : ""}`} />)}</KeyValueGrid></Card>
  </>;
}
