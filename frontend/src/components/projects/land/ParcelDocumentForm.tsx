"use client";

import { useState } from "react";
import { projects } from "@/lib/api";
import type { DocumentReference } from "@/lib/api";
import { useAnswer } from "@/lib/answer";
import { Button, Card, ChoiceCards, DraftBoundary, Field, FormActions, Loading, Notice, RecordPage } from "@/components/ui";

export function ParcelDocumentForm({ projectId, parcelId, onClose, onSaved }: {
  projectId: string; parcelId: string; onClose: () => void; onSaved: (document: DocumentReference) => void;
}) {
  const types = useAnswer(true, () => projects.documentTypes(projectId), [projectId]);
  const [title, setTitle] = useState("");
  const [type, setType] = useState("");
  const [source, setSource] = useState("pdf");
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return <RecordPage icon="documents" title="Add document" onClose={onClose}>
    <Card title="Document details">
      <DraftBoundary dirty={!!(title || type || file || url)} busy={busy}>
        <form onSubmit={async event => {
          event.preventDefault(); if (busy) return;
          setBusy(true); setError(null);
          try {
            if (!title.trim()) throw new Error("Enter a document name.");
            const payload = { title: title.trim(), document_type_code: type, parcel_id: parcelId };
            let saved: DocumentReference;
            if (source === "pdf") {
              if (!file || !file.name.toLowerCase().endsWith(".pdf")) throw new Error("Choose one PDF file.");
              if (file.size > 10 * 1024 * 1024) throw new Error("PDF files must be no larger than 10 MB.");
              saved = await projects.uploadDocument(projectId, payload, file);
            } else {
              let link: URL;
              try { link = new URL(url.trim()); } catch { throw new Error("Enter an HTTPS sharing link."); }
              if (link.protocol !== "https:") throw new Error("Enter an HTTPS sharing link.");
              saved = await projects.createDocument(projectId, { ...payload, external_url: link.href });
            }
            onSaved(saved);
          } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not save the document."); }
          finally { setBusy(false); }
        }}>
          {error ? <Notice tone="error">{error}</Notice> : null}
          <Field label="Document name"><input className="input" required maxLength={200} disabled={busy} value={title} onChange={event => setTitle(event.target.value)} /></Field>
          {types.status === "loading" ? <Loading label="Loading document types…" /> : null}
          {types.status === "denied" ? <Notice tone="error">Document types are not available to your role.</Notice> : null}
          {types.status === "failed" ? <Notice tone="error">Document types could not be loaded.<Button onClick={types.retry}>Retry document types</Button></Notice> : null}
          {types.status === "ready" ? <Field label="Document type" hint={types.data.some(row => row.is_active) ? undefined : "Add a document type in project documents first."}>
            <select className="input" required disabled={busy} value={type} onChange={event => setType(event.target.value)}><option value="">Choose…</option>{types.data.filter(row => row.is_active).map(row => <option key={row.id} value={row.code}>{row.label}</option>)}</select>
          </Field> : null}
          <ChoiceCards label="Document source" name="parcel-document-source" value={source} columns={2} onChange={value => { if (!busy) setSource(value); }} options={[{ value: "pdf", label: "Upload PDF", description: "Stored in the system · up to 10 MB" }, { value: "drive", label: "Google Drive link", description: "Access stays controlled in Google Drive" }]} />
          {source === "pdf" ? <Field label="PDF file" hint="Choose one PDF up to 10 MB."><input className="input" type="file" accept=".pdf,application/pdf" required disabled={busy} onChange={event => setFile(event.target.files?.[0] ?? null)} /></Field> : <Field label="Google Drive link" hint="Paste an HTTPS sharing link. Access remains controlled by Google Drive."><input className="input" type="url" required maxLength={2000} disabled={busy} value={url} onChange={event => setUrl(event.target.value)} /></Field>}
          <FormActions><Button type="submit" variant="primary" disabled={busy || types.status !== "ready" || !type}>Save changes</Button><Button disabled={busy} data-leaves-editor onClick={onClose}>Cancel</Button></FormActions>
        </form>
      </DraftBoundary>
    </Card>
  </RecordPage>;
}
