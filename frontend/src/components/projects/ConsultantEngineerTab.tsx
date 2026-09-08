"use client";

import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { ApiError, consultantEngineering as api } from "@/lib/api";
import type { ConsultantWorkspace, ConsultantEngagement, ConsultantDiscipline, ConsultantStage, ConsultantDeliverable } from "@/lib/api";
import { businessDate } from "@/lib/format";
import { CONSULTANT_EDITORS, hasAnyRole } from "@/lib/roles";
import type { Roles } from "@/lib/roles";
import { Badge, Button, ButtonRow, Card, EmptyState, Field, FieldRow, FormDialog, Loading, Notice, PageHeader, TableScroll } from "@/components/ui";

type Kind = "engagement" | "discipline" | "stage" | "deliverable";
type RecordRow = ConsultantEngagement | ConsultantDiscipline | ConsultantStage | ConsultantDeliverable;
type Editor = { kind: Kind; row?: RecordRow };
const labels = (value: string) => value.replaceAll("_", " ");
const fieldNames: Record<Kind, string[]> = {
  engagement: ["consultant_name", "agreement_reference", "agreement_date", "planned_start_date", "planned_completion_date", "scope_summary", "notes"],
  discipline: ["name", "lead_name", "status", "notes"],
  stage: ["name", "planned_date", "forecast_date", "actual_completion_date", "status", "notes"],
  deliverable: ["name", "stage_id", "discipline_id", "category", "revision_reference", "document_reference", "due_date", "submitted_date", "accepted_date", "status", "notes"],
};
const statuses: Record<Kind, string[]> = {
  engagement: [],
  discipline: ["not_started", "active", "completed", "on_hold"],
  stage: ["not_started", "in_progress", "completed", "on_hold", "cancelled"],
  deliverable: ["not_started", "in_progress", "submitted", "accepted", "superseded", "cancelled"],
};
function values(kind: Kind, row?: RecordRow): Record<string, unknown> {
  const source = row as unknown as Record<string, unknown> | undefined;
  return Object.fromEntries(fieldNames[kind].map((key) => [key, source?.[key] ?? (key === "status" ? "not_started" : null)]));
}

