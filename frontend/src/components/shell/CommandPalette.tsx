"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { DialogPortal, Icon, Kbd, useDensity } from "@/components/ui";
import { useOverlay } from "@/components/ui/overlay";
import type { CurrentUser } from "@/lib/api";
import { workspace } from "@/lib/api/workspace";
import type { SearchResult } from "@/lib/api/workspace";
import type { IconName } from "@/components/ui";
import { hasAnyRole, PORTFOLIO_READERS, roleSet } from "@/lib/roles";

import { PROJECT_NAVIGATION, SETTINGS_NAVIGATION, projectHref, settingsHref, visibleNavigation } from "./navigation";
import { recordHref } from "./recordRoutes";

interface Entry {
  key: string;
  group: "Screens" | "Actions" | "Projects" | "Units" | "Buyers";
  label: string;
  meta?: string;
  icon: IconName;
  run: () => void;
}

/** The statuses a unit hit is read with, in the words the register uses. */
const UNIT_STATUS: Record<string, string> = {
  unreleased: "Unreleased", held: "Held", available: "Available", reserved: "Reserved",
  contract_pending: "Contract pending", contracted: "Contracted", sold: "Sold", returned: "Returned",
};

/**
 * ⌘K anywhere: jump to a screen, a project, a unit or a buyer, or run one of
 * the few actions that are not a screen (design system F2).
 *
 * Screens and actions are known to the browser and filter as you type. The
 * records come from the server's own search, scoped exactly as the registers
 * are: a unit under a phase this person was not granted, or a buyer in another
 * advisor's book, is not in the answer. Arrow keys move, Enter goes, Escape
 * closes; focus returns to what opened it.
 */
