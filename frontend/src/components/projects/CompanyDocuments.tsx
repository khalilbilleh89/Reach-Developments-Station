"use client";

import { useState } from "react";
import { businessDate } from "@/lib/format";
import { companyDocuments, type CompanyDocument, type DocumentMetadata } from "@/lib/api/companies";
import { useAnswer } from "@/lib/answer";
import { Badge, Button, Card, CardRow, CardRows, ChoiceCards, DraftBoundary, EmptyState, ExternalLink, Field, FieldRow, FormActions, FormSection, Loading, Notice, RecordPage, RowMenu, SectionHeader, Segmented, StatusDot } from "@/components/ui";
import { DeleteRecordButton } from "./DeleteRecordButton";

const CATEGORIES = [
  "Company registration certificate", "Registered office/address certificate",
  "Directors & Secretary certificate", "Tax/VAT certificate", "Title deed/property document", "Other",
];
const STATUS: Record<string, string> = { needs_review: "Needs review", verified: "Verified", expired: "Expired", superseded: "Superseded" };
const EXPIRY_NOTES = { not_stated: "Not stated on document", to_verify: "To verify" };
const REMINDER_DAYS = { "30": 30, "60": 60, "90": 90 } as const;

function documentDraft(row?: CompanyDocument) {
  const category = row?.category ?? "";
  return {
    category: category && !CATEGORIES.includes(category) ? "Other" : category,
    otherCategory: row?.other_category ?? (category && !CATEGORIES.includes(category) ? category : ""),
    linkedRecord: row?.linked_record ?? "",
    issueDate: row?.issue_date ?? "",
    issueNotStated: row?.issue_date_not_stated ?? false,
    expiryDate: row?.expiry_date ?? "",
    expiryNote: (row?.expiry_note ?? "") as keyof typeof EXPIRY_NOTES | "",
    reminder: row?.reminder_days ? String(row.reminder_days) : row?.reminder_date ? "legacy" : "",
    status: row ? row.verification_status ?? "" : "needs_review",
  };
}

/** The server's renewal position for a document, as a status pill: a word first, colour only beside it. */
export function renewalState(row: CompanyDocument) {
  if (row.verification_status === "expired") return null;
  if (row.reminder_status === "expired") return <Badge tone="danger">Expired</Badge>;
  if (row.reminder_status === "renewal_due") return <Badge tone="warning">Renewal due</Badge>;
  return null;
}

