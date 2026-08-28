"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, projects } from "@/lib/api";
import type { CurrentUser, ProjectDetail } from "@/lib/api";
import { Badge, Loading, Notice, Panel } from "@/components/ui";
import { AccessTab } from "@/components/projects/AccessTab";
import { DocumentsTab } from "@/components/projects/DocumentsTab";
import { LandTab } from "@/components/projects/LandTab";
import { PermitsTab } from "@/components/projects/PermitsTab";

const STATUS_LABELS: Record<string, string> = {
  setup: "Setup",
  predevelopment: "Pre-development",
  active: "Active",
  on_hold: "On hold",
  completed: "Completed",
  cancelled: "Cancelled",
};

/** Roles that may change project identity and the land record. */
const PROJECT_WRITERS = new Set(["system_admin", "project_manager"]);

/** Roles that may maintain planning, permits and document references. */
const TECHNICAL_WRITERS = new Set(["system_admin", "project_manager", "design_engineering"]);

/**
 * One cohesive project workspace rather than a separate page per record type.
 *
 * Everything about a development is reached from here, because land, planning
 * and permits are only meaningful inside the project that owns them.
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
  const [tab, setTab] = useState("overview");
  const [error, setError] = useState<string | null>(null);

  const roles = new Set(user.roles.map((role) => role.key));
  const isAdmin = roles.has("system_admin");
  const canWriteProject = [...roles].some((role) => PROJECT_WRITERS.has(role));
  const canWriteTechnical = [...roles].some((role) => TECHNICAL_WRITERS.has(role));

  const tabs = [
    { key: "overview", label: "Overview" },
    { key: "land", label: "Land" },
    { key: "permits", label: "Permits" },
    { key: "documents", label: "Documents" },
    ...(isAdmin ? [{ key: "access", label: "Access" }] : []),
  ];

  const load = useCallback(async () => {
    try {
      setProject(await projects.read(projectId));
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
      <Panel title="Project">
        <Notice tone="error">{error}</Notice>
        <button className="button" type="button" onClick={onBack}>
          Back to projects
        </button>
      </Panel>
    );
  }

  if (project === null) {
    return <Loading label="Loading project…" />;
  }

  return (
    <>
      <Panel
        title={`${project.code} — ${project.name}`}
        description={`${project.developer_entity}${project.city ? ` · ${project.city}` : ""}`}
        actions={
          <button className="button button-small" type="button" onClick={onBack}>
            All projects
          </button>
        }
      >
        <div className="chip-list">
          <Badge tone="neutral">{STATUS_LABELS[project.status] ?? project.status}</Badge>
          {project.country_code ? <span className="chip">{project.country_code}</span> : null}
          {project.base_currency_code ? (
            <span className="chip">Base {project.base_currency_code}</span>
          ) : null}
          {project.reporting_currency_code &&
          project.reporting_currency_code !== project.base_currency_code ? (
            <span className="chip">Reporting {project.reporting_currency_code}</span>
          ) : null}
        </div>
      </Panel>

      <nav className="tab-row" role="tablist" aria-label="Project sections">
        {tabs.map((entry) => (
          <button
            key={entry.key}
            role="tab"
            type="button"
            aria-selected={tab === entry.key}
            className={`tab ${tab === entry.key ? "tab-active" : ""}`}
            onClick={() => setTab(entry.key)}
          >
            {entry.label}
          </button>
        ))}
      </nav>

      {tab === "overview" ? (
        <Panel title="Overview" description="What this project is, and what is holding it up.">
          <dl className="reference-list">
            <div>
              <dt className="reference-term">Developer entity</dt>
              <dd className="reference-value">{project.developer_entity}</dd>
            </div>
            <div>
              <dt className="reference-term">Location</dt>
              <dd className="reference-value">{project.location ?? "—"}</dd>
            </div>
            <div>
              <dt className="reference-term">Coordinates</dt>
              <dd className="reference-value mono">
                {project.latitude && project.longitude
                  ? `${project.latitude}, ${project.longitude}`
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="reference-term">Project manager</dt>
              <dd className="reference-value">
                {project.project_manager_display_name ?? "Not assigned"}
              </dd>
            </div>
            <div>
              <dt className="reference-term">Project type</dt>
              <dd className="reference-value">{project.project_type_code ?? "—"}</dd>
            </div>
            <div>
              <dt className="reference-term">Fiscal year starts</dt>
              <dd className="reference-value">Month {project.fiscal_year_start_month}</dd>
            </div>
            <div>
              <dt className="reference-term">Planned start</dt>
              <dd className="reference-value">{project.planned_start ?? "—"}</dd>
            </div>
            <div>
              <dt className="reference-term">Planned completion</dt>
              <dd className="reference-value">{project.planned_completion ?? "—"}</dd>
            </div>
            <div>
              <dt className="reference-term">Planned duration</dt>
              <dd className="reference-value">
                {project.planned_duration_days === null
                  ? "—"
                  : `${project.planned_duration_days} days`}
              </dd>
            </div>
            <div>
              <dt className="reference-term">Parcels</dt>
              <dd className="reference-value">{project.parcel_count}</dd>
            </div>
            <div>
              <dt className="reference-term">Permits</dt>
              <dd className="reference-value">{project.permit_count}</dd>
            </div>
            <div>
              <dt className="reference-term">Blocking permits</dt>
              <dd className="reference-value">{project.blocking_permit_count}</dd>
            </div>
            <div>
              <dt className="reference-term">On the critical path</dt>
              <dd className="reference-value">{project.critical_path_permit_count}</dd>
            </div>
            <div>
              <dt className="reference-term">Past their statutory period</dt>
              <dd className="reference-value">{project.overdue_permit_count}</dd>
            </div>
          </dl>
        </Panel>
      ) : null}

      {tab === "land" ? (
        <LandTab
          projectId={projectId}
          canWriteLand={canWriteProject}
          canWritePlanning={canWriteTechnical}
        />
      ) : null}
      {tab === "permits" ? (
        <PermitsTab projectId={projectId} canWrite={canWriteTechnical} />
      ) : null}
      {tab === "documents" ? (
        <DocumentsTab projectId={projectId} canWrite={canWriteTechnical} />
      ) : null}
      {tab === "access" && isAdmin ? <AccessTab projectId={projectId} /> : null}
    </>
  );
}
