"use client";

import { useEffect, useRef, useState } from "react";
import type { ReactNode, RefObject } from "react";
import { Icon } from "./Icon";

/** One action a row already offers, found in the row itself when its menu opens. */
type RowAction = { label: string; run: () => void };

/** Where a row sits inside the frame, so its menu can be drawn beside it. */
type RowPlace = { index: number; top: number; name: string };

/**
 * A wide table that scrolls inside itself.
 *
 * The registers in this product are genuinely wide — a unit has four status
 * dimensions and a deal has five records behind it — so on a desktop they
 * scroll sideways rather than being cut down. `fixedFirst` keeps the identity
 * column in view while the rest scrolls.
 *
 * On a phone every table instead stacks each row as a card: every cell
 * carries its column heading as `data-label`, copied from the header after
 * each render, so no call site has to repeat its headings. A sideways scroll
 * with most columns out of view hid exactly the money and status a reader
 * opened the table for.
 *
 * Every row also has the same three-dot menu (design system E2). A register
 * that writes its own `RowMenu` keeps it; any other row gets one here, holding
 * the links and buttons the row already shows plus "Copy row". The menu is
 * drawn beside the table rather than inside it, so it never touches the rows
 * React renders, and it stays at the visible right edge while a wide table
 * scrolls sideways.
 */
export function TableScroll({
  label,
  fixedFirst,
  compact,
  stickyHeader,
  rowMenu = true,
  children,
}: {
  label: string;
  fixedFirst?: boolean;
  compact?: boolean;
  /** A register: grows with the page rather than scrolling inside a box. */
  stickyHeader?: boolean;
  /** False only where a row has nothing to act on or copy, such as an editor grid. */
  rowMenu?: boolean;
  children: ReactNode;
}) {
  const frame = useRef<HTMLDivElement>(null);
  const table = useRef<HTMLTableElement>(null);
  const [places, setPlaces] = useState<RowPlace[]>([]);
  useEffect(() => {
    if (!table.current) return;
    const headings = [...table.current.querySelectorAll("thead tr:last-child th")].map(cell => cell.textContent?.trim() ?? "");
    for (const row of table.current.querySelectorAll("tbody tr")) {
      // A row that spans columns (a note, an expanded detail) has no column to name.
      if ([...row.children].some(cell => (cell as HTMLTableCellElement).colSpan > 1)) continue;
      [...row.children].forEach((cell, index) => {
        const heading = headings[index];
        if (heading) cell.setAttribute("data-label", heading);
        else cell.removeAttribute("data-label");
      });
    }
  });
  useEffect(() => {
    const box = frame.current;
    const body = table.current;
    if (!rowMenu || !box || !body) return;
    // Measured from observer callbacks, never during render: rows move when
    // data arrives, when the window resizes and when a phone stacks them.
    const measure = () => {
      const origin = box.getBoundingClientRect().top;
      const next = menuRows(body).map(({ row, index }) => {
        const place = row.getBoundingClientRect();
        return { index, top: Math.round(place.top - origin + (place.height < 80 ? place.height / 2 - 16 : 10)), name: rowName(row) };
      });
      setPlaces(current => same(current, next) ? current : next);
    };
    const resize = new ResizeObserver(measure);
    resize.observe(body);
    const change = new MutationObserver(measure);
    change.observe(body, { childList: true, subtree: true, characterData: true });
    return () => { resize.disconnect(); change.disconnect(); };
  }, [rowMenu]);
  const classes = ["table", fixedFirst ? "table-fixed-first" : "", compact ? "table-compact" : "", "table-stack"]
    .filter(Boolean)
    .join(" ");
  return (
    <div className="table-frame" ref={frame}>
      <div className={stickyHeader ? "table-scroll table-scroll-register" : "table-scroll"} tabIndex={0} role="group" aria-label={label}>
        <table className={classes} ref={table}>
          <caption className="visually-hidden">{label}</caption>
          {children}
        </table>
      </div>
      {rowMenu ? places.map(place => <AutoRowMenu key={place.index} place={place} table={table} />) : null}
    </div>
  );
}

/** The body rows that need a menu: not a spanning note, not one with its own. */
function menuRows(body: HTMLTableElement) {
  return [...body.querySelectorAll<HTMLTableRowElement>(":scope > tbody > tr")]
    .map((row, index) => ({ row, index }))
    .filter(({ row }) => !row.querySelector(".row-menu") && ![...row.cells].some(cell => cell.colSpan > 1) && row.getClientRects().length > 0);
}

