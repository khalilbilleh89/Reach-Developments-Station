"use client";

import { pageOffset, useRegisterFields } from "@/components/shell/registerState";
import { useAnswer } from "@/lib/answer";
import { ReadState } from "@/components/portfolio/ReadState";
import { businessDate, eventTime } from "@/lib/format";

import { audit } from "@/lib/api";
import { Button, Card, DataToolbar, DateRange, DensitySwitch, EmptyState, FilterChips, Notice, RecordPage, RegisterPagination, SavedViews, TableScroll, ToolbarFilter } from "@/components/ui";

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
  const opened = shown.find((event) => event.id === open) ?? null;
  const actionWords = (action: string) => action.replaceAll("_", " ").replaceAll(".", " · ");
  const occurred = fields.occurred_from || fields.occurred_to
    ? [fields.occurred_from ? `from ${businessDate(fields.occurred_from)}` : null, fields.occurred_to ? `to ${businessDate(fields.occurred_to)}` : null].filter(Boolean).join(" ")
    : "";
  const chips = [
    fields.search ? { key: "search", label: `“${fields.search}”`, onRemove: () => filter({ search: "" }) } : null,
    fields.action ? { key: "action", label: `Action: ${fields.action}`, onRemove: () => filter({ action: "" }) } : null,
    fields.entity_type ? { key: "entity_type", label: `Object: ${fields.entity_type}`, onRemove: () => filter({ entity_type: "" }) } : null,
    occurred ? { key: "occurred", label: `Occurred ${occurred} (UTC)`, onRemove: () => filter({ occurred_from: "", occurred_to: "" }) } : null,
    fields.actor_user_id ? { key: "actor", label: "Selected actor", onRemove: () => filter({ actor_user_id: "" }) } : null,
  ].filter((chip): chip is NonNullable<typeof chip> => chip !== null);

  return (
    <div className="stack">
      {invalidDates ? <Notice tone="error">The end date must be on or after the start date.</Notice> : null}

      <DataToolbar
        framed
        search={{ value: fields.search, onChange: search => filter({ search }), placeholder: "Action code, object, person or reason", label: "Search all audit history" }}
        count={answer.status === "ready" ? { shown: shown.length, total: answer.data.total, noun: "event" } : undefined}
        onReset={Object.values(fields).some(Boolean) ? () => change(defaults) : undefined}
        actions={<DensitySwitch />}
      >
        <ToolbarFilter label="Action code (exact)" active={fields.action !== ""}><input className="input" placeholder="Action code" value={fields.action} onChange={e => filter({ action: e.target.value })} maxLength={64} /></ToolbarFilter>
        <ToolbarFilter label="Object type (exact)" active={fields.entity_type !== ""}><input className="input" placeholder="Object type" value={fields.entity_type} onChange={e => filter({ entity_type: e.target.value })} maxLength={64} /></ToolbarFilter>
        <ToolbarFilter label="Occurred (UTC dates)" active={fields.occurred_from !== "" || fields.occurred_to !== ""}><DateRange label="Occurred between (UTC dates)" from={fields.occurred_from} to={fields.occurred_to} onChange={range => filter({ occurred_from: range.from, occurred_to: range.to })} /></ToolbarFilter>
      </DataToolbar>
      <FilterChips chips={chips} onClearAll={() => filter({ search: "", action: "", entity_type: "", occurred_from: "", occurred_to: "", actor_user_id: "" })} />
      <SavedViews
        screen="settings-audit"
        filters={{ search: fields.search, action: fields.action, entity_type: fields.entity_type, occurred_from: fields.occurred_from, occurred_to: fields.occurred_to, actor_user_id: fields.actor_user_id }}
        sort={null}
        onApply={(saved) => filter({ search: String(saved.search ?? ""), action: String(saved.action ?? ""), entity_type: String(saved.entity_type ?? ""), occurred_from: String(saved.occurred_from ?? ""), occurred_to: String(saved.occurred_to ?? ""), actor_user_id: String(saved.actor_user_id ?? "") })}
      />

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
                  <td>{actionWords(event.action)}<p className="hint mono">{event.action}</p></td>
                  <td>{event.entity_type}</td>
                  <td className="cell-prose">{event.reason ?? "—"}</td>
                  <td>
                    <Button small variant="quiet" aria-label={`Open audit event ${actionWords(event.action)}`} onClick={() => setOpen(event.id)}>
                      Detail
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        )}
      </Card>
      {opened ? (
        <RecordPage
          eyebrow="Audit event"
          title={actionWords(opened.action)}
          subtitle={opened.entity_type}
          strip={{
            lead: { label: "Occurred", value: eventTime(opened.occurred_at) },
            items: [
              { label: "Who", value: opened.actor_display_name ?? (opened.actor_user_id ? "Recorded actor" : opened.source) },
              { label: "Action code", value: <span className="mono">{opened.action}</span> },
              { label: "Object", value: opened.entity_type },
              { label: "Reason", value: opened.reason ?? "—" },
            ],
          }}
          onClose={() => setOpen(null)}
        >
          <div className="detail">
            <Snapshot title="Before" data={opened.before_data} />
            <Snapshot title="After" data={opened.after_data} />
            <p className="hint mono">Correlation {opened.correlation_id}</p>
          </div>
        </RecordPage>
      ) : null}
      {answer.status === "ready" ? <RegisterPagination pageSize={50} offset={offset} total={answer.data.total} onChange={offset => change({ offset: String(offset), event: "" })} /> : null}
    </div>
  );
}
