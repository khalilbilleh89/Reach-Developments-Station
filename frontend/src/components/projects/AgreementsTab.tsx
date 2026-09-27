"use client";

import { useState } from "react";
import { agreements, type Agreement, type AgreementFields } from "@/lib/api/agreements";
import { useAnswer } from "@/lib/answer";
import { AGREEMENT_READERS, AGREEMENT_WRITERS, hasAnyRole, type Roles } from "@/lib/roles";
import { Button, Card, DraftBoundary, EmptyState, Field, FieldRow, FormActions, Loading, Notice, PageHeader, RecordPage, TableScroll } from "@/components/ui";
import { DeleteRecordButton } from "./DeleteRecordButton";

export function AgreementForm({ row, onSave, onClose }: {
  row?: Agreement; onSave: (fields: AgreementFields, file: File | null) => Promise<void>; onClose: () => void;
}) {
  const [initial] = useState<AgreementFields>(() => ({ name: row?.name ?? "", signing_company: row?.signing_company ?? "", draft_created_on: row?.draft_created_on ?? "" }));
  const [fields, setFields] = useState(initial);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return <RecordPage title={row ? "Edit agreement" : "Add agreement"} onClose={onClose}>
    <DraftBoundary dirty={file !== null || JSON.stringify(fields) !== JSON.stringify(initial)} busy={busy}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault();
        if (busy) return;
        if (!row && !file) { setError("Choose the final agreement document."); return; }
        setBusy(true); setError(null);
        try { await onSave(fields, file); onClose(); }
        catch (caught) { setError(caught instanceof Error ? caught.message : "Could not save. Your entries have been kept."); }
        finally { setBusy(false); }
      }}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <div className="stack">
          <FieldRow>
            <Field label="Agreement name"><input className="input" disabled={busy} required maxLength={320} value={fields.name} onChange={event => setFields({ ...fields, name: event.target.value })} /></Field>
            <Field label="Signing company"><input className="input" disabled={busy} required maxLength={320} value={fields.signing_company} onChange={event => setFields({ ...fields, signing_company: event.target.value })} /></Field>
            <Field label="Draft creation date"><input className="input" disabled={busy} type="date" required value={fields.draft_created_on} onChange={event => setFields({ ...fields, draft_created_on: event.target.value })} /></Field>
          </FieldRow>
          {row ? <p>Document: <strong>{row.filename}</strong>. To replace the document, add a new agreement and delete the old entry.</p> :
            <Field label="Final agreement document" hint="PDF or Word (.pdf, .doc, .docx), up to 10 MB."><input className="input" disabled={busy} type="file" required accept=".pdf,.doc,.docx" onChange={event => setFile(event.target.files?.[0] ?? null)} /></Field>}
        </div>
        <FormActions><Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save agreement"}</Button><Button variant="default" disabled={busy} data-leaves-editor onClick={onClose}>Cancel</Button></FormActions>
      </form>
    </DraftBoundary>
  </RecordPage>;
}

export function AgreementsTab({ projectId, roles }: { projectId: string; roles: Roles }) {
  const answer = useAnswer(hasAnyRole(roles, AGREEMENT_READERS), () => agreements.list(projectId), [projectId]);
  const canWrite = hasAnyRole(roles, AGREEMENT_WRITERS);
  const [editor, setEditor] = useState<{ row?: Agreement } | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  return <div className="stack">
    <PageHeader title="Agreements" subtitle="Final agreement drafts clients need to sign to complete their purchase." actions={canWrite ? <Button onClick={() => setEditor({})}>Add agreement</Button> : undefined} />
    {answer.status === "loading" ? <Loading label="Loading agreements…" /> : null}
    {answer.status === "off" || answer.status === "denied" ? <Notice tone="info">Agreements are not available to your access level.</Notice> : null}
    {answer.status === "failed" ? <Notice tone="error">{answer.message} <Button variant="default" onClick={answer.retry}>Retry</Button></Notice> : null}
    {downloadError ? <Notice tone="error">{downloadError}</Notice> : null}
    {answer.status === "ready" ? <Card>
      {answer.data.length === 0 ? <EmptyState title="No agreements added" hint="Upload each final draft, name the signing company, and enter the date the draft was created." /> :
        <TableScroll label="Purchase agreement drafts"><thead><tr><th scope="col">Agreement name</th><th scope="col">Signing company</th><th scope="col">Draft creation date</th><th scope="col">Document</th>{canWrite ? <th scope="col">Actions</th> : null}</tr></thead>
          <tbody>{answer.data.map(row => <tr key={row.id}>
            <th scope="row">{row.name}</th><td>{row.signing_company}</td><td><time dateTime={row.draft_created_on}>{row.draft_created_on}</time></td>
            <td><Button variant="default" disabled={downloading !== null} onClick={async () => {
              setDownloading(row.id); setDownloadError(null);
              try { await agreements.download(projectId, row); }
              catch (caught) { setDownloadError(caught instanceof Error ? caught.message : "Could not download the document."); }
              finally { setDownloading(null); }
            }}>{downloading === row.id ? "Downloading…" : row.filename}</Button></td>
            {canWrite ? <td><div className="row-actions"><Button variant="default" onClick={() => setEditor({ row })}>Edit</Button>
              <DeleteRecordButton label="agreement" recordName={row.name} confirmLabel="Delete agreement" description="Remove this final draft from the register. The document and audit history will be retained." onDelete={reason => agreements.remove(projectId, row, reason)} onDeleted={async () => { answer.retry(); }} />
            </div></td> : null}
          </tr>)}</tbody>
        </TableScroll>}
    </Card> : null}
    {editor ? <AgreementForm key={editor.row?.id ?? "new"} row={editor.row} onClose={() => setEditor(null)} onSave={async (fields, file) => {
      if (editor.row) await agreements.update(projectId, editor.row, fields);
      else if (file) await agreements.create(projectId, fields, file);
      answer.retry();
    }} /> : null}
  </div>;
}
