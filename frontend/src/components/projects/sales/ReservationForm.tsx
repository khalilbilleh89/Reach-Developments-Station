"use client";
import { ValidationSummary } from "@/components/ui/ValidationSummary";

import { useEffect, useRef, useState } from "react";
import { ApiError, sales } from "@/lib/api";
import type { SalesClient, SalesPricePreview, SalesUnitOption } from "@/lib/api";
import { DraftBoundary, Button, Field, FieldRow, FormActions, Loading, MoneyInput, Notice, SubPanel } from "@/components/ui";
import { BuyerForm } from "@/components/projects/sales/BuyerForm";
import { useCurrencyCode } from "@/lib/currency";
import { SalesPriceInput } from "./SalesPriceInput";
import { todayISO } from "@/lib/format";

/** Sales preparation retains buyer/terms when price preview or save fails. */
export function ReservationForm({ projectId, unitId, currencyId, unitOption, onChangeUnit, onCreated, onCancel }: {
  projectId: string; unitId: string; currencyId: string | null;
  unitOption: SalesUnitOption; onChangeUnit: () => void;
  onCreated: (reservationId: string) => void; onCancel: () => void;
}) {
  const saving = useRef(false);
  const [requestId] = useState(() => crypto.randomUUID());
  const [price, setPrice] = useState(unitOption.reference_price_ex_tax);
  const [preview, setPreview] = useState<SalesPricePreview | null>(null);
  const [version, setVersion] = useState(unitOption.unit_price_version_id);
  const [eligibility, setEligibility] = useState<string | null>(null);
  const [freshOption, setFreshOption] = useState<SalesUnitOption | null>(null);
  const [buyerRetry, setBuyerRetry] = useState(0);
  const [buyerError, setBuyerError] = useState<string | null>(null);
  async function refreshEligibility() {
    setFreshOption(null);
    try {
      const rows = await sales.unitOptions(projectId, {search: unitOption.unit_reference});
      const current = rows.items.find(row => row.unit_id === unitId);
      setFreshOption(current ?? null);
      setEligibility(current ? "Review the current list price, then retry saving deliberately. Your agreed price and buyer details are retained." : "This unit is no longer offered for a new reservation. Your draft is retained; choose another unit when ready.");
    } catch { setEligibility("Could not refresh unit eligibility. Your draft is retained."); }
  }
  const [buyers, setBuyers] = useState<SalesClient[] | null>(null);
  const [addedBuyer, setAddedBuyer] = useState<SalesClient | null>(null);
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | ApiError | null>(null);
  const [search, setSearch] = useState("");
  const [form, setForm] = useState({ client_id: "", expires_on: "", price_locked_until: "", deposit_required_amount: "", sales_channel_code: "", sales_branch_code: "" });
  const currencyCodeOf = useCurrencyCode();
  useEffect(() => {
    let active = true;
    void sales.clients(projectId, { is_active: "true", ...(search.trim() ? { search: search.trim() } : {}) }).then((rows) => {
      if (active) { setBuyers(rows); setBuyerError(null); }
    }).catch((caught) => { if (active) { setBuyers([]); setBuyerError(caught instanceof ApiError ? caught.message : "Could not load buyers."); } });
    return () => { active = false; };
  }, [projectId, search, buyerRetry]);
  const options = addedBuyer && !buyers?.some((buyer) => buyer.id === addedBuyer.id)
    ? [addedBuyer, ...(buyers ?? [])] : (buyers ?? []);
  const dirty = price !== unitOption.reference_price_ex_tax || Object.values(form).some(value => value !== "");
  return <DraftBoundary dirty={dirty} busy={busy}>{adding ? <SubPanel title="Add a buyer"><BuyerForm projectId={projectId} onCancel={() => setAdding(false)} onSaved={(buyer) => {
    setAddedBuyer(buyer); setForm({ ...form, client_id: buyer.id }); setAdding(false);
  }} /></SubPanel> : <form onSubmit={async (event) => {
    event.preventDefault(); if (saving.current || !preview || eligibility) return; saving.current = true; setBusy(true); setError(null);
    try {
      const result = await sales.createReservation(projectId, {
        creation_request_id: requestId,
        sales_price_ex_tax: price, expected_price_version_id: version,
        unit_id: unitId, client_id: form.client_id, expires_on: form.expires_on, price_locked_until: form.price_locked_until,
        ...(form.deposit_required_amount ? { deposit_required_amount: form.deposit_required_amount } : {}),
        ...(form.sales_channel_code ? { sales_channel_code: form.sales_channel_code } : {}),
        ...(form.sales_branch_code ? { sales_branch_code: form.sales_branch_code } : {}),
      });
      onCreated(result.reservation.id);
    } catch (caught) { setError(caught instanceof ApiError ? caught : "Could not prepare the reservation."); if (caught instanceof ApiError && [403, 409].includes(caught.status)) { setPreview(null); await refreshEligibility(); } }
    finally { saving.current = false; setBusy(false); }
  }}>
    <Notice tone="info">Prepare the reservation, then review and activate it to reserve this unit. Saving a draft leaves the unit available.</Notice>
    <ValidationSummary error={error} />
    <Button data-leaves-editor disabled={busy} onClick={onChangeUnit}>Change selected unit</Button>
    {eligibility ? <Notice tone="info">{eligibility}<Button onClick={() => void refreshEligibility()}>Refresh selected unit</Button>{freshOption ? <Button onClick={() => {setVersion(freshOption.unit_price_version_id); setEligibility(null); setPreview(null);}}>Use current list reference {freshOption.reference_price_ex_tax}</Button> : null}</Notice> : null}
    <SalesPriceInput projectId={projectId} unitId={unitId} versionId={version} currencyId={currencyId ?? unitOption.currency_id} value={price} onChange={value => {setPrice(value); setPreview(null);}} onPreview={setPreview} disabled={busy || !!eligibility} />
    {buyerError ? <Notice tone="error">{buyerError} <Button onClick={() => setBuyerRetry(buyerRetry + 1)}>Retry buyers</Button></Notice> : null}
    {buyers === null ? <Loading label="Loading buyers…" /> : <>
      <FieldRow columns={2}>
        <Field label="Find buyer"><input className="input" type="search" value={search} onChange={(e) => { setSearch(e.target.value); setAddedBuyer(null); setForm({ ...form, client_id: "" }); }} placeholder="Name or client number" /></Field>
        <Field label="Buyer"><select className="input" required name="client_id" value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })}><option value="">Choose a buyer</option>{options.map((b) => <option key={b.id} value={b.id}>{b.client_number} · {b.display_name}</option>)}</select></Field>
      </FieldRow>
      <Button disabled={busy} onClick={() => setAdding(true)}>Add new buyer</Button>
      <FieldRow columns={3}>
        <Field label="Reservation expires"><input className="input" type="date" required min={todayISO()} name="expires_on" value={form.expires_on} onChange={(e) => setForm({ ...form, expires_on: e.target.value })} /></Field>
        <Field label="Price locked until"><input className="input" type="date" required min={todayISO()} name="price_locked_until" value={form.price_locked_until} onChange={(e) => setForm({ ...form, price_locked_until: e.target.value })} /></Field>
        <Field label="Deposit required" optional hint="An activation gate; receipts are recorded in Collections."><MoneyInput code={currencyCodeOf(currencyId)} name="deposit_required_amount" value={form.deposit_required_amount} onChange={(value) => setForm({ ...form, deposit_required_amount: value })} /></Field>
      </FieldRow>
      <FieldRow columns={2}>
        <Field label="Sales channel" optional><input className="input" name="sales_channel_code" value={form.sales_channel_code} onChange={(e) => setForm({ ...form, sales_channel_code: e.target.value })} /></Field>
        <Field label="Sales branch" optional><input className="input" name="sales_branch_code" value={form.sales_branch_code} onChange={(e) => setForm({ ...form, sales_branch_code: e.target.value })} /></Field>
      </FieldRow>
    </>}
    <FormActions><Button type="submit" variant="primary" disabled={busy || !form.client_id || !preview || !!eligibility}>Prepare reservation</Button><Button disabled={busy} data-leaves-editor onClick={onCancel}>Cancel</Button></FormActions>
  </form>}</DraftBoundary>;
}
