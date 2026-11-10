"use client";

import { useState } from "react";
import { Badge, Button, ButtonRow, Card, DataToolbar, EmptyState, Loading, Notice, PageHeader, useToast } from "@/components/ui";
import { useAnswer } from "@/lib/answer";
import { businessDate } from "@/lib/format";
import { siteReports, type SiteReport } from "@/lib/api/siteReports";
import { CONSULTANT_READERS, CONSULTANT_EDITORS, hasAnyRole, type Roles } from "@/lib/roles";
import { DeleteRecordButton } from "./DeleteRecordButton";
import { SiteReportForm, SiteReportViewer, LinkedSiteReportViewer } from "./reports/ReportDocuments";

export function ReportsTab({ projectId, roles }: { projectId: string; roles: Roles }) {
  if (!hasAnyRole(roles, CONSULTANT_READERS)) return <Notice tone="info">Reports is not available to your role.</Notice>;
  return <ReportLibrary key={projectId} projectId={projectId} canWrite={hasAnyRole(roles, CONSULTANT_EDITORS)} />;
}

function ReportLibrary({ projectId, canWrite }: { projectId: string; canWrite: boolean }) {
  const answer = useAnswer(true, () => siteReports.list(projectId), [projectId]);
  const [search, setSearch] = useState("");
  const [editor, setEditor] = useState<{ row?: SiteReport } | null>(null);
  const [viewing, setViewing] = useState<SiteReport | null>(null);
  const { toast } = useToast();
  const term = search.trim().toLocaleLowerCase();
  const rows = answer.status === "ready" ? answer.data.filter(row => [row.title, row.report_date, row.notes, row.filename ?? ""].some(value => value.toLocaleLowerCase().includes(term))) : [];
  return <div className="stack">
    <PageHeader title="Reports" icon="documents" subtitle="Site engineer reports, together in one place. Review the latest visit or return to an earlier report." actions={canWrite ? <Button variant="primary" onClick={() => setEditor({})}>Add report</Button> : undefined} />
    <DataToolbar framed search={{ value: search, onChange: setSearch, placeholder: "Title, date or notes…", label: "Find a report" }} count={answer.status === "ready" ? { shown: rows.length, total: answer.data.length, noun: "report" } : undefined} onReset={search ? () => setSearch("") : undefined} />
    <p className="footnote">Newest report date first. Reports are reference evidence; adding one does not certify completion or approve a payment.</p>
    {answer.status === "loading" ? <Loading label="Loading reports…" shape="rows" /> : null}
    {answer.status === "failed" ? <><Notice tone="error">{answer.message}</Notice><Button onClick={answer.retry}>Retry reports</Button></> : null}
    {answer.status === "denied" ? <Notice tone="warning">Reports require whole-project Design access.</Notice> : null}
    {answer.status === "ready" && !rows.length ? <EmptyState title={answer.data.length ? "No matching reports" : "Your site reports start here"} hint={answer.data.length ? "Change the search or clear it to see all reports." : "Add a title, report date and either a PDF up to 50 MB or a Google Drive link."} /> : null}
    <div className="drawing-grid">{rows.map(row => <Card key={row.id}>
      <div className="stack drawing-card">
        <div className="row-actions"><Badge>{row.source_url ? "Drive link" : "PDF"}</Badge><span className="footnote">Report date · {businessDate(row.report_date)}</span></div>
        <h2><Button variant="link" onClick={() => setViewing(row)}>{row.title}</Button></h2>
        {row.notes ? <p className="drawing-notes">{row.notes}</p> : null}
        <p className="footnote">{row.source_url ? "Shared through Google Drive" : row.filename}</p>
        <ButtonRow><Button onClick={() => setViewing(row)}>Open report</Button>{canWrite ? <><Button variant="quiet" onClick={() => setEditor({ row })}>Edit details</Button><DeleteRecordButton label="report" confirmLabel="Delete report" recordName={row.title} description="Remove this report from the library. Its original PDF or Drive link and audit history are retained." onDelete={reason => siteReports.remove(projectId, row, reason)} onDeleted={async () => { toast({ title: "Report removed. Its evidence remains in history." }); answer.retry(); }} /></> : null}</ButtonRow>
      </div>
    </Card>)}</div>
    {editor ? <SiteReportForm row={editor.row} onClose={() => setEditor(null)} onSaved={() => { toast({ title: editor.row ? "Report details updated." : "Report added." }); answer.retry(); }} onSave={async (fields, file, sourceUrl) => {
      if (editor.row) return siteReports.update(projectId, editor.row, fields);
      if (sourceUrl) return siteReports.createLink(projectId, fields, sourceUrl);
      if (!file) throw new Error("Choose a PDF file.");
      return siteReports.create(projectId, fields, file);
    }} /> : null}
    {viewing ? viewing.source_url ? <LinkedSiteReportViewer key={viewing.id} row={viewing} onClose={() => setViewing(null)} /> : <SiteReportViewer key={viewing.id} projectId={projectId} row={viewing} onClose={() => setViewing(null)} /> : null}
  </div>;
}
