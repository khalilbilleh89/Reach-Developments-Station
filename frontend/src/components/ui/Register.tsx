"use client";

import { useMemo, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";

import { Button } from "./Button";
import { Icon } from "./Icon";

/* ------------------------------------------------------------------------ *
 * Sorting (design system E1)
 * ------------------------------------------------------------------------ */

/** "column" ascending, "-column" descending, null for the register's own order. */
export type SortKey = string | null;

/**
 * Keeps one sort for a register and orders the rows already on screen by it.
 *
 * Ordering is a comparison, not a figure: the rows and every value in them
 * are the server's. A server-paginated register must not use this for the
 * whole set (it would order one page and imply the rest); it is for registers
 * the screen holds in full.
 */
export function useSort<Row>(rows: Row[], read: (row: Row, column: string) => string | number | null | undefined, initial: SortKey = null) {
  const [sort, setSort] = useState<SortKey>(initial);
  const sorted = useMemo(() => {
    if (!sort) return rows;
    const column = sort.replace(/^-/, "");
    const direction = sort.startsWith("-") ? -1 : 1;
    return [...rows].sort((a, b) => compare(read(a, column), read(b, column)) * direction);
  }, [rows, sort, read]);
  const toggle = (column: string) => setSort((current) => (current === column ? `-${column}` : current === `-${column}` ? null : column));
  return { sort, setSort, toggle, sorted };
}

function compare(a: string | number | null | undefined, b: string | number | null | undefined): number {
  // Absent values sink to the end whichever way the column is read.
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  const x = typeof a === "number" ? a : Number(a);
  const y = typeof b === "number" ? b : Number(b);
  if (!Number.isNaN(x) && !Number.isNaN(y) && String(a).trim() !== "" && String(b).trim() !== "") return x - y;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
}

/** A column heading a reader can click to sort by. */
export function SortHeader({ column, sort, onToggle, children, className }: {
  column: string;
  sort: SortKey;
  onToggle: (column: string) => void;
  children: ReactNode;
  className?: string;
}) {
  const direction = sort === column ? "ascending" : sort === `-${column}` ? "descending" : "none";
  return (
    <th scope="col" className={className} aria-sort={direction}>
      <button type="button" className={direction === "none" ? "sort-button" : "sort-button sort-button-active"} onClick={() => onToggle(column)}>
        <span>{children}</span>
        <Icon name="chevron-down" className={direction === "ascending" ? "sort-mark sort-mark-up" : "sort-mark"} />
      </button>
    </th>
  );
}

/* ------------------------------------------------------------------------ *
 * Selection and the bulk bar (design system E1)
 * ------------------------------------------------------------------------ */

/** Which rows are ticked, by id. */
export function useSelection(ids: string[]) {
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const present = useMemo(() => new Set(ids), [ids]);
  const selected = useMemo(() => [...picked].filter((id) => present.has(id)), [picked, present]);
  const all = ids.length > 0 && selected.length === ids.length;
  return {
    selected,
    isSelected: (id: string) => picked.has(id),
    toggle: (id: string) => setPicked((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    }),
    toggleAll: () => setPicked(all ? new Set() : new Set(ids)),
    clear: () => setPicked(new Set()),
    all,
    some: selected.length > 0 && !all,
  };
}

export function SelectAllCell({ checked, indeterminate, onChange, label = "Select all rows" }: {
  checked: boolean;
  indeterminate?: boolean;
  onChange: () => void;
  label?: string;
}) {
  return (
    <th scope="col" className="select-cell">
      <input
        type="checkbox"
        className="select-box"
        aria-label={label}
        checked={checked}
        ref={(element) => { if (element) element.indeterminate = !!indeterminate && !checked; }}
        onChange={onChange}
      />
    </th>
  );
}

export function SelectCell({ checked, onChange, label, disabled }: { checked: boolean; onChange: () => void; label: string; disabled?: boolean }) {
  return (
    <td className="select-cell">
      <input type="checkbox" className="select-box" aria-label={label} checked={checked} disabled={disabled} onChange={onChange} />
    </td>
  );
}

/**
 * The bar that appears once rows are ticked: how many, and what can be done
 * to all of them at once. Every action here is a real server action on the
 * selection; the bar never computes a figure over the ticked rows.
 */
export function BulkBar({ count, noun, children, onClear }: { count: number; noun: string; children: ReactNode; onClear: () => void }) {
  if (count === 0) return null;
  return (
    <div className="bulk-bar" role="region" aria-label="Selected rows">
      <span className="bulk-bar-count"><strong>{count}</strong> {count === 1 ? noun : `${noun}s`} selected</span>
      <span className="bulk-bar-actions">{children}</span>
      <Button small variant="quiet" onClick={onClear}>Clear</Button>
    </div>
  );
}

/* ------------------------------------------------------------------------ *
 * Filter chips (design system F3)
 * ------------------------------------------------------------------------ */

export interface FilterChip {
  key: string;
  label: string;
  onRemove: () => void;
}

/** The filters narrowing a register, each removable in place. */
export function FilterChips({ chips, onClearAll, children }: { chips: FilterChip[]; onClearAll?: () => void; children?: ReactNode }) {
  if (chips.length === 0 && !children) return null;
  return (
    <div className="filter-chips" aria-label="Active filters">
      {chips.map((chip) => (
        <button key={chip.key} type="button" className="filter-chip" onClick={chip.onRemove} aria-label={`Remove filter ${chip.label}`}>
          {chip.label}
          <Icon name="close" />
        </button>
      ))}
      {chips.length > 1 && onClearAll ? <Button small variant="quiet" onClick={onClearAll}>Clear all</Button> : null}
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------------ *
 * Date ranges (design system F4)
 * ------------------------------------------------------------------------ */

export interface DatePreset {
  key: string;
  label: string;
  /** The range this preset names, worked out from today's date. */
  range: () => { from: string; to: string };
}

const iso = (date: Date) => date.toISOString().slice(0, 10);
const today = () => new Date();
const daysAgo = (days: number) => { const date = today(); date.setDate(date.getDate() - days); return date; };

/** The presets most registers want. Calendar arithmetic only; never a figure. */
export const DATE_PRESETS: DatePreset[] = [
  { key: "30d", label: "30 d", range: () => ({ from: iso(daysAgo(30)), to: iso(today()) }) },
  { key: "90d", label: "90 d", range: () => ({ from: iso(daysAgo(90)), to: iso(today()) }) },
  { key: "12m", label: "12 months", range: () => { const date = today(); date.setFullYear(date.getFullYear() - 1); date.setDate(date.getDate() + 1); return { from: iso(date), to: iso(today()) }; } },
  { key: "ytd", label: "YTD", range: () => ({ from: `${today().getFullYear()}-01-01`, to: iso(today()) }) },
];

/**
 * A period as presets with a custom option, instead of two bare date boxes.
 * The pressed preset is the one whose range matches the current dates; when
 * none does, Custom is pressed and the boxes show.
 */
export function DateRange({ label, from, to, onChange, presets = DATE_PRESETS }: {
  label: string;
  from: string;
  to: string;
  onChange: (range: { from: string; to: string }) => void;
  presets?: DatePreset[];
}) {
  const matched = presets.find((preset) => { const range = preset.range(); return range.from === from && range.to === to; });
  const [custom, setCustom] = useState(false);
  const showBoxes = custom || !matched;
  return (
    <div className="date-range">
      <div className="segmented" role="group" aria-label={label}>
        {presets.map((preset) => (
          <button key={preset.key} type="button" className="segment" aria-pressed={!custom && matched?.key === preset.key} onClick={() => { setCustom(false); onChange(preset.range()); }}>
            {preset.label}
          </button>
        ))}
        <button type="button" className="segment" aria-pressed={showBoxes} onClick={() => setCustom(true)}>Custom…</button>
      </div>
      {showBoxes ? (
        <div className="date-range-custom">
          <label><span className="visually-hidden">From</span><input className="input" type="date" value={from} max={to || undefined} onChange={(event) => onChange({ from: event.target.value, to })} /></label>
          <span aria-hidden="true">—</span>
          <label><span className="visually-hidden">To</span><input className="input" type="date" value={to} min={from || undefined} onChange={(event) => onChange({ from, to: event.target.value })} /></label>
        </div>
      ) : null}
    </div>
  );
}

/** The first and last day of the month before this one, as ISO dates. */
const lastMonthEnd = () => { const date = today(); date.setDate(0); return iso(date); };

/**
 * A single "as at" date as presets with a custom option (design system F4):
 * today, the last month end, or a date typed in. The pressed preset is the one
 * the date matches; a date neither matches shows the box.
 */
export function DatePoint({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  const presets = [
    { key: "today", label: "Today", value: iso(today()) },
    { key: "month_end", label: "Last month end", value: lastMonthEnd() },
  ];
  const matched = presets.find((preset) => preset.value === value);
  const [custom, setCustom] = useState(false);
  const showBox = custom || !matched;
  return (
    <div className="date-range">
      <div className="segmented" role="group" aria-label={label}>
        {presets.map((preset) => (
          <button key={preset.key} type="button" className="segment" aria-pressed={!custom && matched?.key === preset.key} onClick={() => { setCustom(false); onChange(preset.value); }}>
            {preset.label}
          </button>
        ))}
        <button type="button" className="segment" aria-pressed={showBox} onClick={() => setCustom(true)}>Custom…</button>
      </div>
      {showBox ? (
        <div className="date-range-custom">
          <label><span className="visually-hidden">{label}</span><input className="input" type="date" value={value} onChange={(event) => onChange(event.target.value)} /></label>
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------------ *
 * Inline editing (design system E3)
 * ------------------------------------------------------------------------ */

/**
 * A cell that edits in place: double-click or Enter opens it, Enter saves,
 * Escape puts the old value back. For one small correction — a date, a short
 * name — where a form page would be ceremony. `onSave` is the server call;
 * the cell shows the server's answer, not what was typed.
 */
export function InlineEdit({ value, display, label, type = "text", onSave, disabled }: {
  value: string;
  display: ReactNode;
  label: string;
  type?: "text" | "date";
  onSave: (value: string) => Promise<void>;
  disabled?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = () => { if (disabled) return; setDraft(value); setError(null); setEditing(true); };
  const cancel = () => { setEditing(false); setError(null); };
  const save = async () => {
    if (draft === value) { cancel(); return; }
    setBusy(true);
    try {
      await onSave(draft);
      setEditing(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  };
  const keys = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") { event.preventDefault(); void save(); }
    if (event.key === "Escape") { event.preventDefault(); cancel(); }
  };

  if (editing) {
    return (
      <span className="inline-edit inline-edit-open">
        <input className="input" type={type} value={draft} aria-label={label} aria-invalid={error ? true : undefined} disabled={busy} autoFocus onChange={(event) => setDraft(event.target.value)} onKeyDown={keys} onBlur={() => { if (!busy) void save(); }} />
        {error ? <span className="field-error" role="alert">{error}</span> : null}
      </span>
    );
  }
  return (
    <button
      type="button"
      className={disabled ? "inline-edit" : "inline-edit inline-edit-editable"}
      aria-label={`${label}: ${typeof display === "string" ? display : value || "not set"}. ${disabled ? "" : "Press Enter to edit."}`}
      disabled={disabled}
      onDoubleClick={open}
      onKeyDown={(event) => { if (event.key === "Enter") open(); }}
    >
      {display}
      {disabled ? null : <Icon name="edit" className="inline-edit-mark" />}
    </button>
  );
}

/* ------------------------------------------------------------------------ *
 * Card rows (design system E5)
 * ------------------------------------------------------------------------ */

/** A register of records with few columns, each a slim card instead of a row. */
export function CardRows({ label, children }: { label: string; children: ReactNode }) {
  return <ul className="card-rows" aria-label={label}>{children}</ul>;
}

/**
 * One record: its identity, two or three facts, its status and its menu.
 * Reads well on a phone without stacking: the facts wrap, the identity stays.
 */
export function CardRow({ title, meta, facts, status, actions, flagged, onOpen }: {
  title: ReactNode;
  meta?: ReactNode;
  facts: { label: string; value: ReactNode }[];
  status?: ReactNode;
  /** The row menu or a single visible action. */
  actions?: ReactNode;
  flagged?: boolean;
  onOpen?: () => void;
}) {
  return (
    <li className={flagged ? "card-row card-row-flag" : "card-row"}>
      <div className="card-row-identity">
        {onOpen ? <button type="button" className="button-link" onClick={onOpen}><strong>{title}</strong></button> : <strong>{title}</strong>}
        {meta ? <span className="card-row-meta">{meta}</span> : null}
      </div>
      {facts.map((fact) => (
        <div key={fact.label} className="card-row-fact">
          <span className="card-row-label">{fact.label}</span>
          <span className="card-row-value">{fact.value}</span>
        </div>
      ))}
      {status ? <div className="card-row-status">{status}</div> : null}
      {actions ? <div className="card-row-actions">{actions}</div> : null}
    </li>
  );
}
