"use client";

import { pageOffset, useRegisterFields } from "@/components/shell/registerState";
import { useAnswer } from "@/lib/answer";
import { ReadState } from "@/components/portfolio/ReadState";
import { eventTime } from "@/lib/format";

import { audit } from "@/lib/api";
import { Button, Card, DataToolbar, Field, EmptyState, Notice, RegisterPagination, TableScroll } from "@/components/ui";

/** Format a before/after snapshot as readable field lines, not raw JSON. */
function Snapshot({ title, data }: { title: string; data: Record<string, unknown> | null }) {
  if (!data) return null;
  return (
    <div className="snapshot">
      <p className="snapshot-title">{title}</p>
      <dl className="snapshot-list">
        {Object.entries(data).map(([key, value]) => (
          <div key={key} className="snapshot-row">
            <dt>{key.replace(/_/g, " ")}</dt>
            <dd>{Array.isArray(value) ? value.join(", ") : String(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/**
 * Audit history.
 *
 * For traceability, not decoration: a compact table with the detail available
 * on demand. No analytics, no dashboards.
 */
export function AuditSection() {
  const defaults = { search: "", action: "", entity_type: "", actor_user_id: "", occurred_from: "", occurred_to: "", offset: "", event: "" };
  const [fields, change] = useRegisterFields(defaults);
  const offset = pageOffset(fields.offset), open = fields.event;
  const filter = (changes: Partial<typeof defaults>) => change({ ...changes, offset: "", event: "" });
  const setOpen = (event: string | null) => change({ event: event ?? "" });
  const query: Record<string, string> = { limit: "50", offset: String(offset) };
  for (const key of ["search", "action", "entity_type", "actor_user_id"] as const) if (fields[key]) query[key] = fields[key];
  if (fields.occurred_from) query.occurred_from = `${fields.occurred_from}T00:00:00Z`;
  if (fields.occurred_to) query.occurred_to = `${fields.occurred_to}T23:59:59.999999Z`;
  const invalidDates = Boolean(fields.occurred_from && fields.occurred_to && fields.occurred_from > fields.occurred_to);
  const answer = useAnswer(!invalidDates, () => audit.list(query), [JSON.stringify(query)]);
  const shown = answer.status === "ready" ? answer.data.items : [];

  return (
    <div className="stack">
      {invalidDates ? <Notice tone="error">The end date must be on or after the start date.</Notice> : null}

      <DataToolbar
        framed
        search={{ value: fields.search, onChange: search => filter({ search }), placeholder: "Action code, object, person or reason", label: "Search all audit history" }}
        count={answer.status === "ready" ? { shown: shown.length, total: answer.data.total, noun: "event" } : undefined}
        onReset={Object.values(fields).some(Boolean) ? () => change(defaults) : undefined}
      >
        <Field className="toolbar-filter" label="Action code (exact)"><input className="input" value={fields.action} onChange={e => filter({ action: e.target.value })} maxLength={64} /></Field>
        <Field className="toolbar-filter" label="Object type (exact)"><input className="input" value={fields.entity_type} onChange={e => filter({ entity_type: e.target.value })} maxLength={64} /></Field>
        <Field className="toolbar-filter" label="From (UTC)"><input className="input" type="date" value={fields.occurred_from} onChange={e => filter({ occurred_from: e.target.value })} /></Field>
        <Field className="toolbar-filter" label="Through (UTC)"><input className="input" type="date" value={fields.occurred_to} onChange={e => filter({ occurred_to: e.target.value })} /></Field>
        {fields.actor_user_id ? <p className="hint">Filtered to selected actor <Button small onClick={() => filter({ actor_user_id: "" })}>Clear actor</Button></p> : null}
      </DataToolbar>

      <Card flush>
        {invalidDates ? null : answer.status !== "ready" ? (
          <ReadState answer={answer} label="Loading audit history…" />
        ) : shown.length === 0 ? (
          <div className="card-body">
            <EmptyState
              title="No matching audit events"
              hint="Adjust the search or filters to see other recorded events."
            />
          </div>
        ) : (
          <TableScroll fixedFirst label="Audit history">
            <thead>
              <tr>
                <th scope="col">When</th>
                <th scope="col">Who</th>
                <th scope="col">Action</th>
                <th scope="col">Object</th>
                <th scope="col">Reason</th>
                <th scope="col">
                  <span className="visually-hidden">Detail</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.map((event) => (
                <tr key={event.id}>
                  <td className="figure">{eventTime(event.occurred_at)}</td>
                  <td>{event.actor_user_id ? <Button variant="link" onClick={() => filter({ actor_user_id: event.actor_user_id! })}>{event.actor_display_name ?? "Recorded actor"}</Button> : event.source}</td>
                  <td>{event.action.replaceAll("_", " ").replaceAll(".", " · ")}<p className="hint mono">{event.action}</p></td>
                  <td>{event.entity_type}</td>
                  <td className="cell-prose">{event.reason ?? "—"}</td>
                  <td>
                    <Button
                      small
                      variant="quiet"
                      aria-expanded={open === event.id}
                      onClick={() => setOpen(open === event.id ? null : event.id)}
                    >
                      {open === event.id ? "Hide" : "Detail"}
                    </Button>
                    {open === event.id ? (
                      <div className="detail">
                        <Snapshot title="Before" data={event.before_data} />
                        <Snapshot title="After" data={event.after_data} />
                        <p className="hint mono">Correlation {event.correlation_id}</p>
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        )}
      </Card>
      {answer.status === "ready" ? <RegisterPagination pageSize={50} offset={offset} total={answer.data.total} onChange={offset => change({ offset: String(offset), event: "" })} /> : null}
    </div>
  );
}
