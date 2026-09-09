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

/** Count-only signed observations. Arithmetic below is exclusively SVG coordinates. */
export function CountSeries({ label, note, rows }: {
  label: string;
  note: string;
  rows: { label: string; count: number }[];
}) {
  const extent = Math.max(1, ...rows.map((row) => Math.abs(row.count)));
  const width = Math.max(320, rows.length * 72);
  return <figure className="count-visual">
    <figcaption><strong>{label}</strong><span>{note}</span></figcaption>
    <div className="count-series-scroll" tabIndex={0} role="group" aria-label={`${label} chart; scroll for all periods`}>
      <svg className="count-series" width={width} height="190" viewBox={`0 0 ${width} 190`} aria-hidden="true">
        <line className="count-zero" x1="0" x2={width} y1="84" y2="84" />
        {rows.map((row, index) => {
          const x = index * 72 + 36;
          const height = Math.abs(row.count) / extent * 60;
          return <g key={row.label}>
            <rect className={row.count < 0 ? "count-bar count-bar-negative" : "count-bar"} x={x - 13} y={row.count < 0 ? 84 : 84 - height} width="26" height={height} rx="2" />
            <text className="count-value" x={x} y={row.count < 0 ? 101 + height : 75 - height}>{row.count}</text>
            <text className="count-period" x={x} y="179">{row.label}</text>
          </g>;
        })}
      </svg>
    </div>
    <dl className="visually-hidden">{rows.map((row) => <div key={row.label}><dt>{row.label}</dt><dd>{row.count} units</dd></div>)}</dl>
  </figure>;
}
