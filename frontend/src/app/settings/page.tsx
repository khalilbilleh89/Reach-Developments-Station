"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

import { useSession } from "@/lib/api/session";
import { roleSet } from "@/lib/roles";
import { AppShell, PasswordGate, SessionScreen } from "@/components/shell/AppShell";
import {
  SETTINGS_NAVIGATION,
  findNavItem,
  isSettingsSection,
  settingsHref,
  visibleNavigation,
} from "@/components/shell/navigation";
import { AccountSection } from "@/components/settings/AccountSection";
import { AuditSection } from "@/components/settings/AuditSection";
import { CountryPacksSection } from "@/components/settings/CountryPacksSection";
import { CurrenciesSection } from "@/components/settings/CurrenciesSection";
import { ReferenceDataSection } from "@/components/settings/ReferenceDataSection";
import { UsersSection } from "@/components/settings/UsersSection";
import { PageHeader } from "@/components/ui";

/**
 * Administration, outside any one project.
 *
 * The sections are the rail's; this page only renders the one that is open.
 * Client-side routing decides what is drawn — the API enforces every action
 * independently, so a section a role cannot write to still shows what it may
 * read.
 */
function SettingsScreen() {
  const router = useRouter();
  const params = useSearchParams();
  const { state } = useSession();
  const requested = params.get("section");

  useEffect(() => {
    if (state.status === "anonymous") router.replace("/login/");
  }, [state, router]);

  if (state.status !== "authenticated") return <SessionScreen status={state.status} />;

  const { user } = state;

  if (user.must_change_password) {
    return <PasswordGate onChanged={() => router.replace("/login/")} />;
  }

  const groups = visibleNavigation(SETTINGS_NAVIGATION, roleSet(user.roles));
  const wanted = isSettingsSection(requested) ? requested : "country";
  const item = findNavItem(groups, wanted) ?? groups[0]?.items[0];
  const section = item?.key ?? "country";

  return (
    <AppShell
      area="settings"
      user={user}
      section={section}
      crumbs={[{ label: "Settings", href: settingsHref() }, { label: item?.label ?? "Settings" }]}
    >
      <PageHeader eyebrow="Settings" title={item?.label ?? "Settings"} subtitle={item?.description} />
      {section === "users" ? <UsersSection /> : null}
      {section === "currencies" ? <CurrenciesSection /> : null}
      {section === "country" ? <CountryPacksSection /> : null}
      {section === "reference" ? <ReferenceDataSection /> : null}
      {section === "audit" ? <AuditSection /> : null}
      {section === "account" ? (
        <AccountSection onChanged={() => router.replace("/login/")} />
      ) : null}
    </AppShell>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<SessionScreen status="loading" />}>
      <SettingsScreen />
    </Suspense>
  );
}
