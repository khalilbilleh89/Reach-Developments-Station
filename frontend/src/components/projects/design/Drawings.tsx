"use client";

import * as ui from "@/components/ui";
import { useState } from "react";
import { useAnswer } from "@/lib/answer";
import { drawings, planCategories, drawingCategories, drawingStatuses, filterDrawings } from "@/lib/api/drawings";
import type { Drawing, DrawingFields } from "@/lib/api/drawings";
import { Badge, Button, ButtonRow, Card, ChoiceCards, Disclosure, Icon, DataToolbar, DraftBoundary, EmptyState, Field, FieldRow, FilterChips, FormActions, Loading, Notice, RecordPage, SectionHeader, Segmented, ToolbarFilter } from "@/components/ui";
import { DeleteRecordButton } from "../DeleteRecordButton";

const blank: DrawingFields = { name: "", category: "architecture", drawing_number: "", location: "", revision: "", status: "reference", notes: "" };
const fieldsOf = (row?: Drawing): DrawingFields => row ? Object.fromEntries(Object.keys(blank).map(key => [key, row[key as keyof DrawingFields]])) as unknown as DrawingFields : { ...blank };
const message = (error: unknown) => error instanceof Error ? error.message : "Could not save the drawing.";

export function DrawingForm({ row, onSave, onClose, onSaved }: { row?: Drawing; onSave: (fields: DrawingFields, file: File | null) => Promise<unknown>; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState(() => fieldsOf(row));
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reset = () => { setForm(fieldsOf(row)); setFile(null); };
  return <RecordPage icon="blueprint" title={row ? "Edit plan details" : "Add plan"} subtitle={row?.filename ?? "Give your plan a title, choose its discipline and upload the PDF."} onClose={onClose}>
    <Card title="Plan details" description="Title, category and PDF. Add extra details only when you need them.">
      <DraftBoundary dirty={JSON.stringify(form) !== JSON.stringify(fieldsOf(row)) || !!file} busy={busy} onDiscard={reset}>
        <form className="stack" onSubmit={async event => {
          event.preventDefault(); setError(null);
          if (!form.name.trim()) { setError("Enter a plan title."); return; }
          if (!row && !file) { setError("Choose a PDF file."); return; }
          setBusy(true);
          try { await onSave({ ...form, name: form.name.trim() }, file); onSaved(); onClose(); }
          catch (caught) { setError(message(caught)); } finally { setBusy(false); }
        }}>
          {error ? <Notice tone="error">{error}</Notice> : null}
          <fieldset className="draft-fields" disabled={busy}><Field label="Plan title"><input className="input" required maxLength={320} disabled={busy} placeholder="e.g. Ground floor — architectural plan" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></Field>
          <ChoiceCards label="Category" name="plan-category" value={form.category} columns={3} required onChange={value => setForm({ ...form, category: value as DrawingFields["category"] })} options={[...Object.entries(planCategories), ...(!Object.hasOwn(planCategories, form.category) ? [[form.category, drawingCategories[form.category]]] : [])].map(([value, label]) => ({value, label}))} />
          {!row ? <Field label="PDF file" hint="Up to 10 MB. Upload revisions separately to preserve the earlier drawing."><input className="input" type="file" accept=".pdf,application/pdf" required disabled={busy} onChange={e => setFile(e.target.files?.[0] ?? null)} /></Field> : <p className="footnote">The original PDF is retained. To add a new revision, upload it as another drawing.</p>}
          <Disclosure title="More details (optional)"><FieldRow columns={2}>
            <Field label="Drawing status" hint="A library label; it does not record consultant or authority approval."><select className="input" disabled={busy} value={form.status} onChange={e => setForm({ ...form, status: e.target.value as DrawingFields["status"] })}>{Object.entries(drawingStatuses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
            <Field label="Drawing number" optional><input className="input" maxLength={120} disabled={busy} value={form.drawing_number} onChange={e => setForm({ ...form, drawing_number: e.target.value })} placeholder="e.g. A-101" /></Field>
            <Field label="Building / floor / location" optional><input className="input" maxLength={200} disabled={busy} value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} placeholder="e.g. Building A · Ground floor" /></Field>
            <Field label="Revision" optional><input className="input" maxLength={80} disabled={busy} value={form.revision} onChange={e => setForm({ ...form, revision: e.target.value })} placeholder="e.g. R02" /></Field>
          </FieldRow>
          <Field label="Notes" optional><textarea className="input" maxLength={2000} rows={3} disabled={busy} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} /></Field>
          </Disclosure></fieldset>
          <FormActions><Button type="submit" variant="primary" disabled={busy}>{busy ? "Saving…" : row ? "Save details" : "Upload plan"}</Button></FormActions>
        </form>
      </DraftBoundary>
    </Card>
  </RecordPage>;
}

export function DrawingViewer({ projectId, row, onClose }: { projectId: string; row: Drawing; onClose: () => void }) {
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(100);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const preview = useAnswer(true, () => drawings.preview(projectId, row, page), [projectId, row.id, page]);
  return <RecordPage icon="blueprint" title={row.name} subtitle={[row.drawing_number, row.location, row.revision && `Revision ${row.revision}`].filter(Boolean).join(" · ")} onClose={onClose} actions={<Button disabled={downloading} onClick={async () => { setDownloading(true); setError(null); try { await drawings.download(projectId, row); } catch (caught) { setError(message(caught)); } finally { setDownloading(false); } }}>{downloading ? "Downloading…" : "Download original PDF"}</Button>}>
    <div className="stack">
      <div className="row-actions"><Badge>{drawingCategories[row.category]}</Badge><Badge tone={row.status === "superseded" ? "muted" : "neutral"}>{drawingStatuses[row.status]}</Badge><span className="footnote">{row.filename}</span></div>
      {row.notes ? <p className="drawing-notes">{row.notes}</p> : null}
      {row.status === "superseded" ? <Notice tone="warning">This drawing is marked superseded. Check for a newer revision before using it.</Notice> : null}
      {error ? <Notice tone="error">{error}</Notice> : null}
      <div className="drawing-view-controls">
        <ButtonRow><Button disabled={page <= 1 || preview.status === "loading"} onClick={() => setPage(page - 1)}>Previous page</Button><span aria-live="polite">Page {page}{preview.status === "ready" ? ` of ${preview.data.page_count}` : ""}</span><Button disabled={preview.status !== "ready" || page >= preview.data.page_count} onClick={() => setPage(page + 1)}>Next page</Button></ButtonRow>
        <form className="row-actions" onSubmit={event => {
          event.preventDefault();
          const target = Number(new FormData(event.currentTarget).get("page"));
          if (preview.status === "ready" && Number.isInteger(target) && target >= 1 && target <= preview.data.page_count) setPage(target);
        }}><Field label="Go to page"><input key={page} className="input" name="page" type="number" min={1} max={preview.status === "ready" ? preview.data.page_count : undefined} defaultValue={page} required disabled={preview.status !== "ready"} /></Field><Button type="submit" disabled={preview.status !== "ready"}>Go</Button></form>
        <Field label="Zoom"><Segmented label="Zoom" value={String(zoom)} onChange={value => setZoom(Number(value))} options={[{ value: "100", label: "Fit width" }, { value: "150", label: "150%" }, { value: "200", label: "200%" }, { value: "300", label: "300%" }]} /></Field>
      </div>
      {preview.status === "loading" ? <Loading label="Opening drawing page…" /> : null}
      {preview.status === "denied" ? <Notice tone="warning">This drawing is no longer available to your account.</Notice> : null}
      {preview.status === "failed" ? <><Notice tone="error">{preview.message} You can still download the original PDF.</Notice><Button onClick={preview.retry}>Retry preview</Button></> : null}
      {preview.status === "ready" ? <div className="drawing-canvas" tabIndex={0} role="region" aria-label="Drawing page. Scroll to inspect the enlarged plan.">
        {/* The source is a server-rendered page image, never executable PDF content. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={preview.data.image} alt={`${row.name}, page ${page}`} style={{ width: `${zoom}%` }} />
      </div> : null}
      <p className="footnote">Preview for review. Download the original PDF for full vector detail and printing to scale.</p>
    </div>
  </RecordPage>;
}

export function Drawings({ projectId, canWrite }: { projectId: string; canWrite: boolean }) {
  const answer = useAnswer(true, () => drawings.list(projectId), [projectId]);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [editor, setEditor] = useState<{ row?: Drawing } | null>(null);
  const [viewing, setViewing] = useState<Drawing | null>(null);
  // The barrel's hook, or a no-op where a test harness stands the barrel in.
  const { toast } = typeof ui.useToast === "function" ? ui.useToast() : { toast: () => {} };
  const setNotice = (text: string | null) => { if (text) toast({ title: text }); };
  const rows = answer.status === "ready" ? filterDrawings(answer.data, search, category, status) : [];
  return <div className="stack">
    <SectionHeader level={2} title="Plan library" description="Choose a discipline, find your plan and open it without leaving the project." actions={canWrite ? <Button variant="primary" onClick={() => setEditor({})}>Add plan</Button> : undefined} />
    <ChoiceCards label="Browse by discipline" name="browse-plans" value={category} columns={3} onChange={setCategory} options={[
      { value: "", label: "All plans", description: "Across every discipline" },
      ...Object.entries(planCategories).map(([value, label]) => ({value, label, description: ({architecture: "Layouts, elevations & spaces", electrical: "Power, lighting & systems", mechanical: "Services, ventilation & plumbing", structure: "Foundations, frame & details", shop_drawing: "Fabrication & installation"} as Record<string, string>)[value]})),
    ]} />
    <DataToolbar framed search={{ value: search, onChange: setSearch, placeholder: "Name, number, floor or revision…", label: "Find a plan" }}
      count={answer.status === "ready" ? { shown: rows.length, total: answer.data.length, noun: "plan" } : undefined}
      onReset={search || category || status ? () => { setSearch(""); setCategory(""); setStatus(""); } : undefined}>
      <ToolbarFilter label="Category" active={category !== ""}><select className="input" value={category} onChange={e => setCategory(e.target.value)}><option value="">All categories</option>{Object.entries(drawingCategories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></ToolbarFilter>
      <ToolbarFilter label="Status" active={status !== ""}><select className="input" value={status} onChange={e => setStatus(e.target.value)}><option value="">All statuses</option>{Object.entries(drawingStatuses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></ToolbarFilter>
    </DataToolbar>
    <FilterChips onClearAll={() => { setSearch(""); setCategory(""); setStatus(""); }} chips={[
      ...(category ? [{ key: "category", label: `Category: ${drawingCategories[category as keyof typeof drawingCategories] ?? category}`, onRemove: () => setCategory("") }] : []),
      ...(status ? [{ key: "status", label: `Status: ${drawingStatuses[status as keyof typeof drawingStatuses] ?? status}`, onRemove: () => setStatus("") }] : []),
      ...(search ? [{ key: "search", label: `“${search}”`, onRemove: () => setSearch("") }] : []),
    ]} />
    {answer.status === "loading" ? <Loading label="Loading plans…" shape="rows" /> : null}
    {answer.status === "failed" ? <><Notice tone="error">{answer.message}</Notice><Button onClick={answer.retry}>Retry plans</Button></> : null}
    {answer.status === "denied" ? <Notice tone="warning">Plans require whole-project Design access.</Notice> : null}
    {answer.status === "ready" && !rows.length ? <EmptyState title={answer.data.length ? "No matching plans" : "Your plan library starts here"} hint={answer.data.length ? "Change the search or clear the filters." : "Add named PDFs for floor plans, elevations, sections and engineering drawings."} /> : null}
    <div className="drawing-grid">{rows.map(row => <Card key={row.id}>
      <div className="stack drawing-card">
        <div className="plan-cover"><Icon name="blueprint" /><span>{drawingCategories[row.category]}</span><span className="mono">PDF</span></div>
        <div className="row-actions"><Badge>{drawingCategories[row.category]}</Badge><Badge tone={row.status === "superseded" ? "muted" : "neutral"}>{drawingStatuses[row.status]}</Badge></div>
        <h3><Button variant="link" onClick={() => setViewing(row)}>{row.name}</Button></h3>
        {row.drawing_number || row.location || row.revision ? <p className="footnote">{[row.drawing_number, row.location, row.revision && `Revision ${row.revision}`].filter(Boolean).join(" · ")}</p> : null}
        <p className="footnote">{row.filename}</p>
        <ButtonRow><Button onClick={() => setViewing(row)}>Open plan</Button>{canWrite ? <><Button variant="quiet" onClick={() => setEditor({ row })}>Edit details</Button><DeleteRecordButton label="plan" confirmLabel="Delete plan" recordName={row.name} description="Remove this drawing from the library. The original PDF and audit history are retained." onDelete={reason => drawings.remove(projectId, row, reason)} onDeleted={async () => { setNotice("Plan removed. Its evidence remains in history."); answer.retry(); }} /></> : null}</ButtonRow>
      </div>
    </Card>)}</div>
    {editor ? <DrawingForm row={editor.row} onClose={() => setEditor(null)} onSaved={() => { setNotice(editor.row ? "Plan details updated." : "Plan uploaded."); answer.retry(); }} onSave={async (fields, file) => {
      if (editor.row) return drawings.update(projectId, editor.row, fields);
      if (!file) throw new Error("Choose a PDF file.");
      return drawings.create(projectId, fields, file);
    }} /> : null}
    {viewing ? <DrawingViewer key={viewing.id} projectId={projectId} row={viewing} onClose={() => setViewing(null)} /> : null}
  </div>;
}
