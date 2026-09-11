"use client";

import { useRef, useState } from "react";
import { ApiError, sales } from "@/lib/api";
import type { ReservationDetail, SalesPricePreview } from "@/lib/api";
import { Button, DraftBoundary, FormActions, Notice, ValidationSummary } from "@/components/ui";
import { SalesPriceInput } from "./SalesPriceInput";

export function ChangeSalesPrice({projectId, detail, onChanged, unavailable}: {
  unavailable?: string | null;
  projectId: string; detail: ReservationDetail; onChanged: () => Promise<void>;
}) {
  const row = detail.reservation;
  const blocker = unavailable ? "Refresh the transaction before changing its price." : detail.sales_price_edit_blocker;
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState(row.sales_price_ex_tax);
  const [preview, setPreview] = useState<SalesPricePreview | null>(null);
  const [error, setError] = useState<string | ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const saving = useRef(false);
  if (!open) return blocker ? <p className="subtle">{blocker}</p> : <Button onClick={() => {setValue(row.sales_price_ex_tax); setOpen(true);}}>Change sales price</Button>;
  return <DraftBoundary dirty={value !== row.sales_price_ex_tax} busy={busy}><form className="stack" onSubmit={async e => {
    e.preventDefault(); if (saving.current || !preview || blocker) return;
    saving.current = true; setBusy(true); setError(null);
    try { await sales.changeSalesPrice(projectId, row.id, value); setOpen(false); await onChanged(); }
    catch (caught) { setError(caught instanceof ApiError ? caught : "Could not change sales price."); if (caught instanceof ApiError && [403,409].includes(caught.status)) await onChanged(); }
    finally { saving.current = false; setBusy(false); }
  }}>
    <ValidationSummary error={error} />
    {blocker ? <Notice tone="info">{blocker}</Notice> : null}
    <SalesPriceInput projectId={projectId} unitId={row.unit_id} versionId={row.unit_price_version_id} reservationId={row.id} currencyId={row.currency_id} value={value} onChange={v => {setValue(v); setPreview(null);}} onPreview={setPreview} disabled={busy || !!blocker} />
    <FormActions><Button type="submit" variant="primary" disabled={busy || !preview || !!blocker}>Save sales price</Button><Button data-leaves-editor disabled={busy} onClick={() => setOpen(false)}>Cancel</Button></FormActions>
  </form></DraftBoundary>;
}
