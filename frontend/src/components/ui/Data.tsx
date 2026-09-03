import type { ReactNode } from "react";

/**
 * Labelled facts about one record, laid out in columns.
 *
 * `mono` marks a value that is a figure — money, a date, a count — so it is
 * set in tabular digits and lines up down the column. Prose stays proportional.
 */
export function KeyValueGrid({
  columns = 2,
  children,
}: {
  columns?: 2 | 3 | 4;
  children: ReactNode;
}) {
  return <dl className={columns === 2 ? "kv" : `kv kv-${columns}`}>{children}</dl>;
}

export function KeyValue({
  label,
  value,
  mono,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="kv-term">{label}</dt>
      <dd className={mono ? "kv-value figure" : "kv-value"}>
        {value === null || value === undefined || value === "" ? "—" : value}
      </dd>
    </div>
  );
}

export type MetricTone = "neutral" | "danger" | "success" | "warning" | "muted";

/**
 * One reported number, labelled.
 *
 * Every figure shown this way came back from the API on this request. Nothing
 * here is derived, totalled or projected in the browser — a number the server
 * did not say is a number nobody is accountable for.
 *
 * `size` is hierarchy, not emphasis: the one figure an executive reads first
 * is `lg`, the row of supporting counts beneath it is `sm`.
 */
export function Metric({
  label,
  value,
  note,
  size = "md",
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  size?: "sm" | "md" | "lg";
  tone?: MetricTone;
}) {
  const valueClass =
    size === "sm" ? "metric-value metric-value-sm" : size === "lg" ? "metric-value metric-value-lg" : "metric-value";
  return (
    <div className={tone === "neutral" ? "metric" : `metric metric-tone-${tone}`}>
      <p className="metric-label">{label}</p>
      <p className={valueClass}>{value === null || value === undefined || value === "" ? "—" : value}</p>
      {note ? <p className="metric-note">{note}</p> : null}
    </div>
  );
}

/** A row of related figures that belong together. */
export function MetricGroup({ children, compact }: { children: ReactNode; compact?: boolean }) {
  return <div className={compact ? "metric-group metric-group-compact" : "metric-group"}>{children}</div>;
}

/** The long-standing names for a metric and a row of them. */
export function Stat({
  label,
  value,
  note,
  small,
}: {
  label: string;
  value: ReactNode;
  note?: string;
  small?: boolean;
}) {
  return <Metric label={label} value={value} note={note} size={small ? "sm" : "md"} />;
}

export const StatRow = MetricGroup;

/**
 * A wide table that scrolls inside itself.
 *
 * The registers in this product are genuinely wide — a unit has four status
 * dimensions and a deal has five records behind it — so they scroll sideways
 * rather than being cut down to what fits a phone. `fixedFirst` keeps the
 * identity column in view while the rest scrolls.
 */
export function TableScroll({
  label,
  fixedFirst,
  compact,
  children,
}: {
  label: string;
  fixedFirst?: boolean;
  compact?: boolean;
  children: ReactNode;
}) {
  const classes = ["table", fixedFirst ? "table-fixed-first" : "", compact ? "table-compact" : ""]
    .filter(Boolean)
    .join(" ");
  return (
    <div className="table-scroll" tabIndex={0} role="group" aria-label={label}>
      <table className={classes}>
        <caption className="visually-hidden">{label}</caption>
        {children}
      </table>
    </div>
  );
}

/**
 * Small facts in a line: "Code RG-01 · Status Active · Base JOD".
 *
 * For identity a reader scans once, not for figures a reader compares.
 */
export function InlineMeta({ children }: { children: ReactNode }) {
  return <ul className="inline-meta">{children}</ul>;
}

export function InlineMetaItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <li>
      <span className="inline-meta-label">{label}</span>
      <span className="inline-meta-value">{children}</span>
    </li>
  );
}

/**
 * The lines a figure is made of, read top to bottom to the total.
 *
 * Every amount is the server's. The rows only lay them out in the order the
 * server applied them, with the subtotals and the total the server named.
 */
export function Waterfall({ children }: { children: ReactNode }) {
  return <ol className="waterfall">{children}</ol>;
}

export function WaterfallRow({
  label,
  note,
  amount,
  kind = "line",
}: {
  label: ReactNode;
  note?: ReactNode;
  amount: ReactNode;
  kind?: "line" | "subtotal" | "total";
}) {
  const className =
    kind === "total"
      ? "waterfall-row waterfall-row-total"
      : kind === "subtotal"
        ? "waterfall-row waterfall-row-subtotal"
        : "waterfall-row";
  return (
    <li className={className}>
      <span className="waterfall-label">
        {label}
        {note ? <span className="waterfall-note">{note}</span> : null}
      </span>
      <span className="waterfall-amount">{amount}</span>
    </li>
  );
}

/**
 * The composition a page is opened for: two to four reported figures, set
 * large, with the label beneath.
 *
 * A tear sheet does it this way for a reason. The number is what a reader came
 * for; the word only confirms which number it is, so the word goes second and
 * goes quiet. Hairlines separate the figures instead of boxes, because they
 * are one answer read across, not three answers stacked.
 *
 * As with every figure in this product, each value arrived from the API on
 * this request. Nothing here is totalled, averaged or projected.
 */
export function Position({ children, compact }: { children: ReactNode; compact?: boolean }) {
  return <div className={compact ? "position position-compact" : "position"}>{children}</div>;
}

