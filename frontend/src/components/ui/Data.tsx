import type { ReactNode } from "react";
import { Icon } from "./Icon";
import type { IconName } from "./Icon";

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
  wide,
}: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  size?: "sm" | "md" | "lg";
  tone?: MetricTone;
  /** A figure wider than a count — money — takes two tracks of a metric grid. */
  wide?: boolean;
}) {
  const valueClass =
    size === "sm" ? "metric-value metric-value-sm" : size === "lg" ? "metric-value metric-value-lg" : "metric-value";
  const classes = ["metric", tone === "neutral" ? "" : `metric-tone-${tone}`, wide ? "metric-wide" : ""]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={classes}>
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
  stickyHeader,
  children,
}: {
  label: string;
  fixedFirst?: boolean;
  compact?: boolean;
  /** Bounded register scrolling keeps column labels visible on long lists. */
  stickyHeader?: boolean;
  children: ReactNode;
}) {
  const classes = ["table", fixedFirst ? "table-fixed-first" : "", compact ? "table-compact" : ""]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={stickyHeader ? "table-scroll table-scroll-register" : "table-scroll"} tabIndex={0} role="group" aria-label={label}>
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
export function Position({ children, compact, layout = "inline" }: {
  children: ReactNode; compact?: boolean; layout?: "inline" | "split";
}) {
  return <div className={["position", compact ? "position-compact" : "", layout === "split" ? "position-split" : ""].filter(Boolean).join(" ")}>{children}</div>;
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
 *
 * `ledger` is the same lines set beside a lead figure on its stage: reading
 * size, the amount at the row's end, a note beneath its label and no leader,
 * because next to a hero figure the dotted line was one more thing to read.
 */
export function Breakdown({ children, ledger }: { children: ReactNode; ledger?: boolean }) {
  return <ul className={ledger ? "breakdown breakdown-ledger" : "breakdown"}>{children}</ul>;
}

export function BreakdownRow({
  label,
  note,
  amount,
  total,
  tone = "neutral",
  mark,
}: {
  label: ReactNode;
  note?: ReactNode;
  amount: ReactNode;
  /** The server's own total for these parts, ruled off beneath them. */
  total?: boolean;
  /** The amount's colour, repeating a state the label already names. */
  tone?: "neutral" | "danger";
  /** A dot before the label, for a state the row's words already carry. */
  mark?: "danger" | "warning";
}) {
  const amountClass = tone === "neutral" ? "breakdown-amount" : `breakdown-amount breakdown-amount-${tone}`;
  return (
    <li className={total ? "breakdown-row breakdown-row-total" : "breakdown-row"}>
      <span className="breakdown-label">
        {mark ? <span className={`breakdown-mark breakdown-mark-${mark}`} aria-hidden="true" /> : null}
        {label}
        {note ? <span className="breakdown-note">{note}</span> : null}
      </span>
      <span className="breakdown-lead" aria-hidden="true" />
      <span className={amountClass}>{amount}</span>
    </li>
  );
}

/** How old a band's money is, in the order the server ages it. */
export type BandHeat = "cool" | "current" | "warm" | "hot" | "late";

/**
 * A balance spread across the bands the server aged it into.
 *
 * Bands sit side by side at equal width with a hairline between and a mark
 * above that warms as the money gets older. The mark is a band marker, not a
 * measurement: no width in the bands encodes an amount, because the browser
 * would have to divide to know one. The one width that means anything is the
 * track above the bands, and that is drawn from shares the server computed —
 * see `DistributionTrack`.
 */
export function Distribution({ children }: { children: ReactNode }) {
  return <ol className="distribution">{children}</ol>;
}

export function DistributionBand({
  label,
  value,
  note,
  heat = "cool",
  empty,
}: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  /** How old this band's money is, in the order the server named the bands. */
  heat?: BandHeat;
  /** Nothing standing in the band: the figure recedes so the eye finds the money. */
  empty?: boolean;
}) {
  const classes = [
    "distribution-band",
    heat === "cool" ? "" : `distribution-band-${heat}`,
    empty ? "distribution-band-empty" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <li className={classes}>
      <p className="distribution-label">{label}</p>
      <p className="distribution-value">{value}</p>
      {note ? <p className="distribution-note">{note}</p> : null}
    </li>
  );
}

/**
 * The bands' shares of a balance, drawn at the widths the server reported.
 *
 * `share` is a percentage the API computed for each band, and a segment grows
 * by that number and nothing else: no amount is divided here, in the same way
 * `Meter` draws the percentage it was given. A band with no positive share
 * draws no segment, and a balance the server gave no shares for draws no track
 * at all, so the bands beneath stand on their own.
 */
export function DistributionTrack({
  label,
  segments,
}: {
  label: string;
  segments: { key: string; label: string; share: string | null | undefined; heat?: BandHeat }[];
}) {
  // Conversion is presentation geometry for a server percentage, never money.
  const drawn = segments.filter((segment) => Number(segment.share) > 0);
  if (drawn.length === 0) return null;
  const spoken = drawn.map((segment) => `${segment.label} ${segment.share}%`).join(", ");
  return (
    <div className="distribution-track" role="img" aria-label={`${label}: ${spoken}`}>
      {drawn.map((segment) => (
        <span
          key={segment.key}
          className={`distribution-track-segment distribution-track-${segment.heat ?? "cool"}`}
          style={{ flexGrow: Number(segment.share) * 10 }}
        />
      ))}
    </div>
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
export function IdentityCell({ name, meta, icon }: { name: ReactNode; meta?: ReactNode; icon?: IconName }) {
  return (
    <span className={icon ? "identity-cell identity-cell-asset" : "identity-cell"}>
      {icon ? <span className="identity-cell-glyph"><Icon name={icon} /></span> : null}
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
  neutral,
}: {
  percent: number | string;
  /** Read out instead of the bar; defaults to the percentage itself. */
  label?: string;
  note?: ReactNode;
  /** A reported ratio is not a risk judgement. Readiness keeps its existing tones. */
  neutral?: boolean;
}) {
  // Conversion is presentation geometry for a server percentage, never money.
  const width = Math.max(0, Math.min(100, Number(percent)));
  const fillClass =
    neutral ? "meter-fill" : width >= 100 ? "meter-fill meter-fill-complete" : width < 50 ? "meter-fill meter-fill-low" : "meter-fill";
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
