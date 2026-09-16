"use client";
import { useState } from "react";
import type { Unit } from "@/lib/api";
import { Button, KeyValue, KeyValueGrid, Notice, SectionHeader } from "@/components/ui";
import { EditForm, asValue } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";
import { businessDate } from "@/lib/format";

const FIELDS: (EditField & {roles: string[]})[] = [
  {name:"release_date",label:"Release date",kind:"date",hint:"On this date the unit goes on sale, provided its launch price is approved.",roles:["system_admin","project_manager","sales_operations"]},
  {name:"release_batch",label:"Release batch",roles:["system_admin","project_manager","sales_operations"]},
  {name:"drawings_approved",label:"Drawings approved",kind:"checkbox",roles:["system_admin","project_manager","design_engineering"]},
];

/** The release date is the decision; everything else here is a fact about the unit. */
export function UnitRelease({unit,roles,onSaveControls}: {
  unit: Unit; roles: Set<string>;
  onSaveControls: (changes: Record<string,unknown>) => Promise<void>;
}) {
  const [editing,setEditing] = useState(false);
  const fields = FIELDS.filter(field => roles.has("master_admin") || field.roles.some(role => roles.has(role)));
  const released = !["unreleased","held"].includes(unit.commercial_status);
  return <section>
    <SectionHeader level={2} title="Release for sales" description="Set the release date. The unit goes on sale on that date once its launch price is approved."
      actions={fields.length ? <Button small data-leaves-editor onClick={() => setEditing(!editing)}>{editing ? "Close editor" : "Edit release"}</Button> : undefined} />
    {editing ? <EditForm fields={fields} initial={Object.fromEntries(fields.map(field => [field.name,asValue(unit[field.name as keyof Unit] as never)]))}
      onSave={async changes => {await onSaveControls(changes); setEditing(false);}} onCancel={() => setEditing(false)} /> : <KeyValueGrid columns={3}>
      <KeyValue label="Release date" value={businessDate(unit.release_date)} />
      <KeyValue label="Release batch" value={unit.release_batch} />
      <KeyValue label="Launch price approved" value={unit.pricing_approved ? "Yes" : "No"} />
      <KeyValue label="Drawings approved" value={unit.drawings_approved ? "Yes" : "No"} />
      <KeyValue label="Legally saleable" value={unit.legal_sale_eligible ? "Yes" : "No"} />
    </KeyValueGrid>}
    {released
      ? <p className="subtle">The unit is on sale. Its commercial lifecycle is managed in Sales.</p>
      : unit.release_blockers.length
        ? <Notice tone="info">
            <strong>Not on sale yet</strong>
            <ul className="unit-release-requirements">
              {unit.release_blockers.map((blocker, index) => <li key={`${index}-${blocker}`}>{blocker}</li>)}
            </ul>
          </Notice>
        : null}
  </section>;
}
