"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import type { Bio, Branding, Nearby } from "@/lib/api/marketing";
import { Button, DraftBoundary, Field, FieldRow, FormActions, FormSection, Notice, RecordPage } from "@/components/ui";

const sections = [["country", "About Country"], ["area", "About Area"], ["project", "About Project"], ["location", "About Location"]] as const;
const lines = (value: string) => value.split("\n");
const cleanLines = (value: string[]) => value.map(line => line.trim()).filter(Boolean);

export function MarketingContentEditor({ kind, initial, onClose, onSave }: { kind: "bio" | "branding"; initial: Bio | Branding; onClose: () => void; onSave: (data: Bio | Branding) => Promise<void> }) {
  const [data, setData] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bio = data as Bio;
  const brand = data as Branding;
  const updateBio = (patch: Partial<Bio>) => setData({ ...bio, ...patch });
  const updateBrand = (patch: Partial<Branding>) => setData({ ...brand, ...patch });
  return <RecordPage title={kind === "bio" ? "Edit Project Bio" : "Edit Branding"} onClose={onClose}>
    <DraftBoundary dirty={JSON.stringify(initial) !== JSON.stringify(data)} busy={busy}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault(); if (busy) return; setBusy(true); setError(null);
        try {
          const saved = kind === "bio" ? { ...bio, country: { ...bio.country, bullets: cleanLines(bio.country.bullets) }, area: { ...bio.area, bullets: cleanLines(bio.area.bullets) }, project: { ...bio.project, bullets: cleanLines(bio.project.bullets) }, location: { ...bio.location, bullets: cleanLines(bio.location.bullets) }, amenities: cleanLines(bio.amenities) } : brand;
          await onSave(saved);
        } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save. Your entries have been kept."); }
        finally { setBusy(false); }
      }}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <fieldset disabled={busy} className="marketing-fieldset stack">
          {kind === "bio" ? <>
            {sections.map(([key, label]) => <FormSection key={key} title={label}>
              <Field label={`${label} paragraph`} optional><textarea rows={4} maxLength={4000} value={bio[key].paragraph} onChange={e => updateBio({ [key]: { ...bio[key], paragraph: e.target.value } })} /></Field>
              <Field label={`${label} bullet points`} hint="One point per line. Remove a line to delete the point." optional><textarea rows={3} value={bio[key].bullets.join("\n")} onChange={e => updateBio({ [key]: { ...bio[key], bullets: lines(e.target.value) } })} /></Field>
            </FormSection>)}
            <FormSection title="Nearby Locations" description="Record journey duration in minutes and the travel mode.">
              {bio.nearby.map((place, i) => <div key={i} className="marketing-entry stack">
                <FieldRow><Field label="Location"><input required maxLength={320} value={place.name} onChange={e => updateBio({ nearby: bio.nearby.map((p, j) => j === i ? { ...p, name: e.target.value } : p) })} /></Field>
                  <Field label="Duration (minutes)" optional><input type="number" min="0" max="10080" step="1" value={place.duration_minutes ?? ""} onChange={e => updateBio({ nearby: bio.nearby.map((p, j) => j === i ? { ...p, duration_minutes: e.target.value === "" ? null : e.target.valueAsNumber } : p) })} /></Field>
                  <Field label="Travel mode"><select value={place.travel_mode} onChange={e => updateBio({ nearby: bio.nearby.map((p, j) => j === i ? { ...p, travel_mode: e.target.value as Nearby["travel_mode"] } : p) })}><option value="drive">Drive</option><option value="walk">Walk</option><option value="transit">Public transport</option><option value="cycle">Cycle</option></select></Field></FieldRow>
                <Field label="Journey notes" optional><input maxLength={4000} value={place.note} onChange={e => updateBio({ nearby: bio.nearby.map((p, j) => j === i ? { ...p, note: e.target.value } : p) })} /></Field>
                <Button variant="danger" onClick={() => updateBio({ nearby: bio.nearby.filter((_, j) => j !== i) })}>Delete location {i + 1}</Button>
              </div>)}
              <Button variant="default" onClick={() => updateBio({ nearby: [...bio.nearby, { name: "", duration_minutes: null, travel_mode: "drive", note: "" }] })}>Add nearby location</Button>
            </FormSection>
            <FormSection title="Project Amenities"><Field label="Amenities" hint="One amenity per line. Remove a line to delete it." optional><textarea rows={5} value={bio.amenities.join("\n")} onChange={e => updateBio({ amenities: lines(e.target.value) })} /></Field></FormSection>
            <FormSection title="Indicative ROI Range" description="This is a stated marketing range. Economics calculates each unit's return separately.">
              <FieldRow><Field label="Minimum ROI (%)" optional><input inputMode="decimal" value={bio.roi_min_percent ?? ""} onChange={e => updateBio({ roi_min_percent: e.target.value || null })} /></Field><Field label="Maximum ROI (%)" optional><input inputMode="decimal" value={bio.roi_max_percent ?? ""} onChange={e => updateBio({ roi_max_percent: e.target.value || null })} /></Field></FieldRow>
              <Field label="Return period and basis" hint="For example: annual net rental yield, or total five-year return including resale." optional><textarea maxLength={4000} value={bio.roi_basis} onChange={e => updateBio({ roi_basis: e.target.value })} /></Field>
            </FormSection>
          </> : <>
            <FormSection title="Project Name Definition"><Field label="Project name" optional><input maxLength={4000} value={brand.project_name} onChange={e => updateBrand({ project_name: e.target.value })} /></Field><Field label="Meaning and story" optional><textarea rows={5} maxLength={4000} value={brand.name_definition} onChange={e => updateBrand({ name_definition: e.target.value })} /></Field></FormSection>
            <FormSection title="Colour Scheme">
              {brand.colors.map((color, i) => <div className="marketing-entry stack" key={i}><FieldRow>
                <Field label="Colour name"><input required maxLength={320} value={color.name} onChange={e => updateBrand({ colors: brand.colors.map((c, j) => j === i ? { ...c, name: e.target.value } : c) })} /></Field>
                <Field label="Hex colour (#RRGGBB)"><input required pattern="#[0-9a-fA-F]{6}" maxLength={7} placeholder="#RRGGBB" value={color.hex} onChange={e => updateBrand({ colors: brand.colors.map((c, j) => j === i ? { ...c, hex: e.target.value } : c) })} /></Field>
                <Field label="Usage" optional><input maxLength={4000} value={color.usage} onChange={e => updateBrand({ colors: brand.colors.map((c, j) => j === i ? { ...c, usage: e.target.value } : c) })} /></Field>
              </FieldRow><Button variant="danger" onClick={() => updateBrand({ colors: brand.colors.filter((_, j) => j !== i) })}>Delete colour {i + 1}</Button></div>)}
              <Button variant="default" onClick={() => updateBrand({ colors: [...brand.colors, { name: "", hex: "", usage: "" }] })}>Add colour</Button>
            </FormSection>
            <FormSection title="Font Types">
              {brand.fonts.map((font, i) => <div className="marketing-entry stack" key={i}><FieldRow><Field label="Font family"><input required maxLength={320} value={font.family} onChange={e => updateBrand({ fonts: brand.fonts.map((f, j) => j === i ? { ...f, family: e.target.value } : f) })} /></Field><Field label="Usage" optional><input maxLength={4000} value={font.usage} onChange={e => updateBrand({ fonts: brand.fonts.map((f, j) => j === i ? { ...f, usage: e.target.value } : f) })} /></Field></FieldRow><Button variant="danger" onClick={() => updateBrand({ fonts: brand.fonts.filter((_, j) => j !== i) })}>Delete font {i + 1}</Button></div>)}
              <Button variant="default" onClick={() => updateBrand({ fonts: [...brand.fonts, { family: "", usage: "" }] })}>Add font</Button>
            </FormSection>
          </>}
          <FormSection title="Supporting Source"><Field label="Source or reference" optional><textarea maxLength={4000} value={data.source} onChange={e => setData({ ...data, source: e.target.value })} /></Field><Field label="As-at date" optional><input type="date" value={data.as_of ?? ""} onChange={e => setData({ ...data, as_of: e.target.value || null })} /></Field></FormSection>
        </fieldset>
        <FormActions><Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save"}</Button><Button variant="default" data-leaves-editor onClick={onClose} disabled={busy}>Cancel</Button></FormActions>
      </form>
    </DraftBoundary>
  </RecordPage>;
}
