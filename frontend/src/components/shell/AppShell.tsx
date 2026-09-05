"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";

import type { CurrentUser, ProjectDetail } from "@/lib/api";
import { useSession } from "@/lib/api/session";
import { roleSet } from "@/lib/roles";
import { ChangePasswordForm } from "@/components/ChangePasswordForm";
import { Loading, Notice } from "@/components/ui";
import { AppSidebar, MobileNavigation } from "./AppSidebar";
import { ContextBar } from "./ContextBar";
import type { Crumb } from "./ContextBar";
import {
  PROJECT_NAVIGATION,
  SETTINGS_NAVIGATION,
  visibleNavigation,
} from "./navigation";
import type { NavGroup } from "./navigation";

export type ShellArea = "projects" | "settings";

/** How the desktop rail is drawn: the viewport decides, or the person did. */
export type RailState = "auto" | "expanded" | "collapsed";

const RAIL_PREFERENCE = "reach.rail";
const NARROW_RAIL = "(width < 75rem)";

/**
 * The chrome every signed-in screen shares.
 *
 * A dark navigation rail on the left, a light working surface on the right,
 * and a thin context bar across the top of the surface saying where you are.
 * The rail carries the product, the open project, the sections of that
 * project grouped by the lifecycle of a development, and the person signed in.
 * It never scrolls away, because losing which project you are inside halfway
 * down a thousand units is how somebody records a reservation against the
 * wrong development.
 *
 * On a wide screen the rail can be collapsed to icons and the choice is kept
 * in the browser; under 1200px it starts collapsed; under 1024px it leaves the
 * page and becomes a drawer behind a menu button. `data-rail` carries the
 * person's preference and `app-narrow` the viewport's verdict, so the
 * stylesheet can draw the collapsed rail from one set of rules.
 */
export function AppShell({
  user,
  area,
  project,
  projectId,
  section,
  crumbs,
  utilities,
  children,
}: {
  user: CurrentUser;
  area: ShellArea;
  /** The open project; `null` while it loads; absent outside a project. */
  project?: ProjectDetail | null;
  projectId?: string;
  section?: string;
  crumbs: Crumb[];
  utilities?: ReactNode;
  children: ReactNode;
}) {
  const router = useRouter();
  const { signOut } = useSession();
  const [rail, setRail] = useState<RailState>("auto");
  const [narrow, setNarrow] = useState(false);
  const [navOpen, setNavOpen] = useState(false);

  // The stored preference and the viewport are read after mount: the page is
  // a static export, and reading either during the first render would make
  // the server's HTML disagree with the browser's.
  useEffect(() => {
    const query = window.matchMedia(NARROW_RAIL);
    const sync = () => setNarrow(query.matches);
    query.addEventListener("change", sync);
    // Deferred rather than set synchronously in the effect body: the first
    // reading of storage and the viewport is a subscription to the browser,
    // not a render-time decision.
    void (async () => {
      await Promise.resolve();
      sync();
      try {
        const stored = window.localStorage.getItem(RAIL_PREFERENCE);
        if (stored === "expanded" || stored === "collapsed") setRail(stored);
      } catch {
        // Storage may be unavailable; the viewport decides instead.
      }
    })();
    return () => query.removeEventListener("change", sync);
  }, []);

  const collapsed = rail === "collapsed" || (rail === "auto" && narrow);

  const toggleRail = useCallback(() => {
    const next: RailState = collapsed ? "expanded" : "collapsed";
    setRail(next);
    try {
      window.localStorage.setItem(RAIL_PREFERENCE, next);
    } catch {
      // Not remembering the choice is an acceptable outcome.
    }
  }, [collapsed]);

  const roles = roleSet(user.roles);
  const groups: NavGroup[] =
    area === "projects" && projectId
      ? visibleNavigation(PROJECT_NAVIGATION, roles)
      : area === "settings"
        ? visibleNavigation(SETTINGS_NAVIGATION, roles)
        : [];

  const onSignOut = () => void signOut().then(() => router.replace("/login/"));

  const sidebarProps = {
    user,
    area,
    project,
    projectId,
    section,
    groups,
    onSignOut,
  };

  return (
    <div className={narrow ? "app app-narrow" : "app"} data-rail={rail}>
      <AppSidebar {...sidebarProps} />
      {navOpen ? (
        <MobileNavigation {...sidebarProps} onClose={() => setNavOpen(false)} />
      ) : null}
      <div className="app-main">
        <ContextBar
          crumbs={crumbs}
          utilities={utilities}
          collapsed={collapsed}
          onToggleRail={toggleRail}
          onOpenNav={() => setNavOpen(true)}
        />
        <main id="main" className="app-content">
          {children}
        </main>
      </div>
    </div>
  );
}

/** What a page shows while the session is still being established, or is gone. */
export function SessionScreen({ status }: { status: "loading" | "anonymous" }) {
  return (
    <div className="shell">
      {status === "loading" ? (
        <div className="panel panel-narrow">
          <Loading label="Establishing your session…" shape="page" />
        </div>
      ) : (
        <div className="panel panel-narrow">
          <Notice tone="info">Your session has ended. Please sign in again.</Notice>
        </div>
      )}
    </div>
  );
}

/**
 * An administrator-issued temporary password gates everything else.
 *
 * Rendered by every signed-in page rather than by one, so a person cannot
 * reach a register by typing its address before choosing their own password.
 */
export function PasswordGate({ onChanged }: { onChanged: () => void }) {
  return (
    <div className="shell">
      <main className="signin">
        <div className="signin-brand">
          <span className="brand-mark" aria-hidden="true">
            R
          </span>
          <span>
            <span className="signin-brand-name">Reach</span>
            <br />
            <span className="signin-brand-sub">Developments Station</span>
          </span>
        </div>
        <div className="panel">
          <h1 className="panel-title">Choose a new password</h1>
          <p className="panel-lead">
            Your account was created with a temporary password. Replace it to continue.
          </p>
          <ChangePasswordForm requireCurrent={false} onChanged={onChanged} />
        </div>
      </main>
    </div>
  );
}
