"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, audit } from "@/lib/api";
import type { AuditEvent } from "@/lib/api";
import { EmptyState, Loading, Notice, Panel } from "@/components/ui";

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
            <dd className="mono">{Array.isArray(value) ? value.join(", ") : String(value)}</dd>
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

  if (events === null) return <Loading label="Loading audit history…" />;

  return (
    <Panel title="Audit" description="Every material governance change, with who made it and why.">
      {error ? <Notice tone="error">{error}</Notice> : null}

      {events.length === 0 && !error ? (
        <EmptyState title="No audit events yet" hint="Changes to users and configuration appear here." />
      ) : null}

      {events.length > 0 ? (
        <div className="table-scroll">
          <table className="table">
            <caption className="visually-hidden">Audit history</caption>
            <thead>
              <tr>
                <th scope="col">Time</th>
                <th scope="col">Actor</th>
                <th scope="col">Action</th>
                <th scope="col">Object</th>
                <th scope="col">Reason</th>
                <th scope="col">Detail</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.id}>
                  <td className="mono nowrap">{new Date(event.occurred_at).toLocaleString()}</td>
                  <td>{event.actor_display_name ?? event.source}</td>
                  <td className="mono">{event.action}</td>
                  <td>{event.entity_type}</td>
                  <td>{event.reason ?? "—"}</td>
                  <td>
                    <button
                      className="button button-small"
                      type="button"
                      aria-expanded={open === event.id}
                      onClick={() => setOpen(open === event.id ? null : event.id)}
                    >
                      {open === event.id ? "Hide" : "Show"}
                    </button>
                    {open === event.id ? (
                      <div className="detail">
                        <Snapshot title="Before" data={event.before_data} />
                        <Snapshot title="After" data={event.after_data} />
                        <p className="subtle mono">Correlation {event.correlation_id}</p>
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </Panel>
  );
}
