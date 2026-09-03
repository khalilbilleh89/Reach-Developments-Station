"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, audit } from "@/lib/api";
import type { AuditEvent } from "@/lib/api";
import { Button, Card, DataToolbar, EmptyState, Loading, Notice, TableScroll } from "@/components/ui";

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
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setEvents((await audit.list()).items);
      setError(null);
    } catch (caught) {
      setEvents([]);
      setError(
        caught instanceof ApiError && caught.isForbidden
          ? "Audit history is limited to System Administrators and Auditors."
          : "Could not load audit history.",
      );
    }
  }, []);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const needle = search.trim().toLowerCase();
  const shown = (events ?? []).filter(
    (event) =>
      !needle ||
      `${event.action} ${event.entity_type} ${event.actor_display_name ?? ""} ${event.reason ?? ""}`
        .toLowerCase()
        .includes(needle),
  );

  return (
    <div className="stack">
      {error ? <Notice tone="error">{error}</Notice> : null}

      <DataToolbar
        search={{ value: search, onChange: setSearch, placeholder: "Action, object, person or reason", label: "Search audit history" }}
        count={events ? { shown: shown.length, total: events.length, noun: "event" } : undefined}
      />

      <Card flush>
        {events === null ? (
          <Loading label="Loading audit history…" shape="rows" />
        ) : shown.length === 0 ? (
          <div className="card-body">
            <EmptyState
              title={events.length === 0 ? "No audit events yet" : "No event matches"}
              hint={events.length === 0 ? "Changes to users and configuration appear here." : "Try another word."}
            />
          </div>
        ) : (
          <TableScroll label="Audit history">
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
                  <td className="figure">{new Date(event.occurred_at).toLocaleString()}</td>
                  <td>{event.actor_display_name ?? event.source}</td>
                  <td className="mono">{event.action}</td>
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
    </div>
  );
}
