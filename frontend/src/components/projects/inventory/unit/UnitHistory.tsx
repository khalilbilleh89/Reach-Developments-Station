"use client";

import type { UnitStatusEvent } from "@/lib/api";
import { Badge, EmptyState, TableScroll } from "@/components/ui";
import { businessDate } from "@/lib/format";
import {
  DIMENSION_LABELS,
  statusLabel,
  statusTone,
} from "@/components/projects/inventory/statusLabels";

/**
 * Every status this unit has held, and why it moved.
 *
 * Newest first is tempting and wrong here: this is the record somebody reads to
 * reconstruct what happened, and it is kept in the order the server returned so
 * the browser is not quietly reordering an audit trail.
 */
export function UnitHistory({ history }: { history: UnitStatusEvent[] }) {
  if (history.length === 0) {
    return (
      <EmptyState
        title="Nothing recorded yet"
        hint="Every status change is kept here with its effective date and reason."
      />
    );
  }

  return (
    <TableScroll label="Unit status history" compact>
      <thead>
        <tr>
          <th scope="col">Effective</th>
          <th scope="col">Dimension</th>
          <th scope="col">From</th>
          <th scope="col">To</th>
          <th scope="col">Reason</th>
        </tr>
      </thead>
      <tbody>
        {history.map((event) => (
          <tr key={event.id}>
            <th scope="row" className="figure">
              {businessDate(event.effective_date)}
            </th>
            <td>{DIMENSION_LABELS[event.dimension] ?? event.dimension}</td>
            <td>{event.from_status ? statusLabel(event.from_status) : "—"}</td>
            <td>
              <Badge tone={statusTone(event.to_status)}>{statusLabel(event.to_status)}</Badge>
            </td>
            <td>{event.reason ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </TableScroll>
  );
}
