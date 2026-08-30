"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

import { useSession } from "@/lib/api/session";
import { AppShell, SessionScreen } from "@/components/AppShell";
import { ProjectWorkspace } from "@/components/projects/ProjectWorkspace";
import { ProjectsRegister } from "@/components/projects/ProjectsRegister";

/**
 * Projects: the register, and the workspace for whichever project is open.
 *
 * The open project travels in the query string rather than in a `[projectId]`
 * path segment. The frontend is a static export (`output: "export"`), so a
 * dynamic segment would need its values known at build time — and project
 * identifiers are runtime data. One page, two states, no server runtime.
 */
function ProjectsScreen() {
  const router = useRouter();
  const params = useSearchParams();
  const { state } = useSession();
  const openProjectId = params.get("project");

  useEffect(() => {
    if (state.status === "anonymous") router.replace("/login/");
  }, [state, router]);

  if (state.status !== "authenticated") return <SessionScreen status={state.status} />;

  const { user } = state;

  return (
    <AppShell current="projects" user={user} wide={Boolean(openProjectId)}>
      {openProjectId ? (
        <ProjectWorkspace
          projectId={openProjectId}
          user={user}
          onBack={() => router.push("/projects/")}
        />
      ) : (
        <ProjectsRegister
          onOpen={(id) => router.push(`/projects/?project=${encodeURIComponent(id)}`)}
        />
      )}
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
