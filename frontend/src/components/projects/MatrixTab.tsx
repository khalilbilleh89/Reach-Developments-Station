"use client";
import * as ui from "@/components/ui";
import { useState } from "react";
import type { ReactNode } from "react";
import { matrices, type Framework, type MatrixRecord } from "@/lib/api/matrix";
import { useAnswer } from "@/lib/answer";
import { Button, DataToolbar, EmptyState, Loading, Notice, PageHeader } from "@/components/ui";
import { MatrixEditor } from "./matrix/MatrixEditor";
import { frameworkKeys, templates } from "./matrix/templates";
import { businessDate } from "@/lib/format";

export function MatrixTab({ projectId }: { projectId: string }) {
 const answer = useAnswer(true, () => matrices.list(projectId), [projectId]);
 const [editor, setEditor] = useState<{ framework: Framework; record?: MatrixRecord } | null>(null);
 const [query, setQuery] = useState("");
 // The barrel's hook, or a no-op where a test harness stands the barrel in.
  const { toast } = typeof ui.useToast === "function" ? ui.useToast() : { toast: () => {} };
 const setNotice = (text: string) => { if (text) toast({ title: text }); };
 const rows = answer.status === "ready" ? answer.data.analyses : [];
 const filtered = rows.filter(row => (row.title + " " + templates[row.framework].name).toLowerCase().includes(query.toLowerCase()));
 const canManage = answer.status === "ready" && answer.data.can_manage;
 return <div className="stack">
  <PageHeader title="Matrix" icon="overview" subtitle="Make your thinking visible. Six perspectives for clearer decisions."/>
  {answer.status === "loading" ? <Loading label="Loading your analyses…"/> : null}
  {answer.status === "failed" ? <Notice tone="error">{answer.message} <Button onClick={answer.retry}>Retry</Button></Notice> : null}
  {answer.status === "denied" || answer.status === "off" ? <Notice tone="info">Matrix requires access to the whole project.</Notice> : null}
  {answer.status === "ready" ? <>
   <div className="matrix-gallery-head"><h2>Start a new analysis</h2><p className="muted">Each opens as its own canvas, drawn in the shape of the framework.</p></div>
   <section aria-label="Choose a framework" className="matrix-template-gallery">{frameworkKeys.map(framework => <button key={framework} type="button" className="matrix-template" disabled={!canManage} onClick={() => setEditor({framework})}>
    <span className={`matrix-mini matrix-mini-${framework}`} aria-hidden="true">{minis[framework]}</span>
    <span className="matrix-template-title"><strong>{templates[framework].name}</strong><span>{parts[framework]}</span></span>
    <span className="matrix-template-purpose">{templates[framework].purpose}</span>
    <span className="matrix-template-action">{canManage ? `Start ${templates[framework].name} →` : "Read-only access"}</span>
   </button>)}</section>
   <h2>Your analyses</h2>
   <DataToolbar search={{value:query,onChange:setQuery,label:"Search analyses",placeholder:"Search title or framework…"}} count={{shown:filtered.length,total:rows.length,noun:"diagram"}} actions={<Button variant="quiet" onClick={answer.retry}>Refresh</Button>}/>
   {filtered.length ? <div className="matrix-saved-grid">{filtered.map(row => <button type="button" className="matrix-saved" key={row.id} onClick={() => setEditor({framework:row.framework,record:row})}><span className={`matrix-saved-badge matrix-saved-badge-${row.framework}`} aria-hidden="true">{badges[row.framework]}</span><span className="matrix-saved-text"><span className="eyebrow">{templates[row.framework].name}</span><strong>{row.title}</strong><span className="muted">As at {businessDate(row.as_of)} · {row.items.length === 1 ? "1 item" : `${row.items.length} items`}</span></span></button>)}</div> : <EmptyState title={rows.length ? "No matching analyses" : "A fresh perspective starts here"} hint={rows.length ? "Try a different title or framework." : "Choose a framework above to create your first visual analysis."}/>}
  </> : null}
  {editor ? <MatrixEditor key={editor.record?.id ?? editor.framework} projectId={projectId} framework={editor.framework} record={editor.record} canManage={canManage} onClose={() => setEditor(null)} onSaved={() => {setEditor(null);setNotice("Matrix updated.");answer.retry();}}/> : null}
 </div>;
}

