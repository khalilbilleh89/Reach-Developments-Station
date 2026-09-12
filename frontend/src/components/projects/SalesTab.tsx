"use client";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError, sales } from "@/lib/api";
import type { SalesTransaction } from "@/lib/api";
import { useRegisterFields, useRegisterRestore } from "@/components/shell/registerState";
import { Badge, Button, Card, EmptyState, Field, Loading, Notice, PageHeader, RecordLink, RegisterPagination, TableScroll } from "@/components/ui";
import { money } from "@/lib/format";
import { useCurrencyCode } from "@/lib/currency";
import { reservationLabel, saleLabel } from "./sales/labels";
import { CommercialUnits } from "./sales/CommercialUnits";
import { ClientsPanel } from "./sales/ClientsPanel";
import { NewReservation } from "./sales/NewReservation";
import { SalesGates } from "./sales/SalesGates";
import { createdSalesHref } from "./sales/salesRoutes";
import { varianceDirection } from "./sales/PriceComparison";

export function SalesTab({projectId, projectStatus, roles}: {
  projectId: string; projectStatus: string; roles: Set<string>; userId: string;
}) {
  const [state, setState] = useRegisterFields({sales_view: "", search: "", transaction_status: "", offset: ""});
  const offsetNumber = Number(state.offset);
  const offset = Number.isSafeInteger(offsetNumber) && offsetNumber >= 0 ? offsetNumber : 0;
  const history = state.sales_view === "history";
  const preparing = state.sales_view === "new";
  const [open, setOpen] = useState<"buyers" | "gates" | "stock" | null>(null);
  const [retry, setRetry] = useState(0);
  const [result, setResult] = useState<{key: string; items: SalesTransaction[]; total: number} | null>(null);
  const [failure, setFailure] = useState<{key: string; message: string} | null>(null);
  const key = JSON.stringify([projectId, history, state.search, state.transaction_status, offset, retry]);
  const codeOf = useCurrencyCode();
  const router = useRouter();
  const params = useSearchParams();
  const canPrepare = roles.has("sales_operations") || roles.has("sales_advisor") || roles.has("master_admin");
  const canAdmin = roles.has("system_admin") || roles.has("master_admin");
  useEffect(() => {
    if (projectStatus === "setup" || preparing) return;
    let active = true;
    const timer = setTimeout(() => {void sales.transactions(projectId, {search: state.search, history: String(history), status: state.transaction_status, offset: String(offset), limit: "50"}).then(rows => {if (active) {setResult({key,...rows}); setFailure(null);}}).catch(e => {if (active) setFailure({key,message:e instanceof ApiError ? e.message : "Could not read Sales transactions."});});}, 150);
    return () => {active = false; clearTimeout(timer);};
  }, [projectId, projectStatus, preparing, history, state.search, state.transaction_status, offset, retry, key]);
  const rows = result?.key === key ? result : null;
  const error = failure?.key === key ? failure.message : null;
  useRegisterRestore(rows !== null && !preparing);
  const refresh = async () => {setRetry(value => value + 1);};
  return <div className="stack">
    <PageHeader icon="sales" title="Sales" subtitle="Buyers, reservations and sale contracts" compact actions={<>
      {canPrepare && projectStatus !== "setup" ? <Button variant="primary" data-leaves-editor onClick={() => {setOpen(null); const next = new URLSearchParams(params); next.set("sales_view", "new"); router.push(`/projects/?${next}`);}}>New Reservation</Button> : null}
      <Button data-leaves-editor onClick={() => {setOpen(null); setState({sales_view: history ? "" : "history", offset:"", transaction_status:""});}}>{history ? "Current transactions" : "Transaction history"}</Button>
      <Button data-leaves-editor onClick={() => {setState({sales_view:""}); setOpen(open === "stock" ? null : "stock");}}>Commercial stock</Button>
      <Button data-leaves-editor onClick={() => {setState({sales_view:""}); setOpen(open === "buyers" ? null : "buyers");}}>Buyers</Button>
      {canAdmin || roles.has("project_manager") ? <Button data-leaves-editor onClick={() => {setState({sales_view:""}); setOpen(open === "gates" ? null : "gates");}}>Sales gates</Button> : null}
    </>} />
    {projectStatus === "setup" ? <Notice tone="info">Sales becomes available when project setup is complete.</Notice> : preparing ? <NewReservation projectId={projectId} allowOwner={roles.has("master_admin")} onSaleCreated={id => {router.replace(createdSalesHref(params,projectId,"sale",id));}} onCancel={() => setState({sales_view:""})} onCreated={id => {router.replace(createdSalesHref(params,projectId,"reservation",id));}} /> : <>
      {open === "stock" ? <CommercialUnits projectId={projectId} roles={roles} onClose={() => setOpen(null)} /> : null}
      {open === "buyers" ? <ClientsPanel projectId={projectId} canWrite={canPrepare} canAdmin={canAdmin} onChanged={refresh} onClose={() => setOpen(null)} /> : null}
      {open === "gates" ? <SalesGates projectId={projectId} onClose={() => setOpen(null)} /> : null}
      <Field label="Find transaction"><input className="input" type="search" placeholder="Buyer, unit, reservation or SPA" value={state.search} onChange={e => setState({search:e.target.value,offset:""})} /></Field>
      <Field label="Transaction status"><select className="input" value={state.transaction_status} onChange={e => setState({transaction_status:e.target.value,offset:""})}><option value="">Any status</option>{["draft","deposit_pending","active","extended","signature_pending","termination_pending",...(history ? ["converted","expired","cancelled"] : [])].map(status => <option key={status} value={status}>{status.replaceAll("_"," ")}</option>)}</select></Field>
      {error ? <Notice tone="error">{error} <Button onClick={() => void refresh()}>Retry Sales transactions</Button></Notice> : !rows ? <Loading label="Loading Sales transactions…" shape="rows" /> : <Card title={history ? "Transaction history" : "Current transactions"} description={`${rows.total} transactions`}>
        {rows.items.length === 0 ? <EmptyState title="No matching transactions" hint="Start a new reservation to select an available unit. Existing transactions can be found by buyer, unit or reference." /> : <TableScroll label="Sales transactions" fixedFirst stickyHeader><thead><tr><th>Transaction / buyer</th><th>Unit</th><th>List price at deal</th><th>Agreed sales price</th><th>Variance</th><th>Status</th><th>SPA</th><th>{history ? "Unit legal · current" : "Legal"}</th><th>{history ? "Unit collections · current" : "Collections"}</th></tr></thead><tbody>{rows.items.map(row => <tr key={`${row.kind}:${row.id}`}>
          <th scope="row" className="sales-primary-cell"><RecordLink projectId={projectId} kind={row.kind} id={row.id}>Open {row.kind === "sale" ? "Sale" : "Reservation"} {row.reference}</RecordLink><span className="cell-secondary">{row.client_display_name}</span></th>
          <td>{row.unit_reference}</td><td>{money(row.reference_price_ex_tax,codeOf(row.currency_id))}</td><td>{money(row.sales_price_ex_tax,codeOf(row.currency_id))}</td>
          <td>{money(row.price_variance_amount,codeOf(row.currency_id))}<span className="cell-secondary">{row.price_variance_fraction === null ? "Percentage unavailable" : row.price_variance_percentage} · {varianceDirection(row.price_variance_amount)}</span></td>
          <td><Badge>{row.kind === "sale" ? saleLabel(row.status) : reservationLabel(row.status)}</Badge></td><td>{row.spa_number ?? "Not prepared"}</td><td>{row.legal_status.replaceAll("_"," ")}</td><td>{row.collection_status.replaceAll("_"," ")}</td>
        </tr>)}</tbody></TableScroll>}
        <RegisterPagination offset={offset} total={rows.total} pageSize={50} onChange={value => setState({offset:String(value)})} />
      </Card>}
    </>}
  </div>;
}
