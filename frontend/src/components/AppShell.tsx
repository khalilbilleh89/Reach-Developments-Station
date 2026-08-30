"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

import type { CurrentUser } from "@/lib/api";
import { useSession } from "@/lib/api/session";
import { Button, Loading, Notice } from "@/components/ui";

/**
 * The chrome every signed-in screen shares.
 *
 * One sticky bar: who the product is, where you are, and who you are signed in
 * as. It stays put because the registers underneath it are long, and losing the
 * project you are inside halfway down a thousand units is how people record
 * things against the wrong development.
 *
 * The bar shows the signed-in person's roles because in this product they are
 * not decoration: the same screen offers a different set of actions to Finance
 * and to Legal, and somebody looking at a button they do not have needs to know
 * why before they blame the software.
 */
export function AppShell({
  current,
  user,
  wide,
  children,
}: {
  current: "projects" | "settings";
  user: CurrentUser;
  wide?: boolean;
  children: ReactNode;
}) {
  const router = useRouter();
  const { signOut } = useSession();
  const roles = user.roles.map((role) => role.label).join(", ");

  return (
    <div className="app-shell">
      <header className="app-bar">
        <div className="app-bar-inner">
          <div className="app-bar-left">
            <span className="app-brand">
              <span className="app-brand-mark">Reach</span>
              <span className="app-brand-sub">Developments Station</span>
            </span>
            <nav className="app-nav" aria-label="Main">
              <button
                type="button"
                aria-current={current === "projects" ? "page" : undefined}
                className={`app-nav-link ${current === "projects" ? "app-nav-link-active" : ""}`}
                onClick={() => router.push("/projects/")}
              >
                Projects
              </button>
              <button
                type="button"
                aria-current={current === "settings" ? "page" : undefined}
                className={`app-nav-link ${current === "settings" ? "app-nav-link-active" : ""}`}
                onClick={() => router.push("/settings/")}
              >
                Settings
              </button>
            </nav>
          </div>
          <div className="app-account">
            <span className="app-user">
              <span className="app-user-name">{user.display_name}</span>
              <span className="app-user-roles">{roles || "No roles"}</span>
            </span>
            <Button
              small
              onClick={() => void signOut().then(() => router.replace("/login/"))}
            >
              Sign out
            </Button>
          </div>
        </div>
      </header>
      <main className={wide ? "app-body app-body-wide" : "app-body"}>{children}</main>
    </div>
  );
}

/** What a page shows while the session is still being established, or is gone. */
export function SessionScreen({ status }: { status: "loading" | "anonymous" }) {
  return (
    <div className="shell shell-centred">
      {status === "loading" ? (
        <Loading label="Loading…" />
      ) : (
        <div className="panel panel-narrow">
          <Notice tone="info">Your session has ended. Please sign in again.</Notice>
        </div>
      )}
    </div>
  );
}
