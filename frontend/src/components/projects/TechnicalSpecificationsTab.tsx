"use client";

import { Notice, PageHeader } from "@/components/ui";
import { hasAnyRole, SPECIFICATION_READERS } from "@/lib/roles";
import { TechnicalSpecifications } from "./construction/TechnicalSpecifications";

export function TechnicalSpecificationsTab({ projectId, roles }: { projectId: string; roles: Set<string> }) {
  if (!hasAnyRole(roles, SPECIFICATION_READERS)) return <Notice tone="info">Technical Specifications is not available to your role.</Notice>;
  return <div className="stack"><PageHeader title="Technical Specifications" icon="blueprint" subtitle="Project features, delivery specifications and optional reference images for Sales." /><TechnicalSpecifications projectId={projectId} roles={roles} /></div>;
}
