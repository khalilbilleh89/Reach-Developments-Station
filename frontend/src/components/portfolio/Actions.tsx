"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge, Button, ButtonRow, Card, DataToolbar, EmptyState, IdentityCell, Loading, Notice, Position, PositionFigure, TableScroll, ToolbarFilter } from "@/components/ui";
import { useAnswer } from "@/lib/answer";
import { management } from "@/lib/api/management";
import type { ActionSource } from "@/lib/api/management";
import { useSession } from "@/lib/api/session";
import { hasAnyRole, PORTFOLIO_READERS, PROJECT_WRITERS, roleSet } from "@/lib/roles";
import { businessDate } from "@/lib/format";
import { ActionRecord, CreateAction, ProjectChoice } from "./ActionRecord";

export function SourceAction({ project, source }: { project: string; source: ActionSource }) {
  const { state } = useSession();
  const [open, setOpen] = useState(false);
  const allowed = state.status === "authenticated" && hasAnyRole(roleSet(state.user.roles), PROJECT_WRITERS);
  return <><Link className="button button-small" href={`/portfolio/?section=actions&project=${project}&source_key=${encodeURIComponent(source.source_key ?? "")}`}>Open actions</Link>
    {allowed ? <Button small onClick={() => setOpen(true)}>Create action</Button> : null}
    {open && allowed ? <CreateAction projectId={project} source={source} onClose={() => setOpen(false)} onSaved={() => setOpen(false)} /> : null}
  </>;
}

export function ManagementSummary({ project }: { project: string }) {
  const { state } = useSession();
  const allowed = state.status === "authenticated" && hasAnyRole(roleSet(state.user.roles), PORTFOLIO_READERS);
  const answer = useAnswer(allowed, () => management.summary(project), [project]);
  if (!allowed) return null;
  return <Card title="Management actions" description="Accountable next steps, independent of source status." actions={<Link href={`/portfolio/?section=actions&project=${project}`}>Open project actions →</Link>}>
    {answer.status === "ready" ? <Position compact><PositionFigure lead label="Open actions" value={answer.data.open_count} /><PositionFigure label="Overdue" value={answer.data.overdue_count} /><PositionFigure label="Next due" value={answer.data.next_due_date ? businessDate(answer.data.next_due_date) : "None"} /><PositionFigure label="Linked to sources" value={answer.data.source_linked_open_count} /></Position> : answer.status === "failed" ? <Notice tone="error">{answer.message}</Notice> : <Loading label="Reading management actions…" />}
  </Card>;
}

export function Actions({ canWrite, initialProject = "", initialAction = null, sourceKey = "", overdueOnly = false }: { canWrite: boolean; initialProject?: string; initialAction?: string | null; sourceKey?: string; overdueOnly?: boolean }) {
  const [project, setProject] = useState(initialProject);
  const [owner, setOwner] = useState("");
  const [status, setStatus] = useState("");
  const [due, setDue] = useState(overdueOnly ? "overdue" : "");
  const [origin, setOrigin] = useState("");
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [action, setAction] = useState(initialAction);
  const [creating, setCreating] = useState(false);
  const ownerOptions = useAnswer(true, () => management.owners(project), [project, revision]);
  const answer = useAnswer(true, () => management.list({ project_id: project, owner: owner === "me" ? "me" : undefined, owner_user_id: owner !== "me" ? owner : undefined, status, due_state: due, source_type: origin, source_key: sourceKey, offset, limit: 20 }), [project, owner, status, due, origin, sourceKey, offset, revision]);
  function filter(setter: (value: string) => void, value: string) { setter(value); setOffset(0); }
  function refresh() { setRevision((value) => value + 1); }
  return <div className="stack">
    <DataToolbar activeSummary={[project ? "Selected development" : "All authorized developments", owner === "me" ? "My actions" : owner ? "Selected owner" : "All owners", status, due, origin].filter(Boolean).join(" · ")}
      count={answer.status === "ready" ? { shown: answer.data.items.length, total: answer.data.total, noun: "action" } : undefined}
      onReset={() => { setProject(""); setOwner(""); setStatus(""); setDue(overdueOnly ? "overdue" : ""); setOrigin(""); setOffset(0); }}
      actions={canWrite ? <Button variant="primary" onClick={() => setCreating(true)}>Create action</Button> : undefined}>
      <ProjectChoice value={project} onChange={(value) => filter(setProject, value)} />
      <ToolbarFilter label="Owner"><select value={owner} onChange={(event) => filter(setOwner, event.target.value)}><option value="">All owners</option><option value="me">My actions</option>{ownerOptions.status === "ready" ? ownerOptions.data.map((user) => <option key={user.user_id} value={user.user_id}>{user.display_name}</option>) : null}</select></ToolbarFilter>
      <ToolbarFilter label="Status"><select value={status} onChange={(event) => filter(setStatus, event.target.value)}><option value="">All statuses</option>{["open", "in_progress", "completed", "cancelled"].map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></ToolbarFilter>
      {!overdueOnly ? <ToolbarFilter label="Due state"><select value={due} onChange={(event) => filter(setDue, event.target.value)}><option value="">All due dates</option>{["overdue", "due_soon", "future", "closed"].map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></ToolbarFilter> : null}
      <ToolbarFilter label="Origin"><select value={origin} onChange={(event) => filter(setOrigin, event.target.value)}><option value="">All origins</option>{["manual", "portfolio_risk", "portfolio_outlook"].map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></ToolbarFilter>
    </DataToolbar>
    {answer.status === "ready" ? <><p className="muted">As of {businessDate(answer.data.as_of)} · Due soon means today through {answer.data.due_soon_days} days ahead. Overdue open actions appear first.</p>
      {!answer.data.total ? <EmptyState title="No matching management actions" hint="Adjust the server filters or create a next step for an authorized development." /> : <TableScroll label="Management action register" stickyHeader fixedFirst><thead><tr>{["Action / development", "Owner", "Due", "Status", "Source"].map((label) => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{answer.data.items.map((row) => <tr key={row.id}><th scope="row"><IdentityCell name={<Button variant="link" onClick={() => setAction(row.id)}>{row.title}</Button>} meta={`${row.project_code} · ${row.project_name}`} /></th><td>{row.owner.display_name}</td><td>{businessDate(row.due_date)}<p><Badge tone={row.due_state === "overdue" ? "danger" : "neutral"}>{row.due_state.replaceAll("_", " ")}</Badge></p></td><td>{row.status.replaceAll("_", " ")}</td><td>{row.source_type.replaceAll("_", " ")}</td></tr>)}</tbody></TableScroll>}
      <ButtonRow><Button disabled={!offset} onClick={() => setOffset(offset - 20)}>Previous actions</Button><Button disabled={offset + 20 >= answer.data.total} onClick={() => setOffset(offset + 20)}>Next actions</Button></ButtonRow>
    </> : answer.status === "failed" ? <Notice tone="error">{answer.message}</Notice> : <Loading label="Reading management actions…" />}
    {creating && canWrite ? <CreateAction projectId={project || undefined} onClose={() => setCreating(false)} onSaved={(row) => { setCreating(false); setAction(row.id); refresh(); }} /> : null}
    {action ? <ActionRecord key={action} id={action} canWrite={canWrite} onClose={() => setAction(null)} onChanged={refresh} /> : null}
  </div>;
}
