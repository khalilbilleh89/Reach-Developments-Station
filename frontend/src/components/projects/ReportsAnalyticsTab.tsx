"use client";

import { useEffect, useState } from "react";
import { analyticsReport } from "@/lib/api/analytics-report";
import type { AnalyticsReport } from "@/lib/api/analytics-report";
import { useAnswer } from "@/lib/answer";
import { ANALYSIS_FINANCIAL_READERS, hasAnyRole } from "@/lib/roles";
import { Button, Field, Loading, Notice, PageHeader } from "@/components/ui";
import { ReportChart, reportValue } from "./reports/ReportChart";

const categories = ["All charts", "Sales", "People", "Cash & cost", "Delivery"];

function ReportIdentity({ report }: { report: AnalyticsReport }) {
  return <header className="report-identity"><div><span className="eyebrow">REACH / MANAGEMENT REPORT</span><h2>{report.project_name}</h2><p>Project analytics · {report.currency}</p></div><dl><div><dt>Activity period</dt><dd>{report.context.period_from} — {report.context.period_to}</dd></div><div><dt>Current position</dt><dd>{report.context.snapshot_as_of}</dd></div><div><dt>Generated (UTC)</dt><dd>{report.generated_at.replace("T", " ").slice(0, 19)}</dd></div><div><dt>Price threshold · ex-tax</dt><dd>{reportValue(report.threshold, report.currency)}</dd></div></dl></header>;
}

function ReportMetrics({ report }: { report: AnalyticsReport }) {
  return <div className="report-metrics">{report.metrics.map(metric => <div key={metric.label}><span>{metric.label}</span><strong>{reportValue(metric.value, metric.unit)}</strong><small>{metric.note}</small></div>)}</div>;
}

function AnalyticsDocument({ report }: { report: AnalyticsReport }) {
  // One chart per A4 page keeps exact values, explanation and source together.
  // Long stage registers continue across pages without discarding any source rows.
  const pages = report.charts.flatMap(chart => chart.kind !== "bars" || chart.points.length <= 10 ? [chart] : Array.from({ length: Math.ceil(chart.points.length / 10) }, (_, index) => ({ ...chart, key: `${chart.key}-${index}`, title: `${chart.title} · ${index + 1}`, points: chart.points.slice(index * 10, index * 10 + 10) })));
  return <div className="analytics-print" aria-hidden="true">
    <section className="analytics-paper analytics-cover"><ReportIdentity report={report} /><div className="report-cover-title"><span className="eyebrow">PERFORMANCE / CAPITAL / DELIVERY</span><h1>The project,<br />in numbers.</h1><p>Management analytics report</p></div><ReportMetrics report={report} /><h2>Reading this report</h2>{report.notices.map(note => <p key={note}>{note}</p>)}<footer className="report-page-footer">REACH · Management use · 1 / {pages.length + 1}</footer></section>
    {pages.map((chart, index) => <section className="analytics-paper" key={chart.key}><ReportIdentity report={report} /><ReportChart chart={chart} print /><footer className="report-page-footer">{report.project_name} · {chart.category} · {index + 2} / {pages.length + 1}</footer></section>)}
  </div>;
}

export function ReportsAnalyticsTab({ projectId, roles, currencies }: { projectId: string; roles: Set<string>; currencies: string[] }) {
  const [periodFrom, setPeriodFrom] = useState("");
  const [periodTo, setPeriodTo] = useState("");
  const [threshold, setThreshold] = useState("400000");
  const [currency, setCurrency] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All charts");
  const answer = useAnswer(hasAnyRole(roles, ANALYSIS_FINANCIAL_READERS), () => analyticsReport(projectId, query), [projectId, query]);
  const ready = answer.status === "ready";
  useEffect(() => {
    if (!ready) return;
    const previous = document.title;
    document.title = `REACH Analytics - ${answer.data.project_name} - ${answer.data.context.snapshot_as_of}`;
    return () => { document.title = previous; };
  }, [ready, answer]);
  return <div className="analytics-workspace">
    <div className="analytics-screen"><PageHeader title="Analytics" icon="economics" subtitle="Reports · A visual view of project performance." actions={<Button variant="primary" disabled={!ready} onClick={() => window.print()}>Export PDF report</Button>} />
      <form className="report-controls" onSubmit={event => { event.preventDefault(); const params = new URLSearchParams({ threshold }); if (periodFrom) params.set("period_from", periodFrom); if (periodTo) params.set("period_to", periodTo); if (currency) params.set("currency", currency); setQuery(params.toString()); }}>
        <Field label="Activity from"><input type="date" value={periodFrom} onChange={event => setPeriodFrom(event.target.value)} /></Field>
        <Field label="Activity to"><input type="date" value={periodTo} onChange={event => setPeriodTo(event.target.value)} /></Field>
        <Field label="Price threshold · ex-tax"><input required type="number" min="0" max="999999999999.99" step="0.01" value={threshold} onChange={event => setThreshold(event.target.value)} /></Field>
        <Field label="Money currency"><select value={currency} onChange={event => setCurrency(event.target.value)}><option value="">Project currency</option>{Array.from(new Set(currencies)).sort().map(code => <option key={code}>{code}</option>)}</select></Field>
        <Button type="submit">Apply filters</Button><Button onClick={answer.retry}>Refresh</Button>
      </form>
      <p className="footnote">Export opens your print dialog: choose Save as PDF. The report includes all charts, exact values, explanations and sources. Applied filters are printed on every page.</p>
      {answer.status === "loading" ? <Loading label="Preparing project analytics" /> : answer.status === "denied" || answer.status === "off" ? <Notice tone="info">Management reporting requires a financial reader role and whole-project access.</Notice> : answer.status === "failed" ? <Notice tone="error">{answer.message}<Button onClick={answer.retry}>Retry</Button></Notice> : <>
        <ReportIdentity report={answer.data} /><ReportMetrics report={answer.data} />
        <div className="report-category-controls" aria-label="Chart categories">{categories.map(item => <Button key={item} small variant={category === item ? "primary" : "default"} aria-pressed={category === item} onClick={() => setCategory(item)}>{item}</Button>)}</div>
        <div className="report-chart-grid">{answer.data.charts.filter(chart => category === "All charts" || chart.category === category).map(chart => <ReportChart key={chart.key} chart={chart} />)}</div>
        <section className="report-method"><h2>Report basis</h2>{answer.data.notices.map(note => <p key={note}>{note}</p>)}</section>
      </>}
    </div>
    {answer.status === "ready" ? <AnalyticsDocument report={answer.data} /> : null}
  </div>;
}
