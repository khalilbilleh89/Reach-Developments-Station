"use client";

import { useState } from "react";
import { businessDate } from "@/lib/format";
import { companyDocuments, type CompanyDocument, type DocumentMetadata } from "@/lib/api/companies";
import { useAnswer } from "@/lib/answer";
import { Button, Card, CardRow, CardRows, DraftBoundary, EmptyState, Field, FieldRow, FormActions, Loading, Notice, RecordPage, RowMenu, SectionHeader } from "@/components/ui";
import { DeleteRecordButton } from "./DeleteRecordButton";

const METADATA_FIELDS: [keyof DocumentMetadata, string][] = [["category", "Document category"], ["linked_record", "Linked project / land record reference"], ["issue_date", "Issue date"], ["expiry_date", "Expiry date"], ["reminder_date", "Renewal reminder date"], ["verification_status", "Verification status"]];

export function CompanyDocumentForm({ row, onSave, onClose, onSaved }: {
  row?: CompanyDocument; onSave: (label: string, file: File | null, metadata: DocumentMetadata, sourceUrl: string | null) => Promise<unknown>;
  onClose: () => void; onSaved: () => void;
}) {
  const [label, setLabel] = useState(row?.label ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState(row?.source_url ? "drive" : "pdf");
  const [sourceUrl, setSourceUrl] = useState(row?.source_url ?? "");
  const [original] = useState(() => Object.fromEntries(METADATA_FIELDS.map(([key]) => [key, row?.[key] ?? ""])));
  const [metadata, setMetadata] = useState(original);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return <RecordPage title={row ? "Edit company document" : "Add company document"} onClose={onClose}>
    <DraftBoundary dirty={label !== (row?.label ?? "") || file !== null || source !== (row?.source_url ? "drive" : "pdf") || sourceUrl !== (row?.source_url ?? "") || JSON.stringify(metadata) !== JSON.stringify(original)} busy={busy}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault();
        if (busy) return;
        if (!label.trim()) { setError("Enter a document label."); return; }
        if (!row && source === "pdf" && !file) { setError("Choose a PDF file."); return; }
        if (!row && source === "drive" && !sourceUrl.trim()) { setError("Enter a Google Drive sharing link."); return; }
        setBusy(true); setError(null);
        try { await onSave(label.trim(), source === "pdf" ? file : null, Object.fromEntries(METADATA_FIELDS.map(([key]) => [key, metadata[key].trim() || null])), source === "drive" ? sourceUrl.trim() : null); onClose(); onSaved(); }
        catch (caught) { setError(caught instanceof Error ? caught.message : "Could not save. Your entries have been kept."); }
        finally { setBusy(false); }
      }}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <Field label="Document label" hint="For example: Certificate of incorporation, Trade licence, or Tax registration."><input className="input" required disabled={busy} maxLength={320} value={label} onChange={event => setLabel(event.target.value)} /></Field>
        {!row ? <Field label="Document source"><select className="input" value={source} disabled={busy} onChange={event => setSource(event.target.value)}><option value="pdf">Upload PDF file</option><option value="drive">Google Drive link</option></select></Field> : null}
        {row ? <p className="company-document-file">Source: <strong>{row.filename || row.source_url}</strong>. Upload a new entry to replace a file, then delete the old entry.</p> : source === "drive" ? <Field label="Google Drive link" hint="Paste an HTTPS sharing link. Access remains controlled by Google Drive."><input className="input" type="url" required disabled={busy} maxLength={2000} value={sourceUrl} onChange={event => setSourceUrl(event.target.value)} /></Field> :
          <Field label="PDF document" hint="PDF only, up to 10 MB per document. Add each document with its own label."><input className="input" type="file" accept=".pdf,application/pdf" required disabled={busy} onChange={event => setFile(event.target.files?.[0] ?? null)} /></Field>}
        <FieldRow>{METADATA_FIELDS.map(([key, label]) => <Field key={key} label={label} optional hint={key === "reminder_date" ? "Shows a renewal reminder in this register on this date; no email is sent." : key === "linked_record" ? "Enter the project or land parcel reference; the owner company is this record’s company." : undefined}>
          {key === "verification_status" ? <select className="input" disabled={busy} value={metadata[key]} onChange={event => setMetadata({ ...metadata, [key]: event.target.value })}><option value="">Not entered</option><option value="needs_review">Needs review</option><option value="verified">Verified</option></select> : <input className="input" type={key.endsWith("_date") ? "date" : "text"} maxLength={key === "linked_record" ? 500 : 320} disabled={busy} value={metadata[key]} onChange={event => setMetadata({ ...metadata, [key]: event.target.value })} />}
        </Field>)}</FieldRow>
        <FormActions><Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save document"}</Button><Button variant="default" disabled={busy} data-leaves-editor onClick={onClose}>Cancel</Button></FormActions>
      </form>
    </DraftBoundary>
  </RecordPage>;
}

