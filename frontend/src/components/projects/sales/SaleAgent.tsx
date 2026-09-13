"use client";

import { useState } from "react";
import { ApiError, sales } from "@/lib/api";
import type { SaleContract, Reservation } from "@/lib/api";
import { Button, Card, DraftBoundary, Field, FormActions, KeyValue, Notice } from "@/components/ui";
import { AgentFields, agentLabels, agentPayload } from "./AgentFields";

export function SaleAgent({projectId, record, isSale, canWrite, onChanged}: {
  projectId: string; record: SaleContract | Reservation; isSale: boolean; canWrite: boolean; onChanged: () => Promise<void>;
}) {
  const initial = {agent_country: record.agent_country ?? "", agent_branch: record.agent_branch ?? "", agent_branch_leader: record.agent_branch_leader ?? "", agent_name: record.agent_name ?? ""};
  const [value, setValue] = useState(initial);
  const [editing, setEditing] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return <Card title="Agent information" description="The sales team for this unit and buyer." actions={isSale && canWrite && record.status !== "cancelled" && !editing ? <Button onClick={() => {setValue(initial); setReason(""); setError(null); setEditing(true);}}>Edit agent information</Button> : null}>
    {editing ? <DraftBoundary dirty={reason !== "" || JSON.stringify(value) !== JSON.stringify(initial)} busy={busy}><form onSubmit={async event => {
      event.preventDefault(); if (busy) return; setBusy(true); setError(null);
      try {await sales.updateSaleAgent(projectId, record.id, {...agentPayload(value), reason: reason.trim()}); setEditing(false); await onChanged();}
      catch (caught) {setError(caught instanceof ApiError ? caught.message : "Could not save agent information.");}
      finally {setBusy(false);}
    }}>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <AgentFields value={value} onChange={setValue} />
      <Field label="Reason for change"><input className="input" required maxLength={1000} value={reason} onChange={event => setReason(event.target.value)} /></Field>
      <FormActions><Button type="submit" variant="primary" disabled={busy || !reason.trim()}>Save agent information</Button><Button disabled={busy} data-leaves-editor onClick={() => setEditing(false)}>Cancel</Button></FormActions>
    </form></DraftBoundary> : Object.entries(agentLabels).map(([key, label]) => <KeyValue key={key} label={label} value={record[key as keyof typeof initial] ?? "Not recorded"} />)}
  </Card>;
}
