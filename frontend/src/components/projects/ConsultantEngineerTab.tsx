"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, consultantEngineering } from "@/lib/api";
import type { ConsultantWorkspace } from "@/lib/api";
import { businessDate } from "@/lib/format";
import { CONSULTANT_EDITORS, hasAnyRole } from "@/lib/roles";
import type { Roles } from "@/lib/roles";
import { sectionDescription } from "@/components/shell/navigation";
import { Badge, Button, Card, EmptyState, Field, FieldRow, FormDialog, Loading, Metric, MetricGroup, Notice, PageHeader, TableScroll } from "@/components/ui";

export function ConsultantEngineerTab({ projectId, roles }: { projectId: string; roles: Roles }) {
  const [data, setData] = useState<ConsultantWorkspace | null>(null);
  const [dialog, setDialog] = useState<"engagement" | "discipline" | "stage" | "deliverable" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canEdit = hasAnyRole(roles, CONSULTANT_EDITORS);
  const load = useCallback(async () => { try { setData(await consultantEngineering.workspace(projectId)); setError(null); } catch (e) { setError(e instanceof ApiError ? e.message : "Could not load Consultant Engineer."); } }, [projectId]);
  useEffect(() => { void (async () => { await load(); })(); }, [load]);
  const active = data?.active_engagement;
  const run = async (action: () => Promise<unknown>) => { try { await action(); setDialog(null); await load(); } catch (e) { setError(e instanceof ApiError ? e.message : "That action could not be completed."); } };
  return <div className="stack">
    <PageHeader title="Consultant Engineer" subtitle={sectionDescription("consultant")} actions={canEdit && !active ? <Button variant="primary" onClick={() => setDialog("engagement")}>Add consultant agreement</Button> : undefined} />
    {error ? <Notice tone="error">{error}</Notice> : null}
    {data ? <MetricGroup compact><Metric label="Disciplines complete" value={`${data.completed_disciplines} / ${data.total_disciplines}`} /><Metric label="Design stages complete" value={`${data.completed_stages} / ${data.total_stages}`} /><Metric label="Outstanding deliverables" value={String(data.outstanding_deliverables)} /><Metric label="Accepted deliverables" value={String(data.accepted_deliverables)} /></MetricGroup> : null}
    <Card title="Active agreement" actions={canEdit && active?.status === "draft" ? <Button onClick={() => void run(() => consultantEngineering.transitionEngagement(projectId, active.id, "activate"))}>Activate agreement</Button> : undefined}>
      {!data ? <Loading label="Loading consultant agreement" /> : active ? <dl className="key-value"><div><dt>Main consultant</dt><dd>{active.consultant_name}</dd></div><div><dt>Agreement</dt><dd>{active.agreement_reference}</dd></div><div><dt>Agreement date</dt><dd>{businessDate(active.agreement_date)}</dd></div><div><dt>Status</dt><dd><Badge>{active.status}</Badge></dd></div></dl> : <EmptyState title="No active consultant agreement" hint="Create an agreement and activate it when appointed." />}
    </Card>
    {active && data ? <>
      <Register title="Disciplines" action={canEdit ? <Button onClick={() => setDialog("discipline")}>Add discipline</Button> : undefined} headers={["Discipline", "Lead", "Status"]} rows={data.disciplines.map((x) => [x.name, x.lead_name ?? "—", x.status])} />
      <Register title="Design stages" action={canEdit ? <Button onClick={() => setDialog("stage")}>Add design stage</Button> : undefined} headers={["Stage", "Position", "Planned", "Forecast", "Actual", "Status"]} rows={data.stages.map((x) => [x.name, String(x.sequence), businessDate(x.planned_date), businessDate(x.forecast_date), businessDate(x.actual_completion_date), x.status])} />
      <Register title="Deliverables" action={canEdit && data.stages.length ? <Button onClick={() => setDialog("deliverable")}>Add deliverable</Button> : undefined} headers={["Deliverable", "Due", "Submitted", "Accepted", "Status", "Reference"]} rows={data.deliverables.map((x) => [x.name, businessDate(x.due_date), businessDate(x.submitted_date), businessDate(x.accepted_date), x.status, x.document_reference ?? "—"])} />
    </> : null}
    {dialog ? <ConsultantDialog kind={dialog} data={data} onCancel={() => setDialog(null)} onSubmit={(body) => { if (dialog === "engagement") return run(() => consultantEngineering.createEngagement(projectId, body)); if (!active) return Promise.resolve(); if (dialog === "discipline") return run(() => consultantEngineering.createDiscipline(projectId, active.id, body)); if (dialog === "stage") return run(() => consultantEngineering.createStage(projectId, active.id, body)); return run(() => consultantEngineering.createDeliverable(projectId, active.id, body)); }} /> : null}
  </div>;
}

function Register({ title, action, headers, rows }: { title: string; action?: React.ReactNode; headers: string[]; rows: string[][] }) { return <Card title={title} actions={action} flush>{rows.length ? <TableScroll label={title} compact><thead><tr>{headers.map((h) => <th key={h}>{h}</th>)}</tr></thead><tbody>{rows.map((row, i) => <tr key={i}>{row.map((v, j) => j === 0 ? <th key={j} scope="row">{v}</th> : <td key={j}>{v}</td>)}</tr>)}</tbody></TableScroll> : <div className="card-body"><EmptyState title={`No ${title.toLowerCase()}`} /></div>}</Card>; }

function ConsultantDialog({ kind, data, onCancel, onSubmit }: { kind: string; data: ConsultantWorkspace | null; onCancel: () => void; onSubmit: (body: Record<string, unknown>) => void }) {
  const [name, setName] = useState(""); const [reference, setReference] = useState(""); const [date, setDate] = useState(""); const [stage, setStage] = useState(data?.stages[0]?.id ?? "");
  const title = kind === "engagement" ? "Add consultant agreement" : kind === "discipline" ? "Add discipline" : kind === "stage" ? "Add design stage" : "Add deliverable";
  return <FormDialog title={title} confirmLabel="Save" disabled={!name || (kind === "engagement" && !reference) || (kind === "deliverable" && !stage)} onCancel={onCancel} onSubmit={() => onSubmit(kind === "engagement" ? { consultant_name: name, agreement_reference: reference, agreement_date: date || null } : kind === "discipline" ? { name } : kind === "stage" ? { name, planned_date: date || null } : { name, stage_id: stage, due_date: date || null })}>
    <Field label={kind === "engagement" ? "Main consultant" : "Name"}><input className="input" value={name} onChange={(e) => setName(e.target.value)} /></Field>
    {kind === "engagement" ? <Field label="Agreement reference"><input className="input" value={reference} onChange={(e) => setReference(e.target.value)} /></Field> : null}
    {kind === "deliverable" ? <Field label="Design stage"><select className="input" value={stage} onChange={(e) => setStage(e.target.value)}>{data?.stages.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field> : null}
    {kind !== "discipline" ? <FieldRow><Field label={kind === "engagement" ? "Agreement date" : kind === "stage" ? "Planned date" : "Due date"} optional><input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field></FieldRow> : null}
  </FormDialog>;
}
