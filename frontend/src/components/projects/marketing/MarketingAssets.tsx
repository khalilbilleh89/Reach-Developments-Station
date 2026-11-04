"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { marketingAssets, type AssetInput, type AssetKind, type AssetPlacement, type MarketingAsset } from "@/lib/api/marketingAssets";
import { useAnswer } from "@/lib/answer";
import { hasAnyRole, MARKETING_READERS, MARKETING_WRITERS } from "@/lib/roles";
import { Badge, Button, Card, DraftBoundary, EmptyState, Field, FieldRow, FormActions, Loading, Notice, PageHeader, RecordPage, RegisterPagination, RowMenu, SectionHeader, TableScroll } from "@/components/ui";
import { sectionIcon } from "@/components/shell/navigation";
import { DeleteRecordButton } from "../DeleteRecordButton";

export function MarketingAssets({ projectId, roles, placement = "material" }: { projectId: string; roles: Set<string>; placement?: AssetPlacement }) {
  const canWrite = hasAnyRole(roles, MARKETING_WRITERS);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [kind, setKind] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<MarketingAsset | null>(null);
  const [editor, setEditor] = useState<{ row?: MarketingAsset } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const answer = useAnswer(hasAnyRole(roles, MARKETING_READERS), () => marketingAssets.list(projectId, placement, search, category, kind, offset), [projectId, placement, search, category, kind, offset]);
  const categories = answer.status === "ready" ? answer.data.categories : [];
  const refresh = () => { setSelected(null); answer.retry(); };
  const saveFile = async (row: MarketingAsset) => {
    setError(null);
    try { await marketingAssets.download(projectId, row); } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Download failed. Please retry."); }
  };
  if (editor) return <AssetEditor placement={placement} row={editor.row} categories={categories} onClose={() => setEditor(null)} onSave={async (values, file) => {
    if (editor.row) await marketingAssets.update(projectId, editor.row, { title: values.title, category: values.category, notes: values.notes });
    else if (file) await marketingAssets.upload(projectId, values, file);
    else await marketingAssets.createLink(projectId, values);
    setEditor(null); refresh();
  }} />;
  if (selected) return <RecordPage title={selected.title} subtitle={`${selected.category} · ${selected.kind}`} onClose={() => { setSelected(null); setError(null); }}>
    <div className="stack"><SectionHeader title="Material details" actions={canWrite ? <Button variant="default" onClick={() => setEditor({ row: selected })}>Edit details</Button> : undefined} />
      {error ? <Notice tone="error">{error}</Notice> : null}
      <p>{selected.notes || "No notes recorded."}</p>
      {selected.external_url ? <><p className="muted">External reference. Access depends on the sharing permissions of its owner.</p><a href={selected.external_url} target="_blank" rel="noopener noreferrer" className="button">Open Drive / reference link</a></> : <>
        <AssetPreview key={selected.id} projectId={projectId} row={selected} />
        <Button variant="default" onClick={() => void saveFile(selected)}>Download {selected.filename}</Button>
      </>}
      {canWrite ? <RowMenu label={`Actions for ${selected.title}`}><DeleteRecordButton label="attachment" recordName={selected.title} description="Remove this item from Marketing. Stored files and audit history are retained. External Drive files are not changed." confirmLabel="Delete attachment" onDelete={reason => marketingAssets.remove(projectId, selected, reason)} onDeleted={async () => refresh()} /></RowMenu> : null}
    </div>
  </RecordPage>;
  const actions = canWrite ? <Button onClick={() => setEditor({})}>{placement === "logo" ? "Add logo" : "Add material"}</Button> : undefined;
  return <div className="stack">
    {placement === "logo" ? <SectionHeader title="Logo attachments" level={2} description="PNG and JPEG variants for this project's identity." actions={actions} /> : <PageHeader title="Materials" icon={sectionIcon("marketing-materials")} subtitle="Project videos, images and reference documents, organized by category." actions={actions} />}
    <Card>
      <FieldRow><Field label={placement === "logo" ? "Search logos" : "Search materials"}><input type="search" className="input" value={search} onChange={e => { setSearch(e.target.value); setOffset(0); }} /></Field>
        <Field label="Category"><select className="input" value={category} onChange={e => { setCategory(e.target.value); setOffset(0); }}><option value="">All categories</option>{category && !categories.includes(category) ? <option value={category}>{category}</option> : null}{categories.map(value => <option key={value} value={value}>{value}</option>)}</select></Field>
        {placement === "material" ? <Field label="Material type"><select className="input" value={kind} onChange={e => { setKind(e.target.value); setOffset(0); }}><option value="">All types</option><option value="video">Video</option><option value="image">Image</option><option value="document">Document / research</option></select></Field> : null}
      </FieldRow>
      {answer.status === "loading" ? <Loading label="Loading attachments…" /> : null}
      {answer.status === "denied" ? <Notice tone="info">Attachments are not available to your access level.</Notice> : null}
      {answer.status === "failed" ? <Notice tone="error">{answer.message} <Button onClick={answer.retry}>Retry</Button></Notice> : null}
      {answer.status === "ready" ? <>{answer.data.items.length ? <TableScroll label={placement === "logo" ? "Project logos" : "Project material library"}><thead><tr><th scope="col">Title</th><th scope="col">Category</th><th scope="col">Type</th><th scope="col">Source</th></tr></thead><tbody>{answer.data.items.map(row => <tr key={row.id}><th scope="row"><Button variant="link" onClick={() => { setSelected(row); setError(null); }}>{row.title}</Button></th><td>{row.category}</td><td><Badge>{row.kind}</Badge></td><td>{row.external_url ? "Drive / external link" : row.filename}</td></tr>)}</tbody></TableScroll> : <EmptyState title="No matching attachments" hint={placement === "logo" ? "Add a PNG or JPEG logo, or adjust the filters." : "Upload a video, image or PDF, or add a Drive reference link."} />}
        <RegisterPagination offset={offset} total={answer.data.total} pageSize={25} onChange={setOffset} />
      </> : null}
    </Card>
  </div>;
}

