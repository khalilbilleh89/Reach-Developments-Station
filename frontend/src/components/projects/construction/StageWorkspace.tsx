"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Badge, Button, Card, Field, FieldRow, FormActions, Loading, Notice } from "@/components/ui";
import { stages } from "@/lib/api/stages";
import type { Stage, UnitProgress, UnitStage } from "@/lib/api/stages";
import { businessDate, todayISO } from "@/lib/format";
import { CONSTRUCTION_STAGE_WRITERS, CONSTRUCTION_STAGE_CONFIGURERS, hasAnyRole } from "@/lib/roles";
import type { Roles } from "@/lib/roles";

const message = (error: unknown) => error instanceof Error ? error.message : "Could not save construction progress.";

export function ProjectStages({ projectId, roles }: { projectId: string; roles: Roles }) {
  const [rows, setRows] = useState<Stage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [planned, setPlanned] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try { setRows(await stages.list(projectId)); setError(null); }
    catch (caught) { setError(message(caught)); }
  }, [projectId]);
  useEffect(() => { void (async () => { await load(); })(); }, [load]);
  return <Card title="Planned construction stages" description="Configure the stages that appear in every unit, in delivery order.">
    {error ? <Notice tone="error">{error}</Notice> : null}
    {!rows && !error ? <Loading label="Loading stages" /> : null}
    {rows?.length === 0 ? <p>No construction stages configured yet.</p> : null}
    <Button type="button" disabled={busy} onClick={() => void load()}>Reload checklist</Button>
    <ol>{rows?.map((stage) => <li key={stage.id}>
      <StageConfiguration stage={stage} rows={rows} projectId={projectId}
        canConfigure={hasAnyRole(roles, CONSTRUCTION_STAGE_CONFIGURERS)} reload={load} />
    </li>)}</ol>
    {hasAnyRole(roles, CONSTRUCTION_STAGE_CONFIGURERS) ? <form onSubmit={async (event) => {
      event.preventDefault(); if (busy) return; setBusy(true);
      try { await stages.create(projectId, name, planned || null); setName(""); setPlanned(""); await load(); }
      catch (caught) { setError(message(caught)); } finally { setBusy(false); }
    }}>
      <FieldRow columns={2}>
        <Field label="Stage name"><input className="input" required maxLength={200} value={name} onChange={(event) => setName(event.target.value)} /></Field>
        <Field label="Planned completion date" optional><input className="input" type="date" value={planned} onChange={(event) => setPlanned(event.target.value)} /></Field>
      </FieldRow>
      <FormActions><Button type="submit" disabled={busy}>Add construction stage</Button></FormActions>
      <p className="footnote">Configuration requires access to the whole project.</p>
    </form> : null}
  </Card>;
}

function StageConfiguration({ stage, rows, projectId, canConfigure, reload }: {
  stage: Stage; rows: Stage[]; projectId: string; canConfigure: boolean; reload: () => Promise<void>;
}) {
  const [editing, setEditing] = useState<Stage | null>(null);
  const [name, setName] = useState("");
  const [planned, setPlanned] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const editControl = useRef<HTMLSpanElement>(null);
  const nameInput = useRef<HTMLInputElement>(null);
  useEffect(() => { if (editing) nameInput.current?.focus(); }, [editing]);
  function close() {
    setEditing(null);
    requestAnimationFrame(() => editControl.current?.querySelector("button")?.focus());
  }
  async function move(position: number) {
    if (busy) return;
    setBusy(true); setError(null);
    try {
      await stages.update(projectId, stage, { sequence: position, expected_order: rows.map((row) => row.id) });
      await reload();
    } catch (caught) { setError(message(caught)); }
    finally { setBusy(false); }
  }
  return <section>
    <p>{stage.name} — {stage.planned_date ? businessDate(stage.planned_date) : "Date not planned"}</p>
    {error ? <Notice tone="error">{error}</Notice> : null}
    {canConfigure ? <>
      <FormActions>
        <span ref={editControl}><Button type="button" disabled={busy || !!editing} aria-label={`Edit ${stage.name}`} onClick={() => {
          setEditing({ ...stage }); setName(stage.name); setPlanned(stage.planned_date ?? ""); setError(null);
        }}>Edit</Button></span>
        <Button type="button" disabled={busy || !!editing || stage.sequence === 1} aria-label={`Move ${stage.name} up`}
          onClick={() => void move(stage.sequence - 1)}>Move up</Button>
        <Button type="button" disabled={busy || !!editing || stage.sequence === rows.length} aria-label={`Move ${stage.name} down`}
          onClick={() => void move(stage.sequence + 1)}>Move down</Button>
      </FormActions>
      {editing ? <form aria-label={`Edit ${editing.name}`} onSubmit={async (event) => {
        event.preventDefault(); if (busy) return; setBusy(true); setError(null);
        try {
          await stages.update(projectId, editing, { name, planned_date: planned || null });
          await reload(); setBusy(false); close();
        } catch (caught) { setError(message(caught)); }
        finally { setBusy(false); }
      }}>
        <FieldRow columns={2}>
          <Field label="Stage name"><input ref={nameInput} className="input" required maxLength={200} value={name} onChange={(event) => setName(event.target.value)} /></Field>
          <Field label="Planned completion date" optional><input className="input" type="date" value={planned} onChange={(event) => setPlanned(event.target.value)} /></Field>
        </FieldRow>
        <p className="footnote">Leave the date empty to clear it. Completion history is retained.</p>
        <FormActions><Button type="submit" disabled={busy}>Save stage</Button>
          <Button type="button" disabled={busy} onClick={close}>Cancel</Button></FormActions>
      </form> : null}
    </> : null}
  </section>;
}

