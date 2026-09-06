"use client";

import { useState } from "react";

import { ApiError, inventory } from "@/lib/api";
import type { ImportReport, WorkbookReport } from "@/lib/api";
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
 * Loading a development's structure, in the order an operator actually works.
 *
 * Download the workbook, fill it in, choose it, validate, read what is wrong,
 * fix the file, apply. Apply stays disabled until a validation run came back
 * clean, and the server reads the bytes again when it does — a clean validate
 * is not a token that unlocks anything.
 *
 * **Excel is the normal path now.** "Load template" used to drop CSV text into
 * a textarea, which is a developer's idea of a template: a project team cannot
 * fill that in, and a team asked to build a spreadsheet from a column list
 * hands back a file that does not import. The button downloads the exact
 * workbook the parser reads.
 *
 * The mature CSV importer is still here, behind one affordance, because it
 * carries area schedules, custom fields and explicit unit identity that the
 * first workbook deliberately does not. It is not the thing to put in front of
 * somebody loading a development for the first time.
 */
export function ImportPanel({
  projectId,
  onApplied,
}: {
  projectId: string;
  onApplied: () => Promise<void>;
}) {
  const [bytes, setBytes] = useState<ArrayBuffer | null>(null);
  const [filename, setFilename] = useState("");
  const [size, setSize] = useState(0);
  const [mode, setMode] = useState<"create" | "upsert">("create");
  const [report, setReport] = useState<WorkbookReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [advanced, setAdvanced] = useState(false);

  const reset = () => {
    setReport(null);
    setNotice(null);
    setError(null);
  };

  const choose = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    reset();
    if (!file) {
      setBytes(null);
      setFilename("");
      setSize(0);
      return;
    }
    setFilename(file.name);
    setSize(file.size);
    setBytes(await file.arrayBuffer());
  };

  const download = async () => {
    reset();
    try {
      await inventory.workbookTemplate(projectId);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Could not download the template.",
      );
    }
  };

  const run = async (apply: boolean) => {
    if (bytes === null) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = apply
        ? await inventory.applyWorkbook(projectId, bytes, { mode })
        : await inventory.validateWorkbook(projectId, bytes, { mode });
      setReport(result);
      if (apply && result.applied) {
        setNotice(
          `Applied: ${result.create_count} created, ${result.update_count} updated. Nothing was left half-written.`,
        );
        await onApplied();
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not read that workbook.");
    } finally {
      setBusy(false);
    }
  };

  const ready = report !== null && report.error_count === 0 && !report.applied;
  const records = report?.structure.records ?? null;

  return (
    <div className="stack">
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      <FieldRow columns={2}>
        <Field
          label="Excel workbook"
          hint={
            filename
              ? `${filename} · ${Math.round(size / 1024)} KB`
              : "Download the template first, fill in the sheets you need, then choose it here."
          }
        >
          <input
            className="input"
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={(event) => void choose(event)}
          />
        </Field>
        <Field
          label="Mode"
          hint="Create refuses a code that already exists. Upsert updates the record that code names."
        >
          <select
            className="input"
            value={mode}
            onChange={(event) => {
              setMode(event.target.value as "create" | "upsert");
              reset();
            }}
          >
            <option value="create">Create</option>
            <option value="upsert">Upsert</option>
          </select>
        </Field>
      </FieldRow>

      <FormActions>
        <Button variant="quiet" onClick={() => void download()}>
          Download Excel template
        </Button>
        <Button disabled={bytes === null || busy} onClick={() => void run(false)}>
          {busy ? "Working…" : "Validate"}
        </Button>
        <Button variant="primary" disabled={!ready || busy} onClick={() => void run(true)}>
          Apply
        </Button>
      </FormActions>

      {report ? (
        <>
          <InlineMeta>
            <InlineMetaItem label="Phases">
              {records ? records.phases.create + records.phases.update : 0}
            </InlineMetaItem>
            <InlineMetaItem label="Buildings">
              {records ? records.buildings.create + records.buildings.update : 0}
            </InlineMetaItem>
            <InlineMetaItem label="Floors">
              {records ? records.floors.create + records.floors.update : 0}
            </InlineMetaItem>
            <InlineMetaItem label="Units">
              {records ? records.units.create + records.units.update : 0}
            </InlineMetaItem>
            <InlineMetaItem label="To create">{report.create_count}</InlineMetaItem>
            <InlineMetaItem label="To update">{report.update_count}</InlineMetaItem>
            <InlineMetaItem label="Errors">{report.error_count}</InlineMetaItem>
          </InlineMeta>
          {report.template_version ? (
            <p className="subtle">Template version {report.template_version}.</p>
          ) : null}
          {ready ? (
            <Notice tone="info">
              Nothing has been written yet. Apply to commit the whole workbook — all four
              sheets, or none of them.
            </Notice>
          ) : null}
          {report.issues.length > 0 ? <IssueRegister issues={report.issues} /> : null}
          {report.issues_truncated ? (
            <p className="subtle">
              Showing the first {report.issues.length} of {report.error_count} problems.
            </p>
          ) : null}
        </>
      ) : null}

      <div>
        <Button variant="quiet" onClick={() => setAdvanced(!advanced)} aria-expanded={advanced}>
          {advanced ? "Hide advanced CSV import" : "Advanced CSV import"}
        </Button>
      </div>
      {advanced ? <CsvImport projectId={projectId} onApplied={onApplied} /> : null}
    </div>
  );
}

