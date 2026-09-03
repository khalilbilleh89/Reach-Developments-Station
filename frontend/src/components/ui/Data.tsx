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