function rowName(row: HTMLTableRowElement) {
  return (row.cells[0]?.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 60) || "this row";
}

function same(a: RowPlace[], b: RowPlace[]) {
  return a.length === b.length && a.every((place, i) => place.index === b[i].index && place.top === b[i].top && place.name === b[i].name);
}

/** Text as it is laid out on screen, its lines joined with a middle dot. */
function shown(element: HTMLElement) {
  return (element.innerText || element.textContent || "")
    .split("\n")
    .map(line => line.replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .join(" · ");
}

/** What a row already lets the reader do, read from the row when its menu opens. */
function rowActions(row: HTMLTableRowElement): RowAction[] {
  const actions: RowAction[] = [];
  const seen = new Set<string>();
  const add = (label: string, run: () => void) => {
    const text = label.replace(/\s+/g, " ").trim().slice(0, 48);
    if (!text || seen.has(text)) return;
    seen.add(text);
    actions.push({ label: text, run });
  };
  for (const control of row.querySelectorAll<HTMLElement>("a[href], button")) {
    if (control.matches(":disabled, .row-menu-trigger, [role='checkbox'], [aria-hidden='true']")) continue;
    // The first line a reader sees on the control: a code above its kind
    // reads "CT-SYN-002", not "CT-SYN-002consultancy".
    const words = shown(control).split(" · ")[0] || control.getAttribute("aria-label") || "";
    // A reference opens its record; a phrase ("Prepare SPA schedule") is
    // already the action and keeps its own words.
    const reference = !/\s/.test(words) || (/\d/.test(words) && words.length <= 24);
    const opens = control.tagName === "A" || control.classList.contains("button-link");
    add(opens && reference ? `Open ${words}` : words, () => control.click());
  }
  return actions;
}

/** Each cell under its column heading, one per line, ready to paste. */
function rowText(row: HTMLTableRowElement) {
  return [...row.cells]
    .map(cell => {
      const value = shown(cell);
      const heading = cell.getAttribute("data-label");
      return value ? (heading ? `${heading}: ${value}` : value) : "";
    })
    .filter(Boolean)
    .join("\n");
}

function AutoRowMenu({ place, table }: { place: RowPlace; table: RefObject<HTMLTableElement | null> }) {
  const [open, setOpen] = useState(false);
  const [actions, setActions] = useState<RowAction[]>([]);
  const [copied, setCopied] = useState(false);
  const [at, setAt] = useState<{ top: number; right: number } | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const row = () => table.current?.querySelectorAll<HTMLTableRowElement>(":scope > tbody > tr")[place.index];
  useEffect(() => {
    if (!open) return;
    root.current?.querySelector<HTMLElement>(".row-menu-list button")?.focus();
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { setOpen(false); trigger.current?.focus(); } };
    const away = () => setOpen(false);
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    window.addEventListener("scroll", away, true);
    window.addEventListener("resize", away);
    return () => {
      document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape);
      window.removeEventListener("scroll", away, true); window.removeEventListener("resize", away);
    };
  }, [open]);
  const toggle = () => {
    const current = row();
    if (!open && current) { setActions(rowActions(current)); setCopied(false); }
    const box = trigger.current?.getBoundingClientRect();
    if (box) setAt({ top: box.bottom + 4, right: window.innerWidth - box.right });
    setOpen(value => !value);
  };
  const copy = () => {
    const current = row();
    if (!current) return;
    void navigator.clipboard?.writeText(rowText(current)).then(() => setCopied(true), () => setCopied(false));
  };
  return <div className="row-menu table-row-menu" ref={root} style={{ top: place.top }}>
    <button ref={trigger} type="button" className="row-menu-trigger" aria-label={`Actions for ${place.name}`} aria-expanded={open} onClick={toggle}><Icon name="more" /></button>
    <div className="row-menu-list" hidden={!open} style={at ?? undefined}>
      {actions.map(action => <button key={action.label} type="button" onClick={() => { setOpen(false); action.run(); }}>{action.label}</button>)}
      <button type="button" onClick={copy}>{copied ? "Copied" : "Copy row"}</button>
    </div>
  </div>;
}
