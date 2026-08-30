"use client";

import { useState } from "react";

import { ApiError, inventory } from "@/lib/api";
import type { ImportReport } from "@/lib/api";
import { Button, Field, Notice, TableScroll } from "@/components/ui";

/**
 * Bulk inventory load, in the order an operator actually works.
 *
 * Choose a file, validate it, read what is wrong, fix the file, apply. Apply
 * stays disabled until a validation run came back clean — nothing is written on
 * file selection, and a 247-row load is never half-applied.
 *
 * The file is read in the browser with `File.text()` and posted as raw
 * `text/csv`, so there is no upload library here and no multipart parser on the
 * server.
 */
export function ImportPanel({
  projectId,
  onApplied,
}: {
  projectId: string;
  onApplied: () => Promise<void>;
}) {
  const [csv, setCsv] = useState<string | null>(null);
  const [filename, setFilename] = useState<string>("");
  const [mode, setMode] = useState<"create" | "upsert">("create");
  const [createHierarchy, setCreateHierarchy] = useState(true);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const query = () => ({
    mode,
    create_missing_hierarchy: String(createHierarchy),
  });

  const choose = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    setReport(null);
    setNotice(null);
    setError(null);
    if (!file) {
      setCsv(null);
      setFilename("");
      return;
    }
    setFilename(file.name);
    setCsv(await file.text());
  };

  const run = async (apply: boolean) => {
    if (csv === null) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = apply
        ? await inventory.applyImport(projectId, csv, query())
        : await inventory.validateImport(projectId, csv, query());
      setReport(result);
      if (apply && result.applied) {
        setNotice(
          `Applied: ${result.create_count} created, ${result.update_count} updated.`,
        );
        await onApplied();
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not read that file.");
    } finally {
      setBusy(false);
    }
  };

  const showTemplate = async () => {
    try {
      const template = await inventory.importTemplate(projectId);
      setCsv(template.content);
      setFilename(template.filename);
      setReport(null);
      setNotice("Template loaded. Validate it to see the shape, or paste your own file.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not load the template.");
    }
  };

  const ready = report !== null && report.error_count === 0 && !report.applied;

  return (
    <div>
      <h3 className="section-heading">Import inventory</h3>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      <div className="form-inline">
        <Field label="CSV file">
          <input className="input" type="file" accept=".csv,text/csv" onChange={choose} />
        </Field>
        <Field label="Mode" hint="Upsert updates existing units by their identifier.">
          <select
            className="input input-short"
            value={mode}
            onChange={(event) => setMode(event.target.value as "create" | "upsert")}
          >
            <option value="create">Create</option>
            <option value="upsert">Upsert</option>
          </select>
        </Field>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={createHierarchy}
            onChange={(event) => setCreateHierarchy(event.target.checked)}
          />
          <span>Create missing phases, buildings and floors</span>
        </label>
      </div>

      <div className="form-actions">
        <Button onClick={() => void showTemplate()}>
          Load template
        </Button>
        <button
          className="button"
          type="button"
          disabled={csv === null || busy}
          onClick={() => void run(false)}
        >
          {busy ? "Working…" : "Validate"}
        </button>
        <button
          className="button button-primary"
          type="button"
          disabled={!ready || busy}
          onClick={() => void run(true)}
        >
          Apply
        </button>
        {filename ? <span className="subtle">{filename}</span> : null}
      </div>

      {report ? (
        <>
          <div className="chip-list">
            <span className="chip">{report.total_rows} rows</span>
            <span className="chip">{report.valid_rows} valid</span>
            <span className="chip">{report.error_count} errors</span>
            <span className="chip">{report.create_count} to create</span>
            <span className="chip">{report.update_count} to update</span>
          </div>
          {report.error_count === 0 && !report.applied ? (
            <Notice tone="info">Nothing has been written yet. Apply to commit the batch.</Notice>
          ) : null}
          {report.issues.length > 0 ? (
            <TableScroll label="Import issues">
                <thead>
                  <tr>
                    <th scope="col">Row</th>
                    <th scope="col">Column</th>
                    <th scope="col">Problem</th>
                  </tr>
                </thead>
                <tbody>
                  {report.issues.map((issue, index) => (
                    <tr key={`${issue.row}-${issue.column}-${index}`}>
                      <th scope="row">{issue.row}</th>
                      <td>{issue.column ?? "—"}</td>
                      <td>{issue.message}</td>
                    </tr>
                  ))}
                </tbody>
</TableScroll>
          ) : null}
          {report.issues_truncated ? (
            <p className="subtle">
              Showing the first {report.issues.length} of {report.error_count} problems.
            </p>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
