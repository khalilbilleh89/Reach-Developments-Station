"use client";

import { useEffect, useState } from "react";
import { ApiError, inventory } from "@/lib/api";
import type { SubAsset } from "@/lib/api";
import { Button, Card, EmptyState, Loading, Notice, TableScroll } from "@/components/ui";
import { DeleteRecordButton } from "../DeleteRecordButton";

/** Detached assets remain discoverable, including after leaving a unit's property file. */
export function UnassignedAssets({ projectId }: { projectId: string }) {
  const [rows, setRows] = useState<SubAsset[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let current = true;
    inventory.subAssets(projectId, { linked: "false" }).then(result => {
      if (current) { setRows(result); setError(null); }
    }).catch(caught => {
      if (current) setError(caught instanceof ApiError ? caught.message : "Could not load unassigned assets.");
    });
    return () => { current = false; };
  }, [projectId, revision]);
  return <Card title="Unassigned parking and storage" description="Detached records stay here until reassigned or deleted.">
    {error ? <Notice tone="error">{error}<Button onClick={() => setRevision(value => value + 1)}>Retry</Button></Notice>
      : rows === null ? <Loading label="Loading unassigned assets" />
        : rows.length === 0 ? <EmptyState title="No unassigned assets" hint="Detached parking and storage records will appear here." />
          : <TableScroll label="Unassigned assets"><thead><tr><th>Reference</th><th>Type</th><th>Actions</th></tr></thead>
            <tbody>{rows.map(row => <tr key={row.id}><th scope="row">{row.asset_reference}</th><td>{row.asset_type}</td><td>
              <DeleteRecordButton label={row.asset_reference} description="Permanently delete this unassigned asset. Linked business records are protected and the audit trail is retained."
                onDelete={reason => inventory.deleteRecord(projectId, "sub-assets", row.id, reason)}
                onDeleted={async () => { setRows(current => current?.filter(asset => asset.id !== row.id) ?? null); setRevision(value => value + 1); }} />
            </td></tr>)}</tbody></TableScroll>}
  </Card>;
}
