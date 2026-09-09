"use client";

import Link from "next/link";
import { useState } from "react";
import type { FormEvent } from "react";
import { Badge, Button, ButtonRow, Drawer, Field, FieldRow, FormSection, KeyValue, KeyValueGrid, Loading, Notice } from "@/components/ui";
import { useAnswer } from "@/lib/answer";
import { management } from "@/lib/api/management";
import type { ActionSource, ActionStatus, ManagementAction } from "@/lib/api/management";
import { businessDate } from "@/lib/format";

export function ProjectChoice({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const [offset, setOffset] = useState(0);
  const answer = useAnswer(true, () => management.projects(offset), [offset]);
  return <div className="stack"><Field label="Project"><select value={value} onChange={(event) => onChange(event.target.value)}><option value="">Select a development</option>{value && answer.status === "ready" && !answer.data.items.some((row) => row.id === value) ? <option value={value}>Selected development</option> : null}{answer.status === "ready" ? answer.data.items.map((project) => <option key={project.id} value={project.id}>{project.code} · {project.name}</option>) : null}</select></Field>
    {answer.status === "failed" ? <span className="field-error">{answer.message}</span> : null}
    {answer.status === "ready" && answer.data.total > 100 ? <ButtonRow><Button small disabled={!offset} onClick={() => setOffset(offset - 100)}>Previous projects</Button><Button small disabled={offset + 100 >= answer.data.total} onClick={() => setOffset(offset + 100)}>More projects</Button></ButtonRow> : null}
  </div>;
}

function ActionForm({ project, initial, source, onSaved, onCancel }: { project: string; initial?: ManagementAction; source: ActionSource; onSaved: (action: ManagementAction) => void; onCancel: () => void }) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [owner, setOwner] = useState(initial?.owner.user_id ?? "");
  const [due, setDue] = useState(initial?.due_date ?? "");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const owners = useAnswer(Boolean(project), () => management.assignees(project), [project]);
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      const result = initial ? await management.update(initial.id, { expected_version: initial.version, title, description: description || null, owner_user_id: owner, due_date: due, reason: reason || null })
        : await management.create({ ...source, project_id: project, title, description: description || null, owner_user_id: owner, due_date: due });
      onSaved(result);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not save action."); }
    finally { setBusy(false); }
  }
  return <form onSubmit={save} className="stack"><FormSection title="Management commitment" description="A named owner and a dated next step. This action does not change its source record.">
    <Field label="Title"><input required maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} /></Field>
    <Field label="Description" optional><textarea maxLength={2000} rows={4} value={description} onChange={(event) => setDescription(event.target.value)} /></Field>
    <FieldRow><Field label="Owner"><select required value={owner} onChange={(event) => setOwner(event.target.value)}><option value="">Select an eligible owner</option>{owners.status === "ready" ? owners.data.map((user) => <option key={user.user_id} value={user.user_id}>{user.display_name}</option>) : null}</select></Field>
      <Field label="Due date"><input required type="date" value={due} onChange={(event) => setDue(event.target.value)} /></Field></FieldRow>
    {initial ? <Field label="Reason" optional hint="Required for due-date changes and reassignment after work starts."><textarea maxLength={2000} value={reason} onChange={(event) => setReason(event.target.value)} /></Field> : null}
  </FormSection>
    {owners.status === "failed" ? <Notice tone="error">{owners.message}</Notice> : null}
    {error ? <Notice tone="error">{error} <Button small onClick={onCancel}>Reload current action</Button></Notice> : null}
    <ButtonRow><Button variant="primary" type="submit" disabled={busy || owners.status !== "ready"}>{busy ? "Saving…" : initial ? "Save changes" : "Create action"}</Button><Button onClick={onCancel}>Cancel</Button></ButtonRow>
  </form>;
}

export function CreateAction({ projectId, source = { source_type: "manual" }, onClose, onSaved }: { projectId?: string; source?: ActionSource; onClose: () => void; onSaved: (action: ManagementAction) => void }) {
  const [project, setProject] = useState(projectId ?? "");
  return <Drawer title="Create management action" subtitle="Owner · due date · accountable history" onClose={onClose}>
    {!projectId ? <ProjectChoice value={project} onChange={setProject} /> : null}
    {source.source_type !== "manual" ? <Notice tone="info">Linked to the current {source.source_type === "portfolio_risk" ? "risk" : "Outlook"} observation. The server verifies its source when you save.</Notice> : null}
    {project ? <ActionForm key={project} project={project} source={source} onSaved={onSaved} onCancel={onClose} /> : <Notice tone="info">Choose the development this action belongs to.</Notice>}
  </Drawer>;
}

const transitions: Record<ActionStatus, ActionStatus[]> = { open: ["in_progress", "completed", "cancelled"], in_progress: ["open", "completed", "cancelled"], completed: ["open"], cancelled: ["open"] };
const labels: Record<ActionStatus, string> = { open: "Reopen", in_progress: "Start", completed: "Complete", cancelled: "Cancel action" };

