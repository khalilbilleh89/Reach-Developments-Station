"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, projects, settings } from "@/lib/api";
import type { CurrentUser, ProjectDetail } from "@/lib/api";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  KeyValue,
  KeyValueGrid,
  Loading,
  Notice,
  PageHeader,
  Stat,
  StatRow,
  SubPanel,
  TabPanel,
  Tabs,
} from "@/components/ui";
import type { Tone } from "@/components/ui";
import { CurrencyProvider } from "@/lib/currency";
import { businessDate } from "@/lib/format";
import { AccessTab } from "@/components/projects/AccessTab";
import { CollectionsTab } from "@/components/projects/CollectionsTab";
import { EditForm, asValue } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";
import { DocumentsTab } from "@/components/projects/DocumentsTab";
import { InventoryTab } from "@/components/projects/InventoryTab";
import { UnitDetailPanel } from "@/components/projects/inventory/UnitDetailPanel";
import { LandTab } from "@/components/projects/LandTab";
import { PaymentPlansTab } from "@/components/projects/PaymentPlansTab";
import { PermitsTab } from "@/components/projects/PermitsTab";
import { PricingTab } from "@/components/projects/PricingTab";
import { SalesTab } from "@/components/projects/SalesTab";

const STATUS_LABELS: Record<string, string> = {
  setup: "Setup",
  predevelopment: "Pre-development",
  active: "Active",
  on_hold: "On hold",
  completed: "Completed",
  cancelled: "Cancelled",
};

/** Presentation only: the word already carries the meaning. */
const STATUS_TONES: Record<string, Tone> = {
  setup: "muted",
  predevelopment: "info",
  active: "success",
  on_hold: "warning",
  completed: "neutral",
  cancelled: "danger",
};

/** What each section is for, said once at the top rather than on every card. */
const TAB_DESCRIPTIONS: Record<string, string> = {
  overview: "What this project is, and what is holding it up.",
  land: "The parcels this development sits on, and what may be built on them.",
  inventory: "Every unit in this development, and what stops each one being released.",
  pricing: "What this development is priced at, and what that price is made of.",
  sales: "Where every unit stands commercially, legally and on delivery.",
  payments: "How each contracted amount is scheduled to be paid, and what makes it due.",
  permits: "The consents this development needs, and which of them are late.",
  documents: "Links to documents held elsewhere. Nothing is uploaded or stored here.",
  access: "Who may open this project. Roles decide what they can do once inside.",
};

/** Roles that may change project identity and the land record. */
const PROJECT_WRITERS = new Set(["system_admin", "project_manager"]);

/** Roles that may maintain planning, permits and document references. */
const TECHNICAL_WRITERS = new Set(["system_admin", "project_manager", "design_engineering"]);

/** Roles that may prepare pricing: build a policy, price units, submit for approval. */
const PRICING_WRITERS = new Set(["system_admin", "project_manager", "finance"]);

/**
 * Roles that may sanction a price. Deliberately not the administrator: the
 * ability to configure a system is not the authority to approve what it
 * charges, and the server refuses either way — this only decides which buttons
 * are worth showing.
 */
const PRICING_APPROVERS = new Set(["approver_cfo"]);

/** Roles that may see anything other than the live list price. */
const INTERNAL_PRICE_READERS = new Set([
  "system_admin",
  "project_manager",
  "finance",
  "approver_cfo",
  "executive_viewer",
  "auditor",
]);

/** Editable project identity. `code` is absent: it is immutable once issued. */
function projectFields(project: ProjectDetail): EditField[] {
  return [
    { name: "name", label: "Name" },
    { name: "developer_entity", label: "Developer entity" },
    { name: "city", label: "City" },
    { name: "location", label: "Location" },
    { name: "latitude", label: "Latitude", kind: "number", hint: "Decimal degrees." },
    { name: "longitude", label: "Longitude", kind: "number" },
    { name: "project_type_code", label: "Project type", hint: "A configured code." },
    {
      name: "status",
      label: "Status",
      kind: "select",
      options: Object.entries(STATUS_LABELS).map(([value, label]) => ({ value, label })),
      // Setup is the opening state only: the backend refuses a return to it,
      // so it is not offered once the project has left it.
      hint: project.status === "setup" ? undefined : "A project cannot return to setup.",
    },
    { name: "fiscal_year_start_month", label: "Fiscal year starts (month)", kind: "number" },
    { name: "planned_start", label: "Planned start", kind: "date" },
    { name: "planned_completion", label: "Planned completion", kind: "date" },
  ];
}

