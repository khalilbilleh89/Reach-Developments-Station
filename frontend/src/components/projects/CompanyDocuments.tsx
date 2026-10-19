"use client";

import { useState } from "react";
import { companyDocuments, type CompanyDocument } from "@/lib/api/companies";
import { useAnswer } from "@/lib/answer";
import { Button, Card, DraftBoundary, EmptyState, Field, FormActions, Loading, Notice, RecordPage, SectionHeader } from "@/components/ui";
import { DeleteRecordButton } from "./DeleteRecordButton";

export function CompanyDocumentForm({ row, onSave, onClose, onSaved }: {
  row?: CompanyDocument; onSave: (label: string, file: File | null) => Promise<unknown>;
  onClose: () => void; onSaved: () => void;
}) {
  const [label, setLabel] = useState(row?.label ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return <RecordPage title={row ? "Edit document label" : "Add company document"} onClose={onClose}>
    <DraftBoundary dirty={label !== (row?.label ?? "") || file !== null} busy={busy}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault();
        if (busy) return;
        if (!label.trim()) { setError("Enter a document label."); return; }
        if (!row && !file) { setError("Choose a PDF file."); return; }
        setBusy(true); setError(null);
        try { await onSave(label.trim(), file); onClose(); onSaved(); }
        catch (caught) { setError(caught instanceof Error ? caught.message : "Could not save. Your entries have been kept."); }
        finally { setBusy(false); }
      }}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <Field label="Document label" hint="For example: Certificate of incorporation, Trade licence, or Tax registration."><input className="input" required disabled={busy} maxLength={320} value={label} onChange={event => setLabel(event.target.value)} /></Field>
        {row ? <p className="company-document-file">File: <strong>{row.filename}</strong>. Upload a new entry to replace a file, then delete the old entry.</p> :
          <Field label="PDF document" hint="PDF only, up to 10 MB per document. Add each document with its own label."><input className="input" type="file" accept=".pdf,application/pdf" required disabled={busy} onChange={event => setFile(event.target.files?.[0] ?? null)} /></Field>}
        <FormActions><Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save document"}</Button><Button variant="default" disabled={busy} data-leaves-editor onClick={onClose}>Cancel</Button></FormActions>
      </form>
    </DraftBoundary>
  </RecordPage>;
}

export function CompanyDocuments({ projectId, companyId, canWrite }: { projectId: string; companyId: string; canWrite: boolean }) {
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
    {answer.status === "ready" && answer.data.length === 0 ? <EmptyState title="No company documents added" hint="Upload company registration PDFs, each with a specific label." /> : null}
    {answer.status === "ready" ? <div className="stack">{answer.data.map(row => <section className="form-section" key={row.id}>
      <SectionHeader title={row.label} actions={canWrite ? <>
        <Button variant="default" onClick={() => setEditor({ row })}>Edit label</Button>
        <DeleteRecordButton label="company document" recordName={row.label} confirmLabel="Delete document" description="Remove this document from the company register. Its PDF and audit history will be retained." onDelete={reason => companyDocuments.remove(projectId, companyId, row, reason)} onDeleted={async () => { answer.retry(); }} />
      </> : undefined} />
      <p className="company-document-file">{row.filename}</p>
      <Button variant="default" disabled={downloading !== null} aria-label={`Download PDF: ${row.label}`} onClick={async () => {
        setDownloading(row.id); setError(null);
        try { await companyDocuments.download(projectId, companyId, row); }
        catch (caught) { setError(caught instanceof Error ? caught.message : "Could not download the PDF."); }
        finally { setDownloading(null); }
      }}>{downloading === row.id ? "Downloading…" : "Download PDF"}</Button>
    </section>)}</div> : null}
    {editor ? <CompanyDocumentForm key={editor.row?.id ?? "new"} row={editor.row} onClose={() => setEditor(null)} onSaved={answer.retry} onSave={async (label, file) => {
      if (editor.row) return companyDocuments.update(projectId, companyId, editor.row, label);
      if (file) return companyDocuments.create(projectId, companyId, label, file);
    }} /> : null}
  </Card></div>;
}
