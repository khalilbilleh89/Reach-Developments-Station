"use client";

import type { ReactNode } from "react";

import type { ProjectDetail } from "@/lib/api";
import { businessDate } from "@/lib/format";
import { Badge, ExternalLink, Icon, InlineMeta, InlineMetaItem, isUrl } from "@/components/ui";
import { projectStatusLabel, projectStatusTone } from "@/components/projects/projectStatus";

/**
 * The development's identity plate: what this project is, in the order a
 * person would say it out loud.
 *
 * The name, then who is developing it, then where it is — and where it is, is
 * a place. A project's location has always been free text, so half of them
 * hold "Abdoun, Amman" and half hold a hundred characters of map query string
 * that somebody pasted because it was the fastest way to record the site.
 * Both are useful, and neither is the project's name: the address goes in the
 * link where a browser wants it, and the plate says the place.
 *
 * Everything beneath is identification, not measurement — a code, a status, a
 * programme, a currency. No figure appears here. Figures are labelled, and
 * they belong in the position beneath.
 */
export function ProjectPlate({ project, actions }: { project: ProjectDetail; actions?: ReactNode }) {
  // The readable place, and separately the destination — the two are only
  // sometimes the same field.
  const mapHref = isUrl(project.location) ? project.location : null;
  const written = mapHref ? null : project.location;
  const place = [written, project.city, project.country_code].filter(Boolean).join(", ");
  const programme =
    project.planned_start || project.planned_completion
      ? `${businessDate(project.planned_start)} → ${businessDate(project.planned_completion)}`
      : null;

  return (
    <header className="plate">
      <div className="plate-main">
        <p className="plate-eyebrow">Project</p>
        <h1 className="plate-title">{project.name}</h1>
        <p className="plate-org">{project.developer_entity}</p>
        {place || mapHref ? (
          <p className="plate-place">
            <Icon name="location" />
            {place ? <span>{place}</span> : <span className="subtle">Location recorded as a link</span>}
            {mapHref ? <ExternalLink href={mapHref}>Open location</ExternalLink> : null}
          </p>
        ) : null}
        <div className="plate-facts">
          <InlineMeta>
            <InlineMetaItem label="Code">
              <span className="mono">{project.code}</span>
            </InlineMetaItem>
            <InlineMetaItem label="Status">
              <Badge tone={projectStatusTone(project.status)}>{projectStatusLabel(project.status)}</Badge>
            </InlineMetaItem>
            {project.project_type_code ? (
              <InlineMetaItem label="Type">{project.project_type_code}</InlineMetaItem>
            ) : null}
            {programme ? <InlineMetaItem label="Programme">{programme}</InlineMetaItem> : null}
            <InlineMetaItem label="Base">{project.base_currency_code ?? "—"}</InlineMetaItem>
            {project.reporting_currency_code && project.reporting_currency_code !== project.base_currency_code ? (
              <InlineMetaItem label="Reporting">{project.reporting_currency_code}</InlineMetaItem>
            ) : null}
            {project.project_manager_display_name ? (
              <InlineMetaItem label="Manager">{project.project_manager_display_name}</InlineMetaItem>
            ) : null}
          </InlineMeta>
        </div>
      </div>
      {actions ? <div className="plate-actions">{actions}</div> : null}
    </header>
  );
}
