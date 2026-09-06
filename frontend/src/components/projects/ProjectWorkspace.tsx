"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, projects, settings } from "@/lib/api";
import type { CurrentUser, ProjectDetail } from "@/lib/api";
import { CurrencyProvider } from "@/lib/currency";
import {
  INTERNAL_PRICE_READERS,
  PRICING_APPROVERS,
  PRICING_WRITERS,
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
import { Badge, Card, EmptyState, Loading, Notice, PageHeader } from "@/components/ui";
import { ProjectCommandCenter } from "@/components/dashboard/ProjectCommandCenter";
import { AccessTab } from "@/components/projects/AccessTab";
import { CashflowTab } from "@/components/projects/CashflowTab";
import { CollectionsTab } from "@/components/projects/CollectionsTab";
import { ConstructionTab } from "@/components/projects/ConstructionTab";
import { DocumentsTab } from "@/components/projects/DocumentsTab";
import { EditForm, asValue } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";
import { InventoryTab } from "@/components/projects/InventoryTab";
import { LandTab } from "@/components/projects/LandTab";
import { PaymentPlansTab } from "@/components/projects/PaymentPlansTab";
import { PermitsTab } from "@/components/projects/PermitsTab";
import { PricingTab } from "@/components/projects/PricingTab";
import { SalesTab } from "@/components/projects/SalesTab";
import { UnitEconomicsTab } from "@/components/projects/UnitEconomicsTab";
import { UnitDetailPanel } from "@/components/projects/inventory/UnitDetailPanel";
import { PROJECT_STATUSES, projectStatusLabel, projectStatusTone } from "./projectStatus";

/** Editable project identity. `code` is absent: it is immutable once issued. */
function projectFields(project: ProjectDetail): EditField[] {
  return [
    { name: "name", label: "Name", group: "Identity" },
    { name: "developer_entity", label: "Developer entity", group: "Identity" },
    { name: "project_type_code", label: "Project type", hint: "A configured code.", group: "Identity", width: "medium" },
    {
      name: "status",
      label: "Status",
      kind: "select",
      group: "Identity",
      options: PROJECT_STATUSES.map((value) => ({ value, label: projectStatusLabel(value) })),
      // Setup is the opening state only: the backend refuses a return to it,
      // so it is not offered once the project has left it.
      hint: project.status === "setup" ? undefined : "A project cannot return to setup.",
    },
    { name: "city", label: "City", group: "Location", width: "medium" },
    { name: "location", label: "Location", group: "Location" },
    { name: "latitude", label: "Latitude", kind: "number", hint: "Decimal degrees.", group: "Location" },
    { name: "longitude", label: "Longitude", kind: "number", group: "Location" },
    { name: "planned_start", label: "Planned start", kind: "date", group: "Programme" },
    { name: "planned_completion", label: "Planned completion", kind: "date", group: "Programme" },
    {
      name: "fiscal_year_start_month",
      label: "Fiscal year starts",
      kind: "number",
      hint: "Month number, 1 to 12.",
      group: "Programme",
    },
  ];
}

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
  const [project, setProject] = useState<ProjectDetail | null>(null);
  // Which currency each currency_id names, for every money figure below this
  // point. Seeded from the currency register (readable by any signed-in user)
  // plus the project's own base and reporting pair, so a row's REAL currency
  // is resolved rather than assumed from the project.
  const [currencyCodes, setCurrencyCodes] = useState<Record<string, string>>({});
  // Opening a unit from the price or sales register reuses the same Unit 360
  // the Inventory section opens. One record file, reached from wherever the
  // person was.
  const [openUnit, setOpenUnit] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  // Every load takes a ticket, and a response that arrives after a newer
  // load began is dropped. The workspace is already remounted per project;
  // this guards the reloads within one project against arriving out of order.
  const generation = useRef(0);

  const roles = roleSet(user.roles);
  const isAdmin = roles.has(ROLE_SYSTEM_ADMIN);
  const canWriteProject = hasAnyRole(roles, PROJECT_WRITERS);
  const canWriteTechnical = hasAnyRole(roles, TECHNICAL_WRITERS);
  const canPrice = hasAnyRole(roles, PRICING_WRITERS);
  const canApprovePricing = hasAnyRole(roles, PRICING_APPROVERS);
  const canSeeInternalPrices = hasAnyRole(roles, INTERNAL_PRICE_READERS);

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
      ? [{ label: project?.name ?? "Project" }]
      : [
          { label: project?.name ?? "Project", href: projectHref(projectId) },
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
    if (section === "overview") {
      return (
        <>
          {editing ? (
            <Card
              title="Edit project"
              description="The code is fixed once issued. Everything else about the project's identity is maintained here."
            >
              <EditForm
                fields={projectFields(project)}
                initial={{
                  name: asValue(project.name),
                  developer_entity: asValue(project.developer_entity),
                  city: asValue(project.city),
                  location: asValue(project.location),
                  latitude: asValue(project.latitude),
                  longitude: asValue(project.longitude),
                  project_type_code: asValue(project.project_type_code),
                  status: asValue(project.status),
                  fiscal_year_start_month: asValue(project.fiscal_year_start_month),
                  planned_start: asValue(project.planned_start),
                  planned_completion: asValue(project.planned_completion),
                }}
                onSave={async (changes) => {
                  await projects.update(projectId, changes);
                  await changed();
                  setEditing(false);
                }}
                onCancel={() => setEditing(false)}
              />
            </Card>
          ) : null}
          <ProjectCommandCenter
            project={project}
            roles={roles}
            canEdit={canWriteProject}
            onEdit={() => setEditing((open) => !open)}
            onNavigate={navigate}
            refreshKey={refreshKey}
          />
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
        {section === "permits" ? <PermitsTab projectId={projectId} canWrite={canWriteTechnical} /> : null}
        {section === "inventory" ? (
          <InventoryTab
            projectId={projectId}
            projectStatus={project.status}
            roles={roles}
            canWriteStructure={canWriteTechnical}
            canConfigure={canWriteProject}
          />
        ) : null}
        {section === "pricing" ? (
          <PricingTab
            projectId={projectId}
            projectStatus={project.status}
            reportingCurrencyId={project.reporting_currency_id}
            canPrice={canPrice}
            canApprove={canApprovePricing}
            canSeeInternal={canSeeInternalPrices}
            onOpenUnit={(unitId) => setOpenUnit(unitId)}
          />
        ) : null}
        {section === "sales" ? (
          <SalesTab
            projectId={projectId}
            projectStatus={project.status}
            roles={roles}
            userId={user.id}
            onOpenUnit={(unitId) => setOpenUnit(unitId)}
          />
        ) : null}
        {section === "payments" ? (
          <PaymentPlansTab projectId={projectId} projectStatus={project.status} roles={roles} />
        ) : null}
        {section === "collections" ? <CollectionsTab projectId={projectId} roles={roles} /> : null}
        {section === "construction" ? <ConstructionTab projectId={projectId} /> : null}
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
        {openUnit ? (
          <UnitDetailPanel
            projectId={projectId}
            roles={roles}
            unitId={openUnit}
            canWriteStructure={canWriteTechnical}
            canConfigure={canWriteProject}
            onClose={() => setOpenUnit(null)}
            onChanged={changed}
          />
        ) : null}
      </AppShell>
    </CurrencyProvider>
  );
}
