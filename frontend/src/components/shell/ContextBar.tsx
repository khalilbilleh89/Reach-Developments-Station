"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Icon } from "@/components/ui";

export interface Crumb {
  label: string;
  /** Absent on the current place, which is text rather than a link. */
  href?: string;
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
  onToggleRail,
  onOpenNav,
}: {
  crumbs: Crumb[];
  utilities?: ReactNode;
  collapsed: boolean;
  onToggleRail: () => void;
  onOpenNav: () => void;
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
        <ol className="crumbs">
          {crumbs.map((crumb, index) => {
            const last = index === crumbs.length - 1;
            return (
              <li key={`${crumb.label}-${index}`}>
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
      {utilities ? <div className="context-utilities">{utilities}</div> : null}
    </header>
  );
}
