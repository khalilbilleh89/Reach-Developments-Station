"use client";

import { useId } from "react";
import type { CSSProperties } from "react";
import type { ReportChart as Chart, ReportPoint } from "@/lib/api/analytics-report";
import { money, decimalText } from "@/lib/format";
import { Disclosure } from "@/components/ui";

export function reportValue(value: string | null, unit: string): string {
  if (value === null) return "Unavailable";
  return /^[A-Z]{3}$/.test(unit) ? money(value, unit) : `${decimalText(value)} ${unit}`;
}
const label = (text: string) => text.replaceAll("_", " ");
const color = (index: number) => `var(--report-color-${index % 6})`;

function Donut({ points, title }: { points: ReportPoint[]; title: string }) {
  // Geometry only: shares are calculated by the API, never business arithmetic here.
  return <svg className="report-donut" viewBox="0 0 160 160" role="img" aria-label={title}>
    <circle cx="80" cy="80" r="58" fill="none" stroke="var(--line-soft)" strokeWidth="23" />
    {points.map((point, index) => {
      const share = Number(point.share_percentage ?? 0);
      const start = points.slice(0, index).reduce((offset, previous) => offset + Number(previous.share_percentage ?? 0), 0);
      return <circle key={index} cx="80" cy="80" r="58" pathLength="100" fill="none" stroke={color(index)} strokeWidth="23" strokeDasharray={`${share} ${100 - share}`} strokeDashoffset={-start} transform="rotate(-90 80 80)"><title>{`${label(point.label)}: ${point.value} (${point.share_percentage ?? "0"}%)`}</title></circle>;
    })}
    <text x="80" y="77" textAnchor="middle" className="report-donut-title">MIX</text>
    <text x="80" y="94" textAnchor="middle" className="report-donut-caption">by count</text>
  </svg>;
}

function Columns({ chart }: { chart: Chart }) {
  const signed = chart.points.some(point => point.value?.startsWith("-"));
  const baseline = signed ? 110 : 180;
  const height = signed ? 85 : 155;
  const step = 600 / Math.max(chart.points.length, 1);
  return <svg className="report-columns" viewBox="0 0 640 260" role="img" aria-label={`${chart.title}; exact values in chart data below`}>
    {[0, 0.5, 1].map(tick => <line key={tick} x1="20" x2="625" y1={baseline - height * tick} y2={baseline - height * tick} stroke="var(--line-soft)" />)}
    <line x1="20" x2="625" y1={baseline} y2={baseline} stroke="var(--text-muted)" />
    {chart.points.map((point, index) => {
      const size = Number(point.scale_percentage) / 100 * height;
      const negative = point.value?.startsWith("-");
      return <g key={index} tabIndex={0} aria-label={`${point.label}: ${reportValue(point.value, chart.unit)}`}>
        <title>{`${point.label}: ${reportValue(point.value, chart.unit)}`}</title>
        <rect x={25 + index * step} y={negative ? baseline : baseline - size} width={Math.max(3, step - 9)} height={size} rx="3" fill={negative ? "var(--danger)" : "var(--brand-gold-strong)"} />
        <text x={25 + index * step} y="220" transform={`rotate(35 ${25 + index * step} 220)`}>{point.label}</text>
      </g>;
    })}
  </svg>;
}

export function ReportChart({ chart, print = false }: { chart: Chart; print?: boolean }) {
  const id = useId();
  const hasValue = chart.points.some(point => point.value !== null);
  return <article className="report-chart" aria-labelledby={id}>
    <header><span className="eyebrow">{chart.category} / {chart.unit}</span><h3 id={id}>{chart.title}</h3></header>
    {!chart.points.length ? <div className="report-empty">No matching records</div> : !hasValue ? <div className="report-empty">Source data unavailable</div> : chart.kind === "columns" ? <Columns chart={chart} /> : <div className={chart.kind === "donut" ? "report-composition" : "report-bars"}>
      {chart.kind === "donut" ? <Donut points={chart.points} title={chart.title} /> : null}
      <ul className="report-legend">{chart.points.map((point, index) => <li key={index}>
        <div><span><i style={{ "--swatch": color(index) } as CSSProperties} />{label(point.label)}</span><strong>{reportValue(point.value, chart.unit)}</strong></div>
        {chart.kind === "bars" ? <span className="report-track"><span className={point.value?.startsWith("-") ? "report-negative" : ""} style={{ width: `${point.scale_percentage}%`, "--bar-color": color(index) } as CSSProperties} /></span> : null}
      </li>)}</ul>
    </div>}
    <p className="report-insight">{chart.insight}</p>
    {chart.note ? <p className="report-note">{chart.note}</p> : null}
    {chart.kind === "columns" && chart.points.length ? print ? <div className="report-print-values">{chart.points.map((point, index) => <span key={index}>{point.label}: <b>{reportValue(point.value, chart.unit)}</b></span>)}</div> : <div className="report-data"><Disclosure title="Exact chart values"><dl>{chart.points.map((point, index) => <div key={index}><dt>{point.label}</dt><dd>{reportValue(point.value, chart.unit)}</dd></div>)}</dl></Disclosure></div> : null}
    <footer>{chart.source}</footer>
  </article>;
}
