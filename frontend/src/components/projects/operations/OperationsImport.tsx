"use client";

import { useState } from "react";
import { operations } from "@/lib/api/operations";
import type { OperationsImportReport } from "@/lib/api/operations";
import { Button, DraftBoundary, Field, FormActions, Notice, RecordPage, TableScroll } from "@/components/ui";

export function OperationsImport({projectId, onClose, onImported}: {
  projectId: string; onClose: () => void; onImported: () => void;
}) {
  const [file, setFile] = useState<{name: string; bytes: ArrayBuffer} | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<OperationsImportReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [validated, setValidated] = useState(false);
  const [completed, setCompleted] = useState(false);
  const run = async (operation: "validate" | "apply") => {
    if (!file || busy || completed) return;
    setBusy(true); setError(null); setValidated(false);
    try {
      const result = await operations.import(projectId, operation, file.bytes, reason);
      setReport(result);
      setValidated(operation === "validate" && result.issues.length === 0 && result.changed_clients > 0);
      if (result.applied) setCompleted(true);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "The import could not be completed."); }
    finally { setBusy(false); }
  };
  return <RecordPage title="Update Operations from Excel" onClose={completed ? onImported : onClose}>
    <DraftBoundary dirty={Boolean(file) && !completed} busy={busy}>
      <div className="stack">
        <ol className="operations-import-steps"><li><strong>Download</strong><span>All accessible clients, current values and this project’s stages.</span></li><li><strong>Fill in Excel</strong><span>One client per row. Blue inputs are editable; Sales signatures remain linked.</span></li><li><strong>Review and import</strong><span>Validate first, inspect the changes, then save the whole batch.</span></li></ol>
        <Button disabled={busy} onClick={async () => {
          setBusy(true); setError(null);
          try { await operations.template(projectId); }
          catch (caught) { setError(caught instanceof Error ? caught.message : "Download failed."); }
          finally { setBusy(false); }
        }}>Download client template</Button>
        <Notice tone="info">Blank cells keep current values. Choose Not recorded to clear a status or purpose; type CLEAR to remove a date. Use Excel dates or YYYY-MM-DD. Keep both header rows and the client IDs. Files are checked again when imported.</Notice>
        <Field label="Completed Excel template" hint=".xlsx, up to 5 MB and 5,000 clients. Nothing is saved during validation.">
          <input type="file" accept=".xlsx" disabled={busy || completed} onChange={async event => {
            const chosen = event.target.files?.[0];
            setFile(null); setReport(null); setValidated(false); setError(null);
            if (!chosen) return;
            if (!chosen.name.toLowerCase().endsWith(".xlsx") || !chosen.size || chosen.size > 5 * 1024 * 1024) {setError("Choose a non-empty .xlsx file up to 5 MB."); return;}
            setBusy(true);
            try {setFile({name:chosen.name, bytes:await chosen.arrayBuffer()});}
            catch {setError("Could not read the file. Choose it again.");}
            finally {setBusy(false);}
          }} />
        </Field>
        {file ? <p className="muted">Selected: {file.name}</p> : null}
        {error ? <Notice tone="error">{error}</Notice> : null}
        {report ? <section className="stack" aria-label="Import review" aria-live="polite">
          <Notice tone={report.applied ? "success" : report.issues.length ? "error" : "info"}>
            {report.applied ? `Updated ${report.changed_clients} clients. ${report.change_count} field changes saved together.` : report.issues.length ? `${report.issues.length} issues found. Nothing saved. Correct the file and upload it again.` : `${report.changed_clients} clients will change; ${report.unchanged_clients} unchanged. ${report.change_count} field changes to review.`}
          </Notice>
          {report.issues.length ? <TableScroll label="Excel issues"><thead><tr><th>Excel row</th><th>Issue</th></tr></thead><tbody>{report.issues.map((issue, index) => <tr key={index}><td>{issue.row}</td><td>{issue.message}</td></tr>)}</tbody></TableScroll> : null}
          {report.changes.length ? <TableScroll label="Proposed Operations changes"><thead><tr><th>Excel row</th><th>Client</th><th>Field</th><th>Current</th><th>From Excel</th></tr></thead><tbody>{report.changes.map((change, index) => <tr key={index}><td>{change.row}</td><th scope="row">{change.client}</th><td>{change.field}</td><td>{change.before}</td><td>{change.after}</td></tr>)}</tbody></TableScroll> : null}
        </section> : null}
        {!completed ? <Field label="Reason for import" hint="Saved in the audit history for every updated client."><input className="input" maxLength={1000} value={reason} disabled={busy} onChange={event => setReason(event.target.value)} /></Field> : null}
        <FormActions>
          {!completed ? <><Button disabled={busy || !file} onClick={() => run("validate")}>{busy ? "Working…" : "Validate and preview"}</Button><Button variant="primary" disabled={busy || !validated || !reason.trim()} onClick={() => run("apply")}>Import {report?.changed_clients ?? ""} client updates</Button></> : null}
          <Button disabled={busy} data-leaves-editor onClick={completed ? onImported : onClose}>{completed ? "Back to updated clients" : "Cancel"}</Button>
        </FormActions>
      </div>
    </DraftBoundary>
  </RecordPage>;
}
