"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

import { useSession } from "@/lib/api/session";
import { ProjectWorkspace } from "@/components/projects/ProjectWorkspace";
import { ProjectsRegister } from "@/components/projects/ProjectsRegister";
import { Loading, Notice } from "@/components/ui";

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
  const { state, signOut } = useSession();
  const openProjectId = params.get("project");

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

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-identity">
          <p className="eyebrow">Reach Developments Station</p>
          <h1 className="app-title">Projects</h1>
        </div>
        <div className="app-account">
          <span className="app-user">{user.display_name}</span>
          <span className="subtle">
            {user.roles.map((role) => role.label).join(", ") || "No roles"}
          </span>
          <button
            className="button button-small"
            type="button"
            onClick={() => router.push("/settings/")}
          >
            Settings
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

      <main className="app-main">
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
      </main>
    </div>
  );
}

export default function ProjectsPage() {
  // `useSearchParams` needs a Suspense boundary in the App Router.
  return (
    <Suspense
      fallback={
        <div className="shell shell-centred">
          <Loading label="Loading…" />
        </div>
      }
    >
      <ProjectsScreen />
    </Suspense>
  );
}
