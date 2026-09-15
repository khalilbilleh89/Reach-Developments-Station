"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, DataToolbar, EmptyState, Loading, Notice, RecordPage, SectionHeader, ToolbarFilter } from "@/components/ui";
import { technicalSpecifications, type TechnicalSpecification } from "@/lib/api/technicalSpecifications";
import { hasAnyRole } from "@/lib/roles";
import { businessDate } from "@/lib/format";
import { EditForm, type EditField } from "../EditForm";
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
const inclusions = [
  { value: "undecided", label: "To be decided" }, { value: "included", label: "Included" },
  { value: "optional", label: "Optional upgrade" }, { value: "excluded", label: "Not included" },
];
const scopes = [{ value: "project", label: "Project & shared areas" }, { value: "units", label: "Inside the units" }];
const statuses = [{ value: "draft", label: "Draft — not confirmed" }, { value: "confirmed", label: "Confirmed" }];

export function TechnicalSpecifications({ projectId, roles }: { projectId: string; roles: Set<string> }) {
  const canWrite = hasAnyRole(roles, new Set(["system_admin", "project_manager", "design_engineering"]));
  const [rows, setRows] = useState<TechnicalSpecification[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [scope, setScope] = useState("");
  const [status, setStatus] = useState("");
  const [editing, setEditing] = useState<TechnicalSpecification | "new" | null>(null);
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
  const row = editing && editing !== "new" ? editing : null;
  const initial = { category: row?.category ?? "finishes", title: row?.title ?? "", scope: row?.scope ?? "units",
    applies_to: row?.applies_to ?? "", description: row?.description ?? "", brand_model: row?.brand_model ?? "",
    inclusion: row?.inclusion ?? "undecided", status: row?.status ?? "draft", source_reference: row?.source_reference ?? "" };
  const fields: EditField[] = [
    { name: "category", label: "Category", kind: "select", options: categories },
    { name: "title", label: "Specification item", hint: "For example: bathroom floor tiles" },
    { name: "scope", label: "Where it applies", kind: "select", options: scopes },
    { name: "applies_to", label: "Applicable areas or unit types", hint: "State the exact coverage, such as all units, 2-bedroom kitchens, or main entrance.", width: "full" },
    { name: "description", label: "What will be delivered", kind: "textarea", width: "full", hint: "Use plain language. Include material, size, finish and any exceptions. Distinguish installed equipment from provision only." },
    { name: "brand_model", label: "Brand / model / range (optional)" },
    { name: "inclusion", label: "Included in delivery?", kind: "select", options: inclusions },
    { name: "status", label: "Confirmation", kind: "select", options: statuses },
    { name: "source_reference", label: "Supporting document / revision", width: "full", hint: "Required for confirmed items. Name the approved specification, drawing, schedule or agreement and its revision." },
  ];
  const needle = search.trim().toLowerCase();
  const shown = (rows ?? []).filter(item => (!scope || item.scope === scope) && (!status || item.status === status) &&
    (!needle || [item.title, item.description, item.applies_to, item.brand_model, item.source_reference, categories.find(category => category.value === item.category)?.label].join(" ").toLowerCase().includes(needle)));
  if (editing) return <RecordPage title={row ? `Edit ${row.title}` : "Add technical specification"} onClose={() => setEditing(null)}>
    <EditForm fields={fields} initial={initial} columns={2} submitLabel="Save specification" onCancel={() => setEditing(null)} onSave={async changes => {
      const values: Record<string, unknown> = { ...initial, ...changes, version: row?.version ?? 1 };
      for (const key of Object.keys(initial)) values[key] = values[key] ?? "";
      if (row) await technicalSpecifications.update(projectId, row.id, values); else await technicalSpecifications.create(projectId, values);
      await load();
    }} />
  </RecordPage>;
  return <section className="stack">
    <SectionHeader title="Technical Specifications" description="A simple guide to what the project and its units will include." actions={canWrite ? <Button variant="primary" disabled={rows === null || !!error} onClick={() => setEditing("new")}>Add specification</Button> : undefined} />
    <Notice tone="info">Check the applicable areas and confirmation on each item. Drafts are still being decided; confirmed items describe the recorded delivery specification, not completed construction.</Notice>
    {error ? <Notice tone="error">{error}<Button onClick={() => void load()}>Retry</Button></Notice> : rows === null ? <Loading label="Loading technical specifications" /> : <>
      <DataToolbar search={{ value: search, onChange: setSearch, placeholder: "Find tiles, hot water, doors or a unit type" }} count={{ shown: shown.length, total: rows.length, noun: "specification" }} onReset={search || scope || status ? () => { setSearch(""); setScope(""); setStatus(""); } : undefined}>
        <ToolbarFilter label="Applies to" active={!!scope}><select className="input" value={scope} onChange={event => setScope(event.target.value)}><option value="">Project & units</option>{scopes.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></ToolbarFilter>
        <ToolbarFilter label="Confirmation" active={!!status}><select className="input" value={status} onChange={event => setStatus(event.target.value)}><option value="">All items</option>{statuses.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></ToolbarFilter>
      </DataToolbar>
      {rows.length === 0 ? <EmptyState title="No specifications recorded yet" hint="The categories below are a checklist, not a statement of what is included. Add the project's verified specifications to build the sales guide." /> : shown.length === 0 ? <EmptyState title="No matching specifications" hint="Change the search or filters to see more items." /> : null}
      {categories.map(category => {
        const items = shown.filter(item => item.category === category.value);
        if (!items.length && (search || scope || status)) return null;
        return <Card key={category.value} title={category.label} description={category.hint}>
          {items.length ? <div className="stack">{items.map(item => <article key={item.id} className="stack stack-tight">
            <SectionHeader title={item.title} actions={canWrite ? <Button onClick={() => setEditing(item)}>Edit</Button> : undefined} />
            <div><Badge tone={item.status === "confirmed" ? "success" : "warning"}>{item.status === "confirmed" ? "Confirmed" : "Draft — not confirmed"}</Badge>{" "}<Badge tone={item.inclusion === "included" && item.status === "confirmed" ? "success" : "neutral"}>{inclusions.find(value => value.value === item.inclusion)?.label}</Badge></div>
            <p><strong>{scopes.find(value => value.value === item.scope)?.label}:</strong> {item.applies_to}</p>
            <p className="specification-description">{item.description}</p>
            {item.brand_model ? <p><strong>Brand / model:</strong> {item.brand_model}</p> : null}
            <p className="footnote">Source: {item.source_reference || "Not recorded"} · Updated {businessDate(item.updated_at.slice(0, 10))}</p>
            {canWrite ? <DeleteRecordButton label={item.title} confirmLabel="Delete specification" description="Removes this item from the guide. Confirmed specifications and the audit history are retained." onDelete={reason => technicalSpecifications.remove(projectId, item.id, reason)} onDeleted={load} /> : null}
          </article>)}</div> : <p className="footnote">Not yet specified</p>}
        </Card>;
      })}
    </>}
  </section>;
}