function AssetPreview({ projectId, row }: { projectId: string; row: MarketingAsset }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <Notice tone="info">Preview unavailable. Download the file to view it in a compatible application.</Notice>;
  if (row.kind === "image") {
    // Authenticated server-decoded image, not a remote image optimizer request.
    // eslint-disable-next-line @next/next/no-img-element
    return <img className="marketing-asset-preview" src={marketingAssets.fileUrl(projectId, row)} alt={row.title} onError={() => setFailed(true)} />;
  }
  if (row.kind === "video") {
    // User-provided videos may not have captions; no synthetic caption track is invented.
    return <video className="marketing-asset-preview" controls preload="metadata" src={marketingAssets.fileUrl(projectId, row)} aria-label={row.title} onError={() => setFailed(true)} />;
  }
  return <p className="muted">PDF reference document. Download to read.</p>;
}

export function AssetEditor({ placement, row, categories, onClose, onSave }: { placement: AssetPlacement; row?: MarketingAsset; categories: string[]; onClose: () => void; onSave: (values: AssetInput, file: File | null) => Promise<void> }) {
  const initial: AssetInput = { placement, kind: row?.kind ?? "image", title: row?.title ?? "", category: row?.category ?? (placement === "logo" ? "Logo" : ""), notes: row?.notes ?? "", external_url: row?.external_url ?? null };
  const [values, setValues] = useState(initial);
  const [source, setSource] = useState(row?.external_url ? "link" : "upload");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = <K extends keyof AssetInput>(key: K, value: AssetInput[K]) => setValues({ ...values, [key]: value });
  return <RecordPage title={row ? "Edit attachment details" : placement === "logo" ? "Add logo" : "Add material"} onClose={onClose}><DraftBoundary busy={busy} dirty={!!file || JSON.stringify(values) !== JSON.stringify(initial) || source !== (row?.external_url ? "link" : "upload")}>
    <form className="stack" onSubmit={async event => {
      event.preventDefault(); if (busy) return;
      if (!row && source === "upload" && !file) { setError("Choose a file to upload."); return; }
      const limit = values.kind === "video" ? 50 * 1024 * 1024 : 10 * 1024 * 1024;
      if (file && (!file.size || file.size > limit)) { setError("Choose a non-empty file: images/PDFs up to 10 MB, MP4 videos up to 50 MB."); return; }
      setBusy(true); setError(null);
      try { await onSave({ ...values, external_url: source === "link" ? values.external_url : null }, source === "upload" ? file : null); }
      catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save. Your entries have been kept."); }
      finally { setBusy(false); }
    }}>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <fieldset disabled={busy} className="marketing-fieldset stack">
        <Field label="Title"><input required maxLength={160} className="input" value={values.title} onChange={e => set("title", e.target.value)} /></Field>
        <Field label="Category" hint="Choose a suggestion or enter your own category."><input required maxLength={80} className="input" list="marketing-asset-categories" value={values.category} onChange={e => set("category", e.target.value)} /><datalist id="marketing-asset-categories">{categories.map(value => <option key={value} value={value} />)}</datalist></Field>
        <Field label="Notes" optional><textarea maxLength={500} className="input" value={values.notes} onChange={e => set("notes", e.target.value)} /></Field>
        {!row ? <>
          {placement === "material" ? <FieldRow><Field label="Type"><select className="input" value={values.kind} onChange={e => { set("kind", e.target.value as AssetKind); setFile(null); }}><option value="image">Image</option><option value="video">Video</option><option value="document">Document / research</option></select></Field><Field label="Source"><select className="input" value={source} onChange={e => { setSource(e.target.value); setFile(null); }}><option value="upload">Upload file</option><option value="link">Drive / external link</option></select></Field></FieldRow> : null}
          {source === "link" ? <Field label="Drive / reference URL" hint="Use an HTTPS link. Sharing permissions stay with the original file owner."><input type="url" required maxLength={2000} className="input" value={values.external_url ?? ""} onChange={e => set("external_url", e.target.value)} /></Field> : <Field label="File" hint="PNG/JPEG or PDF up to 10 MB; MP4 up to 50 MB. Use a Drive link for larger videos."><input key={values.kind} type="file" required accept={values.kind === "image" ? ".png,.jpg,.jpeg" : values.kind === "document" ? ".pdf" : ".mp4"} onChange={e => setFile(e.target.files?.[0] ?? null)} /></Field>}
        </> : <p className="muted">The original file or link is retained. To replace it, delete this item and add the replacement.</p>}
      </fieldset>
      <FormActions><Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save attachment"}</Button><Button variant="default" disabled={busy} data-leaves-editor onClick={onClose}>Cancel</Button></FormActions>
    </form>
  </DraftBoundary></RecordPage>;
}