export function CommandPalette({ user, projectId, onClose, onSignOut }: {
  user: CurrentUser;
  projectId?: string;
  onClose: () => void;
  onSignOut: () => void;
}) {
  const router = useRouter();
  const { density, setDensity } = useDensity();
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<SearchResult | null>(null);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const listId = useId();
  const dialog = useOverlay<HTMLDivElement>(onClose, "input");
  const latest = useRef(0);
  const roles = useMemo(() => roleSet(user.roles), [user.roles]);

  const needle = query.trim();
  // Searching until the server has answered this exact query; a shorter query asks nothing.
  const searching = needle.length >= 2 && found?.query !== needle;

  useEffect(() => {
    if (needle.length < 2) return;
    const ticket = ++latest.current;
    const timer = window.setTimeout(() => {
      void workspace.search(needle)
        .then((result) => { if (ticket === latest.current) setFound(result); })
        .catch(() => { if (ticket === latest.current) setFound({ query: needle, projects: [], units: [], clients: [] }); });
    }, 180);
    return () => window.clearTimeout(timer);
  }, [needle]);

  const go = (href: string) => { onClose(); router.push(href); };

  const entries = useMemo<Entry[]>(() => {
    const screens: Entry[] = [];
    if (hasAnyRole(roles, PORTFOLIO_READERS)) screens.push({ key: "portfolio", group: "Screens", label: "Portfolio", icon: "overview", run: () => go("/portfolio/") });
    screens.push({ key: "projects", group: "Screens", label: "Projects", meta: "All developments", icon: "projects", run: () => go("/projects/") });
    if (projectId) {
      for (const group of visibleNavigation(PROJECT_NAVIGATION, roles)) {
        for (const item of group.items) {
          screens.push({ key: `section-${item.key}`, group: "Screens", label: item.label, meta: group.label ?? "Project", icon: item.icon, run: () => go(projectHref(projectId, item.key)) });
        }
      }
    }
    for (const group of visibleNavigation(SETTINGS_NAVIGATION, roles)) {
      for (const item of group.items) {
        screens.push({ key: `settings-${item.key}`, group: "Screens", label: item.label, meta: "Settings", icon: item.icon, run: () => go(settingsHref(item.key)) });
      }
    }
    const actions: Entry[] = [
      { key: "density", group: "Actions", label: density === "compact" ? "Comfortable rows" : "Compact rows", meta: "Register density, remembered for you", icon: "layers", run: () => { setDensity(density === "compact" ? "comfortable" : "compact"); onClose(); } },
      { key: "switch", group: "Actions", label: "Switch project", icon: "swap", run: () => go("/projects/") },
      { key: "signout", group: "Actions", label: "Sign out", icon: "sign-out", run: () => { onClose(); onSignOut(); } },
    ];
    const lower = needle.toLowerCase();
    const local = [...screens, ...actions].filter((entry) => !lower || `${entry.label} ${entry.meta ?? ""}`.toLowerCase().includes(lower));
    const records: Entry[] = [];
    if (found && found.query === needle) {
      for (const project of found.projects) records.push({ key: `project-${project.id}`, group: "Projects", label: project.name, meta: [project.code, project.city].filter(Boolean).join(" · "), icon: "projects", run: () => go(projectHref(project.id, "overview")) });
      for (const unit of found.units) records.push({ key: `unit-${unit.id}`, group: "Units", label: unit.unit_reference, meta: `${unit.project_code} · ${UNIT_STATUS[unit.commercial_status] ?? unit.commercial_status}`, icon: "inventory", run: () => go(recordHref(unit.project_id, "unit", unit.id)) });
      for (const buyer of found.clients) records.push({ key: `buyer-${buyer.id}`, group: "Buyers", label: buyer.display_name, meta: `${buyer.project_code} · ${buyer.client_number}`, icon: "user", run: () => go(`/projects/?${new URLSearchParams({ project: buyer.project_id, section: "buyers", buyer: buyer.client_number })}`) });
    }
    return [...records, ...local].slice(0, 24);
    // `go` closes over router and onClose, both stable for the palette's life.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roles, projectId, density, needle, found]);

  // The highlighted entry is remembered by key, so a new answer that no longer
  // holds it falls back to the first row without an effect resetting anything.
  const active = Math.max(0, entries.findIndex((entry) => entry.key === activeKey));
  const current = entries[active];
  const move = (step: number) => { const next = entries[Math.min(Math.max(active + step, 0), entries.length - 1)]; if (next) setActiveKey(next.key); };

  let lastGroup: Entry["group"] | null = null;
  return (
    <DialogPortal>
      <div className="dialog-backdrop palette-backdrop" onPointerDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
        <div className="palette" role="dialog" aria-label="Jump to a screen, project, unit or buyer" ref={dialog}>
          <label className="palette-search">
            <Icon name="search" />
            <input
              type="text"
              role="combobox"
              aria-expanded="true"
              aria-controls={listId}
              aria-activedescendant={current ? `${listId}-${current.key}` : undefined}
              aria-autocomplete="list"
              autoComplete="off"
              placeholder="Jump to a unit, buyer, project, screen or action…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "ArrowDown") { event.preventDefault(); move(1); }
                else if (event.key === "ArrowUp") { event.preventDefault(); move(-1); }
                else if (event.key === "Enter" && current) { event.preventDefault(); current.run(); }
              }}
            />
            <Kbd>esc</Kbd>
          </label>
          <ul className="palette-list" id={listId} role="listbox" aria-label="Results">
            {entries.map((entry, index) => {
              const heading = entry.group !== lastGroup ? entry.group : null;
              lastGroup = entry.group;
              return (
                <li key={entry.key} role="presentation">
                  {heading ? <div className="palette-group" aria-hidden="true">{heading}</div> : null}
                  <button
                    type="button"
                    id={`${listId}-${entry.key}`}
                    role="option"
                    aria-selected={index === active}
                    className={index === active ? "palette-item palette-item-active" : "palette-item"}
                    onPointerMove={() => setActiveKey(entry.key)}
                    onClick={entry.run}
                  >
                    <Icon name={entry.icon} />
                    <span className="palette-item-text"><span>{entry.label}</span>{entry.meta ? <span className="palette-item-meta">{entry.meta}</span> : null}</span>
                    {index === active ? <Kbd>↵</Kbd> : null}
                  </button>
                </li>
              );
            })}
            {entries.length === 0 ? <li className="palette-empty" role="presentation">{searching ? "Searching…" : needle.length < 2 ? "Type at least two characters to search records." : "Nothing matches. Try a unit reference, a buyer name or a screen."}</li> : null}
          </ul>
          <p className="palette-foot">{searching ? "Searching records…" : "Records are searched as you may see them: units in your phases, buyers in your book."}</p>
        </div>
      </div>
    </DialogPortal>
  );
}
