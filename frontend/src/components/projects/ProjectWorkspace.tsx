"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useMemo } from "react";

import { ApiError, projects, settings } from "@/lib/api";
import type { CurrentUser, ProjectDetail } from "@/lib/api";
import { CurrencyProvider } from "@/lib/currency";
import {
  PROJECT_FINANCIAL_READERS,
  PROJECT_WRITERS,
  ROLE_SYSTEM_ADMIN,
  TECHNICAL_WRITERS,
  hasAnyRole,
  roleSet,
} from "@/lib/roles";
import { AppShell } from "@/components/shell/AppShell";
import {
  PROJECT_NAVIGATION,
  findNavItem,
  projectHref,
  visibleNavigation,
} from "@/components/shell/navigation";
import type { ProjectSection } from "@/components/shell/navigation";
import { Disclosure, Badge, Card, EmptyState, Loading, Notice, PageHeader } from "@/components/ui";
import { ProjectCommandCenter } from "@/components/dashboard/ProjectCommandCenter";
import { AccessTab } from "@/components/projects/AccessTab";
import { CashflowTab } from "@/components/projects/CashflowTab";
import { CollectionsTab } from "@/components/projects/CollectionsTab";
import { CommissionsTab } from "@/components/projects/CommissionsTab";
import { ConsultantEngineerTab } from "@/components/projects/ConsultantEngineerTab";
import { ConstructionTab } from "@/components/projects/ConstructionTab";
import { ProjectStages } from "@/components/projects/construction/StageWorkspace";
import { DocumentsTab } from "@/components/projects/DocumentsTab";
import { ProjectEdit } from "@/components/projects/ProjectEdit";
import { InventoryTab } from "@/components/projects/InventoryTab";
import { LandTab } from "@/components/projects/LandTab";
import { PaymentPlansTab } from "@/components/projects/PaymentPlansTab";
import { PermitsTab } from "@/components/projects/PermitsTab";
import { PreLaunchTab } from "@/components/projects/PreLaunchTab";
import { SalesTab } from "@/components/projects/SalesTab";
import { UnitEconomicsTab } from "@/components/projects/UnitEconomicsTab";
import { UnitWorkspace } from "@/components/projects/inventory/UnitWorkspace";
import { PaymentPlanWorkspace } from "@/components/projects/payments/PaymentPlanWorkspace";
import { SaleWorkspace } from "@/components/projects/sales/SaleWorkspace";
import { readRecord } from "@/components/shell/recordRoutes";
import { projectStatusLabel, projectStatusTone } from "./projectStatus";

/**
 * One project, inside the shell.
 *
 * The rail names the project and its sections; this component loads the
 * project, resolves the currencies every figure beneath it is denominated in,
 * and renders whichever section the address names. The most expensive mistake
 * this product can allow is recording something against the wrong
 * development, so the project's identity is on screen in the rail, in the
 * breadcrumb and in the context bar whichever section is open.
 */
