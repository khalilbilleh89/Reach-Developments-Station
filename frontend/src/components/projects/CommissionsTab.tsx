"use client";

import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ApiError, commissions, sales } from "@/lib/api";
import type { CommissionEligibleSale, CommissionGrant, CommissionAllocation, SalesAgent } from "@/lib/api";
import { money, percent, percentInput, fractionFromPercent } from "@/lib/format";
import { COMMISSION_PREPARERS, COMMISSION_RELEASERS, hasAnyRole } from "@/lib/roles";
import type { Roles } from "@/lib/roles";
import { sectionDescription } from "@/components/shell/navigation";
import { Badge, Button, ButtonRow, Card, RecordPage, EmptyState, Field, FieldRow, FormDialog, IdentityCell, Loading, MoneyInput, Notice, PageHeader, PromptDialog, RateInput, SectionHeader, TableScroll } from "@/components/ui";

export function CommissionsTab({ projectId, roles, userId, currencyCodes }: { projectId: string; roles: Roles; userId: string; currencyCodes: Record<string, string> }) {
  const [rows, setRows] = useState<CommissionGrant[]>([]); const [eligible, setEligible] = useState<CommissionEligibleSale[]>([]); const params = useSearchParams(); const router = useRouter();
  const selectedId = params.get("commission");
  const selected = rows.find(row => row.id === selectedId) ?? null;
  const commissionHref = (id: string | null) => { const next = new URLSearchParams(params); if (id) next.set("commission", id); else next.delete("commission"); return `/projects/?${next}`; }; const [dialog, setDialog] = useState<"grant" | "edit" | "allocation" | "reverse" | null>(null); const [allocation, setAllocation] = useState<CommissionAllocation | null>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const canPrepare = hasAnyRole(roles, COMMISSION_PREPARERS); const canRelease = hasAnyRole(roles, COMMISSION_RELEASERS);
  const [agents, setAgents] = useState<SalesAgent[]>([]);
  const [agentError, setAgentError] = useState<string | null>(null);
  useEffect(() => {
    if (!canPrepare) return;
    let current = true;
    void sales.agents(projectId, { active_only: "true" }).then((result) => {
      if (current) { setAgents(result); setAgentError(null); }
    }).catch(() => { if (current) setAgentError("Agent roster could not be loaded. Retry by reopening Commissions."); });
    return () => { current = false; };
  }, [canPrepare, projectId]);
  const load = useCallback(async () => { try { const [grants, sales] = await Promise.all([commissions.list(projectId), commissions.eligibleSales(projectId)]); setRows(grants); setEligible(sales);  setLoaded(true); setError(null); } catch (e) { setError(e instanceof ApiError ? e.message : "Could not load commissions."); } }, [projectId]);
  useEffect(() => { void (async () => { await load(); })(); }, [load]); const run = async (fn: () => Promise<unknown>) => { setBusy(true); setError(null); try { await fn(); setDialog(null); setAllocation(null); await load(); } catch (e) { setError(e instanceof ApiError ? e.message : "That action could not be completed."); } finally { setBusy(false); } };
  return <div className="stack">
    <PageHeader icon="money" title="Commissions" subtitle={sectionDescription("commissions")} actions={canPrepare && eligible.length ? <Button variant="primary" onClick={() => setDialog("grant")}>Prepare commission</Button> : undefined} />
    {error && !dialog && !selected ? <Notice tone="error">{error}</Notice> : null}
    <Card title="Commission register" description="Open a sale's commission to review its grant and beneficiary distribution." flush>
      {!loaded ? !error ? <Loading label="Loading commissions" shape="rows" /> : null : rows.length ? (
        <TableScroll label="Commission register" fixedFirst>
          <thead><tr><th scope="col">Unit / sale</th><th scope="col">Buyer</th><th scope="col" className="num">Sold price</th><th scope="col" className="num">Commission base</th><th scope="col" className="num">Granted</th><th scope="col" className="num">Commission total</th><th scope="col">Status</th></tr></thead>
          <tbody>{rows.map((x) => <tr key={x.id} aria-selected={selected?.id === x.id}>
            <th scope="row"><Link className="button-link" href={commissionHref(x.id)} scroll={false} aria-label={`Open ${x.unit_reference} commission`}><IdentityCell icon="inventory" name={x.unit_reference} meta={x.sale_reference} /></Link></th>
            <td>{x.buyer_display}</td>
            <td className="num">{money(x.sold_price_snapshot, currencyCodes[x.currency_id])}</td>
            <td className="num">{money(x.commissionable_base_amount, currencyCodes[x.currency_id])}</td>
            <td className="num">{percent(x.granted_rate_fraction)}</td>
            <td className="num">{money(x.commission_total, currencyCodes[x.currency_id])}</td>
            <td><Badge>{x.status}</Badge></td>
          </tr>)}</tbody>
        </TableScroll>
      ) : <div className="card-body"><EmptyState title="No commission grants" hint="Commission grants are prepared against active sold contracts." /></div>}
      <p className="table-foot">Beneficiary percentages apply directly to the commissionable base. Releasing this distribution does not change Unit Economics, the sale price, or project cash.</p>
    </Card>
    {loaded && selectedId && !selected ? <Notice tone="error">This commission is unavailable. It may no longer be in your accessible register.</Notice> : null}
    {selected ? <RecordPage
      eyebrow="Commission file"
      icon="money"
      title={`${selected.unit_reference} commission`}
      subtitle={`${selected.sale_reference} · ${selected.buyer_display}`}
      meta={<Badge>{selected.status}</Badge>}
      headline={{ value: money(selected.commission_total, currencyCodes[selected.currency_id]), label: "Granted commission" }}
      facts={[
        { label: "Commissionable base", value: money(selected.commissionable_base_amount, currencyCodes[selected.currency_id]) },
        { label: "Granted rate", value: percent(selected.granted_rate_fraction) },
        { label: "Distributed rate", value: percent(selected.allocation_rate_total) },
        { label: "Distributed amount", value: money(selected.allocation_amount_total, currencyCodes[selected.currency_id]) },
      ]}
      onClose={() => { if (!busy) router.push(commissionHref(null), {scroll: false}); }}
      actions={<ButtonRow>
        {canPrepare && selected.status === "draft" ? <Button disabled={busy} onClick={() => setDialog("edit")}>Edit Commission</Button> : null}
        {canRelease && selected.status === "draft" && selected.is_reconciled && selected.prepared_by_user_id !== userId ? <Button variant="primary" disabled={busy} onClick={() => void run(() => commissions.release(projectId, selected.id))}>Release</Button> : null}
        {canRelease && selected.status === "released" ? <Button variant="danger" disabled={busy} onClick={() => setDialog("reverse")}>Reverse commission</Button> : null}
      </ButtonRow>}
    >
      {error && !dialog ? <Notice tone="error">{error}</Notice> : null}
      <section>
        <SectionHeader title="Sale information" />
        <dl className="stack">
          <div><dt>Unit</dt><dd>{selected.unit_reference}</dd></div>
          <div><dt>Sale</dt><dd>{selected.sale_reference}</dd></div>
          <div><dt>Buyer</dt><dd>{selected.buyer_display}</dd></div>
          <div><dt>Sale agent</dt><dd>{selected.sale_agent_name ?? "Not recorded"}{selected.sale_agent_name && !selected.sale_agent_id ? " (legacy attribution)" : ""}</dd></div>
          <div><dt>Sale branch</dt><dd>{selected.sale_agent_branch ?? "Not recorded"}</dd></div>
        </dl>
      </section>
      <section>
        <SectionHeader title="Beneficiary distribution" actions={canPrepare && selected.status === "draft" ? <Button onClick={() => { setAllocation(null); setDialog("allocation"); }}>Add beneficiary</Button> : undefined} />
        {agentError && canPrepare ? <Notice tone="error">{agentError}</Notice> : null}
        <p className="footnote">Each beneficiary rate applies to the commissionable base. Released distributions remain read only.</p>
        {selected.allocations.length ? <TableScroll label="Beneficiary distribution" fixedFirst compact>
          <thead><tr><th scope="col">Type</th><th scope="col">Beneficiary</th><th scope="col">Branch</th><th scope="col" className="num">Rate against base</th><th scope="col" className="num">Calculated amount</th><th scope="col">Actions</th></tr></thead>
          <tbody>{selected.allocations.map((a) => <tr key={a.id}>
            <th scope="row">{a.beneficiary_type === "legacy" ? "Legacy" : a.beneficiary_type === "agent" ? "Agent" : a.beneficiary_type === "branch" ? "Branch" : "Other"}</th>
            <td>{a.beneficiary_name ?? "Other beneficiary"}</td>
            <td>{a.beneficiary_branch_snapshot ?? "—"}</td>
            <td className="num">{percent(a.rate_fraction)}</td>
            <td className="num">{money(a.calculated_amount, currencyCodes[selected.currency_id])}</td>
            <td>{canPrepare && selected.status === "draft" ? <ButtonRow>
              <Button small variant="quiet" disabled={busy} onClick={() => { setAllocation(a); setDialog("allocation"); }}>Edit Beneficiary</Button>
              <Button small variant="danger" disabled={busy} onClick={() => void run(() => commissions.removeAllocation(projectId, selected.id, a.id))}>Remove Beneficiary</Button>
            </ButtonRow> : "Read only"}</td>
          </tr>)}</tbody>
        </TableScroll> : <EmptyState compact title="No beneficiaries assigned" hint="The distribution records each beneficiary's percentage against the base." />}
      </section>
    </RecordPage> : null}
    {dialog === "grant" ? <GrantDialog busy={busy} error={error} sales={eligible} codes={currencyCodes} onCancel={() => setDialog(null)} onSubmit={(body) => void run(() => commissions.create(projectId, body))} /> : null}
    {dialog === "edit" && selected ? <EditCommissionDialog grant={selected} code={currencyCodes[selected.currency_id]} busy={busy} error={error} onCancel={() => setDialog(null)} onSubmit={(body) => void run(() => commissions.update(projectId, selected.id, body))} /> : null}
    {dialog === "allocation" && selected ? <AllocationDialog allocation={allocation} sale={selected} agents={agents} agentError={agentError} busy={busy} error={error} onCancel={() => setDialog(null)} onSubmit={(body) => void run(() => allocation ? commissions.updateAllocation(projectId, selected.id, allocation.id, { ...body, expected_updated_at: allocation.updated_at }) : commissions.addAllocation(projectId, selected.id, body))} /> : null}
    {dialog === "reverse" && selected ? <PromptDialog busy={busy} error={error} title="Reverse commission" label="Reason" hint="This preserves the released record and does not change the sale price, Unit Economics or confirmed project cash." confirmLabel="Reverse" onCancel={() => { if (!busy) setDialog(null); }} onSubmit={(reason) => void run(() => commissions.reverse(projectId, selected.id, reason))} /> : null}
  </div>;
}
function GrantDialog({ busy, error, sales, codes, onCancel, onSubmit }: { busy: boolean; error: string | null; sales: CommissionEligibleSale[]; codes: Record<string, string>; onCancel: () => void; onSubmit: (body: Record<string, unknown>) => void }) { const [sale, setSale] = useState(sales[0]?.id ?? ""); const chosen = sales.find((x) => x.id === sale); const [base, setBase] = useState(""); const [rate, setRate] = useState(""); return <FormDialog busy={busy} title="Prepare commission" confirmLabel="Save draft" disabled={!sale || !base || !rate} onCancel={onCancel} onSubmit={() => onSubmit({ sale_contract_id: sale, commissionable_base_amount: base, granted_rate_fraction: fractionFromPercent(rate) })}>{error ? <Notice tone="error">{error}</Notice> : null}<Field label="Sold contract"><select className="input" value={sale} onChange={(e) => setSale(e.target.value)}>{sales.map((x) => <option key={x.id} value={x.id}>{x.unit_reference} · {x.buyer_display} · {money(x.sold_price, codes[x.currency_id])}</option>)}</select></Field>{chosen ? <p>Sale agent: {chosen.sale_agent_name ?? "Not recorded"}{chosen.sale_agent_name && !chosen.sale_agent_id ? " (legacy attribution)" : ""}<br />Sale branch: {chosen.sale_agent_branch ?? "Not recorded"}</p> : null}<FieldRow><Field label="Commissionable base"><MoneyInput code={chosen ? codes[chosen.currency_id] : null} value={base} onChange={setBase} /></Field><Field label="Granted commission percentage"><RateInput value={rate} onChange={setRate} /></Field></FieldRow></FormDialog>; }
function AllocationDialog({ allocation, sale, agents, agentError, busy, error, onCancel, onSubmit }: { allocation: CommissionAllocation | null; sale: CommissionGrant; agents: SalesAgent[]; agentError: string | null; busy: boolean; error: string | null; onCancel: () => void; onSubmit: (body: Record<string, unknown>) => void }) {
  const [beneficiaryType, setBeneficiaryType] = useState<"agent" | "branch" | "other">(allocation?.beneficiary_type === "legacy" ? "other" : allocation?.beneficiary_type ?? "agent");
  const [agentId, setAgentId] = useState(allocation?.sales_agent_id ?? (agents.some((agent) => agent.id === sale.sale_agent_id) ? sale.sale_agent_id ?? "" : ""));
  const [name, setName] = useState(allocation?.beneficiary_name ?? "");
  const [rate, setRate] = useState(percentInput(allocation?.rate_fraction));
  const [notes, setNotes] = useState(allocation?.notes ?? "");
  const options = allocation?.beneficiary_type === "agent" && allocation.sales_agent_id && !agents.some((agent) => agent.id === allocation.sales_agent_id)
    ? [{ id: allocation.sales_agent_id, display_name: allocation.beneficiary_name ?? "Retained Agent", branch: allocation.beneficiary_branch_snapshot, is_active: false }, ...agents]
    : agents;
  const disabled = !rate || (beneficiaryType === "agent" && (!agentId || Boolean(agentError))) || (beneficiaryType === "branch" && !sale.sale_agent_branch);
  return <FormDialog title={allocation ? "Edit Beneficiary" : "Add beneficiary"} busy={busy} description="The percentage applies directly to the commissionable base." confirmLabel="Save beneficiary" disabled={disabled} onCancel={onCancel} onSubmit={() => onSubmit({ beneficiary_type: beneficiaryType, ...(beneficiaryType === "agent" ? { sales_agent_id: agentId } : beneficiaryType === "other" ? { beneficiary_name: name.trim() || null } : {}), rate_fraction: fractionFromPercent(rate), notes: notes || null })}>
    {error ? <Notice tone="error">{error}</Notice> : null}
    <Field label="Beneficiary type"><select className="input" value={beneficiaryType} onChange={(event) => setBeneficiaryType(event.target.value as "agent" | "branch" | "other")}><option value="agent">Agent</option><option value="branch">Branch</option><option value="other">Other</option></select></Field>
    {beneficiaryType === "agent" ? <Field label="Agent"><select className="input" value={agentId} onChange={(event) => setAgentId(event.target.value)}><option value="">Select registered Agent</option>{options.map((agent) => <option key={agent.id} value={agent.id}>{agent.display_name}{agent.branch ? ` — ${agent.branch}` : ""}{!agent.is_active ? " (inactive; existing allocation only)" : ""}</option>)}</select></Field> : null}
    {beneficiaryType === "branch" ? <p>Sale branch: {sale.sale_agent_branch ?? "No branch is recorded on this Sale. Correct the Sale attribution first."}</p> : null}
    {beneficiaryType === "other" ? <Field label="Beneficiary name" optional><input className="input" value={name} onChange={(event) => setName(event.target.value)} /></Field> : null}
    <Field label="Beneficiary percentage against base"><RateInput value={rate} onChange={setRate} /></Field>
    <Field label="Notes" optional><textarea className="input" value={notes} onChange={(event) => setNotes(event.target.value)} /></Field>
  </FormDialog>;
}
function EditCommissionDialog({ grant, code, busy, error, onCancel, onSubmit }: { grant: CommissionGrant; code: string; busy: boolean; error: string | null; onCancel: () => void; onSubmit: (body: Record<string, unknown>) => void }) {
  const [base, setBase] = useState(grant.commissionable_base_amount);
  const [rate, setRate] = useState(percentInput(grant.granted_rate_fraction));
  const [notes, setNotes] = useState(grant.notes ?? "");
  return <FormDialog title="Edit Commission" busy={busy} confirmLabel="Save draft" onCancel={onCancel} onSubmit={() => onSubmit({ commissionable_base_amount: base, granted_rate_fraction: fractionFromPercent(rate), notes: notes || null, expected_updated_at: grant.updated_at })}>
    {error ? <Notice tone="error">{error}</Notice> : null}
    <Field label="Commissionable base"><MoneyInput code={code} value={base} onChange={setBase} /></Field>
    <Field label="Granted commission percentage"><RateInput value={rate} onChange={setRate} /></Field>
    <Field label="Notes" optional><textarea className="input" value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
  </FormDialog>;
}
