"use client";

import { Badge, Card, DataToolbar, DateRange, DensitySwitch, EmptyState, FilterChips, Notice, RecordLink, RegisterPagination, SavedViews, Segmented, TableScroll, ToolbarFilter, Tooltip } from "@/components/ui";
import { pageOffset, useRegisterFields, useRegisterRestore } from "@/components/shell/registerState";
import { ReadState } from "@/components/portfolio/ReadState";
import { inventory, sales } from "@/lib/api";
import { useAnswer } from "@/lib/answer";
import { businessDate, eventTime } from "@/lib/format";
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
  const statusName = (status: string) => fields.history_kind === "sale" || ["signature_pending", "termination_pending"].includes(status) ? saleLabel(status) : reservationLabel(status);
  const phaseName = phases.status === "ready" ? phases.data.find(p => p.id === fields.history_phase)?.name : undefined;
  const chips = [
    fields.history_kind ? { key: "kind", label: fields.history_kind === "sale" ? "Sales only" : "Reservations only", onRemove: () => filter({ history_kind: "", history_status: "" }) } : null,
    fields.history_status ? { key: "status", label: `Status: ${statusName(fields.history_status)}`, onRemove: () => filter({ history_status: "" }) } : null,
    fields.history_phase ? { key: "phase", label: `Phase: ${phaseName ?? "Selected phase"}`, onRemove: () => filter({ history_phase: "" }) } : null,
    fields.history_from || fields.history_to ? { key: "created", label: `Created ${fields.history_from ? businessDate(fields.history_from) : "any time"} – ${fields.history_to ? businessDate(fields.history_to) : "today"}`, onRemove: () => filter({ history_from: "", history_to: "" }) } : null,
    fields.history_search ? { key: "search", label: `“${fields.history_search}”`, onRemove: () => filter({ history_search: "" }) } : null,
  ].filter((chip): chip is NonNullable<typeof chip> => chip !== null);
  const states = fields.history_kind === "sale" ? ["draft", "signature_pending", "active", "termination_pending", "cancelled"] : fields.history_kind === "reservation" ? ["draft", "deposit_pending", "active", "extended", "converted", "expired", "cancelled"] : ["draft", "deposit_pending", "signature_pending", "active", "extended", "converted", "expired", "termination_pending", "cancelled"];
  return <div className="stack">
    <p>All authorized reservations and sale contracts, including converted, expired and cancelled records. Each transaction has its own row. These records do not add to current Sales totals.</p>
    <DataToolbar framed search={{ value: fields.history_search, onChange: history_search => filter({ history_search }), label: "Search all transactions", placeholder: "Unit, buyer, reservation, sale or SPA" }}
      count={answer.status === "ready" ? { shown: answer.data.items.length, total: answer.data.total, noun: "transaction" } : undefined}
      onReset={Object.values(fields).some(Boolean) ? () => change(defaults) : undefined}
      actions={<DensitySwitch />}>
      <ToolbarFilter label="Transaction type" active={fields.history_kind !== ""}><Segmented label="Transaction type" value={fields.history_kind} onChange={history_kind => filter({ history_kind, history_status: "" })} options={[{ value: "", label: "All" }, { value: "reservation", label: "Reservations" }, { value: "sale", label: "Sales" }]} /></ToolbarFilter>
      <ToolbarFilter label="Transaction status" active={fields.history_status !== ""}><select className="input" value={fields.history_status} onChange={e => filter({ history_status: e.target.value })}><option value="">All statuses</option>{states.map(status => <option key={status} value={status}>{statusName(status)}</option>)}</select></ToolbarFilter>
      <ToolbarFilter label="Phase" active={fields.history_phase !== ""}><select className="input" value={fields.history_phase} onChange={e => filter({ history_phase: e.target.value })}><option value="">Every phase</option>{fields.history_phase && (phases.status !== "ready" || !phases.data.some(p => p.id === fields.history_phase)) ? <option value={fields.history_phase}>Selected phase</option> : null}{phases.status === "ready" ? phases.data.map(p => <option key={p.id} value={p.id}>{p.code} · {p.name}</option>) : null}</select></ToolbarFilter>
      <ToolbarFilter label="Created (UTC)" active={Boolean(fields.history_from || fields.history_to)}><DateRange label="Created (UTC)" from={fields.history_from} to={fields.history_to} onChange={range => filter({ history_from: range.from, history_to: range.to })} /></ToolbarFilter>
    </DataToolbar>
    <FilterChips chips={chips} onClearAll={() => change(defaults)} />
    {/* Server-paginated: a view keeps the filters, never a sort over one page. */}
    <SavedViews screen="sales_all_transactions" filters={{ history_kind: fields.history_kind, history_status: fields.history_status, history_phase: fields.history_phase, history_from: fields.history_from, history_to: fields.history_to }} sort={null}
      onApply={saved => filter({ history_kind: String(saved.history_kind ?? ""), history_status: String(saved.history_status ?? ""), history_phase: String(saved.history_phase ?? ""), history_from: String(saved.history_from ?? ""), history_to: String(saved.history_to ?? "") })} />
    {phases.status !== "ready" ? <ReadState answer={phases} label="Reading phase filters…" /> : null}
    {invalidDates ? <Notice tone="error">The end date must be on or after the start date.</Notice> : answer.status !== "ready" ? <ReadState answer={answer} label="Reading transaction history…" /> : <>
      {!answer.data.total ? <EmptyState title="No matching transactions" hint="Adjust the search or filters to include other transaction states." /> : <Card flush><TableScroll label="Sales transaction history" fixedFirst stickyHeader>
        <thead><tr>{["Transaction", "Unit", "Buyer", "Status"].map(label => <th scope="col" key={label}>{label}</th>)}<th scope="col"><Tooltip term="SPA">Sale and purchase agreement: the contract the buyer signs for the unit.</Tooltip></th><th scope="col">Created (UTC)</th></tr></thead>
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
