"use client";

import { useEffect, useState } from "react";
import { ApiError, projects } from "@/lib/api";
import type { LandParcel, Permit, PermitType } from "@/lib/api";
import { todayISO } from "@/lib/format";
import { Button, Card, DraftBoundary, Field, FieldRow, FormActions, FormSection, Notice, PageHeader } from "@/components/ui";

const DETAILS = [
  ["authority_reference", "Authority reference", "text", "Application", 120],
  ["consultant", "Consultant", "text", "Application", 200],
  ["statutory_sla_days", "Statutory period (days)", "number", "Application", 0],
  ["planned_submission_date", "Planned submission", "date", "Submission dates", 0],
  ["forecast_submission_date", "Forecast submission", "date", "Submission dates", 0],
  ["actual_submission_date", "Actual submission", "date", "Submission dates", 0],
  ["accepted_for_review_date", "Accepted for review", "date", "Submission dates", 0],
  ["comments_received_date", "Comments received", "date", "Submission dates", 0],
  ["resubmission_date", "Resubmission", "date", "Submission dates", 0],
  ["planned_issue_date", "Planned issue", "date", "Issue dates", 0],
  ["forecast_issue_date", "Forecast issue", "date", "Issue dates", 0],
  ["issue_date", "Issued", "date", "Issue dates", 0],
  ["expiry_date", "Expiry", "date", "Issue dates", 0],
  ["renewal_date", "Renewal", "date", "Issue dates", 0],
  ["conditions", "Conditions", "textarea", "Management", 4000],
  ["next_action", "Next action", "text", "Management", 500],
  ["notes", "Notes", "textarea", "Management", 4000],
] as const;

