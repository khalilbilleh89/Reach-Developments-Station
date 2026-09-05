"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { ApiError, projects as projectsApi } from "@/lib/api";
import type { ProjectDetail, ProjectSummary } from "@/lib/api";
import { Icon } from "@/components/ui";
import { useOverlay } from "@/components/ui/overlay";
import { projectStatusLabel } from "@/components/projects/projectStatus";
import { projectHref } from "./navigation";
import type { ProjectSection } from "./navigation";

/** The letters a project code opens with: "RG-01" → "RG", "DT07" → "DT". */
function glyph(code: string): string {
  const letters = /^[A-Za-z]+/.exec(code)?.[0] ?? code;
  return letters.slice(0, 3).toUpperCase();
}

/**
 * Which development you are inside, and the way to another one.
 *
 * The open project is the most important fact on the screen, so it sits at
 * the top of the rail under the brand and stays there whichever section is
 * open. Pressing it lists the projects this person may see — the same list
 * the portfolio screen shows, filtered as you type, and nothing the API would
 * not have returned anyway. A project a person cannot open is simply not in
 * the list.
 *
 * Switching keeps the section: somebody comparing collections across two
 * developments lands on the other project's collections, not its front page.
 */
export function ProjectSwitcher({
  project,
  projectId,
  section,
  onNavigate,
}: {
  project: ProjectDetail | null;
  projectId: string;
  section?: string;
  /** Called when a project is chosen, so a drawer holding the switcher can close. */
  onNavigate?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const [anchor, setAnchor] = useState<{ top: number; left: number } | null>(null);

  const openMenu = () => {
    const rect = button.current?.getBoundingClientRect();
    if (rect) {
      const width = Math.min(384, window.innerWidth - 32);
      setAnchor({
        top: Math.min(rect.bottom + 6, window.innerHeight - 200),
        left: Math.max(16, Math.min(rect.left, window.innerWidth - width - 16)),
      });
    }
    setOpen(true);
  };

  return (
    <div className="switcher">
      <button
        ref={button}
        type="button"
        className="switcher-button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={project ? `Project: ${project.name}. Switch project` : "Switch project"}
        onClick={openMenu}
      >
        <span className="switcher-glyph" aria-hidden="true">
          {project ? glyph(project.code) : "…"}
        </span>
        <span className="switcher-text">
          <span className="switcher-name">{project ? project.name : "Loading project…"}</span>
          <span className="switcher-meta">
            {project
              ? [project.code, projectStatusLabel(project.status), project.city]
                  .filter(Boolean)
                  .join(" · ")
              : ""}
          </span>
        </span>
        <Icon name="chevron-down" className="switcher-chevron" />
      </button>
      {open && anchor ? (
        <SwitcherMenu
          currentId={projectId}
          section={(section as ProjectSection | undefined) ?? "overview"}
          anchor={anchor}
          onClose={() => setOpen(false)}
          onChosen={onNavigate}
        />
      ) : null}
    </div>
  );
}

function SwitcherMenu({
  currentId,
  section,
  anchor,
  onClose,
  onChosen,
}: {
  currentId: string;
  section: ProjectSection;
  anchor: { top: number; left: number };
  onClose: () => void;
  onChosen?: () => void;
}) {
  const choose = () => {
    onClose();
    onChosen?.();
  };
  const panel = useOverlay<HTMLDivElement>(onClose, "input");
  const [rows, setRows] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let live = true;
    void (async () => {
      try {
        const list = await projectsApi.list();
        if (live) setRows(list);
      } catch (caught) {
        if (live) {
          setRows([]);
          setError(caught instanceof ApiError ? caught.message : "Could not load projects.");
        }
      }
    })();
    return () => {
      live = false;
    };
  }, []);

  const needle = query.trim().toLowerCase();
  const shown = (rows ?? []).filter(
    (row) =>
      !needle ||
      row.name.toLowerCase().includes(needle) ||
      row.code.toLowerCase().includes(needle) ||
      (row.city ?? "").toLowerCase().includes(needle),
  );

  return (
    <>
      <div className="menu-scrim" onMouseDown={onClose} />
      <div
        className="switcher-menu"
        role="dialog"
        aria-modal="true"
        aria-label="Switch project"
        ref={panel}
        style={{ top: anchor.top, left: anchor.left }}
      >
        <div className="switcher-search">
          <div className="toolbar-search">
            <Icon name="search" />
            <input
              className="input"
              type="search"
              placeholder="Find a project"
              aria-label="Find a project"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
        </div>
        <ul className="switcher-list">
          {rows === null ? (
            <li className="switcher-note" role="status">
              Loading projects…
            </li>
          ) : error ? (
            <li className="switcher-note">{error}</li>
          ) : shown.length === 0 ? (
            <li className="switcher-note">No project matches.</li>
          ) : (
            shown.map((row) => (
              <li key={row.id}>
                <Link
                  href={projectHref(row.id, section)}
                  className="switcher-option"
                  aria-current={row.id === currentId ? "true" : undefined}
                  onClick={choose}
                >
                  <span className="switcher-option-code">{row.code}</span>
                  <span className="switcher-option-name">{row.name}</span>
                  {row.id === currentId ? <Icon name="check" /> : <span />}
                  <span className="switcher-option-meta">
                    {[projectStatusLabel(row.status), row.city].filter(Boolean).join(" · ")}
                  </span>
                </Link>
              </li>
            ))
          )}
        </ul>
        <div className="switcher-foot">
          <Link href="/projects/" className="button button-small" onClick={choose}>
            All projects
          </Link>
        </div>
      </div>
    </>
  );
}
