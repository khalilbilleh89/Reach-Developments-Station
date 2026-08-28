"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useSession } from "@/lib/api/session";
import { ChangePasswordForm } from "@/components/ChangePasswordForm";
import { AuditSection } from "@/components/settings/AuditSection";
import { CountryPacksSection } from "@/components/settings/CountryPacksSection";
import { ReferenceDataSection } from "@/components/settings/ReferenceDataSection";
import { UsersSection } from "@/components/settings/UsersSection";
import { Loading, Notice } from "@/components/ui";

const TABS = [
  { key: "users", label: "Users" },
  { key: "country", label: "Country packs" },
  { key: "reference", label: "Reference data" },
  { key: "audit", label: "Audit" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

/**
 * The authenticated application shell.
 *
 * One page, four sections. Client-side routing decides only what is rendered —
 * the API enforces every action independently.
 */
export default function SettingsPage() {
  const router = useRouter();
  const { state, signOut } = useSession();
  const [tab, setTab] = useState<TabKey>("users");

  useEffect(() => {
    if (state.status === "anonymous") router.replace("/login/");
  }, [state, router]);

  if (state.status === "loading") {
    return (
      <div className="shell shell-centred">
        <Loading label="Loading…" />
      </div>
    );
  }

  if (state.status === "anonymous") {
    return (
      <div className="shell shell-centred">
        <main className="panel panel-narrow">
          <Notice tone="info">Your session has ended. Please sign in again.</Notice>
        </main>
      </div>
    );
  }

  const { user } = state;

  // An administrator-issued temporary password gates everything else.
  if (user.must_change_password) {
    return (
      <div className="shell shell-centred">
        <main className="panel panel-narrow">
          <p className="eyebrow">Reach Developments Station</p>
          <h1 className="title title-compact">Choose a new password</h1>
          <p className="tagline">
            Your account was created with a temporary password. Replace it to continue.
          </p>
          <ChangePasswordForm requireCurrent={false} onChanged={() => router.replace("/login/")} />
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-identity">
          <p className="eyebrow">Reach Developments Station</p>
          <h1 className="app-title">Settings</h1>
        </div>
        <div className="app-account">
          <span className="app-user">{user.display_name}</span>
          <span className="subtle">{user.roles.map((role) => role.label).join(", ") || "No roles"}</span>
          <button
            className="button button-small"
            type="button"
            onClick={() => router.push("/projects/")}
          >
            Projects
          </button>
          <button
            className="button button-small"
            type="button"
            onClick={() => void signOut().then(() => router.replace("/login/"))}
          >
            Sign out
          </button>
        </div>
      </header>

      <nav className="tab-row" role="tablist" aria-label="Settings sections">
        {TABS.map((entry) => (
          <button
            key={entry.key}
            role="tab"
            type="button"
            aria-selected={tab === entry.key}
            className={`tab ${tab === entry.key ? "tab-active" : ""}`}
            onClick={() => setTab(entry.key)}
          >
            {entry.label}
          </button>
        ))}
      </nav>

      <main className="app-main">
        {tab === "users" ? <UsersSection /> : null}
        {tab === "country" ? <CountryPacksSection /> : null}
        {tab === "reference" ? <ReferenceDataSection /> : null}
        {tab === "audit" ? <AuditSection /> : null}
      </main>
    </div>
  );
}
