"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";

import { Icon, Kbd } from "@/components/ui";
import type { CurrentUser } from "@/lib/api";

import { settingsHref } from "./navigation";

export interface Crumb {
  label: string;
  /** Absent on the current place, which is text rather than a link. */
  href?: string;
  /** Keep the active project visible when the navigation rail is hidden. */
  project?: boolean;
}

/**
 * The thin bar across the top of the working surface.
 *
 * It says where you are and offers the way to the navigation when the rail is
 * hidden. It is deliberately not a second menu: the sidebar already holds the
 * destinations, and the page header below holds the page's own actions. What
 * it may carry, on the right, is a fact about the context — the project's
 * status and base currency — that a person reads at a glance.
 */
export function ContextBar({
  crumbs,
  utilities,
  collapsed,
  user,
  onToggleRail,
  onOpenNav,
  onSearch,
  onSignOut,
}: {
  crumbs: Crumb[];
  utilities?: ReactNode;
  collapsed: boolean;
  user: CurrentUser;
  onToggleRail: () => void;
  onOpenNav: () => void;
  /** Opens the command palette (design system F2). */
  onSearch: () => void;
  onSignOut: () => void;
}) {
  return (
    <header className="context-bar">
      <button
        type="button"
        className="icon-button menu-button"
        aria-label="Open navigation"
        aria-controls="mobile-navigation"
        onClick={onOpenNav}
      >
        <Icon name="menu" />
      </button>
      <button
        type="button"
        className="icon-button rail-toggle"
        aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
        aria-pressed={collapsed}
        onClick={onToggleRail}
      >
        <Icon name="panel-left" />
      </button>
      <nav aria-label="Breadcrumb">
        <ol className={`crumbs${crumbs.some(crumb => crumb.project) ? " crumbs-project" : ""}`}>
          {crumbs.map((crumb, index) => {
            const last = index === crumbs.length - 1;
            return (
              <li key={`${crumb.label}-${index}`} className={crumb.project ? "crumb-project" : undefined}>
                {crumb.href && !last ? (
                  <Link className="crumb crumb-link" href={crumb.href}>
                    {crumb.label}
                  </Link>
                ) : (
                  <span className={last ? "crumb crumb-current" : "crumb"} aria-current={last ? "page" : undefined}>
                    {crumb.label}
                  </span>
                )}
                {!last ? (
                  <span className="crumb-sep" aria-hidden="true">
                    /
                  </span>
                ) : null}
              </li>
            );
          })}
        </ol>
      </nav>
      <div className="context-utilities">
        {utilities}
        <button type="button" className="context-search" onClick={onSearch} aria-label="Search, or jump to a screen (Command or Control K)">
          <Icon name="search" />
          <span className="context-search-text">Search</span>
          <Kbd>⌘K</Kbd>
        </button>
        <AccountMenu user={user} onSignOut={onSignOut} />
      </div>
    </header>
  );
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase() ?? "").join("") || "?";
}

/** The person signed in, as initials on the right; press for Settings and the way out. */
function AccountMenu({ user, onSignOut }: { user: CurrentUser; onSignOut: () => void }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const id = useId();
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [open]);
  const roles = user.roles.map((role) => role.label).join(", ") || "No roles";
  return (
    <div className="account-menu" ref={root}>
      <button type="button" className="account-button" aria-label={`${user.display_name}: account`} aria-expanded={open} aria-controls={id} onClick={() => setOpen((value) => !value)}>
        <span className="avatar" aria-hidden="true">{initials(user.display_name)}</span>
      </button>
      <div className="account-panel" id={id} hidden={!open}>
        <div className="account-identity">
          <strong>{user.display_name}</strong>
          <span>{roles}</span>
        </div>
        <Link href={settingsHref()} className="account-item" onClick={() => setOpen(false)}><Icon name="settings" />Settings</Link>
        <button type="button" className="account-item" onClick={() => { setOpen(false); onSignOut(); }}><Icon name="sign-out" />Sign out</button>
      </div>
    </div>
  );
}
