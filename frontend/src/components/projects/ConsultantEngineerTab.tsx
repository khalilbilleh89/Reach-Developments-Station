"use client";

import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { ApiError, consultantEngineering as api } from "@/lib/api";
import type { ConsultantWorkspace, ConsultantEngagement, ConsultantDiscipline, ConsultantStage, ConsultantDeliverable } from "@/lib/api";
import { businessDate } from "@/lib/format";
import { CONSULTANT_EDITORS, hasAnyRole } from "@/lib/roles";
import type { Roles } from "@/lib/roles";
import { Badge, Button, ButtonRow, Card, ConfirmDialog, EmptyState, Field, FieldRow, DraftBoundary, RecordPage, FormActions, Tabs, TabPanel, FormSection, IdentityCell, InlineMeta, InlineMetaItem, KeyValue, KeyValueGrid, Loading, Notice, PageHeader, Position, PositionFigure, SubPanel, TableScroll } from "@/components/ui";

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
  const [section, setSection] = useState("agreement");
  const [reordering, setReordering] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [terminating, setTerminating] = useState<ConsultantEngagement | null>(null);
  const canEdit = hasAnyRole(roles, CONSULTANT_EDITORS);
  const [readError, setReadError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const load = useCallback(async () => {
    setRetrying(true);
    try { setData(await api.workspace(projectId)); setReadError(null); }
    catch (e) { setReadError(e instanceof ApiError ? e.message : "Could not load Consultant Engineer."); }
    finally { setRetrying(false); }
  }, [projectId]);
  useEffect(() => { void (async () => { await load(); })(); }, [load]);
  const current = data?.active_engagement ?? data?.engagements.find((x) => x.status === "draft");
  const selected = data?.engagements.find((x) => x.id === selectedId) ?? current;
  const editable = canEdit && !!selected && ["draft", "active"].includes(selected.status);
  const disciplines = data?.disciplines.filter((x) => x.engagement_id === selected?.id) ?? [];
  const stages = data?.stages.filter((x) => x.engagement_id === selected?.id) ?? [];
  const deliverables = data?.deliverables.filter((x) => x.engagement_id === selected?.id) ?? [];
  const run = async (action: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    try { await action(); setTerminating(null); await load(); setEditor(null); }
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
  return <div className="stack consultant-workspace">
    <PageHeader icon="building" title="Consultant Engineer" subtitle="Consultant appointment, design programme and delivery." actions={canEdit ? <Button variant="primary" disabled={busy} onClick={() => setEditor({ kind: "engagement" })}>Add consultant agreement</Button> : undefined} />
    {error && !editor ? <Notice tone="error">{error}</Notice> : null}
    {readError ? <><Notice tone="error">{readError}</Notice><Button disabled={retrying} onClick={() => void load()}>{retrying ? "Retrying…" : "Retry Consultant Engineer"}</Button></> : null}
    {data ? <Card tone="command" title="Design position across agreements">
      <Position compact>
        <PositionFigure lead={data.deliverables.length > 0} label="Outstanding deliverables" value={data.deliverables.length ? data.outstanding_deliverables : "Not registered"} note={data.deliverables.length ? undefined : "Add deliverables to establish the delivery position"} />
        <PositionFigure label="Accepted deliverables" value={data.accepted_deliverables} />
        <PositionFigure label="Disciplines complete" value={data.completed_disciplines} note={`Of ${data.total_disciplines} disciplines`} />
        <PositionFigure label="Design stages complete" value={data.completed_stages} note={`Of ${data.total_stages} stages`} />
      </Position>
    </Card> : !readError ? <Loading label="Loading consultant agreement" shape="page" /> : null}
    {data && !current ? <EmptyState title="No active or draft agreement" hint="A consultant agreement establishes the appointment and its design programme. Previous agreements remain in the history below." /> : null}
    {data ? <Tabs label="Consultant views" tabs={[{key:"agreement",icon:"documents",label:"Agreement"},{key:"programme",icon:"calendar",label:"Programme"},{key:"disciplines",icon:"layers",label:"Disciplines"},{key:"deliverables",icon:"blueprint",label:"Deliverables"},{key:"history",icon:"history",label:"History"}]} active={section} onSelect={setSection} /> : null}
    <TabPanel group="Consultant views" tab={section}>
    {selected && section !== "history" ? <>
      <Card title={selected.consultant_name} description="Consultant agreement and design programme" actions={current && selected.id !== current.id ? <Button small onClick={() => setSelectedId(current.id)}>Return to current agreement</Button> : undefined}>
        <InlineMeta>
          <InlineMetaItem label="Agreement"><span className="mono">{selected.agreement_reference}</span></InlineMetaItem>
          <InlineMetaItem label="Status"><Badge>{labels(selected.status)}</Badge></InlineMetaItem>
        </InlineMeta>
        {section === "agreement" ? <><KeyValueGrid columns={3}>
          <KeyValue label="Agreement date" value={businessDate(selected.agreement_date)} />
          <KeyValue label="Planned start" value={businessDate(selected.planned_start_date)} />
          <KeyValue label="Planned completion" value={businessDate(selected.planned_completion_date)} />
        </KeyValueGrid>
        {selected.scope_summary ? <p>{selected.scope_summary}</p> : null}
        {selected.notes ? <p className="footnote">{selected.notes}</p> : null}
        {!editable ? <p className="footnote">Read-only agreement. Its programme and delivery records remain available in their tabs.</p> : null}
        <ButtonRow>
          {editable ? <Button disabled={busy} onClick={() => { setError(null); setEditor({ kind: "engagement", row: selected }); }}>Edit agreement</Button> : null}
          {canEdit && selected.status === "draft" ? <>{!data?.active_engagement ? <Button disabled={busy} onClick={() => void run(() => api.transitionEngagement(projectId, selected.id, "activate"))}>Activate</Button> : null}</> : null}
          {canEdit && selected.status === "active" ? <><Button disabled={busy} onClick={() => void run(() => api.transitionEngagement(projectId, selected.id, "complete"))}>Complete agreement</Button><Button variant="danger" disabled={busy} onClick={() => setTerminating(selected)}>Terminate agreement</Button></> : null}
        </ButtonRow></> : null}
      {section === "disciplines" ? <Register nested title="Disciplines" action={editable ? <Button onClick={() => setEditor({ kind: "discipline" })}>Add discipline</Button> : undefined} headers={["Discipline", "Lead", "Status", "Notes", "Actions"]} rows={disciplines.map((x) => [x.name, x.lead_name ?? "—", labels(x.status), x.notes ?? "—", editable ? <Button key={x.id} small variant="quiet" onClick={() => setEditor({ kind: "discipline", row: x })}>Edit discipline</Button> : "Read only"])} /> : null}
      {section === "programme" ? <SubPanel title="Design programme" actions={editable ? <ButtonRow><Button onClick={() => setEditor({kind:"stage"})}>Add design stage</Button><Button disabled={busy || stages.length < 2} aria-pressed={reordering} onClick={() => setReordering(!reordering)}>{reordering ? "Finish reordering" : "Reorder stages"}</Button></ButtonRow> : undefined}>
        <p className="footnote">Stages follow their recorded sequence. An undated stage is not a forecast milestone.</p>
        {stages.length ? <ol className="consultant-programme">{stages.map((stage,index) => <li key={stage.id} data-status={stage.status}>
          <span className="consultant-stage-number">{stage.sequence}</span>
          <div className="consultant-stage-body"><div className="consultant-stage-heading"><h3>{stage.name}</h3><Badge>{labels(stage.status)}</Badge></div>
            <KeyValueGrid columns={3}><KeyValue label="Planned" value={stage.planned_date ? businessDate(stage.planned_date) : "Not scheduled"}/><KeyValue label="Forecast" value={stage.forecast_date ? businessDate(stage.forecast_date) : "Not recorded"}/><KeyValue label="Completed" value={stage.actual_completion_date ? businessDate(stage.actual_completion_date) : "Not recorded"}/></KeyValueGrid>
            <div className="stage-deliverables"><h4>Stage deliverables</h4>{deliverables.some(item => item.stage_id === stage.id) ? <ul>{deliverables.filter(item => item.stage_id === stage.id).map(item => <li key={item.id}><div><strong>{item.name}</strong><span>{disciplines.find(discipline => discipline.id === item.discipline_id)?.name ?? "Cross-disciplinary"}{item.revision_reference ? " · " + item.revision_reference : ""}</span></div><div><Badge>{labels(item.status)}</Badge><span>{item.due_date ? "Due " + businessDate(item.due_date) : "No due date"}</span></div>{editable && !["accepted","superseded","cancelled"].includes(item.status) ? <Button small variant="quiet" disabled={busy} onClick={() => setEditor({kind:"deliverable",row:item})}>Update deliverable</Button> : null}</li>)}</ul> : <p className="footnote">No deliverables assigned to this stage.</p>}</div>
            {editable ? <ButtonRow><Button small disabled={busy} onClick={() => setEditor({kind:"stage",row:stage})}>Edit stage</Button>{reordering ? <><Button small aria-label={`Move ${stage.name} up`} disabled={busy || index===0} onClick={() => void move(stage,-1)}>Move up</Button><Button small aria-label={`Move ${stage.name} down`} disabled={busy || index===stages.length-1} onClick={() => void move(stage,1)}>Move down</Button></> : null}</ButtonRow> : null}
          </div>
        </li>)}</ol> : <EmptyState compact title="No design stages" hint="Record the agreed stages before assigning deliverables."/>}
      </SubPanel> : null}
      {section === "deliverables" ? <Register nested title="Deliverables" action={editable && stages.length ? <Button onClick={() => setEditor({ kind: "deliverable" })}>Add deliverable</Button> : undefined} headers={["Deliverable", "Stage / discipline", "Due", "Submitted", "Accepted", "Status", "Revision / document", "Actions"]} rows={deliverables.map((x) => [x.name, `${stages.find((s) => s.id === x.stage_id)?.name ?? "—"} / ${disciplines.find((d) => d.id === x.discipline_id)?.name ?? "Cross-disciplinary"}`, businessDate(x.due_date), businessDate(x.submitted_date), businessDate(x.accepted_date), labels(x.status), `${x.revision_reference ?? "—"} / ${x.document_reference ?? "—"}`, editable && !["accepted", "superseded", "cancelled"].includes(x.status) ? <Button key={x.id} small variant="quiet" onClick={() => setEditor({ kind: "deliverable", row: x })}>Update deliverable</Button> : "Historical / read only"])} /> : null}
      </Card>
    </> : null}
    {data && section === "history" ? <Register title="Agreement register and history" headers={["Consultant", "Agreement reference", "Status", "Agreement date", "Planned completion", "Details"]} rows={(data?.engagements ?? []).map((x) => [<Button key={x.id} variant="link" onClick={() => { setSelectedId(x.id); setSection("agreement"); }}><IdentityCell name={x.consultant_name} /></Button>, x.agreement_reference, labels(x.status), businessDate(x.agreement_date), businessDate(x.planned_completion_date), <Button key={x.id} small variant="quiet" onClick={() => { setSelectedId(x.id); setSection("agreement"); }}>View {x.status === "draft" ? "draft" : x.status === "active" ? "active agreement" : "history"}</Button>])} /> : null}
    </TabPanel>
    {terminating ? <ConfirmDialog title="Terminate consultant agreement" body={`Terminate ${terminating.agreement_reference} — ${terminating.consultant_name}? Recorded stages and deliverables remain in history; this agreement will no longer be editable as active work.`} confirmLabel="Terminate agreement" busy={busy} onCancel={() => { if (!busy) setTerminating(null); }} onConfirm={() => void run(() => api.transitionEngagement(projectId, terminating.id, "terminate"))} /> : null}
    {editor ? <ConsultantDialog editor={editor} stages={stages} disciplines={disciplines} busy={busy} error={error} onCancel={() => { if (!busy) { setEditor(null); setError(null); } }} onSubmit={(body) => void save(body)} /> : null}
  </div>;
}

function Register({ title, action, headers, rows, nested }: { title: string; action?: ReactNode; headers: string[]; rows: ReactNode[][]; nested?: boolean }) {
  const [schedule, setSchedule] = useState(false);
  const controls = <ButtonRow>{action}<Button small aria-pressed={schedule} onClick={() => setSchedule(!schedule)}>{schedule ? "Show cards" : "Show schedule"}</Button></ButtonRow>;
  const content = rows.length ? schedule ? <TableScroll label={title} fixedFirst compact>
    <thead><tr>{headers.map((h) => <th key={h} scope="col">{h}</th>)}</tr></thead>
    <tbody>{rows.map((row, i) => <tr key={i}>{row.map((v, j) => j === 0 ? <th key={j} scope="row">{v}</th> : <td key={j}>{v}</td>)}</tr>)}</tbody>
  </TableScroll> : <div className="consultant-record-grid">{rows.map((row, i) => <article className="consultant-record-card" key={i}><header><span className="eyebrow">{headers[0]}</span><h3>{row[0]}</h3></header><dl>{row.slice(1).map((value, j) => <div key={headers[j + 1]}><dt>{headers[j + 1]}</dt><dd>{value}</dd></div>)}</dl></article>)}</div> : <EmptyState compact title={"No " + title.toLowerCase()} hint="Records appear here as the consultant programme is maintained." />;
  return nested ? <SubPanel title={title} actions={controls}>{content}</SubPanel> : <Card title={title} actions={controls}>{content}</Card>;
}

function ConsultantDialog({ editor, stages, disciplines, busy, error, onCancel, onSubmit }: { editor: Editor; stages: ConsultantStage[]; disciplines: ConsultantDiscipline[]; busy: boolean; error: string | null; onCancel: () => void; onSubmit: (body: Record<string, unknown>) => void }) {
  const { kind, row } = editor;
  const [body, setBody] = useState<Record<string, unknown>>(() => ({ ...values(kind, row), ...(kind === "deliverable" && !row ? { stage_id: stages[0]?.id ?? "" } : {}) }));
  const set = (key: string, value: string) => setBody((old) => ({ ...old, [key]: value || null }));
  const title = `${row ? "Edit" : "Add"} ${kind === "engagement" ? "consultant agreement" : kind === "stage" ? "design stage" : kind}`;
  const baseline = { ...values(kind, row), ...(kind === "deliverable" && !row ? { stage_id: stages[0]?.id ?? "" } : {}) };
  return <RecordPage title={title} eyebrow="Consultant Engineer" onClose={onCancel}><DraftBoundary dirty={JSON.stringify(body) !== JSON.stringify(baseline)} busy={busy}><form onSubmit={event => { event.preventDefault(); onSubmit(body); }}>
    {error ? <Notice tone="error">{error}</Notice> : null}
    {[
      { title: "Identity and assignment", keys: ["consultant_name", "agreement_reference", "name", "lead_name", "stage_id", "discipline_id", "category", "revision_reference", "document_reference"] },
      { title: "Programme and status", keys: ["agreement_date", "planned_start_date", "planned_completion_date", "planned_date", "forecast_date", "actual_completion_date", "due_date", "submitted_date", "accepted_date", "status"] },
      { title: "Scope and notes", keys: ["scope_summary", "notes"] },
    ].map((group) => {
      const keys = fieldNames[kind].filter((key) => group.keys.includes(key));
      return keys.length ? <FormSection key={group.title} title={group.title}><FieldRow columns={group.title === "Scope and notes" ? 1 : 2}>{keys.map((key) => {
      const value = String(body[key] ?? "");
      const options = key === "status" ? statuses[kind].map((x) => ({ id: x, name: labels(x) })) : key === "stage_id" ? stages : key === "discipline_id" ? [{ id: "", name: "Cross-disciplinary" }, ...disciplines] : null;
      return <Field key={key} optional={!["name", "consultant_name", "agreement_reference", "stage_id", "status"].includes(key)} label={key === "stage_id" ? "Design stage" : key === "discipline_id" ? "Discipline" : labels(key)}>{options ? <select className="input" aria-label={key === "stage_id" ? "Design stage" : key === "discipline_id" ? "Discipline" : labels(key)} value={value} onChange={(e) => set(key, e.target.value)}>{options.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select> : key === "notes" || key === "scope_summary" ? <textarea className="input" value={value} onChange={(e) => set(key, e.target.value)} /> : <input className="input" type={key.endsWith("_date") ? "date" : "text"} required={["name", "consultant_name", "agreement_reference"].includes(key)} value={value} onChange={(e) => set(key, e.target.value)} />}</Field>;
    })}</FieldRow></FormSection> : null;
    })}
    {kind === "discipline" ? <p>Examples: Architecture, MEP, Structural, QS, Supervision. Other discipline names are welcome.</p> : null}
    {kind === "deliverable" ? <p>Submitted work requires a submitted date; accepted work also requires an accepted date. References identify documents held elsewhere.</p> : null}
    <FormActions><Button variant="primary" type="submit" disabled={busy}>{busy ? "Saving…" : "Save"}</Button><Button data-leaves-editor disabled={busy} onClick={onCancel}>Cancel</Button></FormActions>
  </form></DraftBoundary></RecordPage>;
}