export function ProjectWorkspace({
  projectId,
  section,
  user,
}: {
  projectId: string;
  section: ProjectSection;
  user: CurrentUser;
}) {
  const router = useRouter();
  const record = readRecord(useSearchParams());
  const [project, setProject] = useState<ProjectDetail | null>(null);
  // Which currency each currency_id names, for every money figure below this
  // point. Seeded from the currency register (readable by any signed-in user)
  // plus the project's own base and reporting pair, so a row's REAL currency
  // is resolved rather than assumed from the project.
  const [currencyCodes, setCurrencyCodes] = useState<Record<string, string>>({});
  // Opening a unit from the price or sales register reuses the same Unit 360
  // the Inventory section opens. One record file, reached from wherever the
  // person was.
  const [editing, setEditing] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  // Every load takes a ticket, and a response that arrives after a newer
  // load began is dropped. The workspace is already remounted per project;
  // this guards the reloads within one project against arriving out of order.
  const generation = useRef(0);

  const roles = useMemo(() => roleSet(user.roles), [user.roles]);
  const isAdmin = roles.has(ROLE_SYSTEM_ADMIN);
  const canWriteProject = hasAnyRole(roles, PROJECT_WRITERS);
  const canWriteTechnical = hasAnyRole(roles, TECHNICAL_WRITERS);

  const groups = visibleNavigation(PROJECT_NAVIGATION, roles);
  const item = findNavItem(groups, section);
  const navigate = useCallback(
    (next: ProjectSection) => router.push(projectHref(projectId, next)),
    [router, projectId],
  );

  const load = useCallback(async () => {
    const ticket = ++generation.current;
    try {
      const detail = await projects.read(projectId);
      // Allowed to fail quietly: the project's own base and reporting pair
      // still resolve, and an unknown id shows an undenominated figure rather
      // than a guessed code.
      let register: { id: string; code: string }[] = [];
      try {
        register = await settings.currencies();
      } catch {
        register = [];
      }
      const codes: Record<string, string> = {};
      for (const currency of register) codes[currency.id] = currency.code;
      if (detail.base_currency_code) codes[detail.base_currency_id] = detail.base_currency_code;
      if (detail.reporting_currency_code) {
        codes[detail.reporting_currency_id] = detail.reporting_currency_code;
      }
      if (ticket !== generation.current) return;
      setCurrencyCodes(codes);
      setProject(detail);
      setError(null);
    } catch (caught) {
      if (ticket !== generation.current) return;
      setProject(null);
      setError(
        caught instanceof ApiError && caught.status === 404
          ? "That project is not available to you."
          : "Could not load the project.",
      );
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const changed = async () => {
    await load();
    setRefreshKey((key) => key + 1);
  };

  const crumbs = [
    { label: "Projects", href: "/projects/" },
    ...(section === "overview"
      ? [{ label: project?.name ?? "Project", project: true }]
      : [
          { label: project?.name ?? "Project", href: projectHref(projectId), project: true },
          { label: item?.label ?? "Section" },
        ]),
  ];

  const utilities = project ? (
    <>
      <Badge tone={projectStatusTone(project.status)}>{projectStatusLabel(project.status)}</Badge>
      {project.base_currency_code ? (
        <span className="context-fact">
          Base <strong>{project.base_currency_code}</strong>
        </span>
      ) : null}
    </>
  ) : undefined;

  const body = () => {
    if (error) {
      return (
        <>
          <PageHeader title="Project" />
          <Notice tone="error">{error}</Notice>
        </>
      );
    }
    if (project === null) {
      return <Loading label="Loading project…" shape="page" />;
    }
    if (!item) {
      return (
        <>
          <PageHeader title="Not available" />
          <Card>
            <EmptyState
              title="Not available to your role"
              hint="This section of the project is not part of what your roles may read."
            />
          </Card>
        </>
      );
    }
    if (record) {
      if (record.invalid) return <><PageHeader title="Record not found" /><Notice tone="error">This record address is invalid.</Notice><a href={projectHref(projectId, section)}>Return to register</a></>;
      if (project.status === "setup") return <><PageHeader title="Finalize project setup first" /><Notice tone="info">Complete project setup before opening records.</Notice></>;
      if (record.kind === "payment-plan") return <PaymentPlanWorkspace key={record.id} projectId={projectId} roles={roles} planId={record.id} onChanged={changed} />;
      if (record.kind === "sale" || record.kind === "reservation") return <SaleWorkspace key={`${record.kind}:${record.id}`} projectId={projectId} roles={roles} saleId={record.kind === "sale" ? record.id : null} reservationId={record.kind === "reservation" ? record.id : null} onChanged={changed} />;
      if (record.kind === "unit") return <UnitWorkspace key={record.id} projectId={projectId} roles={roles} unitId={record.id} canWriteStructure={canWriteTechnical} canConfigure={canWriteProject} onChanged={changed} />;
    }
    if (section === "overview") {
      return (
        <>
          {editing ? (
            <ProjectEdit project={project} onSaved={changed} onClose={() => setEditing(false)} />
          ) : null}
          <ProjectCommandCenter
            project={project}
            roles={roles}
            canEdit={canWriteProject}
            onEdit={() => setEditing((open) => !open)}
            onNavigate={navigate}
            refreshKey={refreshKey}
          />
          <Disclosure title={<> Project construction stage configuration </>}>
            <ProjectStages projectId={projectId} roles={roles} />
          </Disclosure>
        </>
      );
    }
    return (
      <>
        {section === "land" ? (
          <LandTab
            projectId={projectId}
            canWriteLand={canWriteProject}
            canWritePlanning={canWriteTechnical}
            canSeeCost={hasAnyRole(roles, PROJECT_FINANCIAL_READERS)}
          />
        ) : null}
        {section === "permits" ? <PermitsTab projectId={projectId} canWrite={canWriteTechnical} canDelete={hasAnyRole(roles, new Set([ROLE_SYSTEM_ADMIN]))} canSeeCost={hasAnyRole(roles, PROJECT_FINANCIAL_READERS)} currencyCode={project.base_currency_code} /> : null}
        {section === "prelaunch" ? (
          <PreLaunchTab
            projectId={projectId}
            currencyId={project.base_currency_id}
            currencyCode={project.base_currency_code}
            roles={roles}
          />
        ) : null}
        {section === "consultant" ? <ConsultantEngineerTab projectId={projectId} roles={roles} /> : null}
        {section === "inventory" ? (
          <InventoryTab
            projectId={projectId}
            projectStatus={project.status}
            roles={roles}
            canWriteStructure={canWriteTechnical}
            canConfigure={canWriteProject}
          />
        ) : null}
        {section === "sales" ? (
          <SalesTab
            projectId={projectId}
            projectStatus={project.status}
            roles={roles}
            userId={user.id}
          />
        ) : null}
        {section === "payments" ? (
          <PaymentPlansTab projectId={projectId} projectStatus={project.status} roles={roles} />
        ) : null}
        {section === "collections" ? <CollectionsTab projectId={projectId} roles={roles} /> : null}
        {section === "commissions" ? <CommissionsTab projectId={projectId} roles={roles} userId={user.id} currencyCodes={currencyCodes} /> : null}
        {section === "construction" ? <ConstructionTab projectId={projectId} roles={roles} currencyId={project.base_currency_id} currencyCode={project.base_currency_code} /> : null}
        {section === "economics" ? <UnitEconomicsTab projectId={projectId} roles={roles} /> : null}
        {section === "cashflow" ? <CashflowTab project={project} roles={roles} /> : null}
        {section === "documents" ? <DocumentsTab projectId={projectId} canWrite={canWriteTechnical} /> : null}
        {section === "access" && isAdmin ? <AccessTab projectId={projectId} /> : null}
      </>
    );
  };

  return (
    <CurrencyProvider codes={currencyCodes}>
      <AppShell
        area="projects"
        user={user}
        project={project}
        projectId={projectId}
        section={section}
        crumbs={crumbs}
        utilities={utilities}
      >
        {body()}
      </AppShell>
    </CurrencyProvider>
  );
}