export function CompanyDocuments({ projectId, companyId, canWrite, companyName }: { projectId: string; companyId: string; canWrite: boolean; companyName?: string }) {
  // Mounted only after the parent Company read has authorized and returned the company.
  const answer = useAnswer(true, () => companyDocuments.list(projectId, companyId), [projectId, companyId]);
  const [editor, setEditor] = useState<{ row?: CompanyDocument } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  return <div className="company-documents"><Card>
    <SectionHeader level={2} title="Company Registration Documents" actions={canWrite ? <Button onClick={() => setEditor({})}>Add document</Button> : undefined} />
    {answer.status === "loading" ? <Loading label="Loading company documents…" /> : null}
    {answer.status === "off" || answer.status === "denied" ? <Notice tone="info">Company documents are not available to your access level.</Notice> : null}
    {answer.status === "failed" ? <Notice tone="error">{answer.message} <Button variant="default" onClick={answer.retry}>Retry</Button></Notice> : null}
    {error ? <Notice tone="error">{error}</Notice> : null}
    {answer.status === "ready" && answer.data.length === 0 ? <EmptyState title="No company documents added" hint="Upload PDFs or add Google Drive links, each with its own label." /> : null}
    {answer.status === "ready" && answer.data.length ? <CardRows label="Company registration documents">{answer.data.map(row => <CardRow key={row.id}
      title={row.label}
      meta={row.filename || "Google Drive link"}
      facts={[
        { label: "Owner company", value: companyName || "Current company" },
        { label: "Category", value: row.category || "Not entered" },
        { label: "Linked record", value: row.linked_record || "Not entered" },
        { label: "Issued", value: row.issue_date ? businessDate(row.issue_date) : "Not entered" },
        { label: "Expires", value: row.expiry_date ? businessDate(row.expiry_date) : "Not entered" },
        { label: "Verification", value: row.verification_status === "verified" ? "Verified" : row.verification_status === "needs_review" ? "Needs review" : "Not entered" },
        { label: "Renewal", value: row.reminder_status === "expired" ? "Expired" : row.reminder_status === "renewal_due" ? "Renewal due" : row.reminder_date ? businessDate(row.reminder_date) : "Not entered" },
      ]}
      actions={<>
        {row.source_url ? <a className="button" href={row.source_url} target="_blank" rel="noopener noreferrer">Open Google Drive</a> : <Button variant="default" disabled={downloading !== null} aria-label={`Download PDF: ${row.label}`} onClick={async () => {
          setDownloading(row.id); setError(null);
          try { await companyDocuments.download(projectId, companyId, row); }
          catch (caught) { setError(caught instanceof Error ? caught.message : "Could not download the PDF."); }
          finally { setDownloading(null); }
        }}>{downloading === row.id ? "Downloading…" : "Download PDF"}</Button>}
        {canWrite ? <RowMenu label={`Actions for ${row.label}`}>
          <Button variant="default" onClick={() => setEditor({ row })}>Edit document</Button>
          <DeleteRecordButton label="company document" recordName={row.label} confirmLabel="Delete document" description="Remove this document from the company register. Its source and audit history will be retained." onDelete={reason => companyDocuments.remove(projectId, companyId, row, reason)} onDeleted={async () => { answer.retry(); }} />
        </RowMenu> : null}
      </>} />)}</CardRows> : null}
    {editor ? <CompanyDocumentForm key={editor.row?.id ?? "new"} row={editor.row} onClose={() => setEditor(null)} onSaved={answer.retry} onSave={async (label, file, metadata, sourceUrl) => {
      if (editor.row) return companyDocuments.update(projectId, companyId, editor.row, label, metadata);
      if (file) return companyDocuments.create(projectId, companyId, label, file, metadata);
      if (sourceUrl) return companyDocuments.link(projectId, companyId, label, sourceUrl, metadata);
    }} /> : null}
  </Card></div>;
}
