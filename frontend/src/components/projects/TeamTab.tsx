"use client";

import { useState } from "react";
import { team, type TeamKind, type TeamMember } from "@/lib/api/team";
import { useAnswer } from "@/lib/answer";
import { Button, DataToolbar, Icon, Loading, Notice, PageHeader } from "@/components/ui";
import { TeamMemberForm } from "./team/TeamMemberForm";
import { TeamSection } from "./team/TeamSection";

export function TeamTab({ projectId }: { projectId: string }) {
  // Every active project member may read the project contact directory, including phase readers.
  const answer = useAnswer(true, () => team.list(projectId), [projectId]);
  const [query, setQuery] = useState("");
  const [editor, setEditor] = useState<{ team: TeamKind; member?: TeamMember } | null>(null);
  const [notice, setNotice] = useState("");
  const rows = answer.status === "ready" ? answer.data.members : [];
  const search = query.trim().toLocaleLowerCase();
  const filtered = rows.filter(row => [row.name, row.title, row.scope_of_work, row.email].some(value => value?.toLocaleLowerCase().includes(search)));
  const canManage = answer.status === "ready" && answer.data.can_manage;
  return <div className="stack">
    <PageHeader title="Team" icon="user" subtitle="The people behind this project. Find a person, understand their role and get in touch."
      actions={canManage ? <Button onClick={() => setEditor({ team: "operations" })}><Icon name="plus" /> Add team member</Button> : undefined} />
    {notice ? <div role="status"><Notice tone="success">{notice}</Notice></div> : null}
    {answer.status === "loading" ? <Loading label="Loading project team…" /> : null}
    {answer.status === "off" || answer.status === "denied" ? <Notice tone="info">This project directory is not available to your access level.</Notice> : null}
    {answer.status === "failed" ? <Notice tone="error">{answer.message} <Button variant="default" onClick={answer.retry}>Retry</Button></Notice> : null}
    {answer.status === "ready" ? <>
      <DataToolbar search={{ value: query, onChange: setQuery, label: "Search team", placeholder: "Search name, title, scope or email…" }}
        count={{ shown: filtered.length, total: rows.length, noun: "team member" }}
        onReset={query ? () => setQuery("") : undefined} actions={<Button variant="quiet" onClick={answer.retry}>Refresh</Button>} />
      {(["operations", "engineering"] as const).map(kind => <TeamSection key={kind} projectId={projectId} kind={kind}
        query={search} members={filtered.filter(member => member.team === kind)} canManage={canManage}
        onAdd={() => setEditor({ team: kind })} onEdit={member => setEditor({ team: member.team, member })}
        onDeleted={async name => { setNotice(`${name} removed from the team.`); answer.retry(); }} />)}
    </> : null}
    {editor ? <TeamMemberForm key={editor.member?.id ?? editor.team} projectId={projectId} initialTeam={editor.team} member={editor.member}
      onClose={() => setEditor(null)} onSaved={name => { setEditor(null); setNotice(`${name} saved to the team.`); answer.retry(); }} /> : null}
  </div>;
}
