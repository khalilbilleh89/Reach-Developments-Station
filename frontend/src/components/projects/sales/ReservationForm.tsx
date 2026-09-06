"use client";

import { useEffect, useState } from "react";
import { ApiError, sales } from "@/lib/api";
import type { SalesClient } from "@/lib/api";
import { Button, Field, FieldRow, FormActions, Loading, MoneyInput, Notice, SubPanel } from "@/components/ui";
import { BuyerForm } from "@/components/projects/sales/BuyerForm";
import { useCurrencyCode } from "@/lib/currency";
import { todayISO } from "@/lib/format";

/** Shared by the unit file and project register; the server quotes and gates. */
export function ReservationForm({ projectId, unitId, currencyId, onCreated, onCancel }: {
  projectId: string; unitId: string; currencyId: string | null;
  onCreated: (reservationId: string) => void; onCancel: () => void;
}) {
  const [buyers, setBuyers] = useState<SalesClient[] | null>(null);
  const [addedBuyer, setAddedBuyer] = useState<SalesClient | null>(null);
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [form, setForm] = useState({ client_id: "", expires_on: "", price_locked_until: "", deposit_required_amount: "", sales_channel_code: "", sales_branch_code: "" });
  const currencyCodeOf = useCurrencyCode();
  useEffect(() => {
    let active = true;
    void sales.clients(projectId, { is_active: "true", ...(search.trim() ? { search: search.trim() } : {}) }).then((rows) => {
      if (active) { setBuyers(rows); setError(null); }
    }).catch((caught) => { if (active) { setBuyers([]); setError(caught instanceof ApiError ? caught.message : "Could not load buyers."); } });
    return () => { active = false; };
  }, [projectId, search]);
  const options = addedBuyer && !buyers?.some((buyer) => buyer.id === addedBuyer.id)
    ? [addedBuyer, ...(buyers ?? [])] : (buyers ?? []);
  if (adding) return <SubPanel title="Add a buyer"><BuyerForm projectId={projectId} onCancel={() => setAdding(false)} onSaved={(buyer) => {
    setAddedBuyer(buyer); setForm({ ...form, client_id: buyer.id }); setAdding(false);
  }} /></SubPanel>;
  return <form onSubmit={async (event) => {
    event.preventDefault(); if (busy) return; setBusy(true); setError(null);
    try {
      const result = await sales.createReservation(projectId, {
        unit_id: unitId, client_id: form.client_id, expires_on: form.expires_on, price_locked_until: form.price_locked_until,
        ...(form.deposit_required_amount ? { deposit_required_amount: form.deposit_required_amount } : {}),
        ...(form.sales_channel_code ? { sales_channel_code: form.sales_channel_code } : {}),
        ...(form.sales_branch_code ? { sales_branch_code: form.sales_branch_code } : {}),
      });
      onCreated(result.reservation.id);
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not prepare the reservation."); }
    finally { setBusy(false); }
  }}>
    <Notice tone="info">Prepare the reservation, then review and activate it to reserve this unit. Saving a draft leaves the unit available.</Notice>
    {error ? <Notice tone="error">{error}</Notice> : null}
    {buyers === null ? <Loading label="Loading buyers…" /> : <>
      <FieldRow columns={2}>
        <Field label="Find buyer"><input className="input" type="search" value={search} onChange={(e) => { setSearch(e.target.value); setAddedBuyer(null); setForm({ ...form, client_id: "" }); }} placeholder="Name or client number" /></Field>
        <Field label="Buyer"><select className="input" required value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })}><option value="">Choose a buyer</option>{options.map((b) => <option key={b.id} value={b.id}>{b.client_number} · {b.display_name}</option>)}</select></Field>
      </FieldRow>
      <Button disabled={busy} onClick={() => setAdding(true)}>Add new buyer</Button>
      <FieldRow columns={3}>
        <Field label="Reservation expires"><input className="input" type="date" required min={todayISO()} value={form.expires_on} onChange={(e) => setForm({ ...form, expires_on: e.target.value })} /></Field>
        <Field label="Price locked until"><input className="input" type="date" required min={todayISO()} value={form.price_locked_until} onChange={(e) => setForm({ ...form, price_locked_until: e.target.value })} /></Field>
        <Field label="Deposit required" optional hint="An activation gate; receipts are recorded in Collections."><MoneyInput code={currencyCodeOf(currencyId)} value={form.deposit_required_amount} onChange={(value) => setForm({ ...form, deposit_required_amount: value })} /></Field>
      </FieldRow>
      <FieldRow columns={2}>
        <Field label="Sales channel" optional><input className="input" value={form.sales_channel_code} onChange={(e) => setForm({ ...form, sales_channel_code: e.target.value })} /></Field>
        <Field label="Sales branch" optional><input className="input" value={form.sales_branch_code} onChange={(e) => setForm({ ...form, sales_branch_code: e.target.value })} /></Field>
      </FieldRow>
    </>}
    <FormActions><Button type="submit" variant="primary" disabled={busy || !form.client_id}>Prepare reservation</Button><Button disabled={busy} onClick={onCancel}>Cancel</Button></FormActions>
  </form>;
}
