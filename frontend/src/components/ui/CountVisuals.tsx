"use client";

import { useState } from "react";
import type { ReactNode } from "react";
import type { Tone } from "./Badge";

/**
 * Mutually exclusive server counts as one slim bar (design system B1).
 *
 * CSS distributes the bar by count; the legend prints each count as the
 * server gave it. No total, share or ratio is worked out here: a figure that
 * matters enough to print is the server's to compute.
 */
export function CountComposition({ label, note, rows, actions }: {
  label: string;
  note: string;
  rows: { label: string; count: number; tone?: Tone }[];
  /** A source note or control beside the caption. */
  actions?: ReactNode;
}) {
  return <figure className="count-visual">
    <figcaption className="count-caption">
      <span className="count-caption-text"><strong>{label}</strong><span>{note}</span></span>
      {actions ? <span className="count-caption-actions">{actions}</span> : null}
    </figcaption>
    <div className="count-composition" aria-hidden="true">
      {rows.filter((row) => row.count > 0).map((row) => <span key={row.label} className={`count-segment count-segment-${row.tone ?? "muted"}`} style={{ flexGrow: row.count }} />)}
    </div>
    <dl className="count-legend">{rows.map((row) => <div key={row.label}>
      <dt><span className={`count-swatch count-segment-${row.tone ?? "muted"}`} aria-hidden="true" />{row.label}</dt>
      <dd>{row.count}</dd>
    </div>)}</dl>
  </figure>;
}

/**
 * One square per unit (design system B3): a building you can count.
 *
 * Squares are drawn in the order the rows are given, so the eye reads the
 * sold ones first. Every square is a server-counted unit; nothing is scaled.
 */
export function UnitGrid({ label, note, rows, actions }: {
  label: string;
  note: string;
  rows: { label: string; count: number; tone?: Tone }[];
  actions?: ReactNode;
}) {
  return <figure className="count-visual">
    <figcaption className="count-caption">
      <span className="count-caption-text"><strong>{label}</strong><span>{note}</span></span>
      {actions ? <span className="count-caption-actions">{actions}</span> : null}
    </figcaption>
    <div className="unit-grid" role="img" aria-label={`Units: ${rows.map((row) => `${row.count} ${row.label.toLowerCase()}`).join(", ")}`}>
      {rows.flatMap((row) => Array.from({ length: row.count }, (_, index) => <i key={`${row.label}-${index}`} className={`unit-cell count-segment-${row.tone ?? "muted"}`} />))}
    </div>
    <dl className="count-legend">{rows.map((row) => <div key={row.label}>
      <dt><span className={`count-swatch count-segment-${row.tone ?? "muted"}`} aria-hidden="true" />{row.label}</dt>
      <dd>{row.count}</dd>
    </div>)}</dl>
  </figure>;
}

/** Each period is one slot this wide; a bar takes a little under half of it. */
const PITCH = 44;
/** Room on the left for the axis figures. */
const GUTTER = 28;
/** How far the largest count reaches from the baseline. */
const REACH = 120;

/** Opens the plot on its latest period where the screen is narrower than the year. */
const showLatest = (element: HTMLDivElement | null) => {
  if (element) element.scrollLeft = element.scrollWidth;
};

/**
 * Count-only signed observations as quiet columns (design system A1), or
 * led by the total with the columns as a small trend strip (A2).
 *
 * The plot is drawn at its natural size, one slot per period, and scrolls
 * sideways where the screen is narrower than the year: scaled to the
 * container it became a wall of type on a desk and a smear on a phone.
 *
 * Arithmetic below is exclusively SVG coordinates. Columns rise from a
 * baseline; only a negative observation opens the half below it. A zero
 * month draws a faint tick and no label: a row of printed zeros was the
 * loudest thing on the page and said the least. The latest non-zero period
 * is drawn in gold so the eye lands on what is current. Hovering a period
 * names its count in a tip, and every count is also printed as text for a
 * reader who cannot see the plot.
 */
