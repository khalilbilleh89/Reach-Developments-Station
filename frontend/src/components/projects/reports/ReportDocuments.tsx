"use client";

import { useState } from "react";
import { useAnswer } from "@/lib/answer";
import { siteReports, reportSections, applicabilityOf } from "@/lib/api/siteReports";
import { businessDate } from "@/lib/format";
import type { ReportKind, SiteReport, SiteReportFields } from "@/lib/api/siteReports";
import { Button, ButtonRow, Card, ChoiceCards, DraftBoundary, ExternalLink, Field, FormActions, Loading, Notice, RecordPage, Segmented } from "@/components/ui";


const fieldsOf = (row?: SiteReport, kind: ReportKind = "site_report"): SiteReportFields => ({ title: row?.title ?? "", report_date: row?.report_date ?? null, notes: row?.notes ?? "", kind: row?.kind ?? kind, building_id: row?.building_id ?? null, unit_ids: row?.unit_ids ?? [] });
import { ReportApplicability } from "./ReportApplicability";

const message = (error: unknown) => error instanceof Error ? error.message : "Could not save the report.";

export function SiteReportForm({ projectId = "", kind = "site_report", row, onSave, onClose, onSaved }: { projectId?: string; kind?: ReportKind; row?: SiteReport; onSave: (fields: SiteReportFields, file: File | null, sourceUrl?: string) => Promise<unknown>; onClose: () => void; onSaved: () => void }) {
  const section = reportSections[kind];
  const isSite = kind === "site_report";
  const [form, setForm] = useState(() => fieldsOf(row, kind));
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("pdf");
  const [sourceUrl, setSourceUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reset = () => { setForm(fieldsOf(row, kind)); setFile(null); setSource("pdf"); setSourceUrl(""); };
  return <RecordPage icon="documents" title={row ? `Edit ${section.singular} details` : section.add} subtitle={row ? row.filename ?? "Google Drive link" : undefined} onClose={onClose}>
    <Card title={isSite ? "Report details" : kind === "architect_certificate" ? "Certificate details" : "Charter details"} description={isSite ? "Title, report date and a PDF or Drive link from your site engineer." : section.description}>
      <DraftBoundary dirty={JSON.stringify(form) !== JSON.stringify(fieldsOf(row, kind)) || !!file || !!sourceUrl || source !== "pdf"} busy={busy} onDiscard={reset}>
        <form className="stack" onSubmit={async event => {
          event.preventDefault(); setError(null);
          if (!form.title.trim()) { setError("Enter a report title."); return; }
          if (isSite && !form.report_date) { setError("Enter the report date."); return; }
          if (!isSite && !form.building_id && !form.unit_ids?.length) { setError(kind === "client_charter" ? "Choose a unit for this charter." : "Choose a building or units for this certificate."); return; }
          if (!row && source === "pdf" && !file) { setError("Choose a PDF file."); return; }
          if (!row && source === "drive" && !sourceUrl.trim()) { setError("Enter a Google Drive link."); return; }
          setBusy(true);
          try { await onSave({ ...form, title: form.title.trim() }, source === "pdf" ? file : null, source === "drive" ? sourceUrl.trim() : undefined); onSaved(); onClose(); }
          catch (caught) { setError(message(caught)); } finally { setBusy(false); }
        }}>
          {error ? <Notice tone="error">{error}</Notice> : null}
          <fieldset className="draft-fields" disabled={busy}><Field label={section.title}><input className="input" required maxLength={320} disabled={busy} placeholder={isSite ? "e.g. Weekly site inspection" : kind === "architect_certificate" ? "e.g. Building A completion certificate" : "e.g. Unit A-101 client charter"} value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} /></Field>
          {!isSite ? <ReportApplicability projectId={projectId} row={row} form={form} onChange={setForm} /> : null}
          <Field label={isSite ? "Report date" : "Document date"} optional={!isSite}><input className="input" type="date" required={isSite} value={form.report_date ?? ""} onChange={e => setForm({ ...form, report_date: e.target.value || null })} /></Field>
          {!row ? <>
            <ChoiceCards label="Document source" name="report-source" value={source} columns={2} onChange={setSource} options={[{value: "pdf", label: "Upload PDF", description: "Review inside the system · up to 50 MB"}, {value: "drive", label: "Google Drive link", description: "Open the shared document in Google Drive"}]} />
            {source === "pdf" ? <Field label="PDF file" hint="Up to 50 MB. Upload revisions separately to preserve the earlier document."><input className="input" type="file" accept=".pdf,application/pdf" required disabled={busy} onChange={e => setFile(e.target.files?.[0] ?? null)} /></Field> : <Field label="Google Drive link" hint="Paste a Google Drive or Google Docs sharing link. Each viewer needs access in Drive."><input className="input" type="url" required maxLength={2000} value={sourceUrl} placeholder="https://drive.google.com/file/d/…/view" onChange={e => setSourceUrl(e.target.value)} /></Field>}
          </> : <p className="footnote">The original PDF or Drive link is retained. Add another document for a new source or revision.</p>}
          <Field label="Notes" optional><textarea className="input" maxLength={2000} rows={3} disabled={busy} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} /></Field>
          </fieldset>
          <FormActions><Button type="submit" variant="primary" disabled={busy}>{busy ? "Saving…" : row ? "Save details" : source === "drive" ? "Save link" : `Upload ${section.singular}`}</Button><Button disabled={busy} data-leaves-editor onClick={onClose}>Cancel</Button></FormActions>
        </form>
      </DraftBoundary>
    </Card>
  </RecordPage>;
}