/**
 * One cohesive project workspace rather than a separate page per record type.
 *
 * Everything about a development is reached from here, because land, planning
 * and permits are only meaningful inside the project that owns them. The header
 * names the project once, at the top, and stays true whichever section is open:
 * the most expensive mistake this product can allow is recording something
 * against the wrong development.
 */
export function ProjectWorkspace({
  projectId,
  user,
  onBack,
}: {
  projectId: string;
  user: CurrentUser;
  onBack: () => void;
}) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  // Which currency each currency_id names, for every money figure below this
  // point. Seeded from the currency register (readable by any signed-in user)
  // plus the project's own base and reporting pair, so a row's REAL currency
  // is resolved rather than assumed from the project.
  const [currencyCodes, setCurrencyCodes] = useState<Record<string, string>>({});
  const [tab, setTab] = useState("overview");
  // Opening a unit from the price register reuses the same detail panel the
  // Inventory tab opens. One Unit 360, reached from wherever the user was.
  const [pricedUnit, setPricedUnit] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const roles = new Set(user.roles.map((role) => role.key));
  const isAdmin = roles.has("system_admin");
  const canWriteProject = [...roles].some((role) => PROJECT_WRITERS.has(role));
  const canWriteTechnical = [...roles].some((role) => TECHNICAL_WRITERS.has(role));
  const canPrice = [...roles].some((role) => PRICING_WRITERS.has(role));
  const canApprovePricing = [...roles].some((role) => PRICING_APPROVERS.has(role));
  const canSeeInternalPrices = [...roles].some((role) => INTERNAL_PRICE_READERS.has(role));

  const tabs = [
    { key: "overview", label: "Overview" },
    { key: "land", label: "Land" },
    { key: "inventory", label: "Inventory" },
    { key: "pricing", label: "Pricing" },
    { key: "sales", label: "Sales" },
    { key: "payments", label: "Payment plans" },
    { key: "collections", label: "Collections" },
    { key: "permits", label: "Permits" },
    { key: "documents", label: "Documents" },
    ...(isAdmin ? [{ key: "access", label: "Access" }] : []),
  ];

  const load = useCallback(async () => {
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
      setCurrencyCodes(codes);
      setProject(detail);
      setError(null);
    } catch (caught) {
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

  if (error) {
    return (
      <>
        <PageHeader
          title="Project"
          actions={<Button onClick={onBack}>All projects</Button>}
        />
        <Card>
          <Notice tone="error">{error}</Notice>
        </Card>
      </>
    );
  }

  if (project === null) {
    return (
      <>
        <PageHeader title="Loading project…" />
        <Card>
          <Loading label="Loading project…" lines={4} />
        </Card>
      </>
    );
  }

  return (
    <CurrencyProvider codes={currencyCodes}>
      <PageHeader
        eyebrow="Project"
        title={project.name}
        subtitle={`${project.developer_entity}${project.city ? ` · ${project.city}` : ""}`}
        actions={<Button onClick={onBack}>All projects</Button>}
        meta={
          <>
            <span className="chip">
              <span className="chip-label">Code</span>
              <strong className="mono">{project.code}</strong>
            </span>
            <Badge tone={STATUS_TONES[project.status] ?? "neutral"}>
              {STATUS_LABELS[project.status] ?? project.status}
            </Badge>
            {project.country_code ? (
              <span className="chip">
                <span className="chip-label">Country</span>
                <strong>{project.country_code}</strong>
              </span>
            ) : null}
            {project.base_currency_code ? (
              <span className="chip">
                <span className="chip-label">Base</span>
                <strong>{project.base_currency_code}</strong>
              </span>
            ) : null}
            {project.reporting_currency_code &&
            project.reporting_currency_code !== project.base_currency_code ? (
              <span className="chip">
                <span className="chip-label">Reporting</span>
                <strong>{project.reporting_currency_code}</strong>
              </span>
            ) : null}
          </>
        }
      />

      <Tabs label="Project sections" tabs={tabs} active={tab} onSelect={setTab} />

      <TabPanel group="Project sections" tab={tab}>
        {tab === "overview" ? (
          <>
            <Card
              title="Overview"
              description={TAB_DESCRIPTIONS.overview}
              actions={
                canWriteProject ? (
                  <Button onClick={() => setEditing((open) => !open)}>
                    {editing ? "Cancel" : "Edit project"}
                  </Button>
                ) : undefined
              }
            >
              {editing ? (
                <SubPanel title="Edit project">
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
                      await load();
                      setEditing(false);
                    }}
                    onCancel={() => setEditing(false)}
                  />
                </SubPanel>
              ) : null}

              <h3 className="section-heading">Identity</h3>
              <KeyValueGrid columns={3}>
                <KeyValue label="Developer entity" value={project.developer_entity} />
                <KeyValue label="Project manager" value={project.project_manager_display_name} />
                <KeyValue label="Project type" value={project.project_type_code} />
                <KeyValue label="Location" value={project.location} />
                <KeyValue
                  label="Coordinates"
                  mono
                  value={
                    project.latitude && project.longitude
                      ? `${project.latitude}, ${project.longitude}`
                      : null
                  }
                />
                <KeyValue
                  label="Fiscal year starts"
                  value={`Month ${project.fiscal_year_start_month}`}
                />
              </KeyValueGrid>

              <h3 className="section-heading">Programme</h3>
              <KeyValueGrid columns={3}>
                <KeyValue label="Planned start" mono value={businessDate(project.planned_start)} />
                <KeyValue label="Planned completion" mono value={businessDate(project.planned_completion)} />
                <KeyValue
                  label="Planned duration"
                  mono
                  value={
                    project.planned_duration_days === null
                      ? null
                      : `${project.planned_duration_days} days`
                  }
                />
              </KeyValueGrid>
            </Card>

            <Card
              title="Land and consents"
              description="Counted across this project. Open Permits to see which ones."
              actions={
                <Button onClick={() => setTab("permits")}>Open permits</Button>
              }
            >
              {/*
                * These counts describe the PERMITS, never the units. A permit
                * flagged as blocking is a management flag on the consent
                * itself; unit release truth lives in inventory and is not
                * derived from permit status. The copy here must not claim a
                * rule the backend does not enforce.
                */}
              <StatRow>
                <Stat label="Parcels" value={project.parcel_count} />
                <Stat label="Permits" value={project.permit_count} />
                <Stat
                  label="Blocking permits"
                  value={project.blocking_permit_count}
                  note="Consents flagged as blocking"
                />
                <Stat
                  label="On the critical path"
                  value={project.critical_path_permit_count}
                />
                <Stat
                  label="Past statutory period"
                  value={project.overdue_permit_count}
                />
              </StatRow>
              {project.blocking_permit_count > 0 || project.overdue_permit_count > 0 ? (
                <p className="footnote">
                  These permits are flagged for management attention. Open Permits to see the
                  affected consents.
                </p>
              ) : null}
            </Card>
          </>
        ) : null}

        {tab === "land" ? (
          <LandTab
            projectId={projectId}
            canWriteLand={canWriteProject}
            canWritePlanning={canWriteTechnical}
          />
        ) : null}
        {tab === "inventory" ? (
          <InventoryTab
            projectId={projectId}
            projectStatus={project.status}
            roles={roles}
            canWriteStructure={canWriteTechnical}
            canConfigure={canWriteProject}
          />
        ) : null}
        {tab === "pricing" ? (
          <PricingTab
            projectId={projectId}
            projectStatus={project.status}
            reportingCurrencyId={project.reporting_currency_id}
            canPrice={canPrice}
            canApprove={canApprovePricing}
            canSeeInternal={canSeeInternalPrices}
            onOpenUnit={(unitId) => setPricedUnit(unitId)}
          />
        ) : null}
        {tab === "sales" ? (
          <SalesTab
            projectId={projectId}
            projectStatus={project.status}
            roles={roles}
            onOpenUnit={(unitId) => setPricedUnit(unitId)}
          />
        ) : null}
        {tab === "payments" ? (
          <PaymentPlansTab
            projectId={projectId}
            projectStatus={project.status}
            roles={roles}
          />
        ) : null}
        {tab === "collections" ? (
          <CollectionsTab projectId={projectId} roles={roles} />
        ) : null}
        {tab === "permits" ? (
          <PermitsTab projectId={projectId} canWrite={canWriteTechnical} />
        ) : null}
        {tab === "documents" ? (
          <DocumentsTab projectId={projectId} canWrite={canWriteTechnical} />
        ) : null}
        {tab === "access" && isAdmin ? <AccessTab projectId={projectId} /> : null}
        {tab === "access" && !isAdmin ? (
          <Card title="Access">
            <EmptyState
              title="Not available to you"
              hint="Project membership is maintained by an administrator."
            />
          </Card>
        ) : null}
      </TabPanel>

      {pricedUnit ? (
        <UnitDetailPanel
          projectId={projectId}
          roles={roles}
          unitId={pricedUnit}
          canWriteStructure={canWriteTechnical}
          canConfigure={canWriteProject}
          onClose={() => setPricedUnit(null)}
          onChanged={load}
        />
      ) : null}
    </CurrencyProvider>
  );
}