export function PermitCreatePage({ projectId, types, parcels, permits, statuses, canSeeCost, currencyCode, onCancel, onCreated }: {
  projectId: string; types: PermitType[] | null; parcels: LandParcel[]; permits: Permit[];
  statuses: Record<string, string>; canSeeCost: boolean; currencyCode: string | null;
  onCancel: () => void; onCreated: (permit: Permit) => Promise<void>;
}) {
  const [baseline] = useState<Record<string, string | boolean>>(() => ({
    permit_code: "", permit_type_code: "", authority: "", initial_status: "not_started",
    status_effective_date: todayISO(), parcel_id: "", prerequisite_permit_id: "",
    owner_user_id: "", escalation_owner_user_id: "", fee_amount: "", is_blocking: false,
    is_critical_path: false, ...Object.fromEntries(DETAILS.map(([name]) => [name, ""])),
  }));
  const [values, setValues] = useState(baseline);
  const [newType, setNewType] = useState(false);
  const [typeCode, setTypeCode] = useState("");
  const [typeName, setTypeName] = useState("");
  const [assignees, setAssignees] = useState<{ id: string; display_name: string }[]>([]);
  const [peopleError, setPeopleError] = useState(false);
  const [retry, setRetry] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    void projects.permitAssignees(projectId).then(rows => { if (!cancelled) { setAssignees(rows); setPeopleError(false); } })
      .catch(() => { if (!cancelled) setPeopleError(true); });
    return () => { cancelled = true; };
  }, [projectId, retry]);
  const set = (name: string, value: string | boolean) => setValues(current => ({ ...current, [name]: value }));
  const dirty = newType || Boolean(typeCode || typeName) || Object.keys(values).some(key => values[key] !== baseline[key]);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError(null);
    try {
      const payload: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(values)) {
        if (key === "fee_amount" && !canSeeCost) continue;
        if (value !== "") payload[key] = typeof value === "string" ? value.trim() : value;
      }
      if (newType) {
        payload.permit_type_code = typeCode.trim();
        payload.new_permit_type = { code: typeCode.trim(), label: typeName.trim() };
      }
      const created = await projects.createPermit(projectId, payload);
      await onCreated(created);
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not add the permit. Your entries are still here."); }
    finally { setBusy(false); }
  };
  return <DraftBoundary dirty={dirty} busy={busy}>
    <article className="record-workspace">
      <Button data-leaves-editor onClick={onCancel} disabled={busy}>Back to permits</Button>
      <PageHeader icon="permits" title="Add permit" subtitle="Enter everything you know and save once. No preliminary registration is needed." />
      <Card><form onSubmit={submit}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <fieldset disabled={busy} className="draft-fields">
          <FormSection title="Permit">
            <FieldRow columns={3}>
              <Field label="Permit code"><input className="input" required maxLength={64} value={String(values.permit_code)} onChange={e => set("permit_code", e.target.value)} /></Field>
              <Field label="Authority"><input className="input" required maxLength={200} value={String(values.authority)} onChange={e => set("authority", e.target.value)} /></Field>
              <Field label="Current status"><select className="input" value={String(values.initial_status)} onChange={e => set("initial_status", e.target.value)}>{Object.entries(statuses).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field>
              <Field label="Status effective date" hint="When this current status took effect, not necessarily today's date."><input className="input" type="date" required value={String(values.status_effective_date)} onChange={e => set("status_effective_date", e.target.value)} /></Field>
            </FieldRow>
            <label className="checkbox"><input type="checkbox" checked={newType} onChange={e => setNewType(e.target.checked)} />This is a new permit type</label>
            {newType ? <FieldRow columns={2}>
              <Field label="New type code"><input className="input" required maxLength={64} value={typeCode} onChange={e => setTypeCode(e.target.value)} /></Field>
              <Field label="New type name" hint="The type and permit are saved together."><input className="input" required maxLength={200} value={typeName} onChange={e => setTypeName(e.target.value)} /></Field>
            </FieldRow> : <Field label="Permit type"><select className="input" required value={String(values.permit_type_code)} onChange={e => set("permit_type_code", e.target.value)}>
              <option value="">{types === null ? "Loading types…" : "Choose a type, or enter a new one above"}</option>
              {types?.filter(type => type.is_active).map(type => <option key={type.id} value={type.code}>{type.label}</option>)}
            </select></Field>}
          </FormSection>
          <FormSection title="Scope and responsibility">
            {peopleError ? <Notice tone="error">Could not load permit owners. <Button onClick={() => setRetry(n => n + 1)}>Retry owners</Button></Notice> : null}
            <FieldRow columns={2}>
              <Field label="Parcel" optional><select className="input" value={String(values.parcel_id)} onChange={e => set("parcel_id", e.target.value)}><option value="">Whole project / not specified</option>{parcels.map(p => <option key={p.id} value={p.id}>{p.plot_number}</option>)}</select></Field>
              <Field label="Prerequisite permit" optional><select className="input" value={String(values.prerequisite_permit_id)} onChange={e => set("prerequisite_permit_id", e.target.value)}><option value="">None</option>{permits.map(p => <option key={p.id} value={p.id}>{p.permit_code}</option>)}</select></Field>
              {[["owner_user_id", "Permit owner"], ["escalation_owner_user_id", "Escalation owner"]].map(([name, label]) => <Field key={name} label={label} optional><select className="input" value={String(values[name])} onChange={e => set(name, e.target.value)}><option value="">Unassigned</option>{assignees.map(p => <option key={p.id} value={p.id}>{p.display_name}</option>)}</select></Field>)}
              {canSeeCost ? <Field label="Fee" optional hint={currencyCode ?? "Project base currency"}><input className="input" inputMode="decimal" value={String(values.fee_amount)} onChange={e => set("fee_amount", e.target.value)} /></Field> : null}
            </FieldRow>
          </FormSection>
          {["Application", "Submission dates", "Issue dates", "Management"].map(group => <FormSection key={group} title={group}>
            <FieldRow columns={3}>{DETAILS.filter(field => field[3] === group).map(([name, label, kind, , maxLength]) => <Field key={name} label={label} optional>
              {kind === "textarea" ? <textarea className="input" maxLength={maxLength} rows={3} value={String(values[name])} onChange={e => set(name, e.target.value)} />
                : <input className="input" type={kind} min={kind === "number" ? 1 : undefined} step={kind === "number" ? 1 : undefined} maxLength={maxLength || undefined} value={String(values[name])} onChange={e => set(name, e.target.value)} />}
            </Field>)}</FieldRow>
          </FormSection>)}
          <label className="checkbox"><input type="checkbox" checked={Boolean(values.is_blocking)} onChange={e => set("is_blocking", e.target.checked)} />Blocking the programme</label>
          <label className="checkbox"><input type="checkbox" checked={Boolean(values.is_critical_path)} onChange={e => set("is_critical_path", e.target.checked)} />On the critical path</label>
          <FormActions><Button variant="primary" type="submit" disabled={busy}>{busy ? "Saving…" : "Add permit"}</Button><Button data-leaves-editor onClick={onCancel} disabled={busy}>Cancel</Button></FormActions>
        </fieldset>
      </form></Card>
    </article>
  </DraftBoundary>;
}
