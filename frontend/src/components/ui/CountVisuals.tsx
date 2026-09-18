"use client";

import { useState } from "react";
import type { Tone } from "./Badge";

/** Mutually exclusive server counts. CSS distributes space; no total or ratio is invented. */
export function CountComposition({ label, note, rows }: {
  label: string;
  note: string;
  rows: { label: string; count: number; tone?: Tone }[];
}) {
  return <figure className="count-visual">
    <figcaption><strong>{label}</strong><span>{note}</span></figcaption>
    <div className="count-composition" aria-hidden="true">
      {rows.filter((row) => row.count > 0).map((row) => <span key={row.label} className={`count-segment count-segment-${row.tone ?? "muted"}`} style={{ flexGrow: row.count }} />)}
    </div>
    <dl className="count-legend">{rows.map((row) => <div key={row.label}>
      <dt><span className={`count-swatch count-segment-${row.tone ?? "muted"}`} aria-hidden="true" />{row.label}</dt><dd>{row.count}</dd>
    </div>)}</dl>
  </figure>;
}

/** Each period is one slot this wide; a bar takes a third of it and the rest is air. */
const PITCH = 72;
/** Room on the left for the axis figures. */
const GUTTER = 32;
/** How far the largest count reaches from the baseline. */
const REACH = 96;

/**
 * Count-only signed observations. Arithmetic below is exclusively SVG coordinates.
 *
 * The plot is as tall as its data. Bars grow up from a baseline that sits
 * directly above the period labels, and only a negative observation opens the
 * half below it: a year of positive months no longer carries an empty band
 * beneath the axis. A zero is a tick on the baseline with its count printed
 * quietly, because a row of bold zeros was the loudest thing on the page and
 * said the least. One hairline marks the largest count so the rest can be
 * judged against it, and hovering a period names its detail in the caption.
 * Every count is also printed as text for a reader who cannot see the plot.
 */
export function CountSeries({ label, note, rows }: {
  label: string;
  note: string;
  rows: { label: string; count: number; detail?: string }[];
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  const extent = Math.max(1, ...rows.map((row) => Math.abs(row.count)));
  const above = rows.some((row) => row.count > 0);
  const below = rows.some((row) => row.count < 0);
  const width = Math.max(320, GUTTER + rows.length * PITCH);
  const zero = 22 + (above ? REACH : 0);
  const floor = zero + (below ? REACH + 18 : 0);
  const height = floor + 32;
  const current = hovered === null ? null : rows[hovered];
  return <figure className="count-visual">
    <figcaption>
      <strong>{label}</strong>
      <span>{note}</span>
      <span className="count-hover" aria-live="polite">
        {current ? `${current.label} · ${current.count} units${current.detail ? ` · ${current.detail}` : ""}` : "Hover a period for its detail"}
      </span>
    </figcaption>
    <div className="count-series-scroll" tabIndex={0} role="group" aria-label={`${label} chart; scroll for all periods`}>
      <svg className="count-series" width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true" onMouseLeave={() => setHovered(null)}>
        {above ? <>
          <line className="count-grid" x1={GUTTER} x2={width} y1={zero - REACH} y2={zero - REACH} />
          <text className="count-axis" x={GUTTER - 8} y={zero - REACH + 4}>{extent}</text>
        </> : null}
        {below ? <>
          <line className="count-grid" x1={GUTTER} x2={width} y1={zero + REACH} y2={zero + REACH} />
          <text className="count-axis" x={GUTTER - 8} y={zero + REACH + 4}>-{extent}</text>
        </> : null}
        <line className="count-zero" x1={GUTTER} x2={width} y1={zero} y2={zero} />
        <text className="count-axis" x={GUTTER - 8} y={zero + 4}>0</text>
        {rows.map((row, index) => {
          const x = GUTTER + index * PITCH + PITCH / 2;
          const length = Math.abs(row.count) / extent * REACH;
          const end = row.count < 0 ? zero + length : zero - length;
          // A bar shorter than its rounded cap is drawn square; the cap needs four pixels.
          const capped = length > 4;
          return <g key={row.label} className="count-slot" onMouseEnter={() => setHovered(index)}>
            <rect className="count-hit" x={x - PITCH / 2} y={0} width={PITCH} height={height} />
            {row.count === 0 ? (
              <rect className="count-tick" x={x - 11} y={zero - 3} width="22" height="3" rx="1.5" />
            ) : capped ? (
              <path
                className={row.count < 0 ? "count-bar count-bar-negative" : "count-bar"}
                d={row.count < 0
                  ? `M${x - 11},${zero} V${end - 4} a4,4 0 0 0 4,4 h14 a4,4 0 0 0 4,-4 V${zero} Z`
                  : `M${x - 11},${zero} V${end + 4} a4,4 0 0 1 4,-4 h14 a4,4 0 0 1 4,4 V${zero} Z`}
              />
            ) : (
              <rect className={row.count < 0 ? "count-bar count-bar-negative" : "count-bar"} x={x - 11} y={Math.min(zero, end)} width="22" height={length} />
            )}
            <text className={row.count === 0 ? "count-value count-value-zero" : "count-value"} x={x} y={row.count < 0 ? end + 16 : row.count === 0 ? zero - 10 : end - 8}>{row.count}</text>
            <text className="count-period" x={x} y={floor + 24}>{row.label}</text>
          </g>;
        })}
      </svg>
    </div>
    <dl className="visually-hidden">{rows.map((row) => <div key={row.label}><dt>{row.label}</dt><dd>{row.count} units</dd></div>)}</dl>
  </figure>;
}
