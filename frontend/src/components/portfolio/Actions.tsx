"use client";

import Link from "next/link";
import { pageOffset, useRegisterFields } from "@/components/shell/registerState";
import { useState } from "react";
import { Badge, Button, ButtonRow, Card, DataToolbar, DensitySwitch, EmptyState, FilterChips, IdentityCell, Position, PositionFigure, SavedViews, Segmented, TableScroll, ToolbarFilter } from "@/components/ui";
import type { Tone } from "@/components/ui";
import { ReadState } from "./ReadState";
import { useAnswer } from "@/lib/answer";
import { management } from "@/lib/api/management";
import type { ActionSource } from "@/lib/api/management";
import { useSession } from "@/lib/api/session";
import { hasAnyRole, PORTFOLIO_READERS, PROJECT_WRITERS, roleSet } from "@/lib/roles";
import { businessDate } from "@/lib/format";
import { ActionRecord, CreateAction, ProjectChoice } from "./ActionRecord";

const words = (value: string) => value.replaceAll("_", " ");
/** An action's own status, in the one pill style (I1). Colour only where it means something. */
export const actionStatusTone: Record<string, Tone> = { open: "neutral", in_progress: "info", completed: "success", cancelled: "muted" };
const ORIGINS = [{ value: "", label: "All" }, { value: "manual", label: "Manual" }, { value: "portfolio_risk", label: "Risk" }, { value: "portfolio_outlook", label: "Outlook" }];

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
  const [creating, setCreating] = useState(false);
  const [revision, setRevision] = useState(0);
  const allowed = state.status === "authenticated" && hasAnyRole(roleSet(state.user.roles), PORTFOLIO_READERS);
  const canWrite = state.status === "authenticated" && hasAnyRole(roleSet(state.user.roles), PROJECT_WRITERS);
  const answer = useAnswer(allowed, () => management.summary(project), [project, revision]);
  if (!allowed) return null;
  return <Card title="Management actions" description="Accountable next steps, independent of source status." actions={<Link href={`/portfolio/?section=actions&project=${project}`}>Open project actions →</Link>}>
    {answer.status === "ready" ? <Position compact><PositionFigure lead label="Open actions" value={answer.data.open_count} /><PositionFigure label="Overdue" value={answer.data.overdue_count} /><PositionFigure label="Next due" value={answer.data.next_due_date ? businessDate(answer.data.next_due_date) : "None"} /><PositionFigure label="Linked to sources" value={answer.data.source_linked_open_count} /></Position> : <ReadState answer={answer} label="Reading management actions…" />}
    {canWrite && answer.status === "ready" ? <Button small onClick={() => setCreating(true)}>Create project action</Button> : null}
    {creating && canWrite ? <CreateAction projectId={project} onClose={() => setCreating(false)} onSaved={() => { setCreating(false); setRevision((value) => value + 1); }} /> : null}
  </Card>;
}

