"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { training, type AssetInput, type AssetKind, type TrainingMaterial } from "@/lib/api/training";
import { useAnswer } from "@/lib/answer";
import { hasAnyRole, PROJECT_WRITERS } from "@/lib/roles";
import { Badge, Button, Card, DraftBoundary, EmptyState, Field, FieldRow, FormActions, Loading, Notice, PageHeader, RecordPage, RegisterPagination, RowMenu, SectionHeader, TableScroll } from "@/components/ui";
import { sectionIcon } from "@/components/shell/navigation";
import { DeleteRecordButton } from "./DeleteRecordButton";

export function TrainingTab({ projectId, roles }: { projectId: string; roles: Set<string> }) {
  const canWrite = hasAnyRole(roles, PROJECT_WRITERS);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [kind, setKind] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<TrainingMaterial | null>(null);
  const [editor, setEditor] = useState<{ row?: TrainingMaterial } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const answer = useAnswer(true, () => training.list(projectId, search, category, kind, offset), [projectId, search, category, kind, offset]);
  const categories = answer.status === "ready" ? answer.data.categories : [];
  const refresh = () => { setSelected(null); answer.retry(); };
  const saveFile = async (row: TrainingMaterial) => {
    setError(null);
    try { await training.download(projectId, row); } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Download failed. Please retry."); }
  };
  if (editor) return <AssetEditor row={editor.row} categories={categories} onClose={() => setEditor(null)} onSave={async (values, file) => {
    if (editor.row) await training.update(projectId, editor.row, { title: values.title, category: values.category, description: values.description, execution_date: values.execution_date });
    else if (file) await training.upload(projectId, values, file);
    else await training.createLink(projectId, values);
    setEditor(null); refresh();
  }} />;
  if (selected) return <RecordPage title={selected.title} subtitle={`${selected.category} · ${selected.kind}`} onClose={() => { setSelected(null); setError(null); }}>
    <div className="stack"><SectionHeader title="Training details" actions={canWrite ? <Button variant="default" onClick={() => setEditor({ row: selected })}>Edit details</Button> : undefined} />
      {error ? <Notice tone="error">{error}</Notice> : null}
      <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{selected.description}</p><p>Execution date: {selected.execution_date}</p>
      {selected.external_url ? <><p className="muted">External reference. Access depends on the sharing permissions of its owner.</p><a href={selected.external_url} target="_blank" rel="noopener noreferrer" className="button">Open Drive / reference link</a></> : <>
        <AssetPreview key={selected.id} projectId={projectId} row={selected} />
        <Button variant="default" onClick={() => void saveFile(selected)}>Download {selected.filename}</Button>
      </>}
      {canWrite ? <RowMenu label={`Actions for ${selected.title}`}><DeleteRecordButton label="training" recordName={selected.title} description="Remove this item from Training. Stored files and audit history are retained. External Drive files are not changed." confirmLabel="Delete training" onDelete={reason => training.remove(projectId, selected, reason)} onDeleted={async () => { if (answer.status === "ready" && answer.data.items.length === 1 && offset > 0) setOffset(Math.max(0, offset - 25)); refresh(); }} /></RowMenu> : null}
    </div>
  </RecordPage>;
  const actions = canWrite ? <Button onClick={() => setEditor({})}>Add training</Button> : undefined;
  return <div className="stack">
    <PageHeader title="Training" icon={sectionIcon("training")} subtitle="Training sessions and learning materials, organized by category." actions={actions} />
    <Card>
      <FieldRow><Field label="Search training"><input type="search" className="input" value={search} onChange={e => { setSearch(e.target.value); setOffset(0); }} /></Field>
        <Field label="Category"><select className="input" value={category} onChange={e => { setCategory(e.target.value); setOffset(0); }}><option value="">All categories</option>{category && !categories.includes(category) ? <option value={category}>{category}</option> : null}{categories.map(value => <option key={value} value={value}>{value}</option>)}</select></Field>
        {<Field label="Material type"><select className="input" value={kind} onChange={e => { setKind(e.target.value); setOffset(0); }}><option value="">All types</option><option value="video">Video</option><option value="document">PDF / reference</option></select></Field>}
      </FieldRow>
      {answer.status === "loading" ? <Loading label="Loading training…" /> : null}
      {answer.status === "denied" ? <Notice tone="info">Attachments are not available to your access level.</Notice> : null}
      {answer.status === "failed" ? <Notice tone="error">{answer.message} <Button onClick={answer.retry}>Retry</Button></Notice> : null}
      {answer.status === "ready" ? <>{answer.data.items.length ? <TableScroll label="Training library"><thead><tr><th scope="col">Title</th><th scope="col">Execution date</th><th scope="col">Category</th><th scope="col">Type</th><th scope="col">Source</th></tr></thead><tbody>{answer.data.items.map(row => <tr key={row.id}><th scope="row"><Button variant="link" onClick={() => { setSelected(row); setError(null); }}>{row.title}</Button></th><td>{row.execution_date}</td><td>{row.category}</td><td><Badge>{row.kind}</Badge></td><td>{row.external_url ? "Drive / external link" : row.filename}</td></tr>)}</tbody></TableScroll> : <EmptyState title="No matching training" hint="Add a training session with a PDF, MP4 video or Drive link, or adjust your filters." />}
        <RegisterPagination offset={offset} total={answer.data.total} pageSize={25} onChange={setOffset} />
      </> : null}
    </Card>
  </div>;
}

