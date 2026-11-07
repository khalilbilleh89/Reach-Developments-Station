"use client";
import { ValidationSummary } from "@/components/ui/ValidationSummary";

import { AgentSelect } from "./AgentSelect";
import { useState } from "react";
import { ApiError, sales } from "@/lib/api";
import type { SalesClient } from "@/lib/api";
import { DraftBoundary, Button, Field, FieldRow, FormActions } from "@/components/ui";

export function BuyerForm({ projectId, onSaved, onCancel }: {
  projectId: string;
  onSaved: (buyer: SalesClient) => void;
  onCancel: () => void;
}) {
  const [agentId, setAgentId] = useState("");
  const [form, setForm] = useState({ name: "", email: "", phone: "", client_folder_url: "", odoo_opportunity_url: "", sole: true });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | ApiError | null>(null);
  return (
    <DraftBoundary dirty={Boolean(agentId || form.name || form.email || form.phone || form.client_folder_url || form.odoo_opportunity_url || !form.sole)} busy={busy}><form onSubmit={async (event) => {
      event.preventDefault();
      if (busy) return;
      setBusy(true);
      setError(null);
      try {
        const buyer = await sales.createClient(projectId, {
          agent_id: agentId || null,
          client_folder_url: form.client_folder_url.trim() || null,
          odoo_opportunity_url: form.odoo_opportunity_url.trim() || null,
          display_name: form.name.trim(),
          ...(form.sole ? { sole_purchaser_name: form.name.trim() } : {}),
          ...(form.email.trim() ? { email: form.email.trim() } : {}),
          ...(form.phone.trim() ? { phone: form.phone.trim() } : {}),
        });
        onSaved(buyer);
      } catch (caught) {
        setError(caught instanceof ApiError ? caught : "Could not add the buyer.");
      } finally { setBusy(false); }
    }}>
      <ValidationSummary error={error} />
      <FieldRow columns={3}>
        <Field label="Buyer name" hint="For a sole purchaser, enter the full name as shown on their identification.">
          <input className="input" required maxLength={200} name="display_name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label="Phone" optional><input className="input" type="tel" maxLength={64} name="phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
        <Field label="Email" optional><input className="input" type="email" maxLength={320} name="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
      </FieldRow>
      <FieldRow columns={2}>
        <Field label="Client Folder link" optional hint="Google Drive folder sharing link."><input className="input" type="url" maxLength={2000} name="client_folder_url" value={form.client_folder_url} onChange={e => setForm({...form, client_folder_url: e.target.value})} /></Field>
        <Field label="Opportunity Odoo link" optional hint="HTTPS link to this client's opportunity."><input className="input" type="url" maxLength={2000} name="odoo_opportunity_url" value={form.odoo_opportunity_url} onChange={e => setForm({...form, odoo_opportunity_url: e.target.value})} /></Field>
      </FieldRow>
      <AgentSelect projectId={projectId} value={agentId} onChange={setAgentId} disabled={busy} />
      <label className="checkbox"><input type="checkbox" checked={form.sole} onChange={(e) => setForm({ ...form, sole: e.target.checked })} /><span>This buyer is the sole purchaser (100% ownership).</span></label>
      {!form.sole ? <p className="footnote">Add the joint purchasers and their shares in Buyers before activating the reservation.</p> : null}
      <FormActions><Button type="submit" variant="primary" disabled={busy || !form.name.trim()}>Add buyer</Button><Button disabled={busy} data-leaves-editor onClick={onCancel}>Cancel</Button></FormActions>
    </form></DraftBoundary>
  );
}
