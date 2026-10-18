"use client";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import { matrices, type Framework, type MatrixFields, type MatrixRecord, type MatrixPoint } from "@/lib/api/matrix";
import { Button, ConfirmDialog, DraftBoundary, Field, FieldRow, FormActions, FormSection, Notice, PromptDialog, RecordPage, ValidationSummary } from "@/components/ui";
import { MatrixCanvas } from "./MatrixCanvas";
import { templates } from "./templates";

export function MatrixEditor({ projectId, framework, record, canManage, onClose, onSaved }: {
 projectId: string; framework: Framework; record?: MatrixRecord; canManage: boolean; onClose: () => void; onSaved: () => void;
}) {
 const [original] = useState<MatrixFields>(() => {
  const now = new Date();
  return { title: record?.title ?? "", framework, as_of: record?.as_of ?? [now.getFullYear(), String(now.getMonth()+1).padStart(2,"0"), String(now.getDate()).padStart(2,"0")].join("-"), context: record?.context ?? "", effect: record?.effect ?? "", growth_threshold_pct: record?.growth_threshold_pct ?? "10", items: record?.items ?? [] };
 });
 const [values, setValues] = useState(original);
 const [view, setView] = useState(Boolean(record));
 const [points, setPoints] = useState<MatrixPoint[]>(record?.points ?? []);
 const [busy, setBusy] = useState(false);
 const [error, setError] = useState<ApiError | string | null>(null);
 const [deleting, setDeleting] = useState(false);
 const [deleteError, setDeleteError] = useState<string | null>(null);
 const [removeIndex, setRemoveIndex] = useState<number | null>(null);
 const template = templates[framework];
 const dirty = JSON.stringify(original) !== JSON.stringify(values);
 const change = <K extends keyof MatrixFields>(key: K, value: MatrixFields[K]) => { setValues(previous => ({ ...previous, [key]: value })); setPoints([]); };
 const save = async () => {
  setBusy(true); setError(null);
  try { if (record) await matrices.update(projectId, record, values); else await matrices.create(projectId, values); onSaved(); }
  catch (caught) { setError(caught instanceof ApiError ? caught : "Could not save. Your inputs have been kept."); }
  finally { setBusy(false); }
 };
 return <RecordPage title={record?.title ?? `Create ${template.name}`} eyebrow="MATRIX STUDIO" icon="overview" subtitle={template.purpose} onClose={onClose}>
  <DraftBoundary dirty={dirty} busy={busy}>
   <div className="stack">
    <div className="matrix-mode-actions">
     {canManage ? <Button variant="default" disabled={busy} onClick={() => { setView(false); setError(null); }}>Edit inputs</Button> : null}
     <Button disabled={busy} variant={view ? "primary" : "default"} onClick={async () => {
      if (!dirty && record) { setPoints(record.points); setView(true); return; }
      setBusy(true); setError(null);
      try { setPoints(await matrices.preview(projectId, values)); setView(true); } catch (caught) { setError(caught instanceof ApiError ? caught : "Could not generate preview. Your inputs have been kept."); } finally { setBusy(false); }
     }}>{busy ? "Working…" : "View diagram"}</Button>
     {record && canManage ? <Button variant="danger" disabled={busy} onClick={() => setDeleting(true)}>Delete analysis</Button> : null}
    </div>
    <ValidationSummary error={error} />
    {view ? <><MatrixCanvas values={values} points={points}/>{dirty ? <Notice tone="info">Preview of unsaved inputs. Save this analysis to keep it.</Notice> : null}</> : canManage ? <form className="stack" onSubmit={event => { event.preventDefault(); if (!busy) void save(); }}>
     <fieldset disabled={busy} className="matrix-fields">
      <FormSection title="Set the scene" description="Name this analysis and state the date and evidence behind your observations.">
       <FieldRow><Field label="Analysis title"><input className="input" required maxLength={200} value={values.title} onChange={e => change("title", e.target.value)}/></Field><Field label="As at"><input className="input" required type="date" value={values.as_of} onChange={e => change("as_of", e.target.value)}/></Field></FieldRow>
       <Field label="Context & sources" optional><textarea className="input" rows={3} maxLength={4000} value={values.context} onChange={e => change("context", e.target.value)} placeholder="What are you analysing? Which sources or assumptions support it?"/></Field>
       {framework === "fishbone" ? <Field label="Problem / effect"><input className="input" required maxLength={300} value={values.effect} onChange={e => change("effect", e.target.value)} placeholder="The specific problem you want to understand"/></Field> : null}
       {framework === "bcg" ? <Field label="High-growth threshold (%)"><input className="input" required type="number" min="0.001" max="100" step="0.001" value={values.growth_threshold_pct} onChange={e => change("growth_threshold_pct", e.target.value)}/></Field> : null}
      </FormSection>
      <FormSection title={framework === "bcg" ? "Products & business units" : "Build your analysis"} description={framework === "bcg" ? "Relative market share is your share divided by the largest competitor’s share. Enter it as a multiple: 1 means equal share. Use comparable markets and periods." : "Add one idea per item, choose its category and record supporting notes. Up to 100 items per analysis."}>
       <div className="matrix-input-list">{values.items.map((item, index) => <div className="matrix-input-item" key={index}>
        <div className="matrix-item-number">Item {index + 1}<Button variant="quiet" onClick={() => setRemoveIndex(index)}>Delete item {index + 1}</Button></div>
        <FieldRow><Field label={framework === "bcg" ? "Product / business unit" : "Observation / idea"}><input className="input" required maxLength={300} value={item.label} onChange={e => change("items", values.items.map((row, i) => i === index ? { ...row, label: e.target.value } : row))}/></Field>
        {framework !== "bcg" ? <Field label="Category"><select className="input" value={item.category} onChange={e => change("items", values.items.map((row, i) => i === index ? { ...row, category: e.target.value } : row))}>{template.categories.map(category => <option key={category}>{category}</option>)}</select></Field> : null}</FieldRow>
        {framework === "bcg" ? <FieldRow><Field label="Market growth (%)"><input className="input" required type="number" min="-100" max="1000" step="0.001" value={item.growth_pct ?? ""} onChange={e => change("items", values.items.map((row, i) => i === index ? { ...row, growth_pct: e.target.value || null } : row))}/></Field><Field label="Relative market share (×)"><input className="input" required type="number" min="0" max="1000" step="0.001" value={item.relative_share ?? ""} onChange={e => change("items", values.items.map((row, i) => i === index ? { ...row, relative_share: e.target.value || null } : row))}/></Field></FieldRow> : null}
        <Field label="Notes / evidence" optional><textarea className="input" rows={2} maxLength={2000} value={item.notes} onChange={e => change("items", values.items.map((row, i) => i === index ? { ...row, notes: e.target.value } : row))}/></Field>
       </div>)}</div>
       <Button variant="default" disabled={values.items.length >= 100} onClick={() => change("items", [...values.items, { label: "", notes: "", category: framework === "bcg" ? "" : template.categories[0], growth_pct: null, relative_share: null }])}>Add {framework === "bcg" ? "product / business unit" : "idea"}</Button>
      </FormSection>
     </fieldset>
     <FormActions><Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save analysis"}</Button><Button variant="default" disabled={busy} data-leaves-editor onClick={onClose}>Cancel</Button></FormActions>
    </form> : null}
    {view && canManage && (!record || dirty) ? <FormActions><Button disabled={busy} onClick={() => void save()}>Save analysis</Button></FormActions> : null}
   </div>
  </DraftBoundary>
  {removeIndex !== null ? <ConfirmDialog title={`Delete item ${removeIndex + 1}?`} body={`Remove “${values.items[removeIndex].label || "empty item"}” from this analysis? The change takes effect when you save.`} confirmLabel="Delete item" onCancel={() => setRemoveIndex(null)} onConfirm={() => { change("items", values.items.filter((_, i) => i !== removeIndex)); setRemoveIndex(null); }}/> : null}
  {deleting && record ? <PromptDialog title={`Delete “${record.title}”?`} description="Removes this analysis from Matrix. Its saved content and audit history are retained." label="Reason" confirmLabel="Delete analysis" destructive busy={busy} error={deleteError} onCancel={() => setDeleting(false)} onSubmit={async reason => {
   setBusy(true); setDeleteError(null);
   try { await matrices.remove(projectId, record, reason); setDeleting(false); onSaved(); } catch(caught) { setDeleteError(caught instanceof ApiError ? caught.message : "Could not delete. Please try again."); } finally { setBusy(false); }
  }}/> : null}
 </RecordPage>;
}
