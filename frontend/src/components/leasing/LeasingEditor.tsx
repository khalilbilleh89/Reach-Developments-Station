"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { leasing, LEASING_STAGES, type LeasingDetail, type LeasingProject, type LeasingSource, type LeasingTerms, type LeasingStage } from "@/lib/api/leasing";
import { useAnswer } from "@/lib/answer";
import { Button, Card, DraftBoundary, EmptyState, Field, FieldRow, FormActions, FormSection, MoneyInput, Notice, RecordPage, RegisterPagination } from "@/components/ui";
import { AnswerState, SourceProfile } from "./LeasingWorkspace";

export function LeasingEditor({ projects, initialProject, row, onClose, onSaved }: {
  projects: LeasingProject[]; initialProject: string; row?: LeasingDetail; onClose: () => void; onSaved: () => void;
}) {
  const [chosen, setChosen] = useState<{ project: string; source: LeasingSource } | null>(null);
  if (row || chosen) return <TermsEditor project={row?.project_id ?? chosen!.project} source={row?.source ?? chosen!.source} row={row} onClose={onClose} onSaved={onSaved} />;
  return <UnitPicker projects={projects} initialProject={initialProject} onClose={onClose} onSelect={(project, source) => setChosen({ project, source })} />;
}

function UnitPicker({ projects, initialProject, onClose, onSelect }: {
  projects: LeasingProject[]; initialProject: string; onClose: () => void; onSelect: (project: string, source: LeasingSource) => void;
}) {
  const [project, setProject] = useState(initialProject);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [unit, setUnit] = useState("");
  const units = useAnswer(!!project, () => leasing.units(project, search, offset), [project, search, offset]);
  const source = useAnswer(!!project && !!unit, () => leasing.source(project, unit), [project, unit]);
  return <RecordPage title="Choose a unit" eyebrow="New leasing instruction Â· 1 of 2" onClose={onClose}><div className="stack">
    <Card><Field label="Project"><select className="input" required value={project} onChange={e => { setProject(e.target.value); setUnit(""); setOffset(0); setSearch(""); }}><option value="">Select a project</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field>
      {project ? <Field label="Search unit reference"><input className="input" type="search" value={search} onChange={e => { setSearch(e.target.value); setOffset(0); }} /></Field> : null}
      <AnswerState answer={units} />
      {units.status === "ready" ? <>{units.data.items.length ? <Field label="Unit"><select className="input" value={unit} onChange={e => setUnit(e.target.value)}><option value="">Select a unit</option>{unit && !units.data.items.some(u => u.id === unit) ? <option value={unit}>{source.status === "ready" ? source.data.unit.unit_reference : "Selected unit"}</option> : null}{units.data.items.map(u => <option key={u.id} value={u.id}>{u.unit_reference} Â· {u.building ?? "â€”"} Â· {u.floor ?? "â€”"}</option>)}</select></Field> : <EmptyState title="No matching units" hint="Check the search or add the unit in the project's Inventory." />}<RegisterPagination offset={offset} total={units.data.total} pageSize={50} onChange={setOffset} /></> : null}
    </Card>
    <AnswerState answer={source} />
    {source.status === "ready" ? <><SourceProfile source={source.data} /><Button onClick={() => onSelect(project, source.data)}>Continue with {source.data.unit.unit_reference}</Button></> : null}
  </div></RecordPage>;
}

export function initialTerms(source: LeasingSource, row?: LeasingDetail): LeasingTerms {
  return {
    owner_client_id: row ? row.owner_client_id : source.sale_client?.id ?? null,
    status: row?.status ?? "draft", mandate_date: row?.mandate_date ?? null, mandate_reference: row?.mandate_reference ?? "",
    asking_rent_monthly: row?.asking_rent_monthly ?? null, available_from: row?.available_from ?? null,
    tenant_name: row?.tenant_name ?? "", agreed_rent_monthly: row?.agreed_rent_monthly ?? null,
    security_deposit: row?.security_deposit ?? null, lease_start: row?.lease_start ?? null, lease_end: row?.lease_end ?? null,
    agreement_reference: row?.agreement_reference ?? "", next_action: row?.next_action ?? "",
    follow_up_date: row?.follow_up_date ?? null, notes: row?.notes ?? "",
  };
}

