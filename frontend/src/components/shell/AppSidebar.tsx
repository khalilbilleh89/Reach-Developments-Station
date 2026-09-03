"use client";

import Link from "next/link";
import { useEffect } from "react";

import type { CurrentUser, ProjectDetail } from "@/lib/api";
import { Icon } from "@/components/ui";
import { useOverlay } from "@/components/ui/overlay";
import { ProjectSwitcher } from "./ProjectSwitcher";
import {
  isProjectSection,
  isSettingsSection,
  projectHref,
  settingsHref,
} from "./navigation";
import type { NavGroup } from "./navigation";
import type { ShellArea } from "./AppShell";

interface SidebarProps {
  user: CurrentUser;
  area: ShellArea;
  project?: ProjectDetail | null;
  projectId?: string;
  section?: string;
  groups: NavGroup[];
  onSignOut: () => void;
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = parts.slice(0, 2).map((part) => part[0]?.toUpperCase() ?? "");
  return letters.join("") || "?";
}

function sectionHref(area: ShellArea, projectId: string | undefined, key: string): string {
  if (area === "settings") return isSettingsSection(key) ? settingsHref(key) : settingsHref();
  if (projectId && isProjectSection(key)) return projectHref(projectId, key);
  return "/projects/";
}

/**
 * What the rail contains, wherever it is drawn.
 *
 * Top to bottom: the product, the open project, the sections of the place you
 * are in, and at the foot the person signed in with the way to Settings and
 * the way out. The same content is rendered inside the sticky desktop rail and
 * inside the phone's navigation drawer, so the two never drift apart.
 */
export function SidebarContent({
  user,
  area,
  project,
  projectId,
  section,
  groups,
  onSignOut,
  onClose,
}: SidebarProps & { onClose?: () => void }) {
  const roles = user.roles.map((role) => role.label).join(", ");
  const onProjects = area === "projects";
  const insideProject = onProjects && Boolean(projectId);

  return (
    <>
      <div className="brand">
        <Link href="/projects/" className="brand-mark" aria-label="Reach — all projects">
          R
        </Link>
        <span className="brand-text">
          <span className="brand-name">Reach</span>
          <span className="brand-sub">Developments Station</span>
        </span>
        {onClose ? (
          <button
            type="button"
            className="icon-button icon-button-nav nav-drawer-close"
            aria-label="Close navigation"
            onClick={onClose}
          >
            <Icon name="close" />
          </button>
        ) : null}
      </div>

      <div className="sidebar-scroll">
        {insideProject && projectId ? (
          <ProjectSwitcher project={project ?? null} projectId={projectId} section={section} onNavigate={onClose} />
        ) : null}

        {!insideProject ? (
          <nav className="nav-group" aria-label="Portfolio">
            <ul className="nav-list">
              <li>
                <Link
                  href="/projects/"
                  className="nav-item"
                  data-label="Projects"
                  aria-current={onProjects ? "page" : undefined}
                  onClick={onClose}
                >
                  <Icon name="projects" className="nav-icon" />
                  <span className="nav-label">Projects</span>
                </Link>
              </li>
            </ul>
          </nav>
        ) : null}

        {groups.map((group) => (
          <nav
            key={group.key}
            className="nav-group"
            aria-label={group.label ?? (area === "settings" ? "Settings" : "Project")}
          >
            {group.label ? <p className="nav-group-label">{group.label}</p> : null}
            <ul className="nav-list">
              {group.items.map((item) => {
                const current = item.key === section;
                return (
                  <li key={item.key}>
                    <Link
                      href={sectionHref(area, projectId, item.key)}
                      className="nav-item"
                      data-label={item.label}
                      aria-current={current ? "page" : undefined}
                      onClick={onClose}
                    >
                      <Icon name={item.icon} className="nav-icon" />
                      <span className="nav-label">{item.label}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
        ))}
      </div>

      <div className="sidebar-foot">
        <div className="sidebar-user" title={`${user.display_name} — ${roles || "No roles"}`}>
          <span className="avatar" aria-hidden="true">
            {initials(user.display_name)}
          </span>
          <span className="sidebar-user-text">
            <span className="sidebar-user-name">{user.display_name}</span>
            <span className="sidebar-user-roles">{roles || "No roles"}</span>
          </span>
        </div>
        <nav aria-label="Account">
          <ul className="nav-list">
            <li>
              <Link
                href={settingsHref()}
                className="nav-item"
                data-label="Settings"
                aria-current={area === "settings" && !section ? "page" : undefined}
                onClick={onClose}
              >
                <Icon name="settings" className="nav-icon" />
                <span className="nav-label">Settings</span>
              </Link>
            </li>
            <li>
              <button type="button" className="nav-item" data-label="Sign out" onClick={onSignOut}>
                <Icon name="sign-out" className="nav-icon" />
                <span className="nav-label">Sign out</span>
              </button>
            </li>
          </ul>
        </nav>
      </div>
    </>
  );
}

/** The sticky rail on a desktop or laptop screen. */
export function AppSidebar(props: SidebarProps) {
  return (
    <aside className="sidebar" aria-label="Primary">
      <SidebarContent {...props} />
    </aside>
  );
}

/**
 * The same rail as a drawer, for a phone or a narrow tablet.
 *
 * Mounted only while open, so the shared overlay helper gives it the modal
 * behaviour every other overlay has: focus moves in, Tab stays inside, Escape
 * closes it, the page behind stops scrolling, and focus returns to the menu
 * button afterwards.
 */
export function MobileNavigation({ onClose, ...props }: SidebarProps & { onClose: () => void }) {
  const panel = useOverlay<HTMLElement>(onClose, "container");

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, []);

  return (
    <>
      <div className="nav-scrim" onMouseDown={onClose} />
      <aside
        id="mobile-navigation"
        className="nav-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
        tabIndex={-1}
        ref={panel}
      >
        <SidebarContent {...props} onClose={onClose} />
      </aside>
    </>
  );
}
