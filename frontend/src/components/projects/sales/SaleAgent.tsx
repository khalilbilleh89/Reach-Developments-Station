"use client";

import { useState } from "react";
import { ApiError, sales } from "@/lib/api";
import type { SaleContract, Reservation } from "@/lib/api";
import { Button, Card, DraftBoundary, Field, FormActions, KeyValue, Notice } from "@/components/ui";
import { AgentSelect } from "./AgentSelect";

const frozenLabels = {agent_country: "Country", agent_branch: "Branch", agent_branch_leader: "Branch leader", agent_name: "Agent"};

export function SaleAgent({projectId, record, isSale, canWrite, onChanged}: {
  projectId: string; record: SaleContract | Reservation; isSale: boolean; canWrite: boolean; onChanged: () => Promise<void>;
}) {
  const initial = record.agent_id ?? "";
  const [value, setValue] = useState(initial);
  const [editing, setEditing] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return <Card title="Agent information" description="The sales team for this unit and buyer." actions={isSale && canWrite && record.status !== "cancelled" && !editing ? <Button onClick={() => {setValue(initial); setReason(""); setError(null); setEditing(true);}}>Edit agent information</Button> : null}>
    {editing ? <DraftBoundary dirty={reason !== "" || value !== initial} busy={busy}><form onSubmit={async event => {
      event.preventDefault(); if (busy) return; setBusy(true); setError(null);
      try {await sales.updateSaleAgent(projectId, record.id, {agent_id: value || null, reason: reason.trim()}); setEditing(false); await onChanged();}
      catch (caught) {setError(caught instanceof ApiError ? caught.message : "Could not save agent information.");}
      finally {setBusy(false);}
    }}>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <AgentSelect projectId={projectId} value={value} onChange={setValue} currentId={record.agent_id} disabled={busy} />
      <Field label="Reason for change"><input className="input" required maxLength={1000} value={reason} onChange={event => setReason(event.target.value)} /></Field>
      <FormActions><Button type="submit" variant="primary" disabled={busy || !reason.trim()}>Save agent information</Button><Button disabled={busy} data-leaves-editor onClick={() => setEditing(false)}>Cancel</Button></FormActions>
    </form></DraftBoundary> : <>{Object.entries(frozenLabels).map(([key, label]) => <KeyValue key={key} label={label} value={record[key as keyof typeof frozenLabels] ?? "Not recorded"} />)}{!record.agent_id && record.agent_name ? <p className="field-hint">Legacy attribution — not linked to an Agent record.</p> : null}</>}
  </Card>;
}