export function CountSeries({ label, note, rows, lead, actions }: {
  label: string;
  note: string;
  rows: { label: string; count: number; detail?: string }[];
  /** A2: the figure that leads, with the columns beside it as a trend. */
  lead?: { value: ReactNode; label: string; note?: ReactNode };
  actions?: ReactNode;
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  const extent = Math.max(1, ...rows.map((row) => Math.abs(row.count)));
  const above = rows.some((row) => row.count > 0);
  const below = rows.some((row) => row.count < 0);
  const reach = lead ? 44 : REACH;
  const gutter = lead ? 0 : GUTTER;
  const width = gutter + rows.length * PITCH;
  const zero = 10 + (above || !below ? reach : 0);
  const floor = zero + (below ? reach : 0);
  const height = floor + (lead ? 6 : 22);
  const current = hovered === null ? null : rows[hovered];
  let latest = -1;
  rows.forEach((row, index) => { if (row.count !== 0) latest = index; });
  const columnWidth = lead ? PITCH * 0.6 : PITCH * 0.5;
  const half = (extent === 1 ? 1 : Math.ceil(extent / 2));

  const plot = <div className="count-series-scroll" ref={showLatest} tabIndex={0} role="group" aria-label={`${label} chart; scroll for all periods`}>
    <svg className="count-series" viewBox={`0 0 ${width} ${height}`} width={width} height={height} aria-hidden="true" onMouseLeave={() => setHovered(null)}>
      {!lead ? <>
        {[extent, half].filter((value, index, all) => all.indexOf(value) === index).map((value) => <g key={value}>
          <line className="count-grid" x1={gutter} x2={width} y1={zero - value / extent * reach} y2={zero - value / extent * reach} />
          <text className="count-axis" x={gutter - 6} y={zero - value / extent * reach + 3}>{value}</text>
        </g>)}
        {below ? <>
          <line className="count-grid" x1={gutter} x2={width} y1={zero + reach} y2={zero + reach} />
          <text className="count-axis" x={gutter - 6} y={zero + reach + 3}>{-extent}</text>
        </> : null}
        <text className="count-axis" x={gutter - 6} y={zero + 3}>0</text>
      </> : null}
      <line className="count-zero" x1={gutter} x2={width} y1={zero} y2={zero} />
      {rows.map((row, index) => {
        const x = gutter + index * PITCH + PITCH / 2;
        const length = Math.abs(row.count) / extent * reach;
        const end = row.count < 0 ? zero + length : zero - length;
        const isLatest = index === latest;
        const classes = ["count-bar", row.count < 0 ? "count-bar-negative" : "", isLatest ? "count-bar-latest" : "", hovered === index ? "count-bar-hover" : ""].filter(Boolean).join(" ");
        return <g key={row.label} className="count-slot" onMouseEnter={() => setHovered(index)}>
          <rect className="count-hit" x={x - PITCH / 2} y={0} width={PITCH} height={height} />
          {row.count === 0
            ? <rect className="count-tick" x={x - columnWidth / 2} y={zero - 1.5} width={columnWidth} height={3} rx={1.5} />
            : <rect className={classes} x={x - columnWidth / 2} y={Math.min(zero, end)} width={columnWidth} height={length} rx={3} />}
          {!lead && row.count !== 0 ? <text className="count-value" x={x} y={row.count < 0 ? end + 14 : end - 6}>{row.count}</text> : null}
          {!lead ? <text className="count-period" x={x} y={floor + 16}>{row.label.split(" ")[0]}</text> : null}
        </g>;
      })}
    </svg>
    <div className={current ? "count-tip count-tip-shown" : "count-tip"} role="status" aria-live="polite" style={current ? { left: `${gutter + (hovered ?? 0) * PITCH + PITCH / 2}px` } : undefined}>
      {current ? <><strong>{current.count} units</strong> · {current.label}{current.detail ? ` · ${current.detail}` : ""}</> : null}
    </div>
  </div>;

  return <figure className={lead ? "count-visual count-visual-lead" : "count-visual"}>
    <figcaption className="count-caption">
      <span className="count-caption-text"><strong>{label}</strong><span>{note}</span></span>
      {actions ? <span className="count-caption-actions">{actions}</span> : null}
    </figcaption>
    {lead ? <div className="count-lead">
      <div className="count-lead-figure">
        <span className="count-lead-value">{lead.value}</span>
        <span className="count-lead-label">{lead.label}</span>
        {lead.note ? <span className="count-lead-note">{lead.note}</span> : null}
      </div>
      {plot}
    </div> : plot}
    <dl className="visually-hidden">{rows.map((row) => <div key={row.label}><dt>{row.label}</dt><dd>{row.count} units</dd></div>)}</dl>
  </figure>;
}