/**
 * Sheet, row, column, problem — in that order.
 *
 * A workbook has four sheets and four row 7s, so a row number without its
 * sheet sends an operator to the wrong tab.
 */
function IssueRegister({ issues }: { issues: ImportReport["issues"] }) {
  return (
    <TableScroll label="Import issues" compact>
      <thead>
        <tr>
          <th scope="col">Sheet</th>
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
        {issues.map((issue, index) => (
          <tr key={`${issue.sheet}-${issue.row}-${issue.column}-${index}`}>
            <th scope="row">{issue.sheet ?? "—"}</th>
            <td className="num">{issue.row}</td>
            <td>{issue.column ?? "—"}</td>
            <td className="cell-prose">{issue.message}</td>
          </tr>
        ))}
      </tbody>
    </TableScroll>
  );
}

/**
 * The mature CSV importer, kept intact and kept out of the way.
 *
 * It carries area schedules, custom fields, `<CLEAR>` and explicit unit
 * identity — everything the first workbook leaves to a later PR. Removing it to
 * make the new screen tidy would take capability away from the people already
 * relying on it.
 */
function CsvImport({
  projectId,
  onApplied,
}: {
  projectId: string;
  onApplied: () => Promise<void>;
}) {
  const [csv, setCsv] = useState<string | null>(null);
  const [filename, setFilename] = useState("");
  const [mode, setMode] = useState<"create" | "upsert">("create");
  const [createHierarchy, setCreateHierarchy] = useState(true);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const query = () => ({ mode, create_missing_hierarchy: String(createHierarchy) });

  const run = async (apply: boolean) => {
    if (csv === null) return;
    setBusy(true);
    setError(null);
    try {
      const result = apply
        ? await inventory.applyImport(projectId, csv, query())
        : await inventory.validateImport(projectId, csv, query());
      setReport(result);
      if (apply && result.applied) await onApplied();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not read that file.");
    } finally {
      setBusy(false);
    }
  };

  const ready = report !== null && report.error_count === 0 && !report.applied;

  return (
    <div className="stack">
      <Notice tone="info">
        The CSV contract is unchanged. Use it for area schedules, custom fields and updates
        that name a unit by its identifier.
      </Notice>
      <FieldRow columns={3}>
        <Field label="CSV file" hint={filename ? `Chosen: ${filename}` : undefined}>
          <input
            className="input"
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => {
              const file = event.target.files?.[0];
              setReport(null);
              setError(null);
              if (!file) {
                setCsv(null);
                setFilename("");
                return;
              }
              setFilename(file.name);
              void file.text().then(setCsv);
            }}
          />
        </Field>
        <Field label="Mode">
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
      {error ? <Notice tone="error">{error}</Notice> : null}
      <FormActions>
        <Button disabled={csv === null || busy} onClick={() => void run(false)}>
          {busy ? "Working…" : "Validate CSV"}
        </Button>
        <Button variant="primary" disabled={!ready || busy} onClick={() => void run(true)}>
          Apply CSV
        </Button>
      </FormActions>
      {report ? (
        <>
          <InlineMeta>
            <InlineMetaItem label="Rows">{report.total_rows}</InlineMetaItem>
            <InlineMetaItem label="Valid">{report.valid_rows}</InlineMetaItem>
            <InlineMetaItem label="Errors">{report.error_count}</InlineMetaItem>
          </InlineMeta>
          {report.issues.length > 0 ? <IssueRegister issues={report.issues} /> : null}
        </>
      ) : null}
    </div>
  );
}
