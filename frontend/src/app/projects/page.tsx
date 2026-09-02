"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

import { useSession } from "@/lib/api/session";
import { AppShell, PasswordGate, SessionScreen } from "@/components/shell/AppShell";
import { isProjectSection, projectHref } from "@/components/shell/navigation";
import { roleSet } from "@/lib/roles";
import { ProjectWorkspace } from "@/components/projects/ProjectWorkspace";
import { ProjectsRegister } from "@/components/projects/ProjectsRegister";

/**
 * Projects: the portfolio, and the workspace for whichever project is open.
 *
 * The open project and its section travel in the query string rather than in
 * a path segment. The frontend is a static export (`output: "export"`), so a
 * dynamic segment would need its values known at build time — and project
 * identifiers are runtime data. One page, two states, no server runtime, and
 * the browser's Back button walks through sections the way a person expects.
 */
function ProjectsScreen() {
  const router = useRouter();
  const params = useSearchParams();
  const { state } = useSession();
  const openProjectId = params.get("project");
  const requested = params.get("section");
  const section = isProjectSection(requested) ? requested : "overview";

  useEffect(() => {
    if (state.status === "anonymous") router.replace("/login/");
  }, [state, router]);

  if (state.status !== "authenticated") return <SessionScreen status={state.status} />;

  const { user } = state;

  if (user.must_change_password) {
    return <PasswordGate onChanged={() => router.replace("/login/")} />;
  }

  if (openProjectId) {
    return <ProjectWorkspace projectId={openProjectId} section={section} user={user} />;
  }

  return (
    <AppShell area="projects" user={user} crumbs={[{ label: "Projects" }]}>
      <ProjectsRegister onOpen={(id) => router.push(projectHref(id))} roles={roleSet(user.roles)} />
    </AppShell>
  );
}

export default function ProjectsPage() {
  // `useSearchParams` needs a Suspense boundary in the App Router.
  return (
    <Suspense fallback={<SessionScreen status="loading" />}>
      <ProjectsScreen />
    </Suspense>
  );
}
