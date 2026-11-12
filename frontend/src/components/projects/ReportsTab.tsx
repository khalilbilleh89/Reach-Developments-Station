"use client";

import { useState } from "react";
import { Badge, Button, Card, CardRow, CardRows, DataToolbar, EmptyState, KeyValue, KeyValueGrid, Loading, Notice, PageHeader, RowMenu, SectionHeader, useToast } from "@/components/ui";
import { useAnswer } from "@/lib/answer";
import { businessDate } from "@/lib/format";
import { siteReports, type SiteReport } from "@/lib/api/siteReports";
import { CONSULTANT_READERS, CONSULTANT_EDITORS, hasAnyRole, type Roles } from "@/lib/roles";
import { DeleteRecordButton } from "./DeleteRecordButton";
import { SiteReportForm, SiteReportViewer, LinkedSiteReportViewer } from "./reports/ReportDocuments";

/** Where the report lives, in words: the stored PDF's name or the Drive link it points to. */
const sourceOf = (row: SiteReport) => row.source_url ? "Google Drive link" : row.filename ?? "PDF";

/** Search what the reader sees as well as what is stored, so "10 Nov" finds the 10 November visit. */
export function matchesReport(row: SiteReport, term: string): boolean {
  if (!term) return true;
  return [row.title, row.report_date, businessDate(row.report_date), row.notes, row.filename ?? ""].some(value => value.toLocaleLowerCase().includes(term));
}

export function ReportsTab({ projectId, roles }: { projectId: string; roles: Roles }) {
  if (!hasAnyRole(roles, CONSULTANT_READERS)) return <Notice tone="info">Reports is not available to your role.</Notice>;
  return <ReportLibrary key={projectId} projectId={projectId} canWrite={hasAnyRole(roles, CONSULTANT_EDITORS)} />;
}

export function ReportLibrary({ projectId, canWrite }: { projectId: string; canWrite: boolean }) {
  const answer = useAnswer(true, () => siteReports.list(projectId), [projectId]);
  const [search, setSearch] = useState("");
  const [editor, setEditor] = useState<{ row?: SiteReport } | null>(null);
  const [viewing, setViewing] = useState<SiteReport | null>(null);
  const { toast } = useToast();
  const term = search.trim().toLocaleLowerCase();
  const all = answer.status === "ready" ? answer.data : [];
  // The server returns the newest report date first; the first row is the latest visit.
  // While a search is applied, every match is listed and nothing is singled out.
  const latest = !term ? all[0] : undefined;
  const rows = all.filter(row => row !== latest && matchesReport(row, term));
  const rowMenu = (row: SiteReport) => canWrite ? <RowMenu label={`Actions for ${row.title}`}>
    <Button variant="quiet" onClick={() => setEditor({ row })}>Edit details</Button>
    <DeleteRecordButton label="report" confirmLabel="Delete report" recordName={row.title} description="Remove this report from the library. Its original PDF or Drive link and audit history are retained." onDelete={reason => siteReports.remove(projectId, row, reason)} onDeleted={async () => { toast({ title: "Report removed. Its evidence remains in history." }); answer.retry(); }} />
  </RowMenu> : null;
  return <div className="stack">
    <PageHeader title="Reports" icon="documents" subtitle="Site engineer reports in one place: the latest visit first, earlier reports beneath." actions={canWrite ? <Button variant="primary" onClick={() => setEditor({})}>Add report</Button> : undefined} />
    {answer.status === "loading" ? <Loading label="Loading reports…" shape="rows" /> : null}
    {answer.status === "failed" ? <Notice tone="error">{answer.message} <Button onClick={answer.retry}>Retry reports</Button></Notice> : null}
    {answer.status === "denied" ? <Notice tone="warning">Reports require whole-project Design access.</Notice> : null}
    {answer.status === "ready" && !all.length ? <Card><EmptyState title="Your site reports start here" hint="Add a title, report date and either a PDF up to 50 MB or a Google Drive link." /></Card> : null}
    {latest ? <Card>
      <SectionHeader level={2} title="Latest report" actions={<>
        <Button onClick={() => setViewing(latest)}>Open report</Button>
        {rowMenu(latest)}
      </>} />
      <div className="stack">
        <h3 className="report-latest-title">{latest.title}</h3>
        <KeyValueGrid><KeyValue label="Report date" value={businessDate(latest.report_date)} /><KeyValue label="Source" value={sourceOf(latest)} /></KeyValueGrid>
        {latest.notes ? <p className="drawing-notes">{latest.notes}</p> : null}
      </div>
    </Card> : null}
    {answer.status === "ready" && (all.length > 1 || term) ? <Card>
      <SectionHeader level={2} title={term ? "Matching reports" : "Earlier reports"} description="Newest report date first. Reports are reference evidence; adding one does not certify completion or approve a payment." />
      <DataToolbar search={{ value: search, onChange: setSearch, placeholder: "Title, date or notes…", label: "Find a report" }} count={{ shown: rows.length, total: term ? all.length : Math.max(all.length - 1, 0), noun: "report" }} onReset={search ? () => setSearch("") : undefined} />
      {rows.length ? <CardRows label={term ? "Matching reports" : "Earlier reports"}>{rows.map(row => <CardRow key={row.id}
        title={row.title}
        meta={row.filename ?? undefined}
        onOpen={() => setViewing(row)}
        facts={[
          { label: "Report date", value: businessDate(row.report_date) },
          { label: "Source", value: <Badge>{row.source_url ? "Drive link" : "PDF"}</Badge> },
        ]}
        actions={<><Button onClick={() => setViewing(row)}>Open</Button>{rowMenu(row)}</>} />)}</CardRows>
        : <EmptyState title="No matching reports" hint="Change the search or clear it to see all reports." />}
    </Card> : null}
    {editor ? <SiteReportForm row={editor.row} onClose={() => setEditor(null)} onSaved={() => { toast({ title: editor.row ? "Report details updated." : "Report added." }); answer.retry(); }} onSave={async (fields, file, sourceUrl) => {
      if (editor.row) return siteReports.update(projectId, editor.row, fields);
      if (sourceUrl) return siteReports.createLink(projectId, fields, sourceUrl);
      if (!file) throw new Error("Choose a PDF file.");
      return siteReports.create(projectId, fields, file);
    }} /> : null}
    {viewing ? viewing.source_url ? <LinkedSiteReportViewer key={viewing.id} row={viewing} onClose={() => setViewing(null)} /> : <SiteReportViewer key={viewing.id} projectId={projectId} row={viewing} onClose={() => setViewing(null)} /> : null}
  </div>;
}