export function ConsultantEngineerTab({ projectId, roles }: { projectId: string; roles: Roles }) {
  const [data, setData] = useState<ConsultantWorkspace | null>(null);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const canEdit = hasAnyRole(roles, CONSULTANT_EDITORS);
  const load = useCallback(async () => { setData(await api.workspace(projectId)); }, [projectId]);
  useEffect(() => { void (async () => { try { await load(); } catch (e) { setError(e instanceof ApiError ? e.message : "Could not load Consultant Engineer."); } })(); }, [load]);
  const current = data?.active_engagement ?? data?.engagements.find((x) => x.status === "draft");
  const selected = data?.engagements.find((x) => x.id === selectedId) ?? current;
  const editable = canEdit && !!selected && ["draft", "active"].includes(selected.status);
  const disciplines = data?.disciplines.filter((x) => x.engagement_id === selected?.id) ?? [];
  const stages = data?.stages.filter((x) => x.engagement_id === selected?.id) ?? [];
  const deliverables = data?.deliverables.filter((x) => x.engagement_id === selected?.id) ?? [];
  const run = async (action: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    try { await action(); await load(); setEditor(null); }
    catch (e) { setError(e instanceof ApiError ? e.message : "That action could not be completed."); }
    finally { setBusy(false); }
  };
  const move = (row: ConsultantStage, offset: number) => run(() => api.updateStage(projectId, row.id, {
    ...values("stage", row), sequence: row.sequence + offset, expected_updated_at: row.updated_at, expected_order: stages.map((x) => x.id),
  }));
  const save = (body: Record<string, unknown>) => run(async () => {
    if (!editor) return;
    const { kind, row } = editor;
    if (kind === "engagement") {
      if (row) await api.updateEngagement(projectId, row.id, { ...body, expected_updated_at: row.updated_at });
      else { const created = await api.createEngagement(projectId, body); setSelectedId(created.id); }
    } else if (selected) {
      if (kind === "discipline") {
        if (row) await api.updateDiscipline(projectId, row.id, body);
        else await api.createDiscipline(projectId, selected.id, body);
      } else if (kind === "stage") {
        if (row) await api.updateStage(projectId, row.id, { ...body, sequence: (row as ConsultantStage).sequence, expected_updated_at: row.updated_at, expected_order: stages.map((x) => x.id) });
        else await api.createStage(projectId, selected.id, body);
      } else {
        if (row) await api.updateDeliverable(projectId, row.id, { ...body, expected_updated_at: row.updated_at });
        else await api.createDeliverable(projectId, selected.id, body);
      }
    }
  });
  return <div className="stack">
    <PageHeader title="Consultant Engineer" subtitle="Consultant appointment, design programme and delivery." actions={canEdit ? <Button variant="primary" disabled={busy} onClick={() => setEditor({ kind: "engagement" })}>Add consultant agreement</Button> : undefined} />
    {error && !editor ? <Notice tone="error">{error}</Notice> : null}
    {data ? <Card title="Design position across agreements"><p>Disciplines complete: {data.completed_disciplines} / {data.total_disciplines}. Design stages complete: {data.completed_stages} / {data.total_stages}. Outstanding deliverables: {data.outstanding_deliverables}. Accepted deliverables: {data.accepted_deliverables}.</p></Card> : null}
    <Card title={current?.status === "draft" ? "Draft Agreement" : "Active Agreement"} actions={current ? <Button onClick={() => setSelectedId(current.id)}>View agreement</Button> : undefined}>
      {!data ? <Loading label="Loading consultant agreement" /> : current ? <><p><strong>{current.consultant_name}</strong> · {current.agreement_reference} · <Badge>{current.status}</Badge></p><p>Agreement {businessDate(current.agreement_date)} · Planned completion {businessDate(current.planned_completion_date)}</p>
        {canEdit && current.status === "draft" ? <Button disabled={busy} onClick={() => void run(() => api.transitionEngagement(projectId, current.id, "activate"))}>Activate Agreement</Button> : null}
      </> : <EmptyState title="No active or draft agreement" hint="Create an agreement to appoint a main consultant." />}
    </Card>
    {selected ? <>
      <Card title={`${selected.consultant_name} — ${labels(selected.status)} agreement`}>
        <p>{selected.agreement_reference} · {businessDate(selected.agreement_date)}</p>
        <p>Programme: {businessDate(selected.planned_start_date)} – {businessDate(selected.planned_completion_date)}</p>
        <p>{selected.scope_summary}</p><p>{selected.notes}</p>
        <ButtonRow>
          {canEdit && selected.status === "draft" ? <><Button disabled={busy} onClick={() => setEditor({ kind: "engagement", row: selected })}>Edit agreement</Button>{!data?.active_engagement ? <Button disabled={busy} onClick={() => void run(() => api.transitionEngagement(projectId, selected.id, "activate"))}>Activate</Button> : null}</> : null}
          {canEdit && selected.status === "active" ? <><Button disabled={busy} onClick={() => void run(() => api.transitionEngagement(projectId, selected.id, "complete"))}>Complete agreement</Button><Button disabled={busy} onClick={() => void run(() => api.transitionEngagement(projectId, selected.id, "terminate"))}>Terminate agreement</Button></> : null}
        </ButtonRow>
      </Card>
      <Register title="Disciplines" action={editable ? <Button onClick={() => setEditor({ kind: "discipline" })}>Add discipline</Button> : undefined} headers={["Discipline", "Lead", "Status", "Notes", "Actions"]} rows={disciplines.map((x) => [x.name, x.lead_name ?? "—", labels(x.status), x.notes ?? "—", editable ? <Button key={x.id} small onClick={() => setEditor({ kind: "discipline", row: x })}>Edit discipline</Button> : "Read only"])} />
      <Register title="Design stages" action={editable ? <Button onClick={() => setEditor({ kind: "stage" })}>Add design stage</Button> : undefined} headers={["Stage", "Position", "Planned", "Forecast", "Actual", "Status", "Actions"]} rows={stages.map((x, i) => [x.name, x.sequence, businessDate(x.planned_date), businessDate(x.forecast_date), businessDate(x.actual_completion_date), labels(x.status), editable ? <ButtonRow key={x.id}><Button small disabled={busy} onClick={() => setEditor({ kind: "stage", row: x })}>Edit stage</Button><Button small aria-label={`Move ${x.name} up`} disabled={busy || i === 0} onClick={() => void move(x, -1)}>Move up</Button><Button small aria-label={`Move ${x.name} down`} disabled={busy || i === stages.length - 1} onClick={() => void move(x, 1)}>Move down</Button></ButtonRow> : "Read only"])} />
      <Register title="Deliverables" action={editable && stages.length ? <Button onClick={() => setEditor({ kind: "deliverable" })}>Add deliverable</Button> : undefined} headers={["Deliverable", "Stage / discipline", "Due", "Submitted", "Accepted", "Status", "Revision / document", "Actions"]} rows={deliverables.map((x) => [x.name, `${stages.find((s) => s.id === x.stage_id)?.name ?? "—"} / ${disciplines.find((d) => d.id === x.discipline_id)?.name ?? "Cross-disciplinary"}`, businessDate(x.due_date), businessDate(x.submitted_date), businessDate(x.accepted_date), labels(x.status), `${x.revision_reference ?? "—"} / ${x.document_reference ?? "—"}`, editable && !["accepted", "superseded", "cancelled"].includes(x.status) ? <Button key={x.id} small onClick={() => setEditor({ kind: "deliverable", row: x })}>Update deliverable</Button> : "Historical / read only"])} />
    </> : null}
    <Register title="Agreement register and history" headers={["Consultant", "Agreement reference", "Status", "Agreement date", "Planned completion", "Details"]} rows={(data?.engagements ?? []).map((x) => [x.consultant_name, x.agreement_reference, labels(x.status), businessDate(x.agreement_date), businessDate(x.planned_completion_date), <Button key={x.id} small onClick={() => setSelectedId(x.id)}>View {x.status === "draft" ? "draft" : x.status === "active" ? "active agreement" : "history"}</Button>])} />
    {editor ? <ConsultantDialog editor={editor} stages={stages} disciplines={disciplines} busy={busy} error={error} onCancel={() => { if (!busy) { setEditor(null); setError(null); } }} onSubmit={(body) => void save(body)} /> : null}
  </div>;
}

