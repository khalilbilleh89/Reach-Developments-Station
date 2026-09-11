"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button, ButtonRow, DataToolbar, Disclosure, EmptyState, Field, FormDialog, KeyValue, KeyValueGrid, Notice, PageHeader, TableScroll, ToolbarFilter } from "@/components/ui";
import { useAnswer } from "@/lib/answer";
import { reporting } from "@/lib/api/reporting";
import type { Snapshot, SnapshotHeader } from "@/lib/api/reporting";
import { management } from "@/lib/api/management";
import { businessDate, eventTime } from "@/lib/format";
import { ReadState } from "./ReadState";
import { ProjectChoice } from "./ActionRecord";
import { pageOffset, rememberRegisterLink, useRegisterRestore } from "@/components/shell/registerState";
import { HistoricalPosition, ComparisonReport, BoardReport } from "./ReportingDocument";

import { reportingHref } from "./reportingRoutes";

export function Reporting({ canWrite }: { canWrite: boolean }) {
  const params = useSearchParams();
  const id = params.get("snapshot");
  return id ? <SnapshotRecord key={id} id={id} /> : <SnapshotRegister canWrite={canWrite} />;
}

function Capture({ initialProject, onClose }: { initialProject: string; onClose: () => void }) {
  const router = useRouter(), params = useSearchParams();
  const [scope, setScope] = useState<"portfolio" | "project">(initialProject ? "project" : "portfolio");
  const [project, setProject] = useState(initialProject), [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [offset, setOffset] = useState(0);
  const projects = useAnswer(scope === "project", () => management.projects(offset), [scope, offset]);
  return <FormDialog title="Capture management snapshot" description="Uses current authoritative system state. A snapshot cannot be backdated, edited or deleted." confirmLabel="Capture snapshot" busy={busy} disabled={scope === "project" && !project} onCancel={onClose} onSubmit={async () => {
    if (busy) return;
    setBusy(true); setError("");
    try { const result = await reporting.capture({ scope, ...(scope === "project" ? { project_id: project } : {}), ...(label.trim() ? { label: label.trim() } : {}) }); router.push(reportingHref(result.id, "position", "", params)); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Snapshot capture failed."); setBusy(false); }
  }}>
    <Field label="Scope"><select className="input" value={scope} onChange={e => setScope(e.target.value as "portfolio" | "project")}><option value="portfolio">My authorized whole-project portfolio</option><option value="project">One project</option></select></Field>
    {scope === "project" ? <><Field label="Project"><select className="input" required value={project} onChange={e => setProject(e.target.value)}><option value="">Choose a project</option>{project && projects.status === "ready" && !projects.data.items.some(p => p.id === project) ? <option value={project}>Selected project</option> : null}{projects.status === "ready" ? projects.data.items.map(p => <option key={p.id} value={p.id}>{p.code} · {p.name}</option>) : null}</select></Field>{projects.status === "ready" ? <ButtonRow><Button small disabled={!offset} onClick={() => setOffset(offset - 100)}>Previous projects</Button><Button small disabled={offset + 100 >= projects.data.total} onClick={() => setOffset(offset + 100)}>More projects</Button></ButtonRow> : <ReadState answer={projects} label="Reading authorized projects…" />}</> : null}
    <Field label="Label (optional)" hint="A meeting label does not change the capture date."><input className="input" maxLength={200} value={label} onChange={e => setLabel(e.target.value)} /></Field>
    {error ? <Notice tone="error">{error}</Notice> : null}
  </FormDialog>;
}

function SnapshotRegister({ canWrite }: { canWrite: boolean }) {
  const params = useSearchParams(), router = useRouter();
  const offset = pageOffset(params.get("offset") ?? ""), scope = params.get("scope") ?? "", project = params.get("project") ?? "";
  const [creating, setCreating] = useState(false);
  const answer = useAnswer(true, () => reporting.list({ scope, project_id: project, limit: 20, offset }), [scope, project, offset]);
  useRegisterRestore(answer.status === "ready");
  function change(values: Record<string, string>) { const next = new URLSearchParams(params); for (const [k,v] of Object.entries(values)) { if (v) next.set(k,v); else next.delete(k); } router.push(`/portfolio/?${next}`); }
  return <div className="stack">
    <PageHeader icon="projects" eyebrow="Historical management" title="Reporting" subtitle="Capture what the system says now. Compare governed snapshots as history grows." />
    <DataToolbar onReset={scope || project || offset ? () => change({ scope: "", project: "", offset: "" }) : undefined} activeSummary={project ? "Selected development" : "All authorized developments"} count={answer.status === "ready" ? { shown: answer.data.items.length, total: answer.data.total, noun: "snapshot" } : undefined} actions={canWrite ? <Button variant="primary" onClick={() => setCreating(true)}>Capture management snapshot</Button> : undefined}>
      <ToolbarFilter label="Scope"><select className="input" value={scope} onChange={e => change({scope:e.target.value, project: e.target.value === "portfolio" ? "" : project, offset:""})}><option value="">All accessible snapshots</option><option value="portfolio">Portfolio</option><option value="project">Project</option></select></ToolbarFilter>
      <ProjectChoice emptyLabel="All authorized developments" value={project} onChange={project => change({ project, scope: project ? "project" : "", offset: "" })} />
    </DataToolbar>
    {answer.status !== "ready" ? <ReadState answer={answer} label="Reading snapshots…" /> : !answer.data.total ? <EmptyState title="No governed snapshots yet" hint="The first capture starts management history. Earlier periods are not reconstructed from today's data." /> : <>
      <TableScroll label="Management snapshot register" stickyHeader><thead><tr>{["Captured / label", "Scope", "Created by", "Coverage", "Open"].map(t => <th scope="col" key={t}>{t}</th>)}</tr></thead><tbody>{answer.data.items.map(s => <tr key={s.id}><th scope="row" className="cell-prose"><Link data-record-link onClick={() => rememberRegisterLink(reportingHref(s.id, "position", "", params))} href={reportingHref(s.id, "position", "", params)}>{s.label ?? "Management snapshot"}</Link><p className="muted">{eventTime(s.captured_at)}</p></th><td>{s.scope_type} · {s.project_count} {s.project_count === 1 ? "project" : "projects"}</td><td>{s.creator_display_name}</td><td>{s.incomplete_project_count} with incomplete coverage</td><td><Link data-record-link onClick={() => rememberRegisterLink(reportingHref(s.id, "comparison", "", params))} href={reportingHref(s.id,"comparison", "", params)}>Compare</Link></td></tr>)}</tbody></TableScroll>
      <ButtonRow><Button disabled={!offset} onClick={() => change({offset:String(Math.max(0,offset-20))})}>Previous snapshots</Button><Button disabled={offset+20>=answer.data.total} onClick={() => change({offset:String(offset+20)})}>Next snapshots</Button></ButtonRow>
    </>}
    {creating && canWrite ? <Capture initialProject={project} onClose={() => setCreating(false)} /> : null}
  </div>;
}

export function SnapshotIdentity({ snapshot }: { snapshot: SnapshotHeader }) {
  return <><KeyValueGrid><KeyValue label="Captured (UTC)" value={eventTime(snapshot.captured_at)} /><KeyValue label="As of" value={businessDate(snapshot.as_of_date)} /><KeyValue label="Scope" value={`${snapshot.scope_type} · ${snapshot.project_count} ${snapshot.project_count === 1 ? "project" : "projects"}`} /><KeyValue label="Captured by" value={snapshot.creator_display_name} /></KeyValueGrid><Disclosure title="Snapshot verification"><KeyValueGrid><KeyValue label="Integrity reference" value={<span className="mono">{snapshot.content_hash}</span>} /><KeyValue label="Schema" value={`Version ${snapshot.schema_version}`} /></KeyValueGrid></Disclosure></>;
}

function SnapshotRecord({ id }: { id: string }) {
  const answer = useAnswer(true, () => reporting.detail(id), [id]);
  if (answer.status !== "ready") return <><PageHeader title="Management snapshot" /><ReadState answer={answer} label="Reading historical snapshot…" /></>;
  return <HistoricalRecord snapshot={answer.data} />;
}

function HistoricalRecord({ snapshot }: { snapshot: Snapshot }) {
  const params = useSearchParams(), router = useRouter(), heading = useRef<HTMLHeadingElement>(null);
  const requested = params.get("view"), view = requested === "comparison" || requested === "board" ? requested : "position", prior = params.get("prior") ?? "";
  const [offset,setOffset] = useState(0);
  const candidates = useAnswer(true, () => reporting.list({ scope: snapshot.scope_type, project_id: snapshot.project_id ?? undefined, created_to: snapshot.captured_at, limit: 20, offset }), [snapshot.id, snapshot.scope_type, snapshot.project_id, snapshot.captured_at, offset]);
  const changes = useAnswer(Boolean(prior) && view === "comparison", () => reporting.compare(prior, snapshot.id), [prior,snapshot.id,view]);
  const pack = useAnswer(view === "board", () => reporting.board(snapshot.id, prior || undefined), [snapshot.id,prior,view]);
  useEffect(() => { heading.current?.focus({preventScroll:true}); }, [snapshot.id, view]);
  useEffect(() => {
    if (view !== "board") return;
    let expanded: HTMLDetailsElement[] = [];
    const preparePrint = () => {
      expanded = Array.from(document.querySelectorAll<HTMLDetailsElement>(".reporting-board details:not([open])"));
      expanded.forEach(section => { section.open = true; });
    };
    const restoreScreen = () => {
      expanded.forEach(section => { section.open = false; });
      expanded = [];
    };
    window.addEventListener("beforeprint", preparePrint);
    window.addEventListener("afterprint", restoreScreen);
    return () => {
      window.removeEventListener("beforeprint", preparePrint);
      window.removeEventListener("afterprint", restoreScreen);
      restoreScreen();
    };
  }, [view]);
  return <article className={`reporting-record ${view === "board" ? "reporting-board" : ""}`}>
    <div className="reporting-controls"><Link href={reportingHref("", "position", "", params)}>← Reporting register</Link></div>
    <header className="reporting-header"><p className="eyebrow">Reach Developments Station · Immutable snapshot</p><h1 ref={heading} tabIndex={-1}>{view === "board" ? "Board Pack" : snapshot.label ?? "Management snapshot"}</h1>{view === "board" ? <p>{snapshot.label ?? "Management review"}</p> : null}<SnapshotIdentity snapshot={snapshot} /><p className="footnote">Historical system position at capture. Current source records may have changed.</p></header>
    <div className="reporting-controls stack"><nav className="tabs" aria-label="Historical report views">{[{key:"position",label:"Snapshot"},{key:"comparison",label:"Comparison"},{key:"board",label:"Board Pack"}].map(v => <Link key={v.key} className={`tab ${view === v.key ? "tab-active" : ""}`} aria-current={view === v.key ? "page" : undefined} href={reportingHref(snapshot.id,v.key,prior, params)}>{v.label}</Link>)}</nav>
      <Field label="Prior snapshot"><select className="input" value={prior} onChange={e => router.push(reportingHref(snapshot.id,view,e.target.value, params))}><option value="">No comparison selected</option>{prior && candidates.status === "ready" && !candidates.data.items.some(s => s.id===prior) ? <option value={prior}>Selected prior snapshot</option> : null}{candidates.status === "ready" ? candidates.data.items.filter(s=>s.id!==snapshot.id && s.captured_at<snapshot.captured_at).map(s=><option key={s.id} value={s.id}>{eventTime(s.captured_at)} · {s.label ?? "Management snapshot"}</option>) : null}</select></Field>
      {candidates.status === "ready" ? <><ButtonRow><Button small disabled={!offset} onClick={()=>setOffset(offset-20)}>Previous choices</Button><Button small disabled={offset+20>=candidates.data.total} onClick={()=>setOffset(offset+20)}>More choices</Button></ButtonRow>{candidates.data.total===1 ? <Notice tone="info">No earlier governed snapshot exists. Future captures enable comparison.</Notice> : null}</> : <ReadState answer={candidates} label="Reading compatible snapshot choices…" />}
      {view==="board" ? <Button onClick={()=>window.print()}>Print / Save as PDF</Button> : null}
    </div>
    {view==="position" ? <HistoricalPosition snapshot={snapshot} /> : view==="comparison" ? !prior ? <EmptyState title="Choose a prior snapshot" hint="Compare two captured management positions. Earlier history is never reconstructed." /> : changes.status==="ready" ? <ComparisonReport comparison={changes.data} /> : <ReadState answer={changes} label="Comparing snapshots…" /> : pack.status==="ready" ? <BoardReport pack={pack.data} /> : <ReadState answer={pack} label="Preparing historical Board Pack…" />}
    <p className="footnote reporting-footer">Snapshot {snapshot.id} · {eventTime(snapshot.captured_at)} · {snapshot.content_hash}</p>
  </article>;
}
