"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useSession } from "@/lib/api/session";
import { AppShell, SessionScreen } from "@/components/AppShell";
import { ChangePasswordForm } from "@/components/ChangePasswordForm";
import { AuditSection } from "@/components/settings/AuditSection";
import { CountryPacksSection } from "@/components/settings/CountryPacksSection";
import { ReferenceDataSection } from "@/components/settings/ReferenceDataSection";
import { UsersSection } from "@/components/settings/UsersSection";
import { PageHeader, TabPanel, Tabs } from "@/components/ui";

const TABS = [
  { key: "users", label: "Users" },
  { key: "country", label: "Country packs" },
  { key: "reference", label: "Reference data" },
  { key: "audit", label: "Audit" },
];

const DESCRIPTIONS: Record<string, string> = {
  users: "Who has an account, and what each of them may do across the portfolio.",
  country: "The tax, currency and legal defaults a project inherits when it is created.",
  reference: "The controlled vocabularies every project chooses its codes from.",
  audit: "What was changed, by whom, and when.",
};

/**
 * Administration, outside any one project.
 *
 * One page, four sections. Client-side routing decides only what is rendered —
 * the API enforces every action independently.
 */
export default function SettingsPage() {
  const router = useRouter();
  const { state } = useSession();
  const [tab, setTab] = useState("users");

  useEffect(() => {
    if (state.status === "anonymous") router.replace("/login/");
  }, [state, router]);

  if (state.status !== "authenticated") return <SessionScreen status={state.status} />;

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
    <AppShell current="settings" user={user}>
      <PageHeader
        eyebrow="Administration"
        title="Settings"
        subtitle={DESCRIPTIONS[tab]}
      />
      <Tabs label="Settings sections" tabs={TABS} active={tab} onSelect={setTab} />
      <TabPanel group="Settings sections" tab={tab}>
        {tab === "users" ? <UsersSection /> : null}
        {tab === "country" ? <CountryPacksSection /> : null}
        {tab === "reference" ? <ReferenceDataSection /> : null}
        {tab === "audit" ? <AuditSection /> : null}
      </TabPanel>
    </AppShell>
  );
}
