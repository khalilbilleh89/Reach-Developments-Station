"use client";

import { useState } from "react";
import type { AmenityDetails, AmenityKey } from "@/lib/api/amenities";
import { Button, Card, Disclosure, KeyValue, KeyValueGrid, RecordPage, SectionHeader } from "@/components/ui";
import { AMENITIES, BALCONY_FIELDS, COMMON, FIELDS, POOL_FIELDS, STATUS, fieldText, recorded, visible, type AmenityField } from "./amenityFields";

export function amenityFacts(key: AmenityKey, details: AmenityDetails): string[] {
  const record = details[key] ?? {};
  const facts: string[] = [];
  if (key === "swimming_pools" && details.swimming_pools?.pools?.length) {
    facts.push(`Pools: ${details.swimming_pools.pools.length}`);
    const pool = details.swimming_pools.pools[0];
    if (pool.name) facts.push(pool.name);
    if (recorded(pool.area_sqm)) facts.push(`Surface area: ${pool.area_sqm} m²`);
  }
  if (key === "balconies" && details.balconies?.balconies?.length) {
    facts.push(`Balcony entries: ${details.balconies.balconies.length}`);
    const balcony = details.balconies.balconies[0];
    if (balcony.overlooks) facts.push(`View: ${balcony.overlooks}`);
    if (recorded(balcony.area_sqm)) facts.push(`Balcony size: ${balcony.area_sqm} m²`);
  }
  for (const field of [STATUS, ...FIELDS[key], ...COMMON]) {
    const value = (record as Record<string, unknown>)[field.key];
    if (field.kind !== "url" && visible(field, record) && recorded(value)) facts.push(`${field.label}: ${fieldText(field, value)}`);
  }
  return facts.slice(0, 3);
}

function Details({ fields, record }: { fields: AmenityField[]; record: Record<string, unknown> }) {
  return <KeyValueGrid>{fields.filter(field => visible(field, record)).map(field => <KeyValue key={field.key} label={field.label} value={field.kind === "url" && recorded(record[field.key]) ? <a href={String(record[field.key])} target="_blank" rel="noopener noreferrer">Open supporting document</a> : fieldText(field, record[field.key])} />)}</KeyValueGrid>;
}

export function ProjectAmenities({ details = {}, legacyNames }: { details?: AmenityDetails; legacyNames: string[] }) {
  const [selected, setSelected] = useState<AmenityKey | null>(null);
  const name = AMENITIES.find(item => item.key === selected)?.name;
  return <>
    <Card><SectionHeader title="Amenities" level={2} />{AMENITIES.map(({ key, name }) => {
      const facts = amenityFacts(key, details);
      return <section key={key} className="marketing-story"><SectionHeader title={name} level={3} />
        {facts.length ? <ul className="marketing-bullets">{facts.map((fact, index) => <li key={index}>{fact}</li>)}</ul> : <p className="muted">Details not recorded.</p>}
        <Button onClick={() => setSelected(key)} aria-label={`View details: ${name}`}>View details</Button>
      </section>;
    })}
    {legacyNames.length ? <Disclosure title="Previously recorded amenity names"><ul className="marketing-bullets">{legacyNames.map((item, index) => <li key={index}>{item}</li>)}</ul></Disclosure> : null}
    </Card>
    {selected ? <RecordPage title={name ?? "Amenity details"} eyebrow="Project Bio · Amenities" onClose={() => setSelected(null)}>
      <div className="stack"><Card><Details fields={[...COMMON, ...(selected === "energy" ? [] : [STATUS]), ...FIELDS[selected]]} record={details[selected] ?? {}} /></Card>
        {selected === "swimming_pools" ? (details.swimming_pools?.pools ?? []).map((pool, index) => <Card key={pool.id}><SectionHeader title={pool.name || `Pool ${index + 1}`} level={2} /><Details fields={POOL_FIELDS} record={pool} /></Card>) : null}
        {selected === "balconies" ? (details.balconies?.balconies ?? []).map((balcony, index) => <Card key={balcony.id}><SectionHeader title={balcony.unit_type || `Balcony entry ${index + 1}`} level={2} /><Details fields={BALCONY_FIELDS} record={balcony} /></Card>) : null}
      </div>
    </RecordPage> : null}
  </>;
}
