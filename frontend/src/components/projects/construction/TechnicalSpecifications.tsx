"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, Disclosure, DataToolbar, Field, EmptyState, FilterChips, Loading, Notice, RecordPage, RowMenu, SectionHeader, Segmented, ToolbarFilter } from "@/components/ui";
import { technicalSpecifications, type TechnicalSpecification } from "@/lib/api/technicalSpecifications";
import { hasAnyRole } from "@/lib/roles";
import { businessDate } from "@/lib/format";
import { EditForm, type EditField } from "../EditForm";
import { SpecificationImages } from "./SpecificationImages";
import { DeleteRecordButton } from "../DeleteRecordButton";

const categories = [
  { value: "structure", label: "Structure & building envelope", hint: "Foundations, frame, walls, roof, insulation and waterproofing." },
  { value: "finishes", label: "Tiles & finishes", hint: "Floor and wall tiles, paint, ceilings, skirting and balcony finishes." },
  { value: "sanitary", label: "Bathrooms & sanitary fittings", hint: "Toilets, basins, taps, showers, bathtubs and accessories." },
  { value: "plumbing", label: "Plumbing & drainage", hint: "Pipework, wastewater, drainage and connection points." },
  { value: "water", label: "Cold & hot water", hint: "Water supply, tanks, pressure, heaters and hot-water systems." },
  { value: "aluminium", label: "Aluminium & glazing", hint: "Window frames, glazing, sliding systems, screens and shutters." },
  { value: "doors", label: "Doors & joinery", hint: "Entrance and internal doors, locks, hardware and wardrobes." },
  { value: "kitchen", label: "Kitchen & appliances", hint: "Cabinets, worktops, sink and included or optional appliances." },
  { value: "electrical", label: "Electrical & communications", hint: "Sockets, switches, lights, data, intercom and security provisions." },
  { value: "heating_cooling", label: "Heating, cooling & ventilation", hint: "Installed equipment, provisions, ventilation and controls." },
  { value: "shared", label: "Shared facilities & external works", hint: "Lifts, entrances, parking, landscaping, pools and common areas." },
  { value: "other", label: "Other specifications", hint: "Additional delivery details and exclusions." },
];
const guideSections = [
  { title: "Engineered for long-term performance", description: "Structure, protection, privacy and the building envelope.", categories: ["structure", "aluminium", "doors"] },
  { title: "Finishes for daily living", description: "Materials, kitchens, bathrooms and their recorded brands.", categories: ["finishes", "sanitary", "kitchen"] },
  { title: "Comfort, efficiency & clean design", description: "Water, electrical systems, cooling and ventilation.", categories: ["plumbing", "water", "electrical", "heating_cooling"] },
  { title: "Outdoor living & shared facilities", description: "Landscaping, recreation, common spaces and additional features.", categories: ["shared", "other"] },
];
const inclusions = [
  { value: "undecided", label: "To be decided" }, { value: "included", label: "Included" },
  { value: "optional", label: "Optional upgrade" }, { value: "excluded", label: "Not included" },
];
const scopes = [{ value: "project", label: "Project & shared areas" }, { value: "units", label: "Inside the units" }, { value: "buildable", label: "All buildable area" }];
const statuses = [{ value: "draft", label: "Draft — not confirmed" }, { value: "confirmed", label: "Confirmed" }];

