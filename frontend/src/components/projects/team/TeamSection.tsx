"use client";

import { useState } from "react";
import type { TeamKind, TeamMember } from "@/lib/api/team";
import { team } from "@/lib/api/team";
import { Badge, Button, Card, Disclosure, EmptyState, Icon, RegisterPagination, SectionHeader } from "@/components/ui";
import { DeleteRecordButton } from "../DeleteRecordButton";

const PAGE_SIZE = 12;
export function TeamSection({ projectId, kind, members, query, canManage, onAdd, onEdit, onDeleted }: {
  projectId: string; kind: TeamKind; members: TeamMember[]; query: string; canManage: boolean;
  onAdd: () => void; onEdit: (member: TeamMember) => void; onDeleted: (name: string) => Promise<void>;
}) {
  const [page, setPage] = useState({ query, offset: 0 });
  const offset = Math.min(page.query === query ? page.offset : 0, Math.max(0, Math.floor((members.length - 1) / PAGE_SIZE) * PAGE_SIZE));
  const title = kind === "operations" ? "Operations Team" : "Engineering Team";
  return <section className={`team-section team-section-${kind}`} aria-labelledby={`team-${kind}`}>
    <div className="team-section-heading">
      <span className="team-section-glyph" aria-hidden="true"><Icon name={kind === "operations" ? "user" : "blueprint"} /></span>
      <div className="team-section-intro"><h2 id={`team-${kind}`}>{title} <Badge>{members.length}</Badge></h2>
        <p className="muted">{kind === "operations" ? "The people coordinating the project's day-to-day operations." : "The people shaping the design and delivering the technical work."}</p>
      </div>
      {canManage ? <Button variant="default" onClick={onAdd}><Icon name="plus" /> Add to {kind === "operations" ? "Operations" : "Engineering"}</Button> : null}
    </div>
    {!members.length ? <Card tone="subtle"><EmptyState title={query ? "No matching team members" : `Build your ${kind} team`}
      hint={query ? "Try another name, title, responsibility or email." : "Add the people involved and keep their responsibilities easy to find."} /></Card> :
      <div className="team-member-grid">{members.slice(offset, offset + PAGE_SIZE).map(member => <Card key={member.id}><div className="team-member-card">
        <div className="team-member-identity">
          <span className="team-avatar" aria-hidden="true">{member.name.trim().split(/\s+/).slice(0, 2).map(part => Array.from(part)[0]).join("")}</span>
          <div><h3>{member.name}</h3><p className="muted">{member.title || "Title not entered"}</p></div>
        </div>
        <div className="team-member-scope"><SectionHeader level={3} title="Scope of Work" />
          {member.scope_of_work ? <>
            <p className="team-scope-preview">{member.scope_of_work}</p>
            <Disclosure title="Read full scope"><p className="team-scope-full">{member.scope_of_work}</p></Disclosure>
          </> : <p className="muted">Scope not entered</p>}
        </div>
        <div className="team-member-contact"><span className="muted">Email Address</span>
          {member.email ? <a href={`mailto:${encodeURIComponent(member.email)}`}>{member.email}</a> : <span className="muted">Email not entered</span>}
        </div>
        {canManage ? <div className="team-member-actions">
          <Button variant="default" onClick={() => onEdit(member)} aria-label={`Edit ${member.name}`}>Edit</Button>
          <DeleteRecordButton label="member" recordName={member.name} confirmLabel="Delete member" destructive
            description="Remove this person from the project directory. Their details and change history will be retained."
            onDelete={reason => team.remove(projectId, member, reason)} onDeleted={() => onDeleted(member.name)} />
        </div> : null}
      </div></Card>)}</div>}
    {members.length > PAGE_SIZE ? <RegisterPagination offset={offset} total={members.length} pageSize={PAGE_SIZE} onChange={next => setPage({ query, offset: next })} /> : null}
  </section>;
}
