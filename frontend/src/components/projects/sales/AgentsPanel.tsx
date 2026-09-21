"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, sales } from "@/lib/api";
import type { SalesAgent } from "@/lib/api";
import { Button, DataToolbar, DraftBoundary, EmptyState, Field, FieldRow, FormActions,
  Loading, Notice, RecordPage, TableScroll } from "@/components/ui";
import { DeleteRecordButton } from "@/components/projects/DeleteRecordButton";

function AgentForm({projectId, agent, onSaved, onCancel}: {
  projectId: string; agent: SalesAgent | null; onSaved: () => Promise<void>; onCancel: () => void;
}) {
  const [draft, setDraft] = useState({
    display_name: agent?.display_name ?? "", country: agent?.country ?? "",
    branch: agent?.branch ?? "", branch_leader: agent?.branch_leader ?? "",
    is_active: agent?.is_active ?? true,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return <DraftBoundary dirty={Boolean(draft.display_name || draft.country || draft.branch || draft.branch_leader || (agent && draft.is_active !== agent.is_active))} busy={busy}>
    <form onSubmit={async event => {
      event.preventDefault(); if (busy) return;
      setBusy(true); setError(null);
      const body = {display_name: draft.display_name.trim(), country: draft.country.trim() || null,
        branch: draft.branch.trim() || null, branch_leader: draft.branch_leader.trim() || null};
      try {
        if (agent) await sales.updateAgent(projectId, agent.id, {...body, is_active: draft.is_active});
        else await sales.createAgent(projectId, body);
        await onSaved();
      } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save the Agent."); }
      finally { setBusy(false); }
    }}>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <FieldRow columns={2}>
        {(["display_name", "country", "branch", "branch_leader"] as const).map(key =>
          <Field key={key} label={{display_name: "Agent name", country: "Country", branch: "Branch", branch_leader: "Branch leader"}[key]} optional={key !== "display_name"}>
            <input className="input" required={key === "display_name"} maxLength={200} value={draft[key]} onChange={event => setDraft({...draft, [key]: event.target.value})} />
          </Field>)}
      </FieldRow>
      {agent ? <label className="checkbox"><input type="checkbox" checked={draft.is_active} onChange={event => setDraft({...draft, is_active: event.target.checked})} /><span>Active — available for new assignments</span></label> : null}
      <FormActions><Button type="submit" variant="primary" disabled={busy || !draft.display_name.trim()}>{agent ? "Save Agent" : "Add agent"}</Button><Button data-leaves-editor disabled={busy} onClick={onCancel}>Cancel</Button></FormActions>
    </form>
  </DraftBoundary>;
}

/** A roster, not a grouping of buyers with matching names. */
export function AgentsPanel({projectId, canWrite}: {projectId: string; canWrite: boolean}) {
  const [agents, setAgents] = useState<SalesAgent[] | null>(null);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<SalesAgent | "new" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const load = useCallback(async () => {
    try { setAgents(await sales.agents(projectId, search ? {search} : {})); setError(null); }
    catch (caught) { setAgents(null); setError(caught instanceof ApiError ? caught.message : "Could not load Agents."); }
  }, [projectId, search]);
  useEffect(() => { void (async () => { await load(); })(); }, [load]);

  if (editing) return <RecordPage title={editing === "new" ? "Add agent" : `Edit ${editing.display_name}`} onClose={() => setEditing(null)}>
    <p className="field-hint">An Agent can exist before any buyer or sale. Changes to this roster never rewrite existing transaction snapshots.</p>
    <AgentForm key={editing === "new" ? "new" : editing.id} projectId={projectId} agent={editing === "new" ? null : editing}
      onCancel={() => setEditing(null)} onSaved={async () => { setEditing(null); setNotice("Agent saved."); await load(); }} />
  </RecordPage>;

  return <div className="stack">
    {error ? <Notice tone="error">{error}<Button onClick={() => void load()}>Retry</Button></Notice> : null}
    {notice ? <Notice tone="success">{notice}</Notice> : null}
    <DataToolbar search={{value: search, onChange: setSearch, label: "Search agents", placeholder: "Agent name"}}
      count={agents ? {shown: agents.length, noun: "agent"} : undefined}
      onReset={search ? () => setSearch("") : undefined}
      actions={canWrite ? <Button variant="primary" onClick={() => setEditing("new")}>Add agent</Button> : undefined} />
    {agents === null ? (error ? null : <Loading label="Loading Agents…" />) : agents.length === 0 ?
      <EmptyState title="No agents registered" hint="Add an Agent before assigning one to a buyer. Buyers may also have no Agent." /> :
      <TableScroll label="Project Agents" fixedFirst>
        <thead><tr><th scope="col">Agent</th><th scope="col">Country</th><th scope="col">Branch</th><th scope="col">Branch leader</th><th scope="col">Status</th>{canWrite ? <th scope="col">Actions</th> : null}</tr></thead>
        <tbody>{agents.map(agent => <tr key={agent.id}>
          <th scope="row">{agent.display_name}</th><td>{agent.country ?? "—"}</td><td>{agent.branch ?? "—"}</td><td>{agent.branch_leader ?? "—"}</td>
          <td>{agent.is_active ? "Active" : "Inactive"}</td>
          {canWrite ? <td><div className="buyer-actions"><Button small onClick={() => setEditing(agent)}>Edit Agent</Button>
            <DeleteRecordButton label={`Agent ${agent.display_name}`} onDelete={reason => sales.deleteAgent(projectId, agent.id, reason)} onDeleted={async () => { setNotice("Unused Agent deleted."); await load(); }} />
          </div></td> : null}
        </tr>)}</tbody>
      </TableScroll>}
  </div>;
}
