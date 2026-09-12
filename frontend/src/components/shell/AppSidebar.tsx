"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
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
import { hasAnyRole, PORTFOLIO_READERS, roleSet } from "@/lib/roles";

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
  const query = useSearchParams();
  const configuration = section === "inventory" && query.get("view") === "configuration" && !query.get("record");
  const stock = section === "inventory" && query.get("view") === "stock" && !query.get("record");
  const roles = user.roles.map((role) => role.label).join(", ");
  const onProjects = area === "projects";
  const insideProject = onProjects && Boolean(projectId);

  return (
    <>
      <div className="brand">
        <Link href="/projects/" className="brand-mark" aria-label="Reach — all projects">
          <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M6 27V5h10c7 0 11 3 11 9 0 4-2 7-6 9l7 4h-9l-9-7h6c4 0 6-2 6-6s-2-5-6-5h-5v18Z" fill="currentColor" /></svg>
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
        {hasAnyRole(roleSet(user.roles), PORTFOLIO_READERS) ? (
          <nav className="nav-group nav-portfolio" aria-label="Portfolio management">
            <ul className="nav-list"><li><Link href="/portfolio/" className="nav-item" data-label="Portfolio" aria-current={area === "portfolio" ? "page" : undefined} onClick={onClose}>
              <Icon name="overview" className="nav-icon" /><span className="nav-label">Portfolio</span>
            </Link></li></ul>
          </nav>
        ) : null}
        {insideProject && projectId ? (
          <ProjectSwitcher project={project ?? null} projectId={projectId} section={section} onNavigate={onClose} />
        ) : null}

        {!insideProject ? (
          <nav className="nav-group" aria-label="Development directory">
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
                const current = item.key === section && !(item.key === "inventory" && (stock || configuration));
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
                    {area === "projects" && item.key === "inventory" && projectId ? <Link href={`${sectionHref(area,projectId,"inventory")}&view=stock`} className="nav-item nav-stock" data-label="Stock" aria-current={stock ? "page" : undefined} onClick={onClose}><Icon name="inventory" className="nav-icon" /><span className="nav-label">Stock</span></Link> : null}
                    {area === "projects" && item.key === "inventory" && projectId ? <Link href={`${sectionHref(area,projectId,"inventory")}&view=configuration`} className="nav-item nav-stock" data-label="Configuration" aria-current={configuration ? "page" : undefined} onClick={onClose}><Icon name="settings" className="nav-icon" /><span className="nav-label">Configuration</span></Link> : null}
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
