"use client";

import { useState } from "react";
import { sales } from "@/lib/api";
import type { SalesClient } from "@/lib/api";
import { Button, Card, FormActions, RecordPage } from "@/components/ui";
import { EditForm } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";

export const clientLinkFields: EditField[] = [
  { name: "client_folder_url", label: "Client Folder link", hint: "Paste the Google Drive folder sharing link. Clear the field to remove it.", width: "full" },
  { name: "odoo_opportunity_url", label: "Opportunity Odoo link", hint: "Paste the HTTPS opportunity link, including its record ID. Clear the field to remove it.", width: "full" },
];

export function ClientLinkButtons({client}: {client: SalesClient}) {
  return <FormActions>
    {client.client_folder_url ? <a className="button" href={client.client_folder_url} target="_blank" rel="noopener noreferrer">Client Folder ↗</a> : null}
    {client.odoo_opportunity_url ? <a className="button" href={client.odoo_opportunity_url} target="_blank" rel="noopener noreferrer">Opportunity Odoo ↗</a> : null}
  </FormActions>;
}

export function ClientLinks({projectId, client, canWrite, onSaved}: {
  projectId: string; client: SalesClient; canWrite: boolean; onSaved: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  // Sensitive links are absent from summary responses, not merely hidden here.
  if (!("client_folder_url" in client)) return null;
  if (editing && canWrite) return <RecordPage title={`Links for ${client.display_name}`} onClose={() => setEditing(false)}>
    <p>These links belong to the client and are shared across their sales in this project.</p>
    <EditForm fields={clientLinkFields} columns={2} initial={{client_folder_url: client.client_folder_url ?? "", odoo_opportunity_url: client.odoo_opportunity_url ?? ""}}
      onCancel={() => setEditing(false)} onSave={async changes => {await sales.updateClient(projectId, client.id, changes); await onSaved();}} />
  </RecordPage>;
  return <Card title="Client links" description="Opens in a new tab. Google Drive and Odoo access permissions still apply.">
    <ClientLinkButtons client={client}/>
    {!client.client_folder_url && !client.odoo_opportunity_url ? <p>No client links added yet.</p> : null}
    {canWrite ? <Button onClick={() => setEditing(true)}>Edit client links</Button> : null}
  </Card>;
}
