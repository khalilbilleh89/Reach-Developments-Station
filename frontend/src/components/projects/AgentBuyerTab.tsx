"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { SalesClient } from "@/lib/api";
import { Notice, PageHeader } from "@/components/ui";
import { ClientsPanel } from "./sales/ClientsPanel";
import { AgentsPanel } from "./sales/AgentsPanel";
import { NewReservation } from "./sales/NewReservation";
import { createdSalesHref } from "./sales/salesRoutes";

/**
 * Two screens over one record, because there are two jobs and only one table.
 *
 * A buyer is the counterparty: who is purchasing, how to reach them, which
 * parties sign and for what share, and which unit they are connecting to. The
 * four `agent_*` fields on the same row are something else entirely — they name
 * the salesperson's country, branch, branch leader and agent, and they exist to
 * be copied onto a reservation and frozen onto the sale that follows.
 *
 * Presenting them together, as one "Agent/Buyer" register did, invited the
 * reading that a buyer *has* a country. They do not: `agent_country` is where
 * the salesperson sits, and a screen that lets somebody mistake it for the
 * purchaser's nationality is a screen that will eventually be used to file one.
 *
 * So the two jobs are separated in the navigation and in the reading, while the
 * data underneath is untouched. There is no agent entity here and this file
 * does not invent one: `mode` chooses which question the screen answers.
 */
export function AgentBuyerTab({
  mode = "buyers",
  projectId,
  projectStatus,
  roles,
}: {
  mode?: "buyers" | "agents";
  projectId: string;
  projectStatus: string;
  roles: Set<string>;
}) {
  const [buyer, setBuyer] = useState<SalesClient | null>(null);
  const router = useRouter();
  const canWrite = roles.has("master_admin") || roles.has("sales_operations") || roles.has("sales_advisor");
  const open = (kind: "sale" | "reservation", id: string) => {
    router.push(createdSalesHref(new URLSearchParams({project: projectId, section: "sales"}), projectId, kind, id));
  };
  if (mode === "agents") {
    return <div className="stack">
      <PageHeader icon="sales" title="Agents" subtitle="The sales team recorded against each buyer, and copied onto their next reservation and sale." compact />
      {projectStatus === "setup" ? <Notice tone="info">Sales team attribution becomes available when project setup is complete.</Notice> : <AgentsPanel projectId={projectId} canWrite={canWrite} />}
    </div>;
  }
  return <div className="stack">
    <PageHeader icon="sales" title="Buyers" subtitle="Register the purchaser and their parties, connect a unit, then follow its progress in Sales." compact />
    {projectStatus === "setup" ? <Notice tone="info">Buyer registration becomes available when project setup is complete.</Notice> : buyer ? <>
      <Notice tone="info">Connecting a unit for {buyer.display_name}.</Notice>
      <NewReservation key={buyer.id} projectId={projectId} clientId={buyer.id} allowOwner={roles.has("master_admin")} onCancel={() => setBuyer(null)} onCreated={id => open("reservation", id)} onSaleCreated={id => open("sale", id)} />
    </> : <ClientsPanel projectId={projectId} canWrite={canWrite} canAdmin={roles.has("master_admin") || roles.has("system_admin")} onChanged={async () => {}} onConnect={setBuyer} />}
  </div>;
}
