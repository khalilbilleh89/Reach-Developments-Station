"use client";

import { Notice, PageHeader } from "@/components/ui";
import { CONSULTANT_READERS, CONSULTANT_EDITORS, hasAnyRole, type Roles } from "@/lib/roles";
import { Drawings } from "./design/Drawings";

export function PlansTab({ projectId, roles }: { projectId: string; roles: Roles }) {
  if (!hasAnyRole(roles, CONSULTANT_READERS)) return <Notice tone="info">Plans is not available to your role.</Notice>;
  return <div className="stack"><PageHeader title="Plans" icon="blueprint" subtitle="The project, on paper. Keep your plans together and review them here." /><Drawings key={projectId} projectId={projectId} canWrite={hasAnyRole(roles, CONSULTANT_EDITORS)} /></div>;
}
