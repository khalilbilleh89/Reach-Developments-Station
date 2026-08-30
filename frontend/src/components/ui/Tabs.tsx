"use client";

import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

/** A stable, unique id stem for one tab group, taken from its label. */
function slug(label: string): string {
  return label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

/**
 * One set of sections.
 *
 * A real tablist, so the arrow keys work and a screen reader announces which of
 * eight sections is showing. On a phone the row scrolls sideways rather than
 * wrapping into three ragged lines.
 *
 * Ids are derived from the group's label rather than from the tab keys alone,
 * because two tab groups can be on screen at once — the project's sections
 * behind a record drawer's — and two elements sharing an id makes both of them
 * unreachable by name.
 */
export function Tabs({
  label,
  tabs,
  active,
  onSelect,
  group,
}: {
  label: string;
  tabs: { key: string; label: string }[];
  active: string;
  onSelect: (key: string) => void;
  group?: string;
}) {
  const stem = group ?? slug(label);
  const row = useRef<HTMLDivElement>(null);

  // On a narrow screen the row scrolls, and the selected section can end up off
  // the edge — which reads as nothing being selected at all. Bring it back.
  useEffect(() => {
    const selected = row.current?.querySelector('[aria-selected="true"]');
    selected?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [active]);

  // Arrow keys move BOTH selection and browser focus. Selection alone is not
  // enough: the old tab immediately drops to tabIndex -1, and a keyboard user
  // pressing Right, Right, Right would be typing at a button that is no longer
  // in the tab order. Focus therefore always follows the selected tab.
  const select = (key: string) => {
    onSelect(key);
    document.getElementById(`${stem}-tab-${key}`)?.focus();
  };

  const move = (index: number, step: number) => {
    const next = tabs[(index + step + tabs.length) % tabs.length];
    if (next) select(next.key);
  };

  return (
    <div className="tabs" role="tablist" aria-label={label} ref={row}>
      {tabs.map((tab, index) => (
        <button
          key={tab.key}
          id={`${stem}-tab-${tab.key}`}
          role="tab"
          type="button"
          aria-selected={active === tab.key}
          aria-controls={`${stem}-panel-${tab.key}`}
          tabIndex={active === tab.key ? 0 : -1}
          className={`tab ${active === tab.key ? "tab-active" : ""}`}
          onClick={() => onSelect(tab.key)}
          onKeyDown={(event) => {
            if (event.key === "ArrowRight") {
              event.preventDefault();
              move(index, 1);
            } else if (event.key === "ArrowLeft") {
              event.preventDefault();
              move(index, -1);
            } else if (event.key === "Home") {
              event.preventDefault();
              if (tabs[0]) select(tabs[0].key);
            } else if (event.key === "End") {
              event.preventDefault();
              const final = tabs[tabs.length - 1];
              if (final) select(final.key);
            }
          }}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

/**
 * The region a tab reveals.
 *
 * `group` must match the label of the `Tabs` that controls it, so the panel and
 * its tab point at each other.
 */
export function TabPanel({
  group,
  tab,
  className,
  children,
}: {
  group: string;
  tab: string;
  className?: string;
  children: ReactNode;
}) {
  const stem = slug(group);
  return (
    <div
      id={`${stem}-panel-${tab}`}
      role="tabpanel"
      aria-labelledby={`${stem}-tab-${tab}`}
      className={className ?? "stack"}
    >
      {children}
    </div>
  );
}
