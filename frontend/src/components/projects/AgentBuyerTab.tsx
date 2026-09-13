"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { SalesClient } from "@/lib/api";
import { Notice, PageHeader } from "@/components/ui";
import { ClientsPanel } from "./sales/ClientsPanel";
import { NewReservation } from "./sales/NewReservation";
import { createdSalesHref } from "./sales/salesRoutes";

export function AgentBuyerTab({projectId, projectStatus, roles}: {projectId: string; projectStatus: string; roles: Set<string>}) {
  const [buyer, setBuyer] = useState<SalesClient | null>(null);
  const router = useRouter();
  const canWrite = roles.has("master_admin") || roles.has("sales_operations") || roles.has("sales_advisor");
  const open = (kind: "sale" | "reservation", id: string) => {
    router.push(createdSalesHref(new URLSearchParams({project: projectId, section: "sales"}), projectId, kind, id));
  };
  return <div className="stack">
    <PageHeader icon="sales" title="Agent/Buyer" subtitle="Register the buyer and sales team, connect a unit, then follow its progress in Sales." compact />
    {projectStatus === "setup" ? <Notice tone="info">Buyer registration becomes available when project setup is complete.</Notice> : buyer ? <>
      <Notice tone="info">Connecting a unit for {buyer.display_name}. {[buyer.agent_country, buyer.agent_branch, buyer.agent_branch_leader, buyer.agent_name].filter(Boolean).join(" · ")}</Notice>
      <NewReservation key={buyer.id} projectId={projectId} clientId={buyer.id} allowOwner={roles.has("master_admin")} onCancel={() => setBuyer(null)} onCreated={id => open("reservation", id)} onSaleCreated={id => open("sale", id)} />
    </> : <ClientsPanel projectId={projectId} canWrite={canWrite} canAdmin={roles.has("master_admin") || roles.has("system_admin")} onChanged={async () => {}} onConnect={setBuyer} />}
  </div>;
}
