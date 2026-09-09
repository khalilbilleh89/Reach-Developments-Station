"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AppShell, PasswordGate, SessionScreen } from "@/components/shell/AppShell";
import { Notice, PageHeader, Tabs, TabPanel } from "@/components/ui";
import { PortfolioOverview, PortfolioProjects, PortfolioRisks, PortfolioProject } from "@/components/portfolio/Portfolio";
import { useSession } from "@/lib/api/session";
import { hasAnyRole, PORTFOLIO_READERS, roleSet } from "@/lib/roles";

function PortfolioScreen() {
  const { state } = useSession();
  const params = useSearchParams();
  const router = useRouter();
  const id = params.get("project");
  const requested = params.get("section");
  const section = requested === "projects" || requested === "risks" ? requested : "overview";
  useEffect(() => { if (state.status === "anonymous") router.replace("/login/"); }, [state.status, router]);
  if (state.status !== "authenticated") return <SessionScreen status={state.status} />;
  if (state.user.must_change_password) return <PasswordGate onChanged={() => router.replace("/login/")} />;
  const allowed = hasAnyRole(roleSet(state.user.roles), PORTFOLIO_READERS);
  return <AppShell area="portfolio" user={state.user} crumbs={[{ label: "Portfolio", href: "/portfolio/" }, { label: id ? "Project management summary" : section }]}>
    <PageHeader icon="projects" eyebrow="Across developments" title={id ? "Portfolio project" : "Portfolio"} subtitle="Capital position, development performance and management attention." />
    {!allowed ? <Notice tone="info">Portfolio is not available to your role.</Notice> : id ? <PortfolioProject key={id} id={id} /> : <>
      <Tabs label="Portfolio sections" tabs={[{ key: "overview", label: "Overview" }, { key: "projects", label: "Projects" }, { key: "risks", label: "Risks" }]} active={section} onSelect={(key) => router.push(`/portfolio/?section=${key}`)} />
      <TabPanel group="portfolio-sections" tab={section}>{section === "projects" ? <PortfolioProjects /> : section === "risks" ? <PortfolioRisks /> : <PortfolioOverview />}</TabPanel>
    </>}
  </AppShell>;
}

export default function PortfolioPage() {
  return <Suspense fallback={<SessionScreen status="loading" />}><PortfolioScreen /></Suspense>;
}