export function TechnicalSpecifications({ projectId, roles }: { projectId: string; roles: Set<string> }) {
  const canWrite = hasAnyRole(roles, new Set(["system_admin", "project_manager", "design_engineering"]));
  const [rows, setRows] = useState<TechnicalSpecification[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [scope, setScope] = useState("");
  const defaultStatus = canWrite ? "" : "confirmed";
  const [status, setStatus] = useState(defaultStatus);
  const [editing, setEditing] = useState<TechnicalSpecification | "new" | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [savedDuringEdit, setSavedDuringEdit] = useState<TechnicalSpecification | null>(null);
  const [fileRevision, setFileRevision] = useState(0);
  const load = useCallback(async () => {
    try { setRows(await technicalSpecifications.list(projectId)); setError(null); }
    catch (caught) { setRows(null); setError(caught instanceof Error ? caught.message : "Could not load technical specifications."); }
  }, [projectId]);
  useEffect(() => {
    let current = true;
    technicalSpecifications.list(projectId).then(data => { if (current) { setRows(data); setError(null); } })
      .catch(caught => { if (current) { setRows(null); setError(caught instanceof Error ? caught.message : "Could not load technical specifications."); } });
    return () => { current = false; };
  }, [projectId]);
  const row = savedDuringEdit ?? (editing && editing !== "new" ? editing : null);
  const initial = { category: row?.category ?? "finishes", title: row?.title ?? "", scope: row?.scope ?? "units",
    applies_to: row?.applies_to ?? "", description: row?.description ?? "", buyer_benefit: row?.buyer_benefit ?? "", brand_model: row?.brand_model ?? "",
    inclusion: row?.inclusion ?? "undecided", status: row?.status ?? "draft", source_reference: row?.source_reference ?? "" };
  const fields: EditField[] = [
    { name: "category", label: "Category", kind: "select", options: categories },
    { name: "title", label: "Feature", hint: "For example: bathroom floor tiles" },
    { name: "scope", label: "Where it applies", kind: "select", options: scopes },
    { name: "applies_to", label: "Applicable areas or unit types (optional)", hint: "Add detail only when needed, such as 2-bedroom kitchens or the main entrance.", width: "full" },
    { name: "description", label: "Technical specification", kind: "textarea", width: "full", hint: "Use plain language. Include material, size, finish and any exceptions. Distinguish installed equipment from provision only." },
    { name: "buyer_benefit", label: "Buyer benefit (optional)", kind: "textarea", width: "full", hint: "Explain what this feature means for the buyer. Keep it supported by the specification; retain any qualifications." },
    { name: "brand_model", label: "Brand / model / range (optional)" },
    { name: "inclusion", label: "Included in delivery?", kind: "select", options: inclusions },
    { name: "status", label: "Confirmation", kind: "select", options: statuses },
    { name: "source_reference", label: "Supporting document / revision (optional)", width: "full", hint: "Add a specification, drawing, schedule or agreement reference when available." },
  ];
  const needle = search.trim().toLowerCase();
  const shown = (rows ?? []).filter(item => (!scope || item.scope === scope) && (!status || item.status === status) &&
    (!needle || [item.title, item.description, item.buyer_benefit, item.applies_to, item.brand_model, item.source_reference, categories.find(category => category.value === item.category)?.label].join(" ").toLowerCase().includes(needle)));
  const closeEditor = () => { setEditing(null); setSavedDuringEdit(null); setFiles([]); void load(); };
  if (editing) return <RecordPage title={row ? `Edit ${row.title}` : "Add technical specification"} onClose={closeEditor}>
    <EditForm fields={fields} initial={initial} columns={2} submitLabel="Save specification" onCancel={closeEditor} additionalDirty={files.length > 0} onSave={async changes => {
      const values: Record<string, unknown> = { ...initial, ...changes, version: row?.version ?? 1 };
      for (const key of Object.keys(initial)) values[key] = values[key] ?? "";
      for (const file of files) {
        if (!file.size || file.size > 10 * 1024 * 1024) throw new Error("Each optional image must be between 1 byte and 10 MB.");
      }
      const saved = row ? await technicalSpecifications.update(projectId, row.id, values) : await technicalSpecifications.create(projectId, values);
      setSavedDuringEdit(saved);
      // Retry the saved record and only the files that did not persist.
      for (const file of files) {
        await technicalSpecifications.addImage(projectId, saved.id, file);
        setFiles(pending => pending.filter(candidate => candidate !== file));
      }
      setFileRevision(revision => revision + 1);
      await load();
    }}>
      <Field label="Images (optional)" hint="Add now or later. JPEG, PNG or WebP, up to 10 MB each. The specification can be saved without images.">
        <input key={fileRevision} className="input" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={event => setFiles(Array.from(event.target.files ?? []))} />
      </Field>
      {files.length ? <ul>{files.map((file, index) => <li key={index}>{file.name} <Button onClick={() => { setFiles(pending => pending.filter(candidate => candidate !== file)); setFileRevision(revision => revision + 1); }}>Remove selected image</Button></li>)}</ul> : null}
      {savedDuringEdit ? <p className="footnote">The specification details are saved. If an image upload fails, retry Save to upload the remaining images, or remove them and continue.</p> : null}
    </EditForm>
  </RecordPage>;
  return <section className="stack">
    <SectionHeader title="Project specification guide" description="The project specification in plain language: each feature, what is specified and why it matters to the buyer." actions={canWrite ? <Button variant="primary" disabled={rows === null || !!error} onClick={() => setEditing("new")}>Add specification</Button> : undefined} />
    <Disclosure title="Reading the specification"><p className="footnote">Use the stated coverage and source when explaining a feature. “Provision only”, “selected areas” and approval conditions remain part of the specification. Confirmation describes the recorded specification, not completed work.</p></Disclosure>
    {error ? <Notice tone="error">{error}<Button onClick={() => void load()}>Retry</Button></Notice> : rows === null ? <Loading label="Loading technical specifications" /> : <>
      <DataToolbar search={{ value: search, onChange: setSearch, placeholder: "Search a feature, brand, buyer benefit or unit type" }} count={{ shown: shown.length, total: rows.length, noun: "specification" }} onReset={search || scope || status !== defaultStatus ? () => { setSearch(""); setScope(""); setStatus(canWrite ? "" : "confirmed"); } : undefined}>
        <ToolbarFilter label="Applies to" active={!!scope}><select className="input" value={scope} onChange={event => setScope(event.target.value)}><option value="">Project & units</option>{scopes.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></ToolbarFilter>
        <ToolbarFilter label="Confirmation" active={!!status}><Segmented label="Confirmation" value={status} onChange={setStatus} options={[{ value: "", label: "All items" }, ...statuses]} /></ToolbarFilter>
      </DataToolbar>
      <FilterChips chips={[
        ...(scope ? [{ key: "scope", label: `Applies to: ${scopes.find(item => item.value === scope)?.label ?? scope}`, onRemove: () => setScope("") }] : []),
        ...(status !== defaultStatus ? [{ key: "status", label: status ? `Confirmation: ${statuses.find(item => item.value === status)?.label ?? status}` : "All items", onRemove: () => setStatus(defaultStatus) }] : []),
        ...(search ? [{ key: "search", label: `“${search}”`, onRemove: () => setSearch("") }] : []),
      ]} />
      {rows.length === 0 ? <EmptyState title="No specifications recorded yet" hint="Add the project’s sourced specifications to build a clear reference for Sales." /> : shown.length === 0 ? <EmptyState title="No matching specifications" hint="Change the search or filters to see more items." /> : null}
      {guideSections.map(group => {
        const items = shown.filter(item => group.categories.includes(item.category));
        if (!items.length) return null;
        return <Card key={group.title} title={group.title} description={group.description}>
          <div className="specification-guide">{items.map(item => <article key={item.id} className="specification-item">
            <SectionHeader title={item.title} actions={canWrite ? <Button onClick={() => setEditing(item)}>Edit</Button> : undefined} />
            <div><Badge tone={item.status === "confirmed" ? "success" : "warning"}>{item.status === "confirmed" ? "Confirmed" : "Draft — not confirmed"}</Badge>{" "}<Badge tone={item.inclusion === "included" && item.status === "confirmed" ? "success" : "neutral"}>{inclusions.find(value => value.value === item.inclusion)?.label}</Badge></div>
            <p className="footnote">{scopes.find(value => value.value === item.scope)?.label}{item.applies_to ? " · " + item.applies_to : ""}</p>
            <dl className="specification-comparison">
              <div><dt>Technical specification</dt><dd className="specification-description">{item.description}</dd>{item.brand_model ? <dd><strong>Brand / model:</strong> {item.brand_model}</dd> : null}</div>
              <div><dt>Buyer benefit</dt><dd className="specification-description">{item.buyer_benefit || "No buyer benefit recorded. Use the technical specification."}</dd></div>
            </dl>
            <SpecificationImages projectId={projectId} specificationId={item.id} images={item.images ?? []} canWrite={canWrite} onChanged={load} />
            <Disclosure title="Source & record details">
              <p className="footnote">Source: {item.source_reference || "Not recorded"} · Updated {businessDate(item.updated_at.slice(0, 10))}</p>
              <p className="footnote">Category: {categories.find(category => category.value === item.category)?.label}</p>
            </Disclosure>
            {canWrite ? <div className="form-actions"><RowMenu label={`Actions for ${item.title}`}><DeleteRecordButton label={item.title} confirmLabel="Delete specification" description="Removes this item from the guide. Confirmed specifications, specifications with image history and the audit trail are retained." onDelete={reason => technicalSpecifications.remove(projectId, item.id, reason)} onDeleted={load} /></RowMenu></div> : null}
          </article>)}</div>
        </Card>;
      })}
    </>}
  </section>;
}
