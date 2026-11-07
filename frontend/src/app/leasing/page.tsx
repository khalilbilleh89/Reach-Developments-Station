"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppShell, PasswordGate, SessionScreen } from "@/components/shell/AppShell";
import { Notice } from "@/components/ui";
import { LeasingWorkspace } from "@/components/leasing/LeasingWorkspace";
import { useSession } from "@/lib/api/session";
import { hasAnyRole, LEASING_READERS, LEASING_WRITERS, roleSet } from "@/lib/roles";

export default function LeasingPage() {
  const { state, refresh } = useSession();
  const router = useRouter();
  useEffect(() => { if (state.status === "anonymous") router.replace("/login/"); }, [state.status, router]);
  if (state.status !== "authenticated") return <SessionScreen status={state.status} onRetry={() => void refresh()} />;
  if (state.user.must_change_password) return <PasswordGate onChanged={() => router.replace("/login/")} />;
  const roles = roleSet(state.user.roles);
  return <AppShell area="leasing" user={state.user} crumbs={[{ label: "Leasing" }]}>
    {hasAnyRole(roles, LEASING_READERS) ? <LeasingWorkspace canWrite={hasAnyRole(roles, LEASING_WRITERS)} /> : <Notice tone="info">Leasing is not available to your role.</Notice>}
  </AppShell>;
}