function AssetPreview({ projectId, row }: { projectId: string; row: TrainingMaterial }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <Notice tone="info">Preview unavailable. Download the file to view it in a compatible application.</Notice>;
  if (row.kind === "video") {
    // User-provided videos may not have captions; no synthetic caption track is invented.
    return <video className="marketing-asset-preview" controls preload="metadata" src={training.fileUrl(projectId, row)} aria-label={row.title} onError={() => setFailed(true)} />;
  }
  return <p className="muted">PDF reference document. Download to read.</p>;
}

export function AssetEditor({ row, categories, onClose, onSave }: { row?: TrainingMaterial; categories: string[]; onClose: () => void; onSave: (values: AssetInput, file: File | null) => Promise<void> }) {
  const initial: AssetInput = { kind: row?.kind ?? "document", title: row?.title ?? "", category: row?.category ?? "", description: row?.description ?? "", execution_date: row?.execution_date ?? "", external_url: row?.external_url ?? null };
  const [values, setValues] = useState(initial);
  const [source, setSource] = useState(row?.external_url ? "link" : "upload");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = <K extends keyof AssetInput>(key: K, value: AssetInput[K]) => setValues({ ...values, [key]: value });
  return <RecordPage title={row ? "Edit training" : "Add training"} onClose={onClose}><DraftBoundary busy={busy} dirty={!!file || JSON.stringify(values) !== JSON.stringify(initial) || source !== (row?.external_url ? "link" : "upload")}>
    <form className="stack" onSubmit={async event => {
      event.preventDefault(); if (busy) return;
      if (!row && source === "upload" && !file) { setError("Choose a file to upload."); return; }
      const limit = values.kind === "video" ? 50 * 1024 * 1024 : 10 * 1024 * 1024;
      if (file && (!file.size || file.size > limit)) { setError("Choose a non-empty file: PDFs up to 10 MB, MP4 videos up to 50 MB."); return; }
      setBusy(true); setError(null);
      try { await onSave({ ...values, external_url: source === "link" ? values.external_url : null }, source === "upload" ? file : null); }
      catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save. Your entries have been kept."); }
      finally { setBusy(false); }
    }}>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <fieldset disabled={busy} className="marketing-fieldset stack">
        <Field label="Title"><input required maxLength={160} className="input" value={values.title} onChange={e => set("title", e.target.value)} /></Field>
        <Field label="Category" hint="Choose a suggestion or enter your own category."><input required maxLength={80} className="input" list="training-categories" value={values.category} onChange={e => set("category", e.target.value)} /><datalist id="training-categories">{categories.map(value => <option key={value} value={value} />)}</datalist></Field>
        <Field label="Execution date"><input required type="date" className="input" value={values.execution_date} onChange={e => set("execution_date", e.target.value)} /></Field>
        <Field label="Training description"><textarea required rows={5} maxLength={4000} className="input" value={values.description} onChange={e => set("description", e.target.value)} /></Field>
        {!row ? <>
          <FieldRow><Field label="Type"><select className="input" value={values.kind} onChange={e => { set("kind", e.target.value as AssetKind); setFile(null); }}><option value="video">Video</option><option value="document">PDF / reference</option></select></Field><Field label="Source"><select className="input" value={source} onChange={e => { setSource(e.target.value); setFile(null); }}><option value="upload">Upload file</option><option value="link">Drive / external link</option></select></Field></FieldRow>
          {source === "link" ? <Field label="Drive / reference URL" hint="Use an HTTPS link. Sharing permissions stay with the original file owner."><input type="url" required maxLength={2000} className="input" value={values.external_url ?? ""} onChange={e => set("external_url", e.target.value)} /></Field> : <Field label="File" hint="PDF up to 10 MB; MP4 up to 50 MB. Use a Drive link for larger videos."><input key={values.kind} type="file" required accept={values.kind === "document" ? ".pdf" : ".mp4"} onChange={e => setFile(e.target.files?.[0] ?? null)} /></Field>}
        </> : <p className="muted">The original file or link is retained. To replace it, delete this item and add the replacement.</p>}
      </fieldset>
      <FormActions><Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save training"}</Button><Button variant="default" disabled={busy} data-leaves-editor onClick={onClose}>Cancel</Button></FormActions>
    </form>
  </DraftBoundary></RecordPage>;
}