const parts: Record<Framework, string> = { swot: "4 quadrants", pestel: "6 lenses", porter: "5 forces", bcg: "Growth × share", ansoff: "4 paths", fishbone: "6 causes" };
const badges: Record<Framework, string> = { swot: "SWOT", pestel: "PEST", porter: "5F", bcg: "BCG", ansoff: "ANS", fishbone: "FISH" };

/** Each tile previews the shape its analysis opens in (Matrix canvas designs, Nov 2026). */
const minis: Record<Framework, ReactNode> = {
 swot: <span className="matrix-mini-swot-grid"><b className="matrix-chip matrix-chip-s">S</b><b className="matrix-chip matrix-chip-w">W</b><b className="matrix-chip matrix-chip-o">O</b><b className="matrix-chip matrix-chip-t">T</b></span>,
 pestel: <svg width="120" height="120" viewBox="0 0 120 120"><circle className="matrix-mini-ink" cx="60" cy="60" r="16" /><g className="matrix-mini-ring"><circle cx="60" cy="60" r="34" /><circle className="matrix-mini-dashed" cx="60" cy="60" r="52" /></g><g className="matrix-mini-gold"><circle cx="60" cy="8" r="7" /><circle cx="105" cy="34" r="7" /><circle cx="105" cy="86" r="7" /><circle className="matrix-mini-petrol" cx="60" cy="112" r="7" /><circle className="matrix-mini-petrol" cx="15" cy="86" r="7" /><circle cx="15" cy="34" r="7" /></g></svg>,
 porter: <svg width="140" height="120" viewBox="0 0 140 120"><circle className="matrix-mini-ink" cx="70" cy="60" r="22" /><path className="matrix-mini-arrow" d="M70 6v22M70 92v22M10 60h28M102 60h28" /><g className="matrix-mini-bronze"><path d="M62 26l8 10 8-10z" /><path d="M62 94l8-10 8 10z" /><path d="M36 52l10 8-10 8z" /><path d="M104 52l-10 8 10 8z" /></g></svg>,
 bcg: <svg width="150" height="116" viewBox="0 0 150 116"><rect className="matrix-mini-paper" x="1" y="1" width="148" height="114" rx="10" /><path className="matrix-mini-grid" d="M75 1v114M1 58h148" /><circle className="matrix-mini-gold" cx="38" cy="30" r="9" /><circle className="matrix-mini-open" cx="118" cy="34" r="7" /><circle className="matrix-mini-petrol" cx="40" cy="90" r="11" /><circle className="matrix-mini-faint" cx="112" cy="88" r="5" /></svg>,
 ansoff: <svg width="150" height="112" viewBox="0 0 150 112"><rect className="matrix-mini-pale" x="6" y="80" width="34" height="26" rx="4" /><rect className="matrix-mini-gold" x="42" y="58" width="34" height="48" rx="4" /><rect className="matrix-mini-bronze" x="78" y="34" width="34" height="72" rx="4" /><rect className="matrix-mini-petrol" x="114" y="8" width="30" height="98" rx="4" /></svg>,
 fishbone: <svg width="170" height="110" viewBox="0 0 170 110"><path className="matrix-mini-spine" d="M8 55h120" /><path className="matrix-mini-bone" d="M30 55L14 20M66 55L50 20M102 55L86 20M30 55L14 90M66 55L50 90M102 55L86 90" /><path className="matrix-mini-gold" d="M128 32h28a6 6 0 0 1 6 6v34a6 6 0 0 1-6 6h-28z" /></svg>,
};
