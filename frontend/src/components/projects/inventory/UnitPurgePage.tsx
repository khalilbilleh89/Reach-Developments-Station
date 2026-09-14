"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, inventory } from "@/lib/api";
import type { RemovedUnit, UnitPurgePreview } from "@/lib/api";
import { Button, Card, Field, Loading, Notice, RecordPage, TableScroll, UnsavedChangesGuard } from "@/components/ui";

export function UnitPurgePage({ projectId, unit, onClose, onPurged }: {
  projectId: string; unit: RemovedUnit; onClose: () => void; onPurged: () => void;
}) {
  const [preview, setPreview] = useState<UnitPurgePreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [reference, setReference] = useState("");
  const [reason, setReason] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [revision, setRevision] = useState(0);
  const form = useRef<HTMLFormElement>(null);
  const refresh = useCallback(() => {
    setPreview(null); setReference(""); setAcknowledged(false);
    setLoading(true); setError(null);
    setRevision(value => value + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    inventory.unitPurgePreview(projectId, unit.id).then(result => {
      if (!cancelled) setPreview(result);
    }).catch(caught => {
      if (!cancelled) setError(caught instanceof ApiError ? caught.message : "Could not preview the unit's history.");
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [projectId, unit.id, revision]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!preview || busy || !acknowledged || reference !== preview.unit_reference || !reason.trim() || preview.blockers.length) return;
    setBusy(true); setError(null);
    try {
      await inventory.purgeUnitHistory(projectId, unit.id, {
        confirm_reference: reference, reason: reason.trim(), fingerprint: preview.fingerprint,
        acknowledge_history_deletion: true,
      });
      onPurged();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not confirm the purge. Refresh the preview to check the current records.");
      setPreview(null); setReference(""); setAcknowledged(false);
    } finally { setBusy(false); }
  }

  return <RecordPage title={`Purge ${unit.unit_reference} and linked history`} icon="inventory" onClose={onClose}
    subtitle="Master Administrator · Permanent database deletion">
    <form ref={form} onSubmit={submit} className="stack">
      <UnsavedChangesGuard form={form} dirty={Boolean(reference || reason || acknowledged)} busy={busy} />
      <Notice tone="warning">This permanently erases the unit and all records listed below, including closed sales, reservations and their financial and legal history. It cannot be undone. The unit number and reference become available again. Audit events, shared client records and saved reports remain.</Notice>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <div><Button type="button" disabled={busy || loading} onClick={refresh}>Refresh preview</Button></div>
      {loading ? <Loading label="Checking linked history" /> : null}
      {preview ? <>
        <Card flush><TableScroll label="Records to permanently erase"><thead><tr><th>Record type</th><th>Count</th></tr></thead>
          <tbody>{preview.counts.map(item => <tr key={item.label}><th scope="row">{item.label}</th><td>{item.count}</td></tr>)}
            <tr><th scope="row">Total records</th><td>{preview.total_records}</td></tr></tbody></TableScroll></Card>
        {preview.transactions.length ? <Card flush><TableScroll label="Sales and reservations to erase">
          <thead><tr><th>Type</th><th>Reference</th><th>Status</th></tr></thead><tbody>{preview.transactions.map((item, index) =>
            <tr key={`${item.kind}-${item.reference}-${index}`}><td>{item.kind}</td><th scope="row">{item.reference}</th><td>{item.status}</td></tr>
          )}</tbody></TableScroll></Card> : null}
        {preview.blockers.length ? <Notice tone="error"><p>Purge is blocked. No records have been deleted.</p><ul>{preview.blockers.map(blocker => <li key={blocker}>{blocker}</li>)}</ul></Notice> :
          <fieldset disabled={busy} className="draft-fields stack">
            <Field label="Reason for permanent purge"><input className="input" required maxLength={500} value={reason} onChange={event => setReason(event.target.value)} /></Field>
            <Field label={`Type ${preview.unit_reference} to confirm`}><input className="input" required autoComplete="off" maxLength={200} value={reference} onChange={event => setReference(event.target.value)} /></Field>
            <label className="checkbox"><input type="checkbox" checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)} /><span>I understand that this unit and the listed linked history will be permanently erased from the database.</span></label>
            <div><Button type="submit" variant="danger" disabled={busy || !acknowledged || reference !== preview.unit_reference || !reason.trim()}>{busy ? "Purging…" : "Permanently purge unit and linked history"}</Button></div>
          </fieldset>}
      </> : null}
    </form>
  </RecordPage>;
}
