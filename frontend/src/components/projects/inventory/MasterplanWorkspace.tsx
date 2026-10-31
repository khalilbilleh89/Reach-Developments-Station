"use client";

import { useEffect, useState } from "react";
import type { UnitSummary } from "@/lib/api";
import { useAnswer } from "@/lib/answer";
import { masterplans } from "@/lib/api/masterplans";
import type { Footprint, Masterplan } from "@/lib/api/masterplans";
import { Badge, Button, EmptyState, Field, Loading, Notice, RecordLink, RecordPage, SectionHeader, Segmented, StatusDot, TableScroll } from "@/components/ui";
import { useRegisterFields } from "@/components/shell/registerState";
import { DeleteRecordButton } from "../DeleteRecordButton";
import { FootprintEditor, PlanEditor } from "./MasterplanEditors";
import { MasterplanCanvas } from "./MasterplanCanvas";
import { statusLabel, statusTone } from "./statusLabels";
import { stockArea } from "./StockView";

export function MasterplanWorkspace({ projectId, canWrite }: { projectId: string; canWrite: boolean }) {
  const [fields, setFields] = useRegisterFields({ masterplan: "", masterplan_mode: "plan", masterplan_search: "", masterplan_state: "" });
  const [editingPlan, setEditingPlan] = useState<Masterplan | "new" | null>(null);
  const [editingMapping, setEditingMapping] = useState<Footprint | "new" | null>(null);
  const [sourceError, setSourceError] = useState<string | null>(null);
  const [presenting, setPresenting] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const plans = useAnswer(true, () => masterplans.list(projectId), [projectId]);
  const units = useAnswer(true, () => masterplans.units(projectId), [projectId]);
  const [unitSnapshot, setUnitSnapshot] = useState<UnitSummary[] | null>(null);
  if (units.status === "ready" && unitSnapshot !== units.data) setUnitSnapshot(units.data);
  const unitRows = units.status === "ready" ? units.data : unitSnapshot;
  const plan = plans.status === "ready" ? plans.data.find(p => p.id === fields.masterplan) ?? plans.data[0] : undefined;
  const mappings = useAnswer(!!plan, () => masterplans.mappings(projectId, plan!.id), [projectId, plan?.id]);
  const [refreshTime, setRefreshTime] = useState<string | null>(null);
  const retryUnits = units.retry;
  useEffect(() => {
    const refresh = () => { if (document.visibilityState === "visible" && !editingPlan && !editingMapping) { retryUnits(); setRefreshTime(new Date().toLocaleTimeString()); } };
    const timer = window.setInterval(refresh, 30000);
    window.addEventListener("focus", refresh);
    return () => { window.clearInterval(timer); window.removeEventListener("focus", refresh); };
  }, [retryUnits, editingPlan, editingMapping]);
  const refreshMappings = async () => { setEditingMapping(null); setSelected(null); mappings.retry(); };
  const refreshPlans = async () => { setEditingPlan(null); setSelected(null); plans.retry(); };
  if (plans.status === "denied" || units.status === "denied" || mappings.status === "denied") return <Notice tone="info">Masterplan requires whole-project access. A drawing can expose every phase.</Notice>;
  if (plans.status === "failed" || units.status === "failed" || mappings.status === "failed") return <Notice tone="error">{plans.status === "failed" ? plans.message : units.status === "failed" ? units.message : mappings.status === "failed" ? mappings.message : "Could not load masterplan."}<Button onClick={() => { plans.retry(); units.retry(); mappings.retry(); }}>Retry</Button></Notice>;
  const editor = editingPlan ? <PlanEditor projectId={projectId} plan={editingPlan === "new" ? undefined : editingPlan} onClose={() => setEditingPlan(null)} onSaved={saved => { setFields({ masterplan: saved.id }); void refreshPlans(); }} /> : null;
  if (plans.status !== "ready" || !unitRows) return <Loading label="Loading project masterplan and inventory" />;
  if (!plan) return <><EmptyState icon="inventory" title="Bring the project into view" hint="Upload your masterplan and floor drawings, then link their unit outlines to live inventory. Add project renders as separate interactive views." actions={canWrite ? <Button variant="primary" onClick={() => setEditingPlan("new")}>Upload first drawing</Button> : undefined} />{editor}</>;
  if (mappings.status !== "ready") return <Loading label="Loading unit footprints" />;
  const mapping = mappings.data.find(m => m.id === selected);
  const unit = unitRows.find(u => u.id === mapping?.unit_id);
  const filtered = mappings.data.filter(m => {
    const u = unitRows.find(u => u.id === m.unit_id);
    return (!fields.masterplan_search || u?.unit_reference.toLowerCase().includes(fields.masterplan_search.toLowerCase())) && (!fields.masterplan_state || u?.commercial_status === fields.masterplan_state);
  });
  return <section className="stack">
    <SectionHeader title="Project masterplan" description="Find a unit in the project and open its live inventory record." actions={<div className="button-row"><Button onClick={() => setPresenting(true)}>Present masterplan</Button>{canWrite ? <Button variant="primary" onClick={() => setEditingPlan("new")}>Upload drawing / render</Button> : null}</div>} />
    <div className="masterplan-controls">
      <Field label="Drawing / project view"><select value={plan.id} onChange={e => { setFields({ masterplan: e.target.value }); setSelected(null); }} >{plans.data.map(p => <option key={p.id} value={p.id}>{p.title}</option>)}</select></Field>
      <Field label="View"><Segmented label="View" value={fields.masterplan_mode} onChange={masterplan_mode => setFields({ masterplan_mode })} options={plan.kind === "plan" && plan.width_m ? [{ value: "plan", label: "Drawing / image" }, { value: "3d", label: "3D massing" }] : [{ value: "plan", label: "Drawing / image" }]} /></Field>
      <Field label="Find unit"><input type="search" value={fields.masterplan_search} onChange={e => setFields({ masterplan_search: e.target.value })} placeholder="Unit reference" /></Field>
      <Field label="Commercial status"><select value={fields.masterplan_state} onChange={e => setFields({ masterplan_state: e.target.value })}><option value="">All statuses</option>{["available", "held", "reserved", "contract_pending", "contracted", "unreleased", "cancelled", "returned"].map(state => <option key={state} value={state}>{statusLabel(state)}</option>)}</select></Field>
    </div>
    {units.status === "loading" ? <Notice tone="info">Refreshing availability. The previous inventory response remains visible until the refresh completes.</Notice> : null}
    <div className="masterplan-caption"><span>{plan.source_reference} · {plan.filename} · page {plan.page_number + 1}</span><div className="button-row"><Button onClick={() => { setSourceError(null); void masterplans.source(projectId, plan).catch(error => setSourceError(error instanceof Error ? error.message : "Could not download source.")); }}>Download source</Button><Button onClick={() => { units.retry(); mappings.retry(); plans.retry(); }}>Refresh inventory</Button></div></div>
    {sourceError ? <Notice tone="error">{sourceError}</Notice> : null}
    <p className="muted">Availability is read from inventory and refreshes every 30 seconds while this page is visible. {refreshTime ? `Refresh requested at ${refreshTime}.` : "Use Refresh inventory before confirming availability with a buyer."} Commercial and legal statuses remain separate.</p>
    {fields.masterplan_mode === "3d" && plan.kind === "plan" && plan.width_m ? <Notice tone="info">Schematic 3D massing from traced outlines, calibrated image width and recorded heights. Reference renders remain separate views; this is not a photorealistic or survey model.</Notice> : !plan.width_m && plan.kind === "plan" ? <Notice tone="info">Calibrate the full drawing width in metres to enable 3D massing. Map units on the plan first.</Notice> : null}
    <MasterplanCanvas key={plan.id} plan={plan} preview={masterplans.preview(projectId, plan.id)} mappings={filtered} units={unitRows} threeD={fields.masterplan_mode === "3d"} selected={selected ?? undefined} onSelect={m => setSelected(m.id)} />
    <div className="masterplan-legend" aria-label="Commercial status legend">{["available", "held", "reserved", "contract_pending", "contracted", "unreleased"].map(state => <Badge key={state} tone={statusTone(state)}>{statusLabel(state)}</Badge>)}</div>
    <div className="button-row">{canWrite ? <><Button onClick={() => setEditingMapping("new")}>Map a unit</Button><Button onClick={() => setEditingPlan(plan)}>Edit drawing / calibration</Button><DeleteRecordButton label={plan.title} description="Remove this uploaded view after deleting its footprints. Inventory, sales and audit history are retained. The original business file is unchanged." onDelete={reason => masterplans.removePlan(projectId, plan, reason)} onDeleted={refreshPlans} /></> : null}</div>
    {!mappings.data.length ? <Notice tone="info">No units are mapped yet. The drawing does not determine availability or create inventory units.</Notice> : null}
    <SectionHeader title="Mapped units" description="Every outline on this view, with the same filters; select a unit here or on the drawing." />
    <TableScroll label="Mapped units"><thead><tr><th scope="col">Unit</th><th scope="col">Location</th><th scope="col">Commercial status</th><th scope="col">Action</th></tr></thead><tbody>{filtered.map(m => { const u = unitRows.find(u => u.id === m.unit_id); return <tr key={m.id}><th scope="row">{u?.unit_reference ?? "Unit unavailable"}</th><td>{[u?.building_code, u?.floor_code].filter(Boolean).join(" / ")}</td><td>{u ? <StatusDot tone={statusTone(u.commercial_status)}>{statusLabel(u.commercial_status)}</StatusDot> : <span className="muted">Outside active inventory</span>}</td><td><Button onClick={() => setSelected(m.id)}>Select unit</Button></td></tr>; })}</tbody></TableScroll>
    {presenting && !mapping && !editingMapping && !editingPlan ? <RecordPage title={plan.title} subtitle={plan.source_reference} onClose={() => setPresenting(false)} actions={<Button onClick={() => setFields({ masterplan_mode: fields.masterplan_mode === "3d" ? "plan" : "3d" })} disabled={plan.kind !== "plan" || !plan.width_m}>{fields.masterplan_mode === "3d" ? "Show drawing" : "Show 3D"}</Button>}>
      <p>{units.status === "loading" ? "Refreshing inventory; previous status shown. " : ""}Choose a unit to see its availability and open Unit 360. Colours follow inventory commercial status; modelling geometry is schematic.</p>
      <MasterplanCanvas key={`presentation-${plan.id}`} plan={plan} preview={masterplans.preview(projectId, plan.id)} mappings={filtered} units={unitRows} threeD={fields.masterplan_mode === "3d"} onSelect={m => setSelected(m.id)} />
      <div className="masterplan-legend">{["available", "held", "reserved", "contract_pending", "contracted", "unreleased"].map(state => <Badge key={state} tone={statusTone(state)}>{statusLabel(state)}</Badge>)}</div>
    </RecordPage> : null}
    {mapping && !editingMapping ? <RecordPage title={unit?.unit_reference ?? "Unit unavailable"} subtitle={unit ? [unit.building_code, unit.floor_code].filter(Boolean).join(" / ") : "This mapping is retained; its unit is no longer in active inventory."} onClose={() => setSelected(null)} status={unit ? <><Badge tone={statusTone(unit.commercial_status)}>{statusLabel(unit.commercial_status)}</Badge><span>{units.status === "loading" ? "Refreshing inventory; previous status shown. " : ""}Legal: {statusLabel(unit.legal_status)} · Collection: {statusLabel(unit.collection_status)} · Delivery: {statusLabel(unit.delivery_status)}</span></> : undefined} facts={unit ? [{ label: "Bedrooms", value: unit.bedrooms ?? "Not recorded" }, { label: "Gross area", value: stockArea(unit.gross_area, unit.gross_area_unit) }, { label: "Net area", value: stockArea(unit.net_area, unit.net_area_unit) }, { label: "View", value: unit.view_class_code ?? "Not recorded" }] : undefined}>
      <div className="stack"><MasterplanCanvas plan={plan} preview={masterplans.preview(projectId, plan.id)} mappings={[mapping]} units={unitRows} selected={mapping.id} />{unit ? <RecordLink projectId={projectId} kind="unit" id={unit.id} tab="detail">Open Unit 360: details, pricing, documents and sales</RecordLink> : null}<div className="button-row">{canWrite ? <><Button onClick={() => setEditingMapping(mapping)}>Edit footprint</Button><DeleteRecordButton label={`footprint ${unit?.unit_reference ?? "for inactive unit"}`} description="Remove this outline from the drawing. The unit, its sales records and audit history remain." onDelete={reason => masterplans.removeMapping(projectId, plan.id, mapping, reason)} onDeleted={refreshMappings} /></> : null}</div></div>
    </RecordPage> : null}
    {editingMapping ? <FootprintEditor projectId={projectId} plan={plan} mappings={mappings.data} units={unitRows} mapping={editingMapping === "new" ? undefined : editingMapping} onClose={() => setEditingMapping(null)} onSaved={() => void refreshMappings()} /> : null}
    {editor}
  </section>;
}
