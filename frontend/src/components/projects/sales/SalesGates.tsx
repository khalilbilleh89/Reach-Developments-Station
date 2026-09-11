"use client";
import { useEffect, useState } from "react";
import { ApiError, sales } from "@/lib/api";
import type { SalesPolicy } from "@/lib/api";
import { Button, Card, DraftBoundary, FormActions, Loading, Notice } from "@/components/ui";
const fields: {name: keyof SalesPolicy; label: string}[] = [
  {name: "reservation_requires_deposit_confirmation", label: "Reservation requires deposit evidence"},
  {name: "handover_requires_legal_clearance", label: "Handover requires legal clearance"},
  {name: "handover_requires_collection_clearance", label: "Handover requires collections clearance"},
  {name: "handover_requires_delivery_clearance", label: "Handover requires delivery clearance"},
  {name: "handover_requires_title_transfer", label: "Handover requires title transfer"},
  {name: "title_transfer_requires_collection_clearance", label: "Title transfer requires collections clearance"},
];
export function SalesGates({projectId, onClose}: {projectId: string; onClose: () => void}) {
  const [form, setForm] = useState<SalesPolicy | null>(null);
  const [saved, setSaved] = useState<SalesPolicy | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {let active = true; void sales.policy(projectId).then(row => {if (active) {setForm(row); setSaved(row); setError(null);}}).catch(e => {if (active) setError(e instanceof ApiError ? e.message : "Could not read Sales gates.");}); return () => {active = false;};}, [projectId,retry]);
  return <DraftBoundary dirty={JSON.stringify(form) !== JSON.stringify(saved)} busy={busy}><Card title="Sales gates" actions={<Button data-leaves-editor disabled={busy} onClick={onClose}>Close</Button>}>
    {error ? <Notice tone="error">{error}{!form ? <Button onClick={() => setRetry(retry + 1)}>Retry Sales gates</Button> : null}</Notice> : null}
    {!form ? <Loading label="Loading Sales gates…" /> : <form onSubmit={async e => {e.preventDefault(); if (busy) return; setBusy(true); try {const row = await sales.writePolicy(projectId, form as unknown as Record<string,unknown>); setForm(row); setSaved(row); setError(null);} catch (e) {setError(e instanceof ApiError ? e.message : "Could not save Sales gates.");} finally {setBusy(false);}}}>
      <div className="checkbox-grid">{fields.map(field => <label className="checkbox" key={field.name}><input type="checkbox" disabled={busy} checked={Boolean(form[field.name])} onChange={e => setForm({...form, [field.name]: e.target.checked})} /><span>{field.label}</span></label>)}</div>
      <FormActions><Button type="submit" variant="primary" disabled={busy}>Save gates</Button></FormActions>
    </form>}
  </Card></DraftBoundary>;
}