export function PositionFigure({
  label,
  value,
  note,
  lead,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  /** The single figure the composition is built around. */
  lead?: boolean;
  tone?: "neutral" | "danger" | "warning" | "success";
}) {
  const valueClass = tone === "neutral" ? "position-value" : `position-value position-value-${tone}`;
  return (
    <div className={lead ? "position-figure position-figure-lead" : "position-figure"}>
      <p className={valueClass}>{value === null || value === undefined || value === "" ? "—" : value}</p>
      <p className="position-label">{label}</p>
      {note ? <p className="position-note">{note}</p> : null}
    </div>
  );
}

/** The supporting facts under a position, on one rule-separated line. */
export function PositionSupport({ children }: { children: ReactNode }) {
  return <div className="position-support">{children}</div>;
}

export function PositionSupportItem({ label, value }: { label: string; value: ReactNode }) {
  return (
    <span className="position-support-item">
      <span className="position-support-label">{label}</span>
      <span className="position-support-value">
        {value === null || value === undefined || value === "" ? "—" : value}
      </span>
    </span>
  );
}

/**
 * A row of counts in one band: "126 Units · 31 Available · 8 Held".
 *
 * For the four or five numbers that describe a register at a glance. They are
 * counts, not findings, and four separate cards for four integers is four
 * times the furniture the information deserves.
 */
export function StatStrip({ children }: { children: ReactNode }) {
  return <div className="stat-strip">{children}</div>;
}

export function StatStripItem({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  tone?: "neutral" | "danger" | "warning";
}) {
  return (
    <span className={tone === "neutral" ? "stat-strip-item" : `stat-strip-item stat-strip-item-${tone}`}>
      <span className="stat-strip-value">{value === null || value === undefined || value === "" ? "—" : value}</span>
      <span className="stat-strip-label">{label}</span>
    </span>
  );
}

/** A closing remark on a stat strip: an as-at date, a basis. */
export function StatStripNote({ children }: { children: ReactNode }) {
  return <span className="stat-strip-note">{children}</span>;
}

/**
 * What a total is made of, line by line, with a leader to each amount.
 *
 * Different from a `Waterfall`: a waterfall is a sequence the server applied
 * in order to reach a figure, and this is a set of parts the server reported
 * beside their total. Neither adds anything up in the browser.
 */
export function Breakdown({ children }: { children: ReactNode }) {
  return <ul className="breakdown">{children}</ul>;
}

export function BreakdownRow({
  label,
  note,
  amount,
  total,
}: {
  label: ReactNode;
  note?: ReactNode;
  amount: ReactNode;
  /** The server's own total for these parts, ruled off beneath them. */
  total?: boolean;
}) {
  return (
    <li className={total ? "breakdown-row breakdown-row-total" : "breakdown-row"}>
      <span className="breakdown-label">
        {label}
        {note ? <span className="breakdown-note"> · {note}</span> : null}
      </span>
      <span className="breakdown-lead" aria-hidden="true" />
      <span className="breakdown-amount">{amount}</span>
    </li>
  );
}

/**
 * A balance spread across the bands the server aged it into.
 *
 * Bands sit side by side at equal width with a hairline between and a two-pixel
 * rule above that warms as the money gets older. The rule is a band marker, not
 * a measurement: no width here encodes an amount, because the browser would
 * have to divide to know one.
 */
export function Distribution({ children }: { children: ReactNode }) {
  return <ol className="distribution">{children}</ol>;
}

export function DistributionBand({
  label,
  value,
  note,
  heat = "cool",
}: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  /** How old this band's money is, in the order the server named the bands. */
  heat?: "cool" | "warm" | "hot" | "late";
}) {
  return (
    <li className={heat === "cool" ? "distribution-band" : `distribution-band distribution-band-${heat}`}>
      <p className="distribution-label">{label}</p>
      <p className="distribution-value">{value}</p>
      {note ? <p className="distribution-note">{note}</p> : null}
    </li>
  );
}

/**
 * A register row's identity: the reference somebody says out loud, and beneath
 * it the few words that tell them which record it is.
 *
 * The anchor of every register in the product. The name carries the weight and
 * the metadata recedes, so a column of two hundred rows scans as a column of
 * references rather than as a paragraph per line.
 */
export function IdentityCell({ name, meta }: { name: ReactNode; meta?: ReactNode }) {
  return (
    <span className="identity-cell">
      <span className="identity-cell-name">{name}</span>
      {meta ? <span className="identity-cell-meta">{meta}</span> : null}
    </span>
  );
}

/** Where a record sits in the development: its container, then the path. */
export function PlaceCell({ main, sub }: { main: ReactNode; sub?: ReactNode }) {
  return (
    <span className="place-cell">
      <span className="place-main">{main === null || main === undefined || main === "" ? "—" : main}</span>
      {sub ? <span className="place-sub">{sub}</span> : null}
    </span>
  );
}

/**
 * A percentage the server reported, drawn at the width it reported.
 *
 * The only bar in this product, and it is not a chart: `percent` is a whole
 * number the API returned for this record, and the fill is that number. There
 * is no series behind it and nothing is interpolated. The figure is printed
 * beside the bar, because a bar alone is not a number anybody can quote.
 */
export function Meter({
  percent,
  label,
  note,
}: {
  percent: number;
  /** Read out instead of the bar; defaults to the percentage itself. */
  label?: string;
  note?: ReactNode;
}) {
  const width = Math.max(0, Math.min(100, percent));
  const fillClass =
    width >= 100 ? "meter-fill meter-fill-complete" : width < 50 ? "meter-fill meter-fill-low" : "meter-fill";
  return (
    <span className="meter-block">
      <span className="meter">
        <span className="meter-track" role="img" aria-label={label ?? `${percent}%`}>
          <span className={fillClass} style={{ width: `${width}%` }} />
        </span>
        <span className="meter-text" aria-hidden="true">
          {percent}%
        </span>
      </span>
      {note ? <span className="meter-note">{note}</span> : null}
    </span>
  );
}
