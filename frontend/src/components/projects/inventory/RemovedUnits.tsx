"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, inventory } from "@/lib/api";
import type { RemovedUnit } from "@/lib/api";
import { UnitPermanentDeletionAction } from "./UnitRemovalAction";
import { UnitPurgePage } from "./UnitPurgePage";
import {
  Button, Card, DataToolbar, EmptyState, Loading, Notice, PromptDialog,
  RecordPage, TableScroll,
} from "@/components/ui";

const PAGE = 50;

export function RemovedUnits({ projectId, onClose, onRestored }: {
  projectId: string;
  onClose: () => void;
  onRestored: () => Promise<void>;
}) {
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<RemovedUnit[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<RemovedUnit | null>(null);
  const [purging, setPurging] = useState<RemovedUnit | null>(null);
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const reload = useCallback(() => setRevision(value => value + 1), []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setRows(null);
      setError(null);
      try {
        const result = await inventory.removedUnits(projectId, {
          search, offset: String(offset), limit: String(PAGE),
        });
        if (!cancelled) setRows(result);
      } catch (caught) {
        if (!cancelled) setError(caught instanceof ApiError ? caught.message : "Could not load removed units.");
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [projectId, search, offset, revision]);

  async function restore(reason: string) {
    if (!selected || busy) return;
    setBusy(true);
    setRestoreError(null);
    try {
      await inventory.restoreUnit(projectId, selected.id, reason);
      setMessage(`${selected.unit_reference} restored to Inventory. Existing sales and history are preserved.`);
      setSelected(null);
      setOffset(0);
      reload();
      await onRestored();
    } catch (caught) {
      setRestoreError(caught instanceof ApiError ? caught.message : "Could not restore the unit.");
    } finally {
      setBusy(false);
    }
  }

  if (purging) return <UnitPurgePage key={`${projectId}:${purging.id}`} projectId={projectId} unit={purging}
    onClose={() => setPurging(null)} onPurged={() => {
      setMessage(`${purging.unit_reference} and its selected history were permanently purged. Its number and reference can be reused.`);
      setPurging(null); setOffset(0); reload();
      void onRestored().catch(() => setError("The unit was purged. Refresh Inventory to update its totals."));
    }} />;

  return <RecordPage title="Removed units" icon="inventory" onClose={onClose}
    subtitle="Recover a retained unit using its original number, reference and history.">
    <div className="stack">
      <Notice tone="info">Removed units are excluded from Active and inactive. Their numbers and references remain reserved. Permanently deleted unused units do not appear here.</Notice>
      {message ? <Notice tone="success">{message}</Notice> : null}
      <DataToolbar search={{ value: search, onChange: value => { setSearch(value); setOffset(0); }, label: "Search removed units", placeholder: "Unit reference or number" }} />
      {error ? <><Notice tone="error">{error}</Notice><Button onClick={reload}>Retry</Button></> : null}
      {!rows && !error ? <Loading label="Loading removed units" /> : null}
      {rows ? <Card flush>
        {rows.length ? <TableScroll label="Removed units"><thead><tr>
          <th>Unit</th><th>Location</th><th>Commercial status</th><th>Removed</th><th>Action</th>
        </tr></thead><tbody>{rows.map(unit => <tr key={unit.id}>
          <th scope="row"><div>{unit.unit_reference}</div><div className="subtle">Number {unit.unit_number}</div></th>
          <td>{[unit.phase_code, unit.building_code, unit.floor_code].filter(Boolean).join(" / ")}</td>
          <td>{unit.commercial_status.replaceAll("_", " ")}</td>
          <td>{new Date(unit.removed_at).toLocaleString()}</td>
          <td><div className="button-row"><Button disabled={busy} onClick={() => { setSelected(unit); setRestoreError(null); }}>Restore {unit.unit_reference}</Button>
            <UnitPermanentDeletionAction projectId={projectId} unitId={unit.id} reference={unit.unit_reference}
              onDeleted={async () => { setOffset(0); reload(); await onRestored(); }} />
            <Button variant="danger" disabled={busy} onClick={() => setPurging(unit)}>Purge unit and linked history</Button>
          </div></td>
        </tr>)}</tbody></TableScroll> : <EmptyState title="No removed units found" hint="Try another reference or return to Inventory to check the current units." />}
      </Card> : null}
      <div className="button-row">
        <Button disabled={offset === 0 || !rows || busy} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous page</Button>
        <Button disabled={!rows || rows.length < PAGE || busy} onClick={() => setOffset(offset + PAGE)}>Next page</Button>
      </div>
    </div>
    {selected ? <PromptDialog title={`Restore ${selected.unit_reference}?`} label="Reason for restoration"
      description={`Restores this unit as active in Inventory. Sales visibility follows each transaction's status; cancelled transactions remain in history. Its commercial status stays ${selected.commercial_status.replaceAll("_", " ")}. Existing prices, measurements, contracts, payments and legal history remain unchanged. This does not create a new sale or release the unit.`}
      confirmLabel="Restore unit" busy={busy} error={restoreError}
      onCancel={() => { if (!busy) setSelected(null); }} onSubmit={reason => void restore(reason)} /> : null}
  </RecordPage>;
}