export function CompanyDocumentForm({ row, onSave, onClose, onSaved }: {
  row?: CompanyDocument; onSave: (label: string, file: File | null, metadata: DocumentMetadata, sourceUrl: string | null) => Promise<unknown>;
  onClose: () => void; onSaved: () => void;
}) {
  const [label, setLabel] = useState(row?.label ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState(row?.source_url ? "drive" : "pdf");
  const [sourceUrl, setSourceUrl] = useState(row?.source_url ?? "");
  const [original] = useState(() => documentDraft(row));
  const [metadata, setMetadata] = useState(original);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return <RecordPage icon="documents" title={row ? "Edit company document" : "Add company document"} subtitle={row ? row.filename || "Google Drive link" : undefined} onClose={onClose}>
    <DraftBoundary dirty={label !== (row?.label ?? "") || file !== null || source !== (row?.source_url ? "drive" : "pdf") || sourceUrl !== (row?.source_url ?? "") || JSON.stringify(metadata) !== JSON.stringify(original)} busy={busy}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault();
        if (busy) return;
        if (!label.trim()) { setError("Enter a document label."); return; }
        if (!row && source === "pdf" && !file) { setError("Choose a PDF file."); return; }
        if (!row && source === "drive" && !sourceUrl.trim()) { setError("Enter a Google Drive sharing link."); return; }
        const categoryChanged = !row || metadata.category !== original.category || metadata.otherCategory !== original.otherCategory;
        if (!row && !metadata.category) { setError("Select a document category."); return; }
        if (categoryChanged && metadata.category === "Other" && !metadata.otherCategory.trim()) { setError("Specify the other document category."); return; }
        const payload: DocumentMetadata = {
          ...(categoryChanged ? { category: metadata.category || null, other_category: metadata.category === "Other" ? metadata.otherCategory.trim() : null } : {}),
          linked_record: metadata.linkedRecord.trim() || null,
          issue_date: metadata.issueDate || null,
          issue_date_not_stated: metadata.issueNotStated,
          expiry_date: metadata.expiryDate || null,
          expiry_note: metadata.expiryNote || null,
          verification_status: metadata.status || null,
          ...(metadata.reminder === "legacy" ? {} : { reminder_days: REMINDER_DAYS[metadata.reminder as keyof typeof REMINDER_DAYS] ?? null }),
        };
        setBusy(true); setError(null);
        try { await onSave(label.trim(), source === "pdf" ? file : null, payload, source === "drive" ? sourceUrl.trim() : null); onClose(); onSaved(); }
        catch (caught) { setError(caught instanceof Error ? caught.message : "Could not save. Your entries have been kept."); }
        finally { setBusy(false); }
      }}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <Field label="Document label" hint="For example: Certificate of incorporation, Trade licence, or Tax registration."><input className="input" required disabled={busy} maxLength={320} value={label} onChange={event => setLabel(event.target.value)} /></Field>
        {!row ? <ChoiceCards label="Document source" name="company-document-source" value={source} columns={2} onChange={value => { if (!busy) setSource(value); }} options={[{ value: "pdf", label: "Upload PDF", description: "Stored in the system · up to 10 MB" }, { value: "drive", label: "Google Drive link", description: "Access stays controlled in Google Drive" }]} /> : null}
        {row ? <p className="footnote">The original PDF or Drive link is retained. To replace it, add a new document and delete this one.</p> : source === "drive" ? <Field label="Google Drive link" hint="Paste an HTTPS sharing link. Access remains controlled by Google Drive."><input className="input" type="url" required disabled={busy} maxLength={2000} value={sourceUrl} onChange={event => setSourceUrl(event.target.value)} /></Field> :
          <Field label="PDF document" hint="PDF only, up to 10 MB per document. Add each document with its own label."><input className="input" type="file" accept=".pdf,application/pdf" required disabled={busy} onChange={event => setFile(event.target.files?.[0] ?? null)} /></Field>}
        <FormSection title="Classification">
          <FieldRow>
            <div className="stack">
              <Field label="Document category" optional={Boolean(row)}>
                <select className="input" required={!row} disabled={busy} value={metadata.category} onChange={event => setMetadata({ ...metadata, category: event.target.value })}>
                  <option value="">Not entered</option>
                  {CATEGORIES.map(category => <option key={category}>{category}</option>)}
                </select>
              </Field>
              {metadata.category === "Other" ? <Field label="Specify category">
                <input className="input" required={original.category !== "Other" || Boolean(original.otherCategory)} disabled={busy} maxLength={320} value={metadata.otherCategory} onChange={event => setMetadata({ ...metadata, otherCategory: event.target.value })} />
              </Field> : null}
            </div>
            <Field label="Linked project / land record reference" optional hint="Enter the project or land parcel reference; the owner company is this record’s company.">
              <input className="input" maxLength={500} disabled={busy} value={metadata.linkedRecord} onChange={event => setMetadata({ ...metadata, linkedRecord: event.target.value })} />
            </Field>
            <Field label="Document status" optional={Boolean(row)}>
              <Segmented label="Document status" value={metadata.status} onChange={value => { if (!busy) setMetadata({ ...metadata, status: value }); }}
                options={[...(row ? [{ value: "", label: "Not entered" }] : []), ...Object.entries(STATUS).map(([value, text]) => ({ value, label: text }))]} />
            </Field>
          </FieldRow>
        </FormSection>
        <FormSection title="Dates & renewal">
          <FieldRow>
            <div className="stack">
              <Field label="Issue date" optional>
                <input className="input" type="date" disabled={busy || metadata.issueNotStated} value={metadata.issueDate} onChange={event => setMetadata({ ...metadata, issueDate: event.target.value })} />
              </Field>
              <label><input type="checkbox" disabled={busy} checked={metadata.issueNotStated} onChange={event => setMetadata({ ...metadata, issueNotStated: event.target.checked, issueDate: "" })} /> Not stated</label>
            </div>
            <div className="stack">
              <Field label="Expiry date" optional>
                <input className="input" type="date" disabled={busy || Boolean(metadata.expiryNote)} value={metadata.expiryDate} onChange={event => setMetadata({ ...metadata, expiryDate: event.target.value, reminder: event.target.value ? metadata.reminder : "" })} />
              </Field>
              <Field label="Expiry information" optional>
                <select className="input" disabled={busy} value={metadata.expiryNote} onChange={event => {
                  const expiryNote = event.target.value as typeof metadata.expiryNote;
                  setMetadata({ ...metadata, expiryNote, ...(expiryNote ? { expiryDate: "", reminder: "" } : {}) });
                }}>
                  <option value="">No note selected</option>
                  {Object.entries(EXPIRY_NOTES).map(([value, text]) => <option key={value} value={value}>{text}</option>)}
                </select>
              </Field>
            </div>
            <Field label="Renewal reminder" optional hint="Appears in this register when due.">
              <select className="input" disabled={busy || !metadata.expiryDate} value={metadata.reminder} onChange={event => setMetadata({ ...metadata, reminder: event.target.value })}>
                <option value="">None</option>
                {Object.keys(REMINDER_DAYS).map(days => <option key={days} value={days}>{days} days before expiry</option>)}
                {original.reminder === "legacy" && row?.reminder_date ? <option value="legacy">Existing reminder on {businessDate(row.reminder_date)}</option> : null}
              </select>
            </Field>
          </FieldRow>
        </FormSection>
        <FormActions><Button type="submit" variant="primary" disabled={busy}>{busy ? "Saving…" : "Save document"}</Button><Button variant="default" disabled={busy} data-leaves-editor onClick={onClose}>Cancel</Button></FormActions>
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
  const [expandedDates, setExpandedDates] = useState<string | null>(null);
  const due = answer.status === "ready" ? answer.data.filter(row => row.reminder_status === "expired" || row.reminder_status === "renewal_due" || row.verification_status === "expired").length : 0;
  return <div className="company-documents"><Card>
    <SectionHeader level={2} title="Registration documents" description={due ? `${due} ${due === 1 ? "document needs" : "documents need"} renewal attention.` : undefined} actions={canWrite ? <Button onClick={() => setEditor({})}>Add document</Button> : undefined} />
    {answer.status === "loading" ? <Loading label="Loading company documents…" /> : null}
    {answer.status === "off" || answer.status === "denied" ? <Notice tone="info">Company documents are not available to your access level.</Notice> : null}
    {answer.status === "failed" ? <Notice tone="error">{answer.message} <Button variant="default" onClick={answer.retry}>Retry</Button></Notice> : null}
    {error ? <Notice tone="error">{error}</Notice> : null}
    {answer.status === "ready" && answer.data.length === 0 ? <EmptyState title="No company documents added" hint="Upload PDFs or add Google Drive links, each with its own label." /> : null}
    {answer.status === "ready" && answer.data.length ? <CardRows label="Company registration documents">{answer.data.map(row => <CardRow key={row.id}
      title={row.label}
      meta={[row.filename || "Google Drive link", row.linked_record].filter(Boolean).join(" · ")}
      flagged={row.reminder_status === "expired" || row.verification_status === "expired"}
      facts={[
        { label: "Category", value: row.other_category || row.category || <span className="muted">Not entered</span> },
        { label: "Expires", value: row.expiry_date ? businessDate(row.expiry_date) : row.expiry_note ? EXPIRY_NOTES[row.expiry_note] : <span className="muted">Not entered</span> },
        { label: "Dates & renewal", value: <>
          <Button variant="link" aria-expanded={expandedDates === row.id} aria-controls={`company-document-dates-${row.id}`} onClick={() => setExpandedDates(expandedDates === row.id ? null : row.id)}>
            {expandedDates === row.id ? "Hide details" : "Show details"}
          </Button>
          <span id={`company-document-dates-${row.id}`} hidden={expandedDates !== row.id}>
            Issue date: {row.issue_date ? businessDate(row.issue_date) : row.issue_date_not_stated ? "Not stated" : "Not entered"}<br />
            Renewal reminder: {row.reminder_days ? `${row.reminder_days} days before expiry` : row.reminder_date ? businessDate(row.reminder_date) : "None"}
          </span>
        </> },
      ]}
      status={<>{renewalState(row)}{row.verification_status === "expired" ? <Badge tone="danger">Expired</Badge> : <StatusDot tone={row.verification_status === "verified" ? "success" : "neutral"}>{STATUS[row.verification_status ?? ""] ?? "Status not entered"}</StatusDot>}</>}
      actions={<>
        {row.source_url ? <ExternalLink className="button" href={row.source_url}>Open in Drive</ExternalLink> : <Button variant="default" disabled={downloading !== null} aria-label={`Download PDF: ${row.label}`} onClick={async () => {
          setDownloading(row.id); setError(null);
          try { await companyDocuments.download(projectId, companyId, row); }
          catch (caught) { setError(caught instanceof Error ? caught.message : "Could not download the PDF."); }
          finally { setDownloading(null); }
        }}>{downloading === row.id ? "Downloading…" : "Download PDF"}</Button>}
        {canWrite ? <RowMenu label={`Actions for ${row.label}`}>
          <Button variant="quiet" onClick={() => setEditor({ row })}>Edit document</Button>
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
