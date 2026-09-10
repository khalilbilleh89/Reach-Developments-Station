"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AppShell, PasswordGate, SessionScreen } from "@/components/shell/AppShell";
import { Notice, PageHeader, SectionHeader, Tabs, TabPanel } from "@/components/ui";
import { PortfolioOverview, PortfolioProjects, PortfolioRisks, PortfolioProject } from "@/components/portfolio/Portfolio";
import { useSession } from "@/lib/api/session";
import { hasAnyRole, PORTFOLIO_READERS, PROJECT_WRITERS, roleSet } from "@/lib/roles";
import { Actions } from "@/components/portfolio/Actions";
import { Reporting } from "@/components/portfolio/Reporting";
import { PortfolioOutlook } from "@/components/portfolio/Outlook";

function PortfolioScreen() {
  const { state } = useSession();
  const params = useSearchParams();
  const router = useRouter();
  const id = params.get("project");
  const requested = params.get("section");
  const section = requested === "risks" ? "exceptions" : ["projects", "outlook", "exceptions", "actions", "reporting"].includes(requested ?? "") ? requested! : "overview";
  const projectDetail = Boolean(id) && section === "overview";
  useEffect(() => { if (state.status === "anonymous") router.replace("/login/"); }, [state.status, router]);
  if (state.status !== "authenticated") return <SessionScreen status={state.status} />;
  if (state.user.must_change_password) return <PasswordGate onChanged={() => router.replace("/login/")} />;
  const allowed = hasAnyRole(roleSet(state.user.roles), PORTFOLIO_READERS);
  const canWrite = hasAnyRole(roleSet(state.user.roles), PROJECT_WRITERS);
  return <AppShell area="portfolio" user={state.user} crumbs={[{ label: "Portfolio", href: "/portfolio/" }, { label: id ? "Project management summary" : section }]}>
    {section !== "reporting" || !allowed ? <PageHeader icon="projects" eyebrow="Across developments" title={projectDetail ? "Portfolio project" : "Portfolio"} subtitle="Capital position, forward outlook and accountable management actions." /> : null}
    {!allowed ? <Notice tone="info">Portfolio is not available to your role.</Notice> : projectDetail && id ? <PortfolioProject key={id} id={id} /> : <>
      <Tabs label="Portfolio sections" tabs={[{ key: "overview", label: "Overview" }, { key: "projects", label: "Projects" }, { key: "outlook", label: "Outlook" }, { key: "exceptions", label: "Exceptions" }, { key: "actions", label: "Actions" }, { key: "reporting", label: "Reporting" }]} active={section} onSelect={(key) => router.push(`/portfolio/?section=${key}`)} />
      <TabPanel group="portfolio-sections" tab={section}>{section === "reporting" ? <Reporting canWrite={canWrite} /> : section === "projects" ? <PortfolioProjects /> : section === "outlook" ? <PortfolioOutlook project={id ?? undefined} /> : section === "actions" ? <Actions key={`${id}:${params.get("source_key")}:${params.get("action")}`} canWrite={canWrite} initialProject={id ?? ""} initialAction={params.get("action")} sourceKey={params.get("source_key") ?? ""} /> : section === "exceptions" ? <div className="stack"><SectionHeader title="Source risks" /><PortfolioRisks /><SectionHeader title="Overdue management actions" /><Notice tone="info">Action lateness is separate from source risk severity. Completing an action does not resolve a risk.</Notice><Actions canWrite={canWrite} overdueOnly /></div> : <PortfolioOverview />}</TabPanel>
    </>}
  </AppShell>;
}

export default function PortfolioPage() {
  return <Suspense fallback={<SessionScreen status="loading" />}><PortfolioScreen /></Suspense>;
}
