"use client";

import { useState } from "react";
import Link from "next/link";
import { recordHref } from "@/components/shell/recordRoutes";
import { leasing, LEASING_STAGES, type LeasingDetail, type LeasingRow, type LeasingSource } from "@/lib/api/leasing";
import { useAnswer } from "@/lib/answer";
import type { Answer } from "@/lib/answer";
import { money, businessDate } from "@/lib/format";
import { Badge, Button, Card, EmptyState, Field, FieldRow, Loading, Notice, PageHeader, RecordPage, RegisterPagination, SectionHeader, StatStrip, StatStripItem, TableScroll } from "@/components/ui";
import { DeleteRecordButton } from "@/components/projects/DeleteRecordButton";
import { LeasingEditor } from "./LeasingEditor";

export function AnswerState<T>({ answer }: { answer: Answer<T> & { retry: () => void } }) {
  if (answer.status === "loading") return <Loading label="Loading leasing records…" />;
  if (answer.status === "failed") return <Notice tone="error">{answer.message} <Button onClick={answer.retry}>Retry</Button></Notice>;
  if (answer.status === "denied") return <Notice tone="info">These records are not available to your access level.</Notice>;
  return null;
}

export function SourceProfile({ source }: { source: LeasingSource }) {
  return <Card><SectionHeader title="Linked unit" /><p className="muted">Current details from the development register.</p>
    <dl className="leasing-facts">
      <div><dt>Project / location</dt><dd>{source.project_name} · {source.location ?? "Location not recorded"}</dd></div>
      <div><dt>Unit / building / floor</dt><dd>{source.unit.unit_reference} · {source.unit.building ?? "—"} · {source.unit.floor ?? "—"}</dd></div>
      <div><dt>Type / bedrooms / bathrooms</dt><dd>{source.asset_class} · {source.bedrooms ?? "—"} beds · {source.bathrooms ?? "—"} baths</dd></div>
      <div><dt>Approved internal area</dt><dd>{source.internal_area === null ? "Not recorded" : `${source.internal_area} ${source.area_unit ?? ""}`}</dd></div>
      <div><dt>Furnishing / delivery</dt><dd>{source.furnishing ?? "Not recorded"} · {source.delivery_status.replaceAll("_", " ")}</dd></div>
      <div><dt>Buyer on active sale</dt><dd>{source.sale_client?.display_name ?? "No active sale linked"}{source.sale_reference ? ` · ${source.sale_reference}` : ""}</dd></div>
    </dl>
    {!source.unit.is_active ? <Notice tone="warning">This unit has been removed or made inactive in Inventory. Its leasing history is retained.</Notice> : null}
  </Card>;
}

export function LeasingWorkspace({ canWrite }: { canWrite: boolean }) {
  const [project, setProject] = useState("");
  const [search, setSearch] = useState("");
  const [stage, setStage] = useState("");
  const [focus, setFocus] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<LeasingRow | null>(null);
  const [editor, setEditor] = useState<{ row?: LeasingDetail } | null>(null);
  const projects = useAnswer(true, leasing.projects, []);
  const answer = useAnswer(true, () => leasing.list(project, search, stage, focus, offset), [project, search, stage, focus, offset]);
  const detail = useAnswer(!!selected, () => leasing.detail(selected!), [selected?.project_id, selected?.id]);
  const refresh = () => { setSelected(null); setOffset(0); answer.retry(); };
  if (editor) return <LeasingEditor projects={projects.status === "ready" ? projects.data : []} initialProject={project} row={editor.row} onClose={() => setEditor(null)} onSaved={() => { setEditor(null); refresh(); }} />;
  if (selected) return <RecordPage title={selected.unit_reference} eyebrow="Leasing instruction" subtitle={selected.project_name} onClose={() => setSelected(null)}>
    <AnswerState answer={detail} />
    {detail.status === "ready" ? <InstructionDetail row={detail.data} canWrite={canWrite} onEdit={() => setEditor({ row: detail.data })} onDeleted={async () => refresh()} /> : null}
  </RecordPage>;
  return <div className="stack">
    <PageHeader icon="leasing" eyebrow="Owner services" title="Leasing" subtitle="From owner instruction to the next tenancy. Every unit stays connected to its development."
      actions={canWrite ? <Button variant="primary" disabled={projects.status !== "ready" || !projects.data.length} onClick={() => setEditor({})}>New instruction</Button> : undefined} />
    <AnswerState answer={projects} />
    {projects.status === "ready" && !projects.data.length ? <Notice tone="info">No whole-project access is available. A project administrator can grant access before you start leasing.</Notice> : null}
    <div className="leasing-intro"><div><h2>A place for every letting</h2><p>Confirm the owner, bring the unit to market, then keep the tenancy and next action in view.</p></div><span className="leasing-journey">Instruction <span aria-hidden="true">→</span> Market <span aria-hidden="true">→</span> Tenancy</span></div>
    <Card><FieldRow columns={3}>
      <Field label="Search unit, owner or tenant"><input className="input" type="search" value={search} onChange={e => { setSearch(e.target.value); setOffset(0); }} /></Field>
      <Field label="Project"><select className="input" value={project} onChange={e => { setProject(e.target.value); setOffset(0); }}><option value="">All projects</option>{projects.status === "ready" ? projects.data.map(p => <option key={p.id} value={p.id}>{p.name}</option>) : null}</select></Field>
      <Field label="Stage"><select className="input" value={stage} onChange={e => { setStage(e.target.value); setFocus(""); setOffset(0); }}><option value="">All stages</option>{LEASING_STAGES.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}</select></Field>
    </FieldRow></Card>
    <AnswerState answer={answer} />
    {answer.status === "ready" ? <>
      <StatStrip>{LEASING_STAGES.map(s => <StatStripItem key={s.key} label={s.label} value={String(answer.data.counts[s.key] ?? 0)} />)}</StatStrip>
      <div className="leasing-actions"><Button variant={focus === "follow_up" ? "primary" : "default"} onClick={() => { setFocus(focus === "follow_up" ? "" : "follow_up"); setStage(""); setOffset(0); }}>Follow-ups due · {answer.data.counts.follow_up ?? 0}</Button>
        <Button variant={focus === "expiring" ? "primary" : "default"} onClick={() => { setFocus(focus === "expiring" ? "" : "expiring"); setStage(""); setOffset(0); }}>Expiring in 60 days · {answer.data.counts.expiring ?? 0}</Button>
        <span className="muted">As at {businessDate(answer.data.as_at)} · counts follow project and search</span>
        {search || project || stage || focus ? <Button variant="link" onClick={() => { setSearch(""); setProject(""); setStage(""); setFocus(""); setOffset(0); }}>Reset filters</Button> : null}
      </div>
      <Card><SectionHeader title="Leasing register" description={focus === "expiring" ? "Leased units ending within the next 60 days." : focus === "follow_up" ? "Open instructions with an action due today or earlier." : "Open a unit to manage its instruction and tenancy."} />
        {answer.data.items.length ? <TableScroll label="Leasing instructions" fixedFirst stickyHeader><thead><tr><th scope="col">Unit / project</th><th scope="col">Owner</th><th scope="col">Stage</th><th scope="col">Monthly rent</th><th scope="col">Next step</th></tr></thead><tbody>
          {answer.data.items.map(row => <tr key={row.id}><th scope="row"><Button variant="link" onClick={() => setSelected(row)}>{row.unit_reference}</Button><div className="muted">{row.project_name}</div></th><td>{row.owner_name ?? "Owner not linked"}</td><td><Badge>{LEASING_STAGES.find(s => s.key === row.status)?.label}</Badge>{row.tenant_name ? <div className="muted">{row.tenant_name}</div> : null}</td><td className="numeric">{money(row.status === "leased" ? row.agreed_rent_monthly : row.asking_rent_monthly, row.currency_code)}<div className="muted">{row.status === "leased" ? "Agreed" : "Asking"}</div></td><td>{row.next_action || "No action recorded"}{row.follow_up_date ? <div>{businessDate(row.follow_up_date)}</div> : null}{row.attention.map(note => <div key={note} className="muted">{note}</div>)}</td></tr>)}
        </tbody></TableScroll> : <EmptyState title="No leasing instructions yet" hint="Start with New instruction and choose an existing unit, or reset your filters." />}
        <RegisterPagination offset={offset} total={answer.data.total} pageSize={25} onChange={setOffset} />
      </Card>
    </> : null}
  </div>;
}