export function ActionRecord({ id, canWrite, onClose, onChanged }: { id: string; canWrite: boolean; onClose: () => void; onChanged: () => void }) {
  const [revision, setRevision] = useState(0);
  const [tab, setTab] = useState("action");
  const [editing, setEditing] = useState(false);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const answer = useAnswer(true, () => management.detail(id), [id, revision]);
  const history = useAnswer(tab === "history", () => management.history(id, historyOffset), [id, revision, historyOffset]);
  const source = useAnswer(tab === "source", () => management.source(id), [id, revision]);
  function refresh() { setEditing(false); setRevision((value) => value + 1); onChanged(); }
  async function move(status: ActionStatus) {
    if (answer.status !== "ready") return;
    setBusy(true); setError(null);
    try { await management.transition(id, answer.data.version, status, reason || null); setReason(""); refresh(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not change status."); }
    finally { setBusy(false); }
  }
  const action = answer.status === "ready" ? answer.data : null;
  return <Drawer title={action?.title ?? "Management action"} subtitle={action ? `${action.project_code} · ${action.project_name}` : undefined}
    status={action ? <Badge>{action.status.replaceAll("_", " ")}</Badge> : undefined}
    facts={action ? [{ label: "Owner", value: action.owner.display_name }, { label: "Due", value: businessDate(action.due_date), note: action.due_state.replaceAll("_", " "), tone: action.due_state === "overdue" ? "danger" : undefined }] : undefined}
    tabs={[{ key: "action", label: "Action" }, { key: "source", label: "Source" }, { key: "history", label: "History" }]} activeTab={tab} onSelectTab={setTab} onClose={onClose}>
    {answer.status === "failed" ? <Notice tone="error">{answer.message}</Notice> : !action ? <Loading label="Reading action…" /> : tab === "action" ? <div className="stack">
      {editing && canWrite ? <ActionForm key={action.version} project={action.project_id} initial={action} source={action} onSaved={refresh} onCancel={refresh} /> : <>
        <p className="cell-prose">{action.description || "No description recorded."}</p>
        <KeyValueGrid><KeyValue label="Created by" value={action.created_by.display_name} /><KeyValue label="Created" value={action.created_at} /><KeyValue label="Updated" value={action.updated_at} /></KeyValueGrid>
        <Notice tone="info">Completing this action records management work. The source condition and its financial or delivery state remain independently governed.</Notice>
        {canWrite ? <><Field label="Transition reason" optional hint="Required to cancel or reopen a completed/cancelled action."><textarea maxLength={2000} value={reason} onChange={(event) => setReason(event.target.value)} /></Field><ButtonRow>
          {transitions[action.status].map((status) => <Button key={status} disabled={busy} onClick={() => void move(status)}>{status === "open" && action.status === "in_progress" ? "Return to open" : labels[status]}</Button>)}
          {action.status === "open" || action.status === "in_progress" ? <Button disabled={busy} onClick={() => setEditing(true)}>Edit owner, due date or details</Button> : null}
        </ButtonRow></> : null}
      </>}
      {error ? <Notice tone="error">{error} <Button small onClick={refresh}>Reload action</Button></Notice> : null}
    </div> : tab === "source" ? <div className="stack"><KeyValueGrid><KeyValue label="Origin" value={action.source_type.replaceAll("_", " ")} /><KeyValue label="Observed" value={action.source_observation_date ? businessDate(action.source_observation_date) : "Manual"} /></KeyValueGrid>
      {source.status === "ready" ? <Notice tone="info">{source.data.title} {source.data.drilldown ? <Link href={source.data.drilldown}>Inspect current source</Link> : null}</Notice> : source.status === "failed" ? <Notice tone="error">{source.message}</Notice> : <Loading label="Checking current source…" />}
    </div> : history.status === "ready" ? <div className="stack"><ol className="stack">{history.data.items.map((event) => <li key={event.id}><strong>{event.event_type.replaceAll("_", " ")} · {event.actor.display_name}</strong><p className="muted"><time dateTime={event.occurred_at}>{event.occurred_at}</time></p>
      <ul>{Object.entries(event.changes).map(([field, change]) => <li key={field}>{field.replaceAll("_", " ")}: {change.old ?? "Not set"} → {change.new ?? "Cleared"}</li>)}</ul>{event.reason ? <p>Reason: {event.reason}</p> : null}</li>)}</ol>
      <ButtonRow><Button disabled={!historyOffset} onClick={() => setHistoryOffset(historyOffset - 20)}>Earlier history</Button><Button disabled={historyOffset + 20 >= history.data.total} onClick={() => setHistoryOffset(historyOffset + 20)}>Later history</Button></ButtonRow>
    </div> : history.status === "failed" ? <Notice tone="error">{history.message}</Notice> : <Loading label="Reading history…" />}
  </Drawer>;
}