export function UnitStages({ projectId, unitId, roles }: { projectId: string; unitId: string; roles: Roles }) {
  const [progress, setProgress] = useState<UnitProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try { setProgress(await stages.unit(projectId, unitId)); setError(null); }
    catch (caught) { setError(message(caught)); }
  }, [projectId, unitId]);
  useEffect(() => { void (async () => { await load(); })(); }, [load]);
  const canWrite = hasAnyRole(roles, CONSTRUCTION_STAGE_WRITERS);
  return <Card title="Construction progress">
    {error ? <Notice tone="error">{error}</Notice> : null}
    {!progress && !error ? <Loading label="Loading unit progress" /> : null}
    {progress ? <>
      <p>Delivery: {progress.delivery_status.replaceAll("_", " ")} · {progress.completed_count} of {progress.stage_count} stages complete</p>
      <p className="footnote">Physical stage completion records progress. Delivery readiness and payment milestone certification have their own approvals.</p>
      {progress.stage_count === 0 ? <p>No stages configured. A Project Manager can add them in the project overview.</p> : null}
      <div className="stack">{progress.stages.map((stage) => <StageRecord key={`${stage.id}:${stage.revision}`} stage={stage} canWrite={canWrite}
        save={async (day, reason) => { await stages.complete(projectId, unitId, stage, day, reason); await load(); }} />)}</div>
    </> : null}
  </Card>;
}

function StageRecord({ stage, canWrite, save }: { stage: UnitStage; canWrite: boolean;
  save: (day: string | null, reason: string) => Promise<void> }) {
  const [day, setDay] = useState(stage.completed_date ?? todayISO());
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(completed: string | null) {
    if (busy) return; setBusy(true);
    try { await save(completed, reason); } catch (caught) { setError(message(caught)); }
    finally { setBusy(false); }
  }
  return <section>
    <h3>{stage.sequence}. {stage.name} <Badge tone={stage.status === "complete" ? "success" : "neutral"}>{stage.status}</Badge></h3>
    <p>Planned: {stage.planned_date ? businessDate(stage.planned_date) : "Not set"} · Completed: {stage.completed_date ? businessDate(stage.completed_date) : "Not recorded"}</p>
    {error ? <Notice tone="error">{error}</Notice> : null}
    {canWrite ? <details><summary>{stage.completed_date ? "Correct completion" : "Record completion"}</summary>
      <form onSubmit={(event) => { event.preventDefault(); void submit(day); }}>
        <FieldRow columns={2}>
          <Field label="Actual completion date"><input className="input" type="date" required max={todayISO()} value={day} onChange={(event) => setDay(event.target.value)} /></Field>
          <Field label="Completion note or correction reason"><input className="input" required maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} /></Field>
        </FieldRow>
        <FormActions><Button type="submit" disabled={busy}>Save completion</Button>
          {stage.completed_date ? <Button type="button" disabled={busy || !reason.trim()} onClick={() => void submit(null)}>Reopen stage</Button> : null}
        </FormActions>
      </form>
    </details> : null}
    {stage.history.length ? <details><summary>Completion history</summary><ol>{stage.history.map((entry) => <li key={entry.sequence}>
      {entry.completed_date ? `Completed ${businessDate(entry.completed_date)}` : "Reopened"} — {entry.reason}
      <span className="footnote"> · Recorded {entry.recorded_at} · User {entry.actor_user_id}</span>
    </li>)}</ol></details> : null}
  </section>;
}
