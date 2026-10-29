"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { salesImport } from "@/lib/api/salesImport";
import type { ImportKind, SalesImportReport } from "@/lib/api/salesImport";
import { Button, DraftBoundary, Field, FormActions, Notice, RecordPage, TableScroll } from "@/components/ui";

export function SalesImport({projectId, kind, onClose, onImported}: {
  projectId: string; kind: ImportKind; onClose: () => void; onImported: () => void;
}) {
  const [file, setFile] = useState<{ name: string; bytes: ArrayBuffer } | null>(null);
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<SalesImportReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [validated, setValidated] = useState(false);
  const [completed, setCompleted] = useState(false);
  const showError = (caught: unknown) => setError(caught instanceof ApiError || caught instanceof Error ? caught.message : "Import could not be completed.");
  const run = async (operation: "validate" | "apply") => {
    if (!file || busy) return;
    setBusy(true); setError(null); setValidated(false);
    try {
      const result = await salesImport.run(projectId, kind, operation, file.bytes);
      setReport(result);
      setValidated(operation === "validate" && result.error_count === 0);
      if (result.applied) { setCompleted(true); onImported(); }
    } catch (caught) { showError(caught); }
    finally { setBusy(false); }
  };
  const label = kind === "faqs" ? "FAQs" : kind;
  return <RecordPage title={`Import ${label} from Excel`} onClose={onClose}>
    <DraftBoundary dirty={Boolean(file) && !completed} busy={busy}>
      <div className="stack">
        <p>Download the template, fill one record per row, then upload it here. Up to 1,000 records and 5 MB per file. {kind === "faqs" ? "Enter a Question and Answer for each FAQ. Duplicate questions are flagged; existing answers are never overwritten." : "The fields match registration; existing records are never updated."}</p>
        <Button disabled={busy} onClick={async () => {
          setBusy(true); setError(null);
          try { await salesImport.template(projectId, kind); } catch (caught) { showError(caught); }
          finally { setBusy(false); }
        }}>Download Excel template</Button>
        <Field label="Completed Excel template" hint={kind === "faqs" ? "Use .xlsx with plain text. Line breaks and all languages are supported. Keep the template's sheet names and headers." : "Use .xlsx. Keep phone numbers as Text to preserve leading zeros."}>
          <input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" disabled={busy} onChange={async event => {
            const chosen = event.target.files?.[0];
            setFile(null); setReport(null); setValidated(false); setCompleted(false); setError(null);
            if (!chosen) return;
            if (!chosen.name.toLowerCase().endsWith(".xlsx") || !chosen.size || chosen.size > 5 * 1024 * 1024) {
              setError("Choose a non-empty .xlsx file up to 5 MB."); return;
            }
            setBusy(true);
            try { setFile({name: chosen.name, bytes: await chosen.arrayBuffer()}); }
            catch { setError("Could not read that file. Choose it again."); }
            finally { setBusy(false); }
          }} />
        </Field>
        {file ? <p className="subtle">Selected: {file.name}</p> : null}
        {error ? <Notice tone="error">{error}</Notice> : null}
        {report ? <div aria-live="polite" className="stack">
          <Notice tone={report.applied ? "success" : report.error_count ? "error" : "info"}>
            {report.applied ? `Imported ${report.created_count} ${label}.` : report.error_count ? `${report.error_count} issues found. No records imported. Fix the file and upload it again.` : `${report.total_rows} rows validated. Ready to import.`}
          </Notice>
          {report.issues.length ? <TableScroll label="Import issues"><thead><tr><th>Excel row</th><th>Field</th><th>Issue</th></tr></thead><tbody>{report.issues.map((issue, index) => <tr key={index}><td>{issue.row}</td><td>{issue.column ?? "Record"}</td><td>{issue.message}</td></tr>)}</tbody></TableScroll> : null}
          {report.issues_truncated ? <p>Showing the first 200 issues. Fix these and validate again.</p> : null}
        </div> : null}
        <FormActions>
          <Button disabled={busy || !file || completed} onClick={() => run("validate")}>{busy ? "Working…" : "Validate file"}</Button>
          <Button variant="primary" disabled={busy || !validated || completed} onClick={() => run("apply")}>Import {report?.total_rows ?? ""} {label}</Button>
          <Button disabled={busy} data-leaves-editor onClick={onClose}>{completed ? "Back to register" : "Cancel"}</Button>
        </FormActions>
      </div>
    </DraftBoundary>
  </RecordPage>;
}
