"use client";

import { Badge, Card, DataToolbar, Field, EmptyState, Notice, RecordLink, RegisterPagination, TableScroll, ToolbarFilter } from "@/components/ui";
import { pageOffset, useRegisterFields, useRegisterRestore } from "@/components/shell/registerState";
import { ReadState } from "@/components/portfolio/ReadState";
import { inventory, sales } from "@/lib/api";
import { useAnswer } from "@/lib/answer";
import { eventTime } from "@/lib/format";
import { reservationLabel, reservationTone, saleLabel, saleTone } from "./labels";

const defaults = { history_search: "", history_kind: "", history_status: "", history_phase: "", history_from: "", history_to: "", history_offset: "" };
export function SalesHistory({ projectId }: { projectId: string }) {
  const [fields, change] = useRegisterFields(defaults);
  const offset = pageOffset(fields.history_offset);
  const invalidDates = Boolean(fields.history_from && fields.history_to && fields.history_from > fields.history_to);
  const filter = (changes: Partial<typeof defaults>) => change({ ...changes, history_offset: "" });
  const query: Record<string, string> = { limit: "50", offset: String(offset) };
  for (const [key, value] of Object.entries({ search: fields.history_search, kind: fields.history_kind, status: fields.history_status, phase_id: fields.history_phase, created_from: fields.history_from, created_to: fields.history_to })) if (value) query[key] = value;
  const answer = useAnswer(!invalidDates, () => sales.history(projectId, query), [projectId, JSON.stringify(query)]);
  useRegisterRestore(answer.status === "ready");
  const phases = useAnswer(true, () => inventory.phases(projectId), [projectId]);
  const states = fields.history_kind === "sale" ? ["draft", "signature_pending", "active", "termination_pending", "cancelled"] : fields.history_kind === "reservation" ? ["draft", "deposit_pending", "active", "extended", "converted", "expired", "cancelled"] : ["draft", "deposit_pending", "signature_pending", "active", "extended", "converted", "expired", "termination_pending", "cancelled"];
  return <div className="stack">
    <p>All authorized reservations and sale contracts, including converted, expired and cancelled records. Each transaction has its own row. These records do not add to current Sales totals.</p>
    <DataToolbar framed search={{ value: fields.history_search, onChange: history_search => filter({ history_search }), label: "Search all transactions", placeholder: "Unit, buyer, reservation, sale or SPA" }}
      count={answer.status === "ready" ? { shown: answer.data.items.length, total: answer.data.total, noun: "transaction" } : undefined}
      onReset={Object.values(fields).some(Boolean) ? () => change(defaults) : undefined}>
      <ToolbarFilter label="Transaction type"><select className="input" value={fields.history_kind} onChange={e => filter({ history_kind: e.target.value, history_status: "" })}><option value="">All transactions</option><option value="reservation">Reservations</option><option value="sale">Sales</option></select></ToolbarFilter>
      <ToolbarFilter label="Transaction status"><select className="input" value={fields.history_status} onChange={e => filter({ history_status: e.target.value })}><option value="">All statuses</option>{states.map(status => <option key={status} value={status}>{fields.history_kind === "sale" || ["signature_pending", "termination_pending"].includes(status) ? saleLabel(status) : reservationLabel(status)}</option>)}</select></ToolbarFilter>
      <ToolbarFilter label="Phase"><select className="input" value={fields.history_phase} onChange={e => filter({ history_phase: e.target.value })}><option value="">Every phase</option>{fields.history_phase && (phases.status !== "ready" || !phases.data.some(p => p.id === fields.history_phase)) ? <option value={fields.history_phase}>Selected phase</option> : null}{phases.status === "ready" ? phases.data.map(p => <option key={p.id} value={p.id}>{p.code} · {p.name}</option>) : null}</select></ToolbarFilter>
      <Field className="toolbar-filter" label="Created from (UTC)"><input className="input" type="date" value={fields.history_from} onChange={e => filter({ history_from: e.target.value })} /></Field>
      <Field className="toolbar-filter" label="Created through (UTC)"><input className="input" type="date" value={fields.history_to} onChange={e => filter({ history_to: e.target.value })} /></Field>
    </DataToolbar>
    {phases.status !== "ready" ? <ReadState answer={phases} label="Reading phase filters…" /> : null}
    {invalidDates ? <Notice tone="error">The end date must be on or after the start date.</Notice> : answer.status !== "ready" ? <ReadState answer={answer} label="Reading transaction history…" /> : <>
      {!answer.data.total ? <EmptyState title="No matching transactions" hint="Adjust the search or filters to include other transaction states." /> : <Card flush><TableScroll label="Sales transaction history" fixedFirst stickyHeader>
        <thead><tr>{["Transaction", "Unit", "Buyer", "Status", "SPA", "Created (UTC)"].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead>
        <tbody>{answer.data.items.map(row => <tr key={`${row.kind}:${row.id}`}>
          <th scope="row"><RecordLink projectId={projectId} kind={row.kind} id={row.id}>{row.kind === "sale" ? "Sale" : "Reservation"} · {row.reference}</RecordLink></th>
          <td><RecordLink projectId={projectId} kind="unit" id={row.unit_id}>{row.unit_reference}</RecordLink></td>
          <td>{row.client_display_name}</td><td><Badge tone={row.kind === "sale" ? saleTone(row.status) : reservationTone(row.status)}>{row.kind === "sale" ? saleLabel(row.status) : reservationLabel(row.status)}</Badge></td>
          <td>{row.spa_number ?? "—"}</td><td>{eventTime(row.created_at)}</td>
        </tr>)}</tbody>
      </TableScroll></Card>}
      <RegisterPagination offset={offset} pageSize={50} total={answer.data.total} onChange={offset => change({ history_offset: String(offset) })} />
    </>}
  </div>;
}
