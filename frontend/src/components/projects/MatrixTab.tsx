"use client";
import { useState } from "react";
import { matrices, type Framework, type MatrixRecord } from "@/lib/api/matrix";
import { useAnswer } from "@/lib/answer";
import { Button, DataToolbar, EmptyState, Loading, Notice, PageHeader } from "@/components/ui";
import { MatrixEditor } from "./matrix/MatrixEditor";
import { frameworkKeys, templates } from "./matrix/templates";

export function MatrixTab({ projectId }: { projectId: string }) {
 const answer = useAnswer(true, () => matrices.list(projectId), [projectId]);
 const [editor, setEditor] = useState<{ framework: Framework; record?: MatrixRecord } | null>(null);
 const [query, setQuery] = useState("");
 const [notice, setNotice] = useState("");
 const rows = answer.status === "ready" ? answer.data.analyses : [];
 const filtered = rows.filter(row => (row.title + " " + templates[row.framework].name).toLowerCase().includes(query.toLowerCase()));
 const canManage = answer.status === "ready" && answer.data.can_manage;
 return <div className="stack">
  <PageHeader title="Matrix" icon="overview" subtitle="Make your thinking visible. Six perspectives for clearer decisions."/>
  {notice ? <Notice tone="success">{notice}</Notice> : null}
  {answer.status === "loading" ? <Loading label="Loading your analyses…"/> : null}
  {answer.status === "failed" ? <Notice tone="error">{answer.message} <Button onClick={answer.retry}>Retry</Button></Notice> : null}
  {answer.status === "denied" || answer.status === "off" ? <Notice tone="info">Matrix requires access to the whole project.</Notice> : null}
  {answer.status === "ready" ? <>
   <section aria-label="Choose a framework" className="matrix-template-gallery">{frameworkKeys.map((framework, index) => <button key={framework} type="button" className={`matrix-template matrix-tone-${index}`} disabled={!canManage} onClick={() => setEditor({framework})}>
    <span className={`matrix-mini matrix-mini-${framework}`} aria-hidden="true">{Array.from({length:framework === "pestel" || framework === "fishbone" ? 6 : framework === "porter" ? 5 : 4},(_, i) => <i key={i}/>)}</span>
    <strong>{templates[framework].name}</strong><span>{templates[framework].purpose}</span><span className="matrix-template-action">{canManage ? "Create analysis ↗" : "Read-only access"}</span>
   </button>)}</section>
   <h2>Your analyses</h2>
   <DataToolbar search={{value:query,onChange:setQuery,label:"Search analyses",placeholder:"Search title or framework…"}} count={{shown:filtered.length,total:rows.length,noun:"analysis"}} actions={<Button variant="quiet" onClick={answer.retry}>Refresh</Button>}/>
   {filtered.length ? <div className="matrix-saved-grid">{filtered.map(row => <button type="button" className="matrix-saved" key={row.id} onClick={() => setEditor({framework:row.framework,record:row})}><span className="eyebrow">{templates[row.framework].name}</span><strong>{row.title}</strong><span>As at {row.as_of}</span><span>Open diagram →</span></button>)}</div> : <EmptyState title={rows.length ? "No matching analyses" : "A fresh perspective starts here"} hint={rows.length ? "Try a different title or framework." : "Choose a framework above to create your first visual analysis."}/>}
  </> : null}
  {editor ? <MatrixEditor key={editor.record?.id ?? editor.framework} projectId={projectId} framework={editor.framework} record={editor.record} canManage={canManage} onClose={() => setEditor(null)} onSaved={() => {setEditor(null);setNotice("Matrix updated.");answer.retry();}}/> : null}
 </div>;
}
