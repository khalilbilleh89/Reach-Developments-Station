"use client";

import { useState } from "react";
import type { UnitSummary } from "@/lib/api";
import { masterplans } from "@/lib/api/masterplans";
import type { Footprint, Masterplan, Point, PlanInput } from "@/lib/api/masterplans";
import { Button, Disclosure, DraftBoundary, Field, Notice, RecordPage } from "@/components/ui";
import { MasterplanCanvas } from "./MasterplanCanvas";

const message = (error: unknown) => error instanceof Error ? error.message : "Could not save. Your draft is retained.";

export function PlanEditor({ projectId, plan, onClose, onSaved }: { projectId: string; plan?: Masterplan; onClose: () => void; onSaved: (plan: Masterplan) => void }) {
  const initial: PlanInput = { title: plan?.title ?? "", source_reference: plan?.source_reference ?? "", kind: plan?.kind ?? "plan", width_m: plan?.width_m ?? null };
  const [values, setValues] = useState(initial), [file, setFile] = useState<File | null>(null), [page, setPage] = useState("1");
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null);
  return <RecordPage title={plan ? `Edit ${plan.title}` : "Upload a drawing or 3D reference"} onClose={onClose}>
    <DraftBoundary dirty={JSON.stringify(values) !== JSON.stringify(initial) || !!file} busy={busy}>
      <form className="stack" onSubmit={async e => {
        e.preventDefault(); if (busy) return; setBusy(true); setError(null);
        try {
          if (!plan && (!file || file.size > 10 * 1024 * 1024)) throw new Error("Choose a file up to 10 MiB.");
          const saved = plan ? await masterplans.update(projectId, plan, values) : await masterplans.upload(projectId, file!, values, Number(page) - 1);
          onSaved(saved);
        } catch (error) { setError(message(error)); } finally { setBusy(false); }
      }}>
        <Notice tone="info">Upload a masterplan, floor drawing, elevation or rendered project image. One PDF page becomes one selectable view. Geometry is traced and linked to existing units after upload.</Notice>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <Field label="View title"><input required maxLength={200} value={values.title} onChange={e => setValues({ ...values, title: e.target.value })} /></Field>
        <Field label="Drawing reference / revision" hint="Record the drawing number, revision and date from your source."><input required maxLength={500} value={values.source_reference} onChange={e => setValues({ ...values, source_reference: e.target.value })} /></Field>
        <Field label="View type"><select value={values.kind} onChange={e => setValues({ ...values, kind: e.target.value as Masterplan["kind"] })}><option value="plan">Plan: mapped footprints and 3D massing</option><option value="render">3D reference image: selectable hotspots</option><option value="elevation">Elevation / section: selectable hotspots</option></select></Field>
        <Field label="Full image width in metres" optional hint="For plan views only. Use the measured width of the entire uploaded page, including margins; do not enter a building width or scale denominator. Required for spatial 3D."><input type="number" min="0.0001" max="10000" step="0.0001" value={values.width_m ?? ""} onChange={e => setValues({ ...values, width_m: e.target.value || null })} /></Field>
        {!plan ? <><Field label="PDF or image" hint="PDF, PNG, JPEG or WebP; maximum 10 MiB. Originals stay unchanged."><input required type="file" accept="application/pdf,image/png,image/jpeg,image/webp" onChange={e => setFile(e.target.files?.[0] ?? null)} /></Field><Field label="PDF page" hint="Starts at 1. Upload additional pages as separate views."><input type="number" min="1" max="1000" required value={page} onChange={e => setPage(e.target.value)} /></Field></> : <p>Source file: {plan.filename}, page {plan.page_number + 1}. Upload a new view for a revised drawing so existing footprints keep their source.</p>}
        <div className="button-row"><Button type="submit" variant="primary" disabled={busy}>{busy ? "Saving…" : plan ? "Save drawing" : "Upload drawing"}</Button><Button data-leaves-editor onClick={onClose}>Cancel</Button></div>
      </form>
    </DraftBoundary>
  </RecordPage>;
}