function Register({ title, action, headers, rows }: { title: string; action?: ReactNode; headers: string[]; rows: ReactNode[][] }) {
  return <Card title={title} actions={action} flush>{rows.length ? <TableScroll label={title} compact><thead><tr>{headers.map((h) => <th key={h} scope="col">{h}</th>)}</tr></thead><tbody>{rows.map((row, i) => <tr key={i}>{row.map((v, j) => j === 0 ? <th key={j} scope="row">{v}</th> : <td key={j}>{v}</td>)}</tr>)}</tbody></TableScroll> : <div className="card-body"><EmptyState title={`No ${title.toLowerCase()}`} /></div>}</Card>;
}

function ConsultantDialog({ editor, stages, disciplines, busy, error, onCancel, onSubmit }: { editor: Editor; stages: ConsultantStage[]; disciplines: ConsultantDiscipline[]; busy: boolean; error: string | null; onCancel: () => void; onSubmit: (body: Record<string, unknown>) => void }) {
  const { kind, row } = editor;
  const [body, setBody] = useState<Record<string, unknown>>(() => ({ ...values(kind, row), ...(kind === "deliverable" && !row ? { stage_id: stages[0]?.id ?? "" } : {}) }));
  const set = (key: string, value: string) => setBody((old) => ({ ...old, [key]: value || null }));
  const title = `${row ? "Edit" : "Add"} ${kind === "engagement" ? "consultant agreement" : kind === "stage" ? "design stage" : kind}`;
  return <FormDialog title={title} confirmLabel="Save" busy={busy} onCancel={onCancel} onSubmit={() => onSubmit(body)}>
    {error ? <Notice tone="error">{error}</Notice> : null}
    <FieldRow columns={2}>{fieldNames[kind].map((key) => {
      const value = String(body[key] ?? "");
      const options = key === "status" ? statuses[kind].map((x) => ({ id: x, name: labels(x) })) : key === "stage_id" ? stages : key === "discipline_id" ? [{ id: "", name: "Cross-disciplinary" }, ...disciplines] : null;
      return <Field key={key} label={key === "stage_id" ? "Design stage" : key === "discipline_id" ? "Discipline" : labels(key)}>{options ? <select className="input" aria-label={key === "stage_id" ? "Design stage" : key === "discipline_id" ? "Discipline" : labels(key)} value={value} onChange={(e) => set(key, e.target.value)}>{options.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select> : key === "notes" || key === "scope_summary" ? <textarea className="input" value={value} onChange={(e) => set(key, e.target.value)} /> : <input className="input" type={key.endsWith("_date") ? "date" : "text"} required={["name", "consultant_name", "agreement_reference"].includes(key)} value={value} onChange={(e) => set(key, e.target.value)} />}</Field>;
    })}</FieldRow>
    {kind === "discipline" ? <p>Examples: Architecture, MEP, Structural, QS, Supervision. Other discipline names are welcome.</p> : null}
    {kind === "deliverable" ? <p>Submitted work requires a submitted date; accepted work also requires an accepted date. References identify documents held elsewhere.</p> : null}
  </FormDialog>;
}
