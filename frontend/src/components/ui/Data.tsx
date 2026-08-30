import type { ReactNode } from "react";

/**
 * Labelled facts about one record, laid out in columns.
 *
 * `mono` is for anything a person compares down a column — a figure, a date, a
 * reference — so the digits line up. Prose stays in the proportional face.
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
      <dd className={mono ? "kv-value mono" : "kv-value"}>
        {value === null || value === undefined || value === "" ? "—" : value}
      </dd>
    </div>
  );
}

/**
 * One reported number.
 *
 * Every figure shown this way came back from the API on this request. Nothing
 * here is derived, totalled or projected in the browser — a number the server
 * did not say is a number nobody is accountable for.
 */
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
  return (
    <div className="stat">
      <p className="stat-label">{label}</p>
      <p className={small ? "stat-value stat-value-sm" : "stat-value"}>{value ?? "—"}</p>
      {note ? <p className="stat-note">{note}</p> : null}
    </div>
  );
}

export function StatRow({ children }: { children: ReactNode }) {
  return <div className="stat-row">{children}</div>;
}

/**
 * A wide table that scrolls inside itself.
 *
 * The registers in this product are genuinely wide — a unit has four status
 * dimensions and a deal has five records behind it — so they scroll sideways
 * rather than being cut down to what fits a phone.
 */
export function TableScroll({
  label,
  fixedFirst,
  children,
}: {
  label: string;
  fixedFirst?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="table-scroll" tabIndex={0} role="group" aria-label={label}>
      <table className={fixedFirst ? "table table-fixed-first" : "table"}>
        <caption className="visually-hidden">{label}</caption>
        {children}
      </table>
    </div>
  );
}