export function TermsEditor({ project, source, row, onClose, onSaved }: {
  project: string; source: LeasingSource; row?: LeasingDetail; onClose: () => void; onSaved: () => void;
}) {
  const [values, setValues] = useState(() => initialTerms(source, row));
  const [ownerSearch, setOwnerSearch] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const owners = useAnswer(true, () => leasing.clients(project, ownerSearch), [project, ownerSearch]);
  const set = <K extends keyof LeasingTerms>(key: K, value: LeasingTerms[K]) => setValues({ ...values, [key]: value });
  const code = row?.currency_code ?? source.currency_code;
  const selectedOwner = row?.owner?.id === values.owner_client_id ? row.owner : source.sale_client?.id === values.owner_client_id ? source.sale_client : null;
  return <RecordPage title={row ? `Edit ${source.unit.unit_reference}` : `Lease ${source.unit.unit_reference}`} eyebrow={row ? "Leasing instruction" : "New leasing instruction Â· 2 of 2"} subtitle={source.project_name} onClose={onClose}>
    <DraftBoundary dirty={JSON.stringify(values) !== JSON.stringify(initialTerms(source, row)) || !!reason} busy={busy}><form className="stack" onSubmit={async e => {
      e.preventDefault(); if (busy) return; setBusy(true); setError(null);
      try { if (row) await leasing.update(row, values, reason); else await leasing.create(project, source.unit.id, values); onSaved(); }
      catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save. Your entries have been kept."); }
      finally { setBusy(false); }
    }}>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <fieldset className="leasing-fieldset stack" disabled={busy}>
        <SourceProfile source={source} />
        <FormSection title="Owner instruction" description="Confirm who is asking us to let the unit. The active sale's buyer is preselected where available.">
          <FieldRow><Field label="Find project client" optional hint="Search by client name or number; up to 50 matches."><input className="input" type="search" value={ownerSearch} onChange={e => setOwnerSearch(e.target.value)} /></Field>
            <Field label="Instructing owner" optional><select className="input" value={values.owner_client_id ?? ""} onChange={e => set("owner_client_id", e.target.value || null)}><option value="">Not yet linked</option>{selectedOwner && (owners.status !== "ready" || !owners.data.some(c => c.id === selectedOwner.id)) ? <option value={selectedOwner.id}>{selectedOwner.display_name}</option> : null}{owners.status === "ready" ? owners.data.map(c => <option value={c.id} key={c.id}>{c.display_name} Â· {c.client_number}</option>) : null}</select></Field></FieldRow>
          <AnswerState answer={owners} />
          <p className="muted">Missing client? Add the owner in the project’s Buyers register, then return here. Save as Instruction while details are pending.</p>
          <FieldRow><Field label="Instruction date" optional><input className="input" type="date" value={values.mandate_date ?? ""} onChange={e => set("mandate_date", e.target.value || null)} /></Field><Field label="Instruction / mandate reference" optional><input className="input" maxLength={200} value={values.mandate_reference} onChange={e => set("mandate_reference", e.target.value)} /></Field></FieldRow>
        </FormSection>
        <FormSection title="Market the unit" description="Monthly rents use the instruction's currency. Complete the owner instruction before moving to On market.">
          <FieldRow columns={3}><Field label="Stage"><select className="input" value={values.status} onChange={e => set("status", e.target.value as LeasingStage)}>{LEASING_STAGES.filter(s => row?.status !== "closed" || s.key === "closed").map(s => <option key={s.key} value={s.key}>{s.label}</option>)}</select></Field>
            <Field label="Monthly asking rent" optional><MoneyInput code={code} value={values.asking_rent_monthly ?? ""} onChange={value => set("asking_rent_monthly", value || null)} /></Field>
            <Field label="Available from" optional><input className="input" type="date" value={values.available_from ?? ""} onChange={e => set("available_from", e.target.value || null)} /></Field></FieldRow>
        </FormSection>
        <FormSection title="Tenancy" description="Complete these details when the unit is leased. Agreed amounts do not record receipts.">
          <FieldRow><Field label="Tenant name" optional><input className="input" maxLength={200} value={values.tenant_name} onChange={e => set("tenant_name", e.target.value)} /></Field><Field label="Agreement reference" optional><input className="input" maxLength={200} value={values.agreement_reference} onChange={e => set("agreement_reference", e.target.value)} /></Field></FieldRow>
          <FieldRow><Field label="Lease start" optional><input className="input" type="date" value={values.lease_start ?? ""} onChange={e => set("lease_start", e.target.value || null)} /></Field><Field label="Lease end" optional><input className="input" type="date" value={values.lease_end ?? ""} onChange={e => set("lease_end", e.target.value || null)} /></Field></FieldRow>
          <FieldRow><Field label="Agreed monthly rent" optional><MoneyInput code={code} value={values.agreed_rent_monthly ?? ""} onChange={value => set("agreed_rent_monthly", value || null)} /></Field><Field label="Security deposit agreed" optional><MoneyInput code={code} value={values.security_deposit ?? ""} onChange={value => set("security_deposit", value || null)} /></Field></FieldRow>
          <p className="muted">For the next tenancy, close this cycle and create a new instruction. Previous terms stay in history.</p>
        </FormSection>
        <FormSection title="Next action" description="Keep the next owner call, viewing or renewal conversation visible.">
          <FieldRow><Field label="Action" optional><input className="input" maxLength={300} value={values.next_action} onChange={e => set("next_action", e.target.value)} /></Field><Field label="Follow-up date" optional><input className="input" type="date" value={values.follow_up_date ?? ""} onChange={e => set("follow_up_date", e.target.value || null)} /></Field></FieldRow>
          <Field label="Notes" optional><textarea className="input" rows={4} maxLength={4000} value={values.notes} onChange={e => set("notes", e.target.value)} /></Field>
        </FormSection>
        {row ? <Field label="Reason for change"><input required className="input" maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></Field> : null}
      </fieldset>
      <FormActions><Button type="submit" disabled={busy}>{busy ? "Savingâ€¦" : "Save instruction"}</Button><Button variant="default" data-leaves-editor disabled={busy} onClick={onClose}>Cancel</Button></FormActions>
    </form></DraftBoundary>
  </RecordPage>;
}
