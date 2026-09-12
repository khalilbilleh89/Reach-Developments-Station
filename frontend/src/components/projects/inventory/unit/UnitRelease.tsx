"use client";
import { useState } from "react";
import type { Unit } from "@/lib/api";
import { Button, Field, FormActions, KeyValue, KeyValueGrid, Notice, SectionHeader } from "@/components/ui";
import { EditForm, asValue } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";
import { businessDate, todayISO } from "@/lib/format";

const FIELDS: (EditField & {roles: string[]})[] = [
  {name:"drawings_approved",label:"Drawings approved",kind:"checkbox",roles:["system_admin","project_manager","design_engineering"]},
  {name:"release_date",label:"Release date",kind:"date",roles:["system_admin","project_manager","sales_operations"]},
  {name:"release_batch",label:"Release batch",roles:["system_admin","project_manager","sales_operations"]},
];
export function UnitRelease({unit,roles,busy,onSaveControls,onTransition}: {
  unit: Unit; roles: Set<string>; busy: boolean;
  onSaveControls: (changes: Record<string,unknown>) => Promise<void>;
  onTransition: (move: {to_status:string;effective_date:string;reason:string}) => void;
}) {
  const [editing,setEditing] = useState(false);
  const [date,setDate] = useState(todayISO());
  const fields = FIELDS.filter(field => roles.has("master_admin") || field.roles.some(role => roles.has(role)));
  const canRelease = ["master_admin","system_admin","project_manager","sales_operations"].some(role => roles.has(role));
  const preparing = ["unreleased","held"].includes(unit.commercial_status);
  return <section>
    <SectionHeader level={2} title="Release for sales" description="Prepare the unit and release it as Available for Sales."
      actions={fields.length ? <Button small data-leaves-editor onClick={() => setEditing(!editing)}>{editing ? "Close editor" : "Edit release"}</Button> : undefined} />
    {editing ? <EditForm fields={fields} initial={Object.fromEntries(fields.map(field => [field.name,asValue(unit[field.name as keyof Unit] as never)]))}
      onSave={async changes => {await onSaveControls(changes); setEditing(false);}} onCancel={() => setEditing(false)} /> : <KeyValueGrid columns={3}>
      <KeyValue label="Drawings approved" value={unit.drawings_approved ? "Yes" : "No"} />
      <KeyValue label="Launch price approved" value={unit.pricing_approved ? "Yes" : "No"} />
      <KeyValue label="Release date" value={businessDate(unit.release_date)} />
      <KeyValue label="Release batch" value={unit.release_batch} />
    </KeyValueGrid>}
    {preparing ? <>
      {unit.release_blockers.length ? <Notice tone="info">Before release: {unit.release_blockers.join("; ")}. Commercial eligibility is managed in Sales.</Notice> : null}
      {canRelease ? <form onSubmit={event => {event.preventDefault(); onTransition({to_status:"available",effective_date:date,reason:""});}}>
        <Field label="Effective release date"><input className="input" type="date" required disabled={busy} value={date} onChange={event => setDate(event.target.value)} /></Field>
        <FormActions><Button type="submit" variant="primary" disabled={busy || !unit.is_active || !unit.release_eligible}>{busy ? "Releasing…" : "Release as Available"}</Button></FormActions>
      </form> : null}
    </> : <p className="subtle">The unit has been released. Its commercial lifecycle is managed in Sales.</p>}
  </section>;
}