function InstructionDetail({ row, canWrite, onEdit, onDeleted }: { row: LeasingDetail; canWrite: boolean; onEdit: () => void; onDeleted: () => Promise<void> }) {
  return <div className="stack">
    <SectionHeader title={LEASING_STAGES.find(s => s.key === row.status)?.label ?? row.status} actions={canWrite ? <Button onClick={onEdit}>Edit instruction</Button> : undefined} />
    {row.owner_matches_sale === false ? <Notice tone="warning">The linked owner differs from the buyer on the current active sale. Review the owner’s instruction before proceeding.</Notice> : null}
    {row.attention.length ? <Notice tone="info">{row.attention.join(" · ")}</Notice> : null}
    <SourceProfile source={row.source} />
    <p><Link className="button button-default" href={recordHref(row.project_id, "unit", row.unit_id)}>Open unit in project</Link></p>
    <Card><SectionHeader title="Owner instruction" /><dl className="leasing-facts">
      <div><dt>Owner / client</dt><dd>{row.owner_name ?? "Not linked"}</dd></div>
      <div><dt>Instruction date / reference</dt><dd>{businessDate(row.mandate_date)} · {row.mandate_reference || "Not recorded"}</dd></div>
      <div><dt>Monthly asking rent</dt><dd>{money(row.asking_rent_monthly, row.currency_code)}</dd></div>
      <div><dt>Available from</dt><dd>{businessDate(row.available_from)}</dd></div>
    </dl><p className="muted">The client link identifies the instructing owner. A buyer on a sale is a source reference, not proof of registered title.</p></Card>
    <Card><SectionHeader title="Tenancy" /><dl className="leasing-facts">
      <div><dt>Tenant</dt><dd>{row.tenant_name || "Not recorded"}</dd></div>
      <div><dt>Lease period</dt><dd>{businessDate(row.lease_start)} → {businessDate(row.lease_end)}</dd></div>
      <div><dt>Agreed monthly rent</dt><dd>{money(row.agreed_rent_monthly, row.currency_code)}</dd></div>
      <div><dt>Security deposit agreed</dt><dd>{money(row.security_deposit, row.currency_code)}</dd></div>
      <div><dt>Agreement reference</dt><dd>{row.agreement_reference || "Not recorded"}</dd></div>
    </dl><p className="muted">Recorded terms only. Rent and deposit amounts do not record a payment or receipt.</p></Card>
    <Card><SectionHeader title="Next action and notes" /><p>{row.next_action || "No action recorded"} · {businessDate(row.follow_up_date)}</p><p className="leasing-notes">{row.notes || "No notes"}</p></Card>
    {canWrite ? <DeleteRecordButton label="instruction" recordName={row.unit_reference} confirmLabel="Delete instruction" description="Remove this instruction from Leasing. Its terms and audit history are retained. The project, unit and owner records remain linked and unchanged." onDelete={reason => leasing.remove(row, reason)} onDeleted={onDeleted} /> : null}
  </div>;
}
