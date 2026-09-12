"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, sales } from "@/lib/api";
import type { SalesClient, SalesUnitOption, SalesPricePreview } from "@/lib/api";
import { SalesPriceInput } from "./SalesPriceInput";
import { ValidationSummary } from "@/components/ui/ValidationSummary";

import { Button, DraftBoundary, Field, FieldRow, FormActions, Loading, Notice } from "@/components/ui";

export function RegisterBuyerSaleForm({ projectId, unitId, clientId, unitOption, onSaved, onCancel }: {
  projectId: string; unitId: string; clientId?: string | null; unitOption: SalesUnitOption;
  onSaved: (saleId: string) => void; onCancel: () => void;
}) {
  const [buyers, setBuyers] = useState<SalesClient[] | null>(null);
  const [price, setPrice] = useState(unitOption.reference_price_ex_tax);
  const [preview, setPreview] = useState<SalesPricePreview | null>(null);
  const [version, setVersion] = useState(unitOption.unit_price_version_id);
  const [eligibility, setEligibility] = useState<string | null>(null);
  const [freshOption, setFreshOption] = useState<SalesUnitOption | null>(null);
  async function refreshEligibility() {
    setFreshOption(null);
    try {
      const rows = await sales.unitOptions(projectId, {search: unitOption.unit_reference});
      const current = rows.items.find(row => row.unit_id === unitId);
      setFreshOption(current ?? null);
      setEligibility(current ? "Review the current list reference before retrying. Your buyer, agreed price and reason are retained." : "This unit is no longer available. Your draft is retained.");
    } catch { setEligibility("Could not refresh unit eligibility. Your draft is retained."); }
  }
  const saving = useRef(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [form, setForm] = useState({ client: clientId ?? "new", name: "", phone: "", email: "", reason: "", date: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | ApiError | null>(null);

  useEffect(() => {
    let cancelled = false;
    void sales.clients(projectId, { is_active: "true" })
      .then(rows => { if (!cancelled) { setBuyers(rows); setLoadError(null); } })
      .catch(caught => { if (!cancelled) setLoadError(caught instanceof ApiError ? caught.message : "Could not load buyers and price."); });
    return () => { cancelled = true; };
  }, [projectId, unitId, attempt]);
  if (loadError) return <Notice tone="error">{loadError}<Button onClick={() => setAttempt(value => value + 1)}>Retry</Button></Notice>;
  if (!buyers) return <Loading label="Loading buyers and selling price…" />;
  const needsPrice = !preview || !!eligibility;
  return <DraftBoundary dirty={Boolean(price !== unitOption.reference_price_ex_tax || form.name || form.phone || form.email || form.reason || form.date || form.client !== (clientId ?? "new"))} busy={busy}>
    <form onSubmit={async event => {
      event.preventDefault(); if (saving.current || needsPrice) return;
      saving.current = true;
      setBusy(true); setError(null);
      try {
        const result = await sales.registerBuyer(projectId, {
          sales_price_ex_tax: price, expected_price_version_id: version,
          unit_id: unitId, reason: form.reason.trim(), ...(form.date ? { sale_date: form.date } : {}),
          ...(form.client === "new" ? { buyer: { display_name: form.name.trim(), sole_purchaser_name: form.name.trim(),
            ...(form.email.trim() ? { email: form.email.trim() } : {}), ...(form.phone.trim() ? { phone: form.phone.trim() } : {}) } } : { client_id: form.client }),
        });
        onSaved(result.sale.id);
      } catch (caught) {
        setError(caught instanceof ApiError ? caught : "Could not register the sale.");
        if (caught instanceof ApiError && [403, 409].includes(caught.status)) {setPreview(null); await refreshEligibility();}
      }
      finally { saving.current = false; setBusy(false); }
    }}>
      <ValidationSummary error={error} />
      {eligibility ? <Notice tone="info">{eligibility}<Button onClick={() => void refreshEligibility()}>Refresh selected unit</Button>{freshOption ? <Button onClick={() => {setVersion(freshOption.unit_price_version_id); setEligibility(null); setPreview(null);}}>Use current list reference {freshOption.reference_price_ex_tax}</Button> : null}</Notice> : null}
      <p>This commits the unit to its buyer and marks it <strong>Sold</strong>. SPA signatures, title registration and payments remain separate records. No receipt or signature is created.</p>
      <SalesPriceInput projectId={projectId} unitId={unitId} versionId={version} currencyId={unitOption.currency_id} value={price} onChange={v => {setPrice(v); setPreview(null);}} onPreview={setPreview} disabled={busy || !!eligibility} />
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
