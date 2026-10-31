"use client";

import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

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
  /** A register: grows with the page rather than scrolling inside a box. */
  stickyHeader?: boolean;
  children: ReactNode;
}) {
  const table = useRef<HTMLTableElement>(null);
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
  const classes = ["table", fixedFirst ? "table-fixed-first" : "", compact ? "table-compact" : "", "table-stack"]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={stickyHeader ? "table-scroll table-scroll-register" : "table-scroll"} tabIndex={0} role="group" aria-label={label}>
      <table className={classes} ref={table}>
        <caption className="visually-hidden">{label}</caption>
        {children}
      </table>
    </div>
  );
}
