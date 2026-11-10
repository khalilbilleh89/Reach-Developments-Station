"use client";

import { useState } from "react";
import { useAnswer } from "@/lib/answer";
import { siteReports } from "@/lib/api/siteReports";
import { businessDate } from "@/lib/format";
import type { SiteReport, SiteReportFields } from "@/lib/api/siteReports";
import { Button, ButtonRow, Card, ChoiceCards, DraftBoundary, ExternalLink, Field, FormActions, Loading, Notice, RecordPage, Segmented } from "@/components/ui";


const blank: SiteReportFields = { title: "", report_date: "", notes: "" };
const fieldsOf = (row?: SiteReport): SiteReportFields => row ? Object.fromEntries(Object.keys(blank).map(key => [key, row[key as keyof SiteReportFields]])) as unknown as SiteReportFields : { ...blank };
const message = (error: unknown) => error instanceof Error ? error.message : "Could not save the report.";

export function SiteReportForm({ row, onSave, onClose, onSaved }: { row?: SiteReport; onSave: (fields: SiteReportFields, file: File | null, sourceUrl?: string) => Promise<unknown>; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState(() => fieldsOf(row));
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("pdf");
  const [sourceUrl, setSourceUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reset = () => { setForm(fieldsOf(row)); setFile(null); setSource("pdf"); setSourceUrl(""); };
  return <RecordPage icon="documents" title={row ? "Edit report details" : "Add report"} subtitle={row?.filename ?? (row?.source_url ? "Google Drive link" : "Give your report a title and choose a PDF or Google Drive link.")} onClose={onClose}>
    <Card title="Report details" description="Title, report date and a PDF or Drive link from your site engineer.">
      <DraftBoundary dirty={JSON.stringify(form) !== JSON.stringify(fieldsOf(row)) || !!file || !!sourceUrl || source !== "pdf"} busy={busy} onDiscard={reset}>
        <form className="stack" onSubmit={async event => {
          event.preventDefault(); setError(null);
          if (!form.title.trim()) { setError("Enter a report title."); return; }
          if (!form.report_date) { setError("Enter the report date."); return; }
          if (!row && source === "pdf" && !file) { setError("Choose a PDF file."); return; }
          if (!row && source === "drive" && !sourceUrl.trim()) { setError("Enter a Google Drive link."); return; }
          setBusy(true);
          try { await onSave({ ...form, title: form.title.trim() }, source === "pdf" ? file : null, source === "drive" ? sourceUrl.trim() : undefined); onSaved(); onClose(); }
          catch (caught) { setError(message(caught)); } finally { setBusy(false); }
        }}>
          {error ? <Notice tone="error">{error}</Notice> : null}
          <fieldset className="draft-fields" disabled={busy}><Field label="Report title"><input className="input" required maxLength={320} disabled={busy} placeholder="e.g. Weekly site inspection" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} /></Field>
          <Field label="Report date"><input className="input" type="date" required value={form.report_date} onChange={e => setForm({ ...form, report_date: e.target.value })} /></Field>
          {!row ? <>
            <ChoiceCards label="Report source" name="report-source" value={source} columns={2} onChange={setSource} options={[{value: "pdf", label: "Upload PDF", description: "Review inside the system · up to 50 MB"}, {value: "drive", label: "Google Drive link", description: "Open the shared report in Google Drive"}]} />
            {source === "pdf" ? <Field label="PDF file" hint="Up to 50 MB. Upload revisions separately to preserve the earlier report."><input className="input" type="file" accept=".pdf,application/pdf" required disabled={busy} onChange={e => setFile(e.target.files?.[0] ?? null)} /></Field> : <Field label="Google Drive link" hint="Paste a Google Drive or Google Docs sharing link. Each viewer needs access in Drive."><input className="input" type="url" required maxLength={2000} value={sourceUrl} placeholder="https://drive.google.com/file/d/…/view" onChange={e => setSourceUrl(e.target.value)} /></Field>}
          </> : <p className="footnote">The original PDF or Drive link is retained. Add another report for a new source or revision.</p>}
          <Field label="Notes" optional><textarea className="input" maxLength={2000} rows={3} disabled={busy} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} /></Field>
          </fieldset>
          <FormActions><Button type="submit" variant="primary" disabled={busy}>{busy ? "Saving…" : row ? "Save details" : source === "drive" ? "Save link" : "Upload report"}</Button></FormActions>
        </form>
      </DraftBoundary>
    </Card>
  </RecordPage>;
}

export function LinkedSiteReportViewer({ row, onClose }: { row: SiteReport; onClose: () => void }) {
  return <RecordPage icon="documents" title={row.title} subtitle="Google Drive report" onClose={onClose}>
    <Card title="Open the shared report" description="This report is stored in Google Drive. Your Drive account must have permission to view it.">
      <div className="stack">
        <p className="footnote">{businessDate(row.report_date)}</p>
        {row.notes ? <p className="drawing-notes">{row.notes}</p> : null}
        {row.source_url ? <ExternalLink href={row.source_url}>Open report in Google Drive</ExternalLink> : null}
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
  return <RecordPage icon="documents" title={row.title} subtitle={businessDate(row.report_date)} onClose={onClose} actions={<Button disabled={downloading} onClick={async () => { setDownloading(true); setError(null); try { await siteReports.download(projectId, row); } catch (caught) { setError(message(caught)); } finally { setDownloading(false); } }}>{downloading ? "Downloading…" : "Download original PDF"}</Button>}>
    <div className="stack">
      <p className="footnote">{row.filename}</p>
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
