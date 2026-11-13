"use client";

import { useState } from "react";
import type { AmenityDetails, AmenityKey } from "@/lib/api/amenities";
import { Button, ConfirmDialog, Field, FieldRow, SectionHeader } from "@/components/ui";
import { AMENITIES, BALCONY_FIELDS, COMMON, FIELDS, POOL_FIELDS, STATUS, visible, type AmenityField } from "./amenityFields";

function Fields({ fields, value, onChange }: { fields: AmenityField[]; value: Record<string, unknown>; onChange: (key: string, value: string | number | boolean | null) => void }) {
  return <FieldRow>{fields.filter(field => visible(field, value)).map(field => <Field key={field.key} label={field.label} optional>
    {field.kind === "choice" || field.kind === "boolean" ? <select className="input" value={value[field.key] === null || value[field.key] === undefined ? "" : String(value[field.key])} onChange={event => onChange(field.key, event.target.value === "" ? null : field.kind === "boolean" ? event.target.value === "true" : event.target.value)}>
      <option value="">Not recorded</option>{(field.kind === "boolean" ? [{ value: "true", label: "Yes" }, { value: "false", label: "No" }] : field.options)?.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
    </select> : <input className="input" type={field.kind === "url" ? "url" : field.kind === "count" || field.kind === "decimal" ? "number" : "text"} min={field.kind === "count" || field.kind === "decimal" ? 0 : undefined} step={field.kind === "decimal" ? "0.0001" : field.kind === "count" ? "1" : undefined} maxLength={4000} value={String(value[field.key] ?? "")} onChange={event => onChange(field.key, field.kind === "count" ? event.target.value === "" ? null : event.target.valueAsNumber : field.kind === "decimal" || field.kind === "url" ? event.target.value || null : event.target.value)} />}
  </Field>)}</FieldRow>;
}

export function AmenityEditor({ value = {}, onChange }: { value?: AmenityDetails; onChange: (value: AmenityDetails) => void }) {
  const [removal, setRemoval] = useState<{ name: string; apply: () => void } | null>(null);
  const update = (key: AmenityKey, patch: Record<string, unknown>) => onChange({ ...value, [key]: { ...value[key], ...patch } });
  return <div className="stack">
    <p className="muted">All details are optional. Enter confirmed facts; leave unknown values unrecorded. Deletions take effect when you save changes.</p>
    {AMENITIES.map(({ key, name }) => {
      const record = value[key] ?? {};
      return <section key={key} className="marketing-entry stack" aria-label={name}>
        <SectionHeader title={name} level={3} />
        <Fields fields={[...COMMON, ...(key === "energy" ? [] : [STATUS]), ...FIELDS[key]]} value={record} onChange={(field, next) => update(key, { [field]: next })} />
        {key === "swimming_pools" ? <>
          {(value.swimming_pools?.pools ?? []).map((pool, index) => <section key={pool.id} className="marketing-entry stack" aria-label={`Pool ${index + 1}`}>
            <SectionHeader title={pool.name || `Pool ${index + 1}`} level={3} />
            <Fields fields={POOL_FIELDS} value={pool} onChange={(field, next) => update(key, { pools: value.swimming_pools?.pools?.map(item => item.id === pool.id ? { ...item, [field]: next } : item) })} />
            <Button variant="danger" onClick={() => setRemoval({ name: pool.name || `Pool ${index + 1}`, apply: () => update(key, { pools: value.swimming_pools?.pools?.filter(item => item.id !== pool.id) }) })}>Delete pool {index + 1}</Button>
          </section>)}
          <Button onClick={() => update(key, { pools: [...(value.swimming_pools?.pools ?? []), { id: crypto.randomUUID() }] })}>Add pool</Button>
        </> : null}
        {key === "balconies" ? <>
          {(value.balconies?.balconies ?? []).map((balcony, index) => <section key={balcony.id} className="marketing-entry stack" aria-label={`Balcony entry ${index + 1}`}>
            <SectionHeader title={balcony.unit_type || `Balcony entry ${index + 1}`} level={3} />
            <Fields fields={BALCONY_FIELDS} value={balcony} onChange={(field, next) => update(key, { balconies: value.balconies?.balconies?.map(item => item.id === balcony.id ? { ...item, [field]: next } : item) })} />
            <Button variant="danger" onClick={() => setRemoval({ name: balcony.unit_type || `Balcony entry ${index + 1}`, apply: () => update(key, { balconies: value.balconies?.balconies?.filter(item => item.id !== balcony.id) }) })}>Delete balcony entry {index + 1}</Button>
          </section>)}
          <Button onClick={() => update(key, { balconies: [...(value.balconies?.balconies ?? []), { id: crypto.randomUUID() }] })}>Add balcony entry</Button>
        </> : null}
        <Button variant="danger" onClick={() => setRemoval({ name: `${name} details`, apply: () => onChange({ ...value, [key]: {} }) })}>Delete {name} details</Button>
      </section>;
    })}
    {removal ? <ConfirmDialog title={`Delete ${removal.name}?`} body="This removes the details from your draft. Save changes to apply the deletion; previous saved values remain in the audit history. The amenity name stays in the panel." confirmLabel="Delete details" onCancel={() => setRemoval(null)} onConfirm={() => { removal.apply(); setRemoval(null); }} /> : null}
  </div>;
}