export function Actions({ canWrite, overdueOnly = false }: { canWrite: boolean; overdueOnly?: boolean }) {
  const [fields, change] = useRegisterFields({ project: "", owner: "", status: "", due: "", origin: "", offset: "", action: "", source_key: "" });
  const { project, owner, status, origin, source_key: sourceKey } = fields;
  const due = overdueOnly ? "overdue" : fields.due;
  const offset = pageOffset(fields.offset), action = fields.action;
  const setProject = (project: string) => change({ project });
  const setOwner = (owner: string) => change({ owner });
  const setStatus = (status: string) => change({ status });
  const setDue = (due: string) => change({ due });
  const setOrigin = (origin: string) => change({ origin });
  const setOffset = (offset: number) => change({ offset: String(offset) });
  const setAction = (action: string | null) => change({ action: action ?? "" });
  const [ownerOffset, setOwnerOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [creating, setCreating] = useState(false);
  const ownerOptions = useAnswer(true, () => management.owners(project, ownerOffset), [project, revision, ownerOffset]);
  const answer = useAnswer(true, () => management.list({ project_id: project, owner: owner === "me" ? "me" : undefined, owner_user_id: owner !== "me" ? owner : undefined, status, due_state: due, source_type: origin, source_key: sourceKey, offset, limit: 20 }), [project, owner, status, due, origin, sourceKey, offset, revision]);
  function filter(setter: (value: string) => void, value: string) { setter(value); setOffset(0); }
  function refresh() { setRevision((value) => value + 1); }
  const clearAll = () => { change({ project: "", owner: "", status: "", due: "", origin: "", offset: "", source_key: "", action: "" }); setOwnerOffset(0); };
  const chips = [
    project ? { key: "project", label: "Selected development", onRemove: () => { change({ project: "", owner: "", offset: "" }); setOwnerOffset(0); } } : null,
    owner ? { key: "owner", label: owner === "me" ? "My actions" : "Selected owner", onRemove: () => change({ owner: "", offset: "" }) } : null,
    status ? { key: "status", label: `Status: ${words(status)}`, onRemove: () => change({ status: "", offset: "" }) } : null,
    !overdueOnly && fields.due ? { key: "due", label: `Due: ${words(fields.due)}`, onRemove: () => change({ due: "", offset: "" }) } : null,
    origin ? { key: "origin", label: `Origin: ${words(origin)}`, onRemove: () => change({ origin: "", offset: "" }) } : null,
    sourceKey ? { key: "source", label: "Linked source", onRemove: () => change({ source_key: "", offset: "" }) } : null,
  ].filter((chip): chip is NonNullable<typeof chip> => chip !== null);
  return <div className="stack">
    <DataToolbar activeSummary={[project ? "Selected development" : "All authorized developments", owner === "me" ? "My actions" : owner ? "Selected owner" : "All owners", status.replaceAll("_", " "), due.replaceAll("_", " "), origin.replaceAll("_", " "), sourceKey ? "Linked source" : ""].filter(Boolean).join(" · ")}
      count={answer.status === "ready" ? { shown: answer.data.items.length, total: answer.data.total, noun: "action" } : undefined}
      onReset={project || owner || status || fields.due || origin || sourceKey || offset ? clearAll : undefined}
      actions={<><DensitySwitch />{canWrite ? <Button variant="primary" onClick={() => setCreating(true)}>Create action</Button> : null}</>}>
      <ProjectChoice emptyLabel="All authorized developments" value={project} onChange={(value) => { filter(setProject, value); setOwner(""); setOwnerOffset(0); }} />
      <ToolbarFilter label="Owner" active={owner !== ""}><select className="input" value={owner} onChange={(event) => filter(setOwner, event.target.value)}><option value="">All owners</option><option value="me">My actions</option>{owner && owner !== "me" && ownerOptions.status === "ready" && !ownerOptions.data.some((user) => user.user_id === owner) ? <option value={owner}>Selected owner</option> : null}{ownerOptions.status === "ready" ? ownerOptions.data.map((user) => <option key={user.user_id} value={user.user_id}>{user.display_name}</option>) : null}</select></ToolbarFilter>
      {ownerOptions.status === "ready" && (ownerOffset > 0 || ownerOptions.data.length === 100) ? <ButtonRow><Button small disabled={!ownerOffset} onClick={() => setOwnerOffset(ownerOffset - 100)}>Previous owners</Button><Button small disabled={ownerOptions.data.length < 100} onClick={() => setOwnerOffset(ownerOffset + 100)}>More owners</Button></ButtonRow> : null}
      <ToolbarFilter label="Status" active={status !== ""}><select className="input" value={status} onChange={(event) => filter(setStatus, event.target.value)}><option value="">All statuses</option>{["open", "in_progress", "completed", "cancelled"].map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></ToolbarFilter>
      {!overdueOnly ? <ToolbarFilter label="Due state" active={due !== ""}><select className="input" value={due} onChange={(event) => filter(setDue, event.target.value)}><option value="">All due dates</option>{["overdue", "due_soon", "future", "closed"].map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></ToolbarFilter> : null}
      <ToolbarFilter label="Origin" active={origin !== ""}><Segmented label="Origin" value={origin} options={ORIGINS} onChange={(value) => filter(setOrigin, value)} /></ToolbarFilter>
    </DataToolbar>
    <FilterChips chips={chips} onClearAll={clearAll} />
    <SavedViews screen={overdueOnly ? "portfolio-actions-overdue" : "portfolio-actions"} filters={{ project, owner, status, due: overdueOnly ? "" : fields.due, origin }} sort={null}
      onApply={(saved) => { change({ project: String(saved.project ?? ""), owner: String(saved.owner ?? ""), status: String(saved.status ?? ""), due: overdueOnly ? fields.due : String(saved.due ?? ""), origin: String(saved.origin ?? ""), source_key: "", offset: "", action: "" }); setOwnerOffset(0); }} />
    {answer.status === "ready" ? <><p className="muted">As of {businessDate(answer.data.as_of)} · Due soon means today through {answer.data.due_soon_days} days ahead. Overdue open actions appear first.</p>
      {!answer.data.total ? <EmptyState title="No matching management actions" hint="Adjust the server filters or create a next step for an authorized development." /> : <TableScroll label="Management action register" stickyHeader fixedFirst><thead><tr>{["Action / development", "Owner", "Due", "Status", "Source"].map((label) => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{answer.data.items.map((row) => <tr key={row.id}><th scope="row" className="cell-prose"><IdentityCell name={<Button variant="link" onClick={() => setAction(row.id)}>{row.title}</Button>} meta={`${row.project_code} · ${row.project_name}`} /></th><td>{row.owner.display_name}</td><td>{businessDate(row.due_date)}<p><Badge tone={row.due_state === "overdue" ? "danger" : "neutral"}>{row.due_state.replaceAll("_", " ")}</Badge></p></td><td><Badge tone={actionStatusTone[row.status] ?? "neutral"}>{words(row.status)}</Badge></td><td>{words(row.source_type)}</td></tr>)}</tbody></TableScroll>}
      <ButtonRow><Button disabled={!offset} onClick={() => setOffset(offset - 20)}>Previous actions</Button><Button disabled={offset + 20 >= answer.data.total} onClick={() => setOffset(offset + 20)}>Next actions</Button></ButtonRow>
    </> : <ReadState answer={answer} label="Reading management actions…" />}
    {creating && canWrite ? <CreateAction projectId={project || undefined} onClose={() => setCreating(false)} onSaved={(row) => { setCreating(false); setAction(row.id); refresh(); }} /> : null}
    {action ? <ActionRecord key={action} id={action} canWrite={canWrite} onClose={() => setAction(null)} onChanged={refresh} /> : null}
  </div>;
}
