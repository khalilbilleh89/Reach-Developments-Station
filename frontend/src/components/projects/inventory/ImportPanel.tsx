"use client";

import { useState } from "react";

import { ApiError, inventory } from "@/lib/api";
import type { ImportReport } from "@/lib/api";
import {
  Button,
  Field,
  FieldRow,
  FormActions,
  InlineMeta,
  InlineMetaItem,
  Notice,
  TableScroll,
} from "@/components/ui";

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
        setNotice(`Applied: ${result.create_count} created, ${result.update_count} updated.`);
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
      setNotice("Template loaded. Validate it to see the shape, or choose your own file.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not load the template.");
    }
  };

  const ready = report !== null && report.error_count === 0 && !report.applied;

  return (
    <div className="stack">
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      <FieldRow columns={3}>
        <Field label="CSV file" hint={filename ? `Chosen: ${filename}` : "Or load the template to see the shape."}>
          <input className="input" type="file" accept=".csv,text/csv" onChange={choose} />
        </Field>
        <Field label="Mode" hint="Upsert updates existing units by their identifier.">
          <select
            className="input"
            value={mode}
            onChange={(event) => setMode(event.target.value as "create" | "upsert")}
          >
            <option value="create">Create</option>
            <option value="upsert">Upsert</option>
          </select>
        </Field>
        <Field label="Structure">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={createHierarchy}
              onChange={(event) => setCreateHierarchy(event.target.checked)}
            />
            <span>Create missing phases, buildings and floors</span>
          </label>
        </Field>
      </FieldRow>

      <FormActions>
        <Button variant="quiet" onClick={() => void showTemplate()}>
          Load template
        </Button>
        <Button disabled={csv === null || busy} onClick={() => void run(false)}>
          {busy ? "Working…" : "Validate"}
        </Button>
        <Button variant="primary" disabled={!ready || busy} onClick={() => void run(true)}>
          Apply
        </Button>
      </FormActions>

      {report ? (
        <>
          <InlineMeta>
            <InlineMetaItem label="Rows">{report.total_rows}</InlineMetaItem>
            <InlineMetaItem label="Valid">{report.valid_rows}</InlineMetaItem>
            <InlineMetaItem label="Errors">{report.error_count}</InlineMetaItem>
            <InlineMetaItem label="To create">{report.create_count}</InlineMetaItem>
            <InlineMetaItem label="To update">{report.update_count}</InlineMetaItem>
          </InlineMeta>
          {report.error_count === 0 && !report.applied ? (
            <Notice tone="info">Nothing has been written yet. Apply to commit the batch.</Notice>
          ) : null}
          {report.issues.length > 0 ? (
            <TableScroll label="Import issues" compact>
              <thead>
                <tr>
                  <th scope="col" className="num">
                    Row
                  </th>
                  <th scope="col">Column</th>
                  <th scope="col" className="cell-prose">
                    Problem
                  </th>
                </tr>
              </thead>
              <tbody>
                {report.issues.map((issue, index) => (
                  <tr key={`${issue.row}-${issue.column}-${index}`}>
                    <th scope="row" className="num">
                      {issue.row}
                    </th>
                    <td>{issue.column ?? "—"}</td>
                    <td className="cell-prose">{issue.message}</td>
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
