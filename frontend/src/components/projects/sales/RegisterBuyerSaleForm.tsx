"use client";

import { useEffect, useState } from "react";
import { ApiError, pricing, sales } from "@/lib/api";
import type { SalesClient, UnitPricing } from "@/lib/api";
import { useCurrencyCode } from "@/lib/currency";
import { money } from "@/lib/format";
import { Button, DraftBoundary, Field, FieldRow, FormActions, Loading, Notice, RecordLink } from "@/components/ui";

export function RegisterBuyerSaleForm({ projectId, unitId, clientId, onSaved, onCancel }: {
  projectId: string; unitId: string; clientId?: string | null;
  onSaved: (saleId: string) => void; onCancel: () => void;
}) {
  const [buyers, setBuyers] = useState<SalesClient[] | null>(null);
  const [price, setPrice] = useState<UnitPricing | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [form, setForm] = useState({ client: clientId ?? "new", name: "", phone: "", email: "", reason: "", date: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const currency = useCurrencyCode();
  useEffect(() => {
    let cancelled = false;
    void Promise.all([sales.clients(projectId, { is_active: "true" }), pricing.unit(projectId, unitId)])
      .then(([rows, current]) => { if (!cancelled) { setBuyers(rows); setPrice(current); setLoadError(null); } })
      .catch(caught => { if (!cancelled) setLoadError(caught instanceof ApiError ? caught.message : "Could not load buyers and price."); });
    return () => { cancelled = true; };
  }, [projectId, unitId, attempt]);
  if (loadError) return <Notice tone="error">{loadError}<Button onClick={() => setAttempt(value => value + 1)}>Retry</Button></Notice>;
  if (!buyers || !price) return <Loading label="Loading buyers and selling price…" />;
  const needsPrice = !clientId && (!price.active_price || price.repricing_required);
  return <DraftBoundary dirty={Boolean(form.name || form.phone || form.email || form.reason || form.date || form.client !== (clientId ?? "new"))} busy={busy}>
    <form onSubmit={async event => {
      event.preventDefault(); if (busy || needsPrice) return;
      setBusy(true); setError(null);
      try {
        const result = await sales.registerBuyer(projectId, {
          unit_id: unitId, reason: form.reason.trim(), ...(form.date ? { sale_date: form.date } : {}),
          ...(form.client === "new" ? { buyer: { display_name: form.name.trim(), sole_purchaser_name: form.name.trim(),
            ...(form.email.trim() ? { email: form.email.trim() } : {}), ...(form.phone.trim() ? { phone: form.phone.trim() } : {}) } } : { client_id: form.client }),
        });
        onSaved(result.sale.id);
      } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not register the sale."); }
      finally { setBusy(false); }
    }}>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <p>This commits the unit to its buyer and marks it <strong>Sold</strong>. SPA signatures, title registration and payments remain separate records. No receipt or signature is created.</p>
      {needsPrice ? <Notice tone="warning">Enter and activate a selling price first. <RecordLink projectId={projectId} kind="unit" id={unitId} tab="pricing">Open unit pricing</RecordLink></Notice> : <p>{clientId ? "This sale will use the existing reservation’s agreed price." : `Selling price (ex tax): ${money(price.active_price?.reference_price_ex_tax, currency(price.active_price?.currency_id))}`}</p>}
      <Field label="Buyer"><select className="input" value={form.client} disabled={busy || !!clientId} onChange={e => setForm({ ...form, client: e.target.value })}>
        <option value="new">Register a new sole purchaser</option>{buyers.map(buyer => <option key={buyer.id} value={buyer.id}>{buyer.display_name} · {buyer.client_number}</option>)}
      </select></Field>
      {form.client === "new" ? <FieldRow columns={3}>
        <Field label="Full buyer name"><input className="input" required maxLength={200} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></Field>
        <Field label="Phone" optional><input className="input" type="tel" maxLength={64} value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} /></Field>
        <Field label="Email" optional><input className="input" type="email" maxLength={320} value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} /></Field>
      </FieldRow> : <p className="field-hint">Existing buyer parties and ownership shares are preserved. Joint buyers must total 100%.</p>}
      <Field label="Sale date" optional hint="Leave blank for today."><input className="input" type="date" value={form.date} onChange={e => setForm({ ...form, date: e.target.value })} /></Field>
      <Field label="Owner confirmation / reason" hint="Records your decision and any release/deposit approval override in the audit trail."><textarea className="input" required maxLength={500} value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })} /></Field>
      <FormActions><Button variant="primary" type="submit" disabled={busy || needsPrice || !form.reason.trim() || (form.client === "new" && !form.name.trim())}>{busy ? "Registering…" : "Register buyer & mark sold"}</Button><Button disabled={busy} data-leaves-editor onClick={onCancel}>Cancel</Button></FormActions>
    </form>
  </DraftBoundary>;
}
