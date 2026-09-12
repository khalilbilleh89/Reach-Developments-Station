"use client";

import { useEffect, useState } from "react";
import { ApiError, projects, settings } from "@/lib/api";
import type { CountryPack, Currency, ProjectDetail } from "@/lib/api";
import { Loading, Notice, RecordPage } from "@/components/ui";
import { EditForm, asValue } from "./EditForm";
import type { EditField } from "./EditForm";
import { PROJECT_STATUSES, projectStatusLabel } from "./projectStatus";

export function projectFields(project: ProjectDetail, packs: CountryPack[], currencies: Currency[]): EditField[] {
  const basis = project.status === "setup";
  return [
    { name: "code", label: "Project code", group: "Identity", hint: "Letters, digits, hyphen or underscore; 2 to 32 characters." },
    { name: "name", label: "Name", group: "Identity" },
    { name: "developer_entity", label: "Developer entity", group: "Identity" },
    { name: "project_type_code", label: "Project type", hint: "A configured code.", group: "Identity", width: "medium" },
    {
      name: "status",
      label: "Status",
      kind: "select",
      group: "Identity",
      options: PROJECT_STATUSES.filter(value => project.status === "setup" || value !== "setup").map((value) => ({ value, label: projectStatusLabel(value) })),
      // Setup is the opening state only: the backend refuses a return to it,
      // so it is not offered once the project has left it.
      hint: project.status === "setup" ? undefined : "A project cannot return to setup.",
    },
    { name: "country_pack_id", label: "Country configuration", group: "Financial basis", kind: "select", visible: basis,
      options: packs.filter(p => p.is_active || p.id === project.country_pack_id).map(p => ({ value: p.id, label: `${p.name} (${p.country_code})` })) },
    { name: "base_currency_id", label: "Base currency", group: "Financial basis", kind: "select", visible: basis,
      options: currencies.filter(c => c.is_active || c.id === project.base_currency_id).map(c => ({ value: c.id, label: `${c.code} — ${c.name}` })) },
    { name: "reporting_currency_id", label: "Reporting currency", group: "Financial basis", kind: "select", visible: basis,
      options: currencies.filter(c => c.is_active || c.id === project.reporting_currency_id).map(c => ({ value: c.id, label: `${c.code} — ${c.name}` })) },
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
      group: "Financial basis",
    },
  ];
}

export function ProjectEdit({ project, onSaved, onClose }: {
  project: ProjectDetail; onSaved: () => Promise<void>; onClose: () => void;
}) {
  const [configuration, setConfiguration] = useState<{ packs: CountryPack[]; currencies: Currency[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    Promise.all([settings.countryPacks(), settings.currencies()]).then(([packs, currencies]) => {
      if (active) setConfiguration({ packs, currencies });
    }).catch(caught => {
      if (active) setError(caught instanceof ApiError ? caught.message : "Could not load country and currency options. Close and reopen the editor to retry.");
    });
    return () => { active = false; };
  }, []);
  const fields = configuration ? projectFields(project, configuration.packs, configuration.currencies) : [];
  const initial = Object.fromEntries(fields.map(field => [field.name, asValue(project[field.name as keyof ProjectDetail]) ]));
  return <RecordPage title="Edit project" subtitle={project.name} onClose={onClose}>
    {error ? <Notice tone="error">{error}</Notice> : !configuration ? <Loading label="Loading project options…" /> : <>
      {project.status !== "setup" ? <Notice tone="info">
        Country configuration: {configuration.packs.find(pack => pack.id === project.country_pack_id)?.name ?? project.country_code ?? "Unavailable"}.
        Base currency: {project.base_currency_code}. Reporting currency: {project.reporting_currency_code}.
        These settings are locked after setup to preserve the basis of existing records. All other details below remain editable.
      </Notice> : <Notice tone="info">Country and currency corrections are available during setup. Existing land, permit, document or monetary records may prevent a change. Changing a currency does not convert amounts.</Notice>}
      <EditForm fields={fields} initial={initial} onCancel={onClose} onSave={async changes => {
        await projects.update(project.id, changes);
        await onSaved();
      }} />
    </>}
  </RecordPage>;
}