export function FootprintEditor({ projectId, plan, mappings, units, mapping, onClose, onSaved }: { projectId: string; plan: Masterplan; mappings: Footprint[]; units: UnitSummary[]; mapping?: Footprint; onClose: () => void; onSaved: () => void }) {
  const [unit, setUnit] = useState(mapping?.unit_id ?? ""), [points, setPoints] = useState<Point[]>(mapping?.points ?? []);
  const [base, setBase] = useState(mapping?.base_m ?? ""), [height, setHeight] = useState(mapping?.height_m ?? "");
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null);
  const initial = JSON.stringify([mapping?.unit_id ?? "", mapping?.points ?? [], mapping?.base_m ?? "", mapping?.height_m ?? ""]);
  const dirty = JSON.stringify([unit, points, base, height]) !== initial;
  return <RecordPage title={mapping ? "Edit unit footprint" : "Map a unit"} onClose={onClose}>
    <DraftBoundary dirty={dirty} busy={busy}>
      <form className="stack" onSubmit={async e => {
        e.preventDefault(); if (busy) return; setBusy(true); setError(null);
        try { await masterplans.saveMapping(projectId, plan.id, { unit_id: unit, points, base_m: base, height_m: height }, mapping); onSaved(); }
        catch (error) { setError(message(error)); } finally { setBusy(false); }
      }}>
        <Notice tone="info">Select an existing unit, then click its boundary corners in order. Use Undo or the coordinate list to correct it. Heights are explicit modelling inputs and do not change approved inventory areas or sale status.</Notice>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <Field label="Inventory unit"><select required value={unit} onChange={e => setUnit(e.target.value)}><option value="">Select unit</option>{units.filter(u => u.id === mapping?.unit_id || !mappings.some(m => m.unit_id === u.id)).map(u => <option value={u.id} key={u.id}>{u.unit_reference} · {[u.building_code, u.floor_code].filter(Boolean).join(" / ")}</option>)}</select></Field>
        <div className="masterplan-controls"><Field label="Base elevation in metres" hint="Relative to this plan's modelling datum."><input required type="number" min="0" max="1000" step="0.0001" value={base} onChange={e => setBase(e.target.value)} /></Field><Field label="Unit height in metres"><input required type="number" min="0.0001" max="1000" step="0.0001" value={height} onChange={e => setHeight(e.target.value)} /></Field></div>
        <MasterplanCanvas plan={plan} preview={masterplans.preview(projectId, plan.id)} mappings={mappings.filter(m => m.id !== mapping?.id)} units={units} draft={points} onPoint={point => { if (points.length < 64) setPoints([...points, point]); }} />
        <div className="button-row"><Button disabled={!points.length} onClick={() => setPoints(points.slice(0, -1))}>Undo vertex</Button><Button disabled={!points.length} onClick={() => setPoints([])}>Clear outline</Button><Button disabled={points.length >= 64} onClick={() => setPoints([...points, [0.5, 0.5]])}>Add vertex by coordinates</Button></div>
        <Disclosure title="Vertex coordinates (fractions of the full image)"><ol className="masterplan-vertices">{points.map((point, i) => <li key={i}><Field label={`Vertex ${i + 1} X`}><input required type="number" min="0" max="1" step="any" value={point[0]} onChange={e => setPoints(points.map((p, j) => j === i ? [Number(e.target.value), p[1]] : p))} /></Field><Field label={`Vertex ${i + 1} Y`}><input required type="number" min="0" max="1" step="any" value={point[1]} onChange={e => setPoints(points.map((p, j) => j === i ? [p[0], Number(e.target.value)] : p))} /></Field><Button onClick={() => setPoints(points.filter((_, j) => j !== i))}>Remove vertex {i + 1}</Button></li>)}</ol></Disclosure>
        <div className="button-row"><Button type="submit" variant="primary" disabled={busy || points.length < 3}>{busy ? "Saving…" : "Save footprint"}</Button><Button data-leaves-editor onClick={onClose}>Cancel</Button></div>
      </form>
    </DraftBoundary>
  </RecordPage>;
}