export function LinkedSiteReportViewer({ row, onClose }: { row: SiteReport; onClose: () => void }) {
  return <RecordPage icon="documents" title={row.title} subtitle={`${row.report_date ? businessDate(row.report_date) + " · " : ""}${applicabilityOf(row) ? applicabilityOf(row) + " · " : ""}Google Drive`} onClose={onClose}>
    <Card title="Open the shared document" description="This document is stored in Google Drive. Your Drive account must have permission to view it.">
      <div className="stack">
        {row.notes ? <p className="drawing-notes">{row.notes}</p> : null}
        {row.source_url ? <ExternalLink href={row.source_url}>Open document in Google Drive</ExternalLink> : null}
        <p className="footnote">Opens in a new tab. The library stores the link, not a copy of the file; changes and sharing are managed in Drive.</p>
      </div>
    </Card>
  </RecordPage>;
}

export function SiteReportViewer({ projectId, row, onClose }: { projectId: string; row: SiteReport; onClose: () => void }) {
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(100);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const preview = useAnswer(true, () => siteReports.preview(projectId, row, page), [projectId, row.id, page]);
  return <RecordPage icon="documents" title={row.title} subtitle={[row.report_date ? businessDate(row.report_date) : "", applicabilityOf(row), row.filename].filter(Boolean).join(" · ")} onClose={onClose} actions={<Button disabled={downloading} onClick={async () => { setDownloading(true); setError(null); try { await siteReports.download(projectId, row); } catch (caught) { setError(message(caught)); } finally { setDownloading(false); } }}>{downloading ? "Downloading…" : "Download original PDF"}</Button>}>
    <div className="stack">
      {row.notes ? <p className="drawing-notes">{row.notes}</p> : null}
      {error ? <Notice tone="error">{error}</Notice> : null}
      <div className="drawing-view-controls">
        <ButtonRow><Button disabled={page <= 1 || preview.status === "loading"} onClick={() => setPage(page - 1)}>Previous page</Button><span aria-live="polite">Page {page}{preview.status === "ready" ? ` of ${preview.data.page_count}` : ""}</span><Button disabled={preview.status !== "ready" || page >= preview.data.page_count} onClick={() => setPage(page + 1)}>Next page</Button></ButtonRow>
        <form className="row-actions" onSubmit={event => {
          event.preventDefault();
          const target = Number(new FormData(event.currentTarget).get("page"));
          if (preview.status === "ready" && Number.isInteger(target) && target >= 1 && target <= preview.data.page_count) setPage(target);
        }}><Field label="Go to page"><input key={page} className="input" name="page" type="number" min={1} max={preview.status === "ready" ? preview.data.page_count : undefined} defaultValue={page} required disabled={preview.status !== "ready"} /></Field><Button type="submit" disabled={preview.status !== "ready"}>Go</Button></form>
        <Field label="Zoom"><Segmented label="Zoom" value={String(zoom)} onChange={value => setZoom(Number(value))} options={[{ value: "100", label: "Fit width" }, { value: "150", label: "150%" }, { value: "200", label: "200%" }, { value: "300", label: "300%" }]} /></Field>
      </div>
      {preview.status === "loading" ? <Loading label="Opening report page…" /> : null}
      {preview.status === "denied" ? <Notice tone="warning">This report is no longer available to your account.</Notice> : null}
      {preview.status === "failed" ? <><Notice tone="error">{preview.message} You can still download the original PDF.</Notice><Button onClick={preview.retry}>Retry preview</Button></> : null}
      {preview.status === "ready" ? <div className="drawing-canvas" tabIndex={0} role="region" aria-label="Report page. Scroll to inspect the enlarged report.">
        {/* The source is a server-rendered page image, never executable PDF content. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={preview.data.image} alt={`${row.title}, page ${page}`} style={{ width: `${zoom}%` }} />
      </div> : null}
      <p className="footnote">Preview for review. Download the original PDF for full vector detail and printing to scale.</p>
    </div>
  </RecordPage>;
}
