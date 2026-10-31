"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRegisterFields } from "@/components/shell/registerState";
import { ContractHeaderEditor } from "./construction/ContractWorkflow";
import { CONSTRUCTION_READERS, ECONOMICS_READERS, TECHNICAL_WRITERS, hasAnyRole } from "@/lib/roles";

import {
  Badge,
  Button,
  Card,
  DataToolbar,
  EmptyState,
  IdentityCell,
  InlineEdit,
  Loading,
  Notice,
  PageHeader,
  SortHeader,
  Tabs,
  TabPanel,
  TableScroll,
  ToolbarFilter,
  useSort,
} from "@/components/ui";
import { ApiError, construction } from "@/lib/api";
import type {
  Certificate,
  ConstructionContract,
  ConstructionInvoice,
  ConstructionMilestone,
  ConstructionPayment,
  ConstructionSummary,
  ForecastDetail,
  Variation,
} from "@/lib/api";
import { businessDate, money } from "@/lib/format";
import { sectionDescription } from "@/components/shell/navigation";

import { CertificateFile } from "@/components/projects/construction/CertificateFile";
import { ConstructionSummaryView } from "@/components/projects/construction/ConstructionSummaryView";
import { ContractFile } from "@/components/projects/construction/ContractFile";
import {
  certificateLabel,
  certificateTone,
  contractLabel,
  contractTone,
  forecastLabel,
  forecastTone,
  invoiceLabel,
  invoiceTone,
  milestoneLabel,
  milestoneTone,
  paymentLabel,
  paymentTone,
  variationLabel,
  variationTone,
} from "@/components/projects/construction/labels";

/** Denomination belongs to the contract, never an assumed project currency. */
function contractCurrency(contracts: ConstructionContract[], contractId: string | undefined): string {
  return contracts.find((contract) => contract.id === contractId)?.currency_code ?? "Currency unavailable";
}

import { CurrentCostAnalysis } from "./economics/CurrentCostAnalysis";

/*
 * What each register column sorts by. Every value is one the server returned —
 * a reference, a name, an ISO date, a decimal amount or a status label — and
 * is only compared for ordering, never combined.
 */
type SortValue = string | number | null;

function readContractColumn(row: ConstructionContract, column: string): SortValue {
  switch (column) {
    case "contract": return row.contract_number;
    case "vendor": return row.vendor_name;
    case "original": return row.original_contract_value_ex_tax;
    case "variations": return row.approved_variation_delta;
    // An uncommitted contract shows no commitment, so it sorts with the absent values.
    case "revised": return ["draft", "submitted", "cancelled"].includes(row.status) ? null : row.revised_commitment;
    case "certified": return row.certified_to_date;
    case "status": return contractLabel(row.status);
    default: return null;
  }
}

function readVariationColumn(row: Variation, column: string): SortValue {
  switch (column) {
    case "variation": return row.variation_number;
    case "contract": return row.contract_number;
    case "requested": return row.requested_date;
    case "value": return row.total_value_ex_tax;
    case "status": return variationLabel(row.status);
    default: return null;
  }
}

function readCertificateColumn(row: Certificate, column: string): SortValue {
  switch (column) {
    case "certificate": return row.certificate_number;
    case "contract": return row.contract_number;
    case "work": return row.current_work_value_ex_tax;
    case "retention": return row.retention_held_amount;
    case "net": return row.net_due;
    case "status": return certificateLabel(row.status);
    default: return null;
  }
}

function readInvoiceColumn(row: ConstructionInvoice, column: string): SortValue {
  switch (column) {
    case "invoice": return row.invoice_number;
    case "contract": return row.contract_number;
    case "type": return row.invoice_type;
    case "dated": return row.invoice_date;
    case "payable": return row.net_payable;
    case "outstanding": return row.outstanding;
    case "status": return invoiceLabel(row.status);
    default: return null;
  }
}

function readPaymentColumn(row: ConstructionPayment, column: string): SortValue {
  switch (column) {
    case "reference": return row.payment_reference;
    case "contract": return row.contract_number;
    case "dated": return row.payment_date;
    case "amount": return row.amount;
    case "unallocated": return row.unallocated;
    case "status": return paymentLabel(row.status);
    default: return null;
  }
}

function readMilestoneColumn(row: ConstructionMilestone, column: string): SortValue {
  switch (column) {
    case "milestone": return row.code;
    case "scope": return row.scope_label ?? "Whole project";
    case "planned": return row.planned_date;
    case "forecast": return row.forecast_date;
    case "reported": return row.actual_achieved_date;
    case "certified": return row.certified_date;
    case "delay": return row.delay_days;
    case "status": return milestoneLabel(row.status);
    default: return null;
  }
}

// Stable stand-ins while a register is still loading, so the sort hooks run unconditionally.
const NO_INVOICES: ConstructionInvoice[] = [];
const NO_PAYMENTS: ConstructionPayment[] = [];
const NO_MILESTONES: ConstructionMilestone[] = [];

const SECTIONS = [
  { key: "overview", label: "Overview" },
  { key: "unit-costs", label: "Unit cost analysis" },
  { key: "contracts", label: "Contracts" },
  { key: "variations", label: "Variations & reductions" },
  { key: "certificates", label: "Certificates" },
  { key: "cash", label: "Invoices & Payments" },
  { key: "milestones", label: "Milestones" },
  { key: "forecast", label: "Forecast" },
];

/** Contract-first costing. All financial totals arrive from the server. */
export function ConstructionTab({ projectId, roles = new Set<string>(), currencyId = "", currencyCode = null }: { projectId: string; roles?: Set<string>; currencyId?: string; currencyCode?: string | null }) {
  const canReadCosts = hasAnyRole(roles, CONSTRUCTION_READERS);
  const sections = canReadCosts ? SECTIONS.filter(item => item.key !== "unit-costs" || hasAnyRole(roles, ECONOMICS_READERS)) : [];
  const [view, setView] = useRegisterFields({ constructionTab: "contracts" });
  const section = sections.some(item => item.key === view.constructionTab) ? view.constructionTab : "contracts";
  const setSection = (constructionTab: string) => setView({ constructionTab });
  const [summary, setSummary] = useState<ConstructionSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [retrying, setRetrying] = useState(false);
  const load = useCallback(async () => {
    if (!canReadCosts) return;
    setRetrying(true);
    try {
      setSummary(await construction.summary(projectId));
      setError(null);
    } catch (caught) {
      setSummary(null);
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not load the construction position.",
      );
    } finally {
      setRetrying(false);
    }
  }, [projectId, canReadCosts]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  if (!canReadCosts) return <Notice tone="info">Construction costs are not available to your role. Open Technical Specifications under Delivery.</Notice>;

  return (
    <div className="stack">
      <PageHeader
        icon="building"
        title="Construction"
        subtitle={canReadCosts ? sectionDescription("construction") : "What the project and its units will include."}
        meta={
          canReadCosts && summary ? (
            <>
              <Badge
                tone={
                  summary.controls.has_active_forecast ? "success" : "neutral"
                }
              >
                {summary.controls.has_active_forecast
                  ? `Forecast v${summary.forecast_version_number}`
                  : "No forecast in force"}
              </Badge>
            </>
          ) : undefined
        }
      />

      {canReadCosts && error ? <><Notice tone="error">{error}</Notice><Button disabled={retrying} onClick={() => void load()}>{retrying ? "Retrying…" : "Retry construction position"}</Button></> : null}

      <Tabs
        label="Construction sections"
        tabs={sections}
        active={section}
        onSelect={setSection}
        group="construction"
      />

      <TabPanel group="construction" tab={section}>
      {section === "unit-costs" ? <CurrentCostAnalysis key={projectId} projectId={projectId} roles={roles} /> : null}
      {section === "overview" ? (
        summary ? (
          <ConstructionSummaryView summary={summary} />
        ) : error ? null : (
          <Loading label="Loading the construction position" shape="metrics" />
        )
      ) : null}
      {section === "contracts" ? (
        <ContractsSection projectId={projectId} roles={roles} currencyId={currencyId} currencyCode={currencyCode} onChanged={load} />
      ) : null}
      {section === "variations" ? (
        <VariationsSection projectId={projectId} />
      ) : null}
      {section === "certificates" ? (
        <CertificatesSection projectId={projectId} />
      ) : null}
      {section === "cash" ? <CashSection projectId={projectId} /> : null}
      {section === "milestones" ? (
        <MilestonesSection projectId={projectId} roles={roles} />
      ) : null}
      {section === "forecast" ? (
        <ForecastSection projectId={projectId} />
      ) : null}
      </TabPanel>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Contracts
// --------------------------------------------------------------------------- //

function ContractsSection({ projectId, roles = new Set<string>(), currencyId = "", currencyCode = null, onChanged = async () => {} }: { projectId: string; roles?: Set<string>; currencyId?: string; currencyCode?: string | null; onChanged?: () => Promise<void> }) {
  const [rows, setRows] = useState<ConstructionContract[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useRegisterFields({ contractSearch: "", contractStatus: "", constructionContract: "", contractTab: "position" });
  const search = view.contractSearch; const status = view.contractStatus; const open = view.constructionContract;
  const setSearch = (contractSearch: string) => setView({ contractSearch });
  const setStatus = (contractStatus: string) => setView({ contractStatus });
  const setOpen = (constructionContract: string | null) => setView({ constructionContract: constructionContract ?? "", contractTab: "position" });
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [writeError, setWriteError] = useState<Error | null>(null);
  async function create(body: Record<string, unknown>) {
    if (saving) return;
    setSaving(true); setWriteError(null);
    try {
      const created = await construction.createContract(projectId, body);
      setCreating(false); setOpen(created.id); await load(); void onChanged();
    } catch (caught) { setWriteError(caught instanceof Error ? caught : new Error("Could not create contract.")); }
    finally { setSaving(false); }
  }


  const [retrying, setRetrying] = useState(false);
  const load = useCallback(async () => {
    setRetrying(true);
    try {
      setRows(await construction.contracts(projectId));
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not load the contracts.",
      );
    } finally {
      setRetrying(false);
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const shown = useMemo(() => {
    if (!rows) return [];
    const needle = search.trim().toLowerCase();
    return rows.filter((row) => {
      if (status && row.status !== status) return false;
      if (!needle) return true;
      return (
        row.contract_number.toLowerCase().includes(needle) ||
        row.vendor_name.toLowerCase().includes(needle)
      );
    });
  }, [rows, search, status]);
  const { sort, toggle, sorted } = useSort(shown, readContractColumn);

  if (error) return <><Notice tone="error">{error}</Notice><Button disabled={retrying} onClick={() => void load()}>{retrying ? "Retrying…" : "Retry"}</Button></>;
  if (!rows) return <Loading label="Loading the contracts" shape="rows" />;

  return (
    <div className="stack stack-tight">
      {hasAnyRole(roles, new Set(["finance", "project_manager"])) ? <Button variant="primary" disabled={!currencyId} onClick={() => { setWriteError(null); setCreating(true); }}>Add signed contract</Button> : null}
      {creating ? <ContractHeaderEditor currencyId={currencyId} currencyCode={currencyCode} busy={saving} failure={writeError} onSubmit={body => void create(body)} onCancel={() => setCreating(false)} /> : null}
      <DataToolbar
        framed
        search={{
          value: search,
          onChange: setSearch,
          placeholder: "Contract or vendor",
        }}
        count={{ shown: shown.length, total: rows.length, noun: "contract" }}
        onReset={
          search || status
            ? () => {
                setSearch("");
                setStatus("");
              }
            : undefined
        }
      >
        <ToolbarFilter label="Status" active={status !== ""}>
          <select
            className="input"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">Any status</option>
            <option value="draft">Draft</option>
            <option value="submitted">Awaiting authorisation</option>
            <option value="active">Live</option>
            <option value="completed">Completed</option>
            <option value="terminated">Terminated</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </ToolbarFilter>
      </DataToolbar>

      {shown.length === 0 ? (
        <EmptyState
          title="No contracts"
          hint={
            rows.length === 0
              ? "Nothing has been committed on this development yet."
              : "No contract matches these filters."
          }
        />
      ) : (
        <Card flush>
        <TableScroll label="Contracts" fixedFirst>
          <thead>
            <tr>
              <SortHeader column="contract" sort={sort} onToggle={toggle}>Contract</SortHeader>
              <SortHeader column="vendor" sort={sort} onToggle={toggle}>Vendor</SortHeader>
              <SortHeader column="original" sort={sort} onToggle={toggle} className="num">
                Original
              </SortHeader>
              <SortHeader column="variations" sort={sort} onToggle={toggle} className="num">
                Variations
              </SortHeader>
              <SortHeader column="revised" sort={sort} onToggle={toggle} className="num">
                Revised commitment
              </SortHeader>
              <SortHeader column="certified" sort={sort} onToggle={toggle} className="num">
                Certified
              </SortHeader>
              <SortHeader column="status" sort={sort} onToggle={toggle}>Status</SortHeader>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr
                key={row.id}
                onClick={() => setOpen(row.id)}
                className="row-clickable"
                aria-selected={open === row.id}
              >
                <th scope="row">
                  <Button variant="link" onClick={() => setOpen(row.id)} aria-label={`Open contract ${row.contract_number}`}>
                  <IdentityCell
                    name={row.contract_number}
                    meta={row.contract_type}
                  />
                  </Button>
                </th>
                <td>{row.vendor_name}</td>
                <td className="num">
                  {money(row.original_contract_value_ex_tax, row.currency_code)}
                </td>
                <td className="num">
                  {money(row.approved_variation_delta, row.currency_code)}
                </td>
                <td className="num">
                  {["draft", "submitted", "cancelled"].includes(row.status) ? "Not committed" : money(row.revised_commitment, row.currency_code)}
                </td>
                <td className="num">
                  {money(row.certified_to_date, row.currency_code)}
                </td>
                <td>
                  <Badge tone={contractTone(row.status)}>
                    {contractLabel(row.status)}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
        </Card>
      )}

      {open ? (
        <ContractFile key={open} roles={roles}
          projectId={projectId}
          contractId={open}
          onChanged={async () => { await load(); void onChanged(); }}
          onClose={() => setOpen(null)}
        />
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Variations
// --------------------------------------------------------------------------- //

/**
 * Change orders, with the escalation the server decided beside each one.
 *
 * `requires_escalation` is a server field and is drawn, never recomputed. A
 * threshold re-derived in the browser is a threshold that can disagree with the
 * one the server will enforce, and the disagreement surfaces as an approval
 * button that refuses when pressed.
 */
function VariationsSection({ projectId }: { projectId: string }) {
  const [rows, setRows] = useState<Variation[] | null>(null);
  const [contracts, setContracts] = useState<ConstructionContract[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");

  const [retrying, setRetrying] = useState(false);
  const load = useCallback(async () => {
    setRetrying(true);
    try {
      const [variations, contracts] = await Promise.all([
        construction.variations(projectId), construction.contracts(projectId),
      ]);
      setRows(variations);
      setContracts(contracts);
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not load the variations.",
      );
    } finally {
      setRetrying(false);
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const shown = useMemo(
    () => (rows ?? []).filter((row) => !status || row.status === status),
    [rows, status],
  );
  const { sort, toggle, sorted } = useSort(shown, readVariationColumn);

  if (error) return <><Notice tone="error">{error}</Notice><Button disabled={retrying} onClick={() => void load()}>{retrying ? "Retrying…" : "Retry"}</Button></>;
  if (!rows) return <Loading label="Loading the variations" shape="rows" />;

  return (
    <div className="stack stack-tight">
      <DataToolbar
        framed
        count={{ shown: shown.length, total: rows.length, noun: "variation" }}
        onReset={status ? () => setStatus("") : undefined}
      >
        <ToolbarFilter label="Status" active={status !== ""}>
          <select
            className="input"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">Any status</option>
            <option value="draft">Draft</option>
            <option value="submitted">Awaiting decision</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="withdrawn">Withdrawn</option>
          </select>
        </ToolbarFilter>
      </DataToolbar>

      {shown.length === 0 ? (
        <EmptyState
          title="No variations"
          hint={
            rows.length === 0
              ? "Nothing has changed a contract on this development."
              : "No variation matches these filters."
          }
        />
      ) : (
        <Card flush>
        <TableScroll label="Variations" fixedFirst>
          <thead>
            <tr>
              <SortHeader column="variation" sort={sort} onToggle={toggle}>Variation</SortHeader>
              <SortHeader column="contract" sort={sort} onToggle={toggle}>Contract</SortHeader>
              <th scope="col">Description</th>
              <SortHeader column="requested" sort={sort} onToggle={toggle}>Requested</SortHeader>
              <SortHeader column="value" sort={sort} onToggle={toggle} className="num">
                Value
              </SortHeader>
              <th scope="col">Approval</th>
              <SortHeader column="status" sort={sort} onToggle={toggle}>Status</SortHeader>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr key={row.id}>
                <td>{row.variation_number}</td>
                <td>{row.contract_number}</td>
                <td>{row.description}</td>
                <td>{businessDate(row.requested_date)}</td>
                <td className="num">{money(row.total_value_ex_tax, contractCurrency(contracts, row.contract_id))}</td>
                <td>
                  {row.requires_escalation ? (
                    <Badge tone="warning">
                      Needs the Approver
                      {row.review_amount
                        ? ` (over ${money(row.review_amount, contractCurrency(contracts, row.contract_id))})`
                        : ""}
                    </Badge>
                  ) : (
                    <span className="footnote">Second Finance signature</span>
                  )}
                </td>
                <td>
                  <Badge tone={variationTone(row.status)}>
                    {variationLabel(row.status)}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
        </Card>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Certificates
// --------------------------------------------------------------------------- //

function CertificatesSection({ projectId }: { projectId: string }) {
  const [rows, setRows] = useState<Certificate[] | null>(null);
  const [contracts, setContracts] = useState<ConstructionContract[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [contract, setContract] = useState<string | null>(null);

  const [retrying, setRetrying] = useState(false);
  const load = useCallback(async () => {
    setRetrying(true);
    try {
      const [certificates, contracts] = await Promise.all([
        construction.certificates(projectId), construction.contracts(projectId),
      ]);
      setRows(certificates);
      setContracts(contracts);
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not load the certificates.",
      );
    } finally {
      setRetrying(false);
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const shown = useMemo(
    () => (rows ?? []).filter((row) => !status || row.status === status),
    [rows, status],
  );
  const { sort, toggle, sorted } = useSort(shown, readCertificateColumn);

  if (error) return <><Notice tone="error">{error}</Notice><Button disabled={retrying} onClick={() => void load()}>{retrying ? "Retrying…" : "Retry"}</Button></>;
  if (!rows) return <Loading label="Loading the certificates" shape="rows" />;

  return (
    <div className="stack stack-tight">
      <DataToolbar
        framed
        count={{ shown: shown.length, total: rows.length, noun: "certificate" }}
        onReset={status ? () => setStatus("") : undefined}
      >
        <ToolbarFilter label="Status" active={status !== ""}>
          <select
            className="input"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">Any status</option>
            <option value="draft">Draft</option>
            <option value="submitted">Awaiting certification</option>
            <option value="certified">Certified</option>
            <option value="rejected">Rejected</option>
            <option value="reversed">Reversed</option>
          </select>
        </ToolbarFilter>
      </DataToolbar>

      {shown.length === 0 ? (
        <EmptyState
          title="No certificates"
          hint={
            rows.length === 0
              ? "No work has been valued on this development yet."
              : "No certificate matches these filters."
          }
        />
      ) : (
        <Card flush>
        <TableScroll label="Certificates" fixedFirst>
          <thead>
            <tr>
              <SortHeader column="certificate" sort={sort} onToggle={toggle}>Certificate</SortHeader>
              <SortHeader column="contract" sort={sort} onToggle={toggle}>Contract</SortHeader>
              <th scope="col">Period</th>
              <SortHeader column="work" sort={sort} onToggle={toggle} className="num">
                Work
              </SortHeader>
              <SortHeader column="retention" sort={sort} onToggle={toggle} className="num">
                Retention held
              </SortHeader>
              <SortHeader column="net" sort={sort} onToggle={toggle} className="num">
                Net due
              </SortHeader>
              <SortHeader column="status" sort={sort} onToggle={toggle}>Status</SortHeader>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr
                key={row.id}
                onClick={() => setOpen(row.id)}
                className="row-clickable"
                aria-selected={open === row.id}
              >
                <th scope="row"><Button variant="link" onClick={() => setOpen(row.id)} aria-label={`Open certificate ${row.certificate_number}`}>{row.certificate_number}</Button></th>
                <td>{row.contract_number}</td>
                <td>
                  {businessDate(row.period_start)} to{" "}
                  {businessDate(row.period_end)}
                </td>
                <td className="num">
                  {money(row.current_work_value_ex_tax, contractCurrency(contracts, row.contract_id))}
                </td>
                <td className="num">{money(row.retention_held_amount, contractCurrency(contracts, row.contract_id))}</td>
                <td className="num">{money(row.net_due, contractCurrency(contracts, row.contract_id))}</td>
                <td>
                  <Badge tone={certificateTone(row.status)}>
                    {certificateLabel(row.status)}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
        </Card>
      )}

      {open ? (
        <CertificateFile
          projectId={projectId}
          certificateId={open}
          currency={contractCurrency(contracts, rows.find((row) => row.id === open)?.contract_id)}
          onClose={() => setOpen(null)}
          onOpenContract={(contractId) => {
            setOpen(null);
            setContract(contractId);
          }}
        />
      ) : null}
      {contract ? (
        <ContractFile
          projectId={projectId}
          contractId={contract}
          onClose={() => setContract(null)}
        />
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Invoices and payments
// --------------------------------------------------------------------------- //

/**
 * The cash side, on one screen and in two tables.
 *
 * Both are stated including tax, and the heading says so, because these are the
 * only figures in this module that are — and the certified figures a reader
 * just looked at on the previous tab are not.
 */
function CashSection({ projectId }: { projectId: string }) {
  const [invoices, setInvoices] = useState<ConstructionInvoice[] | null>(null);
  const [payments, setPayments] = useState<ConstructionPayment[] | null>(null);
  const [contracts, setContracts] = useState<ConstructionContract[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [retrying, setRetrying] = useState(false);
  const load = useCallback(async () => {
    setRetrying(true);
    try {
      const [claims, cash, contracts] = await Promise.all([
        construction.invoices(projectId),
        construction.payments(projectId),
        construction.contracts(projectId),
      ]);
      setInvoices(claims);
      setPayments(cash);
      setContracts(contracts);
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not load the cash position.",
      );
    } finally {
      setRetrying(false);
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const { sort: invoiceSort, toggle: toggleInvoice, sorted: sortedInvoices } = useSort(invoices ?? NO_INVOICES, readInvoiceColumn);
  const { sort: paymentSort, toggle: togglePayment, sorted: sortedPayments } = useSort(payments ?? NO_PAYMENTS, readPaymentColumn);

  if (error) return <><Notice tone="error">{error}</Notice><Button disabled={retrying} onClick={() => void load()}>{retrying ? "Retrying…" : "Retry"}</Button></>;
  if (!invoices || !payments)
    return <Loading label="Loading invoices and payments" shape="rows" />;

  return (
    <div className="stack">
      <Card
        title="Invoices"
        description="Including tax. An invoice is a liability only once it has been approved."
      >
        {invoices.length === 0 ? (
          <EmptyState title="No invoices" hint="Nothing has been claimed." />
        ) : (
          <TableScroll label="Invoices" fixedFirst>
            <thead>
              <tr>
                <SortHeader column="invoice" sort={invoiceSort} onToggle={toggleInvoice}>Invoice</SortHeader>
                <SortHeader column="contract" sort={invoiceSort} onToggle={toggleInvoice}>Contract</SortHeader>
                <SortHeader column="type" sort={invoiceSort} onToggle={toggleInvoice}>Type</SortHeader>
                <SortHeader column="dated" sort={invoiceSort} onToggle={toggleInvoice}>Dated</SortHeader>
                <SortHeader column="payable" sort={invoiceSort} onToggle={toggleInvoice} className="num">
                  Payable
                </SortHeader>
                <SortHeader column="outstanding" sort={invoiceSort} onToggle={toggleInvoice} className="num">
                  Outstanding
                </SortHeader>
                <SortHeader column="status" sort={invoiceSort} onToggle={toggleInvoice}>Status</SortHeader>
              </tr>
            </thead>
            <tbody>
              {sortedInvoices.map((row) => (
                <tr key={row.id}>
                  <td>{row.invoice_number}</td>
                  <td>{row.contract_number}</td>
                  <td>{row.invoice_type}</td>
                  <td>{businessDate(row.invoice_date)}</td>
                  <td className="num">{money(row.net_payable, contractCurrency(contracts, row.contract_id))}</td>
                  <td className="num">{money(row.outstanding, contractCurrency(contracts, row.contract_id))}</td>
                  <td>
                    <Badge tone={invoiceTone(row.status)}>
                      {invoiceLabel(row.status)}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        )}
      </Card>

      <Card
        title="Payments"
        description="Including tax. Cash has left only once a payment is confirmed."
      >
        {payments.length === 0 ? (
          <EmptyState title="No payments" hint="Nothing has been paid." />
        ) : (
          <TableScroll label="Payments" fixedFirst>
            <thead>
              <tr>
                <SortHeader column="reference" sort={paymentSort} onToggle={togglePayment}>Reference</SortHeader>
                <SortHeader column="contract" sort={paymentSort} onToggle={togglePayment}>Contract</SortHeader>
                <SortHeader column="dated" sort={paymentSort} onToggle={togglePayment}>Dated</SortHeader>
                <SortHeader column="amount" sort={paymentSort} onToggle={togglePayment} className="num">
                  Amount
                </SortHeader>
                <SortHeader column="unallocated" sort={paymentSort} onToggle={togglePayment} className="num">
                  Unallocated
                </SortHeader>
                <SortHeader column="status" sort={paymentSort} onToggle={togglePayment}>Status</SortHeader>
              </tr>
            </thead>
            <tbody>
              {sortedPayments.map((row) => (
                <tr key={row.id}>
                  <td>{row.payment_reference}</td>
                  <td>{row.contract_number}</td>
                  <td>{businessDate(row.payment_date)}</td>
                  <td className="num">
                    {money(row.amount, row.currency_code)}
                  </td>
                  <td className="num">
                    {money(row.unallocated, row.currency_code)}
                  </td>
                  <td>
                    <Badge tone={paymentTone(row.status)}>
                      {paymentLabel(row.status)}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        )}
      </Card>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Milestones
// --------------------------------------------------------------------------- //

/**
 * The programme, and the one column that reaches a buyer's money.
 *
 * "Reported complete" and "Certified" are drawn as different states in
 * different tones on purpose. The first is site saying the work is done; only
 * the second makes an instalment fall due, and a screen that collapsed them
 * would show a buyer's payment as triggered when nothing had been certified.
 */
function MilestonesSection({ projectId, roles }: { projectId: string; roles: Set<string> }) {
  // The same people who may move a milestone by its form may correct its forecast in place.
  const canForecast = hasAnyRole(roles, TECHNICAL_WRITERS);
  const [rows, setRows] = useState<ConstructionMilestone[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [retrying, setRetrying] = useState(false);
  const load = useCallback(async () => {
    setRetrying(true);
    try {
      setRows(await construction.milestones(projectId));
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not load the milestones.",
      );
    } finally {
      setRetrying(false);
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const { sort, toggle, sorted } = useSort(rows ?? NO_MILESTONES, readMilestoneColumn);

  if (error) return <><Notice tone="error">{error}</Notice><Button disabled={retrying} onClick={() => void load()}>{retrying ? "Retrying…" : "Retry"}</Button></>;
  if (!rows) return <Loading label="Loading the milestones" shape="rows" />;
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No milestones"
        hint="Nothing in the programme is being tracked yet. A payment plan cannot point an instalment at a milestone that does not exist."
      />
    );
  }

  return (
    <Card flush>
    <TableScroll label="Milestones" fixedFirst>
      <thead>
        <tr>
          <SortHeader column="milestone" sort={sort} onToggle={toggle}>Milestone</SortHeader>
          <SortHeader column="scope" sort={sort} onToggle={toggle}>Scope</SortHeader>
          <SortHeader column="planned" sort={sort} onToggle={toggle}>Planned</SortHeader>
          <SortHeader column="forecast" sort={sort} onToggle={toggle}>Forecast</SortHeader>
          <SortHeader column="reported" sort={sort} onToggle={toggle}>Reported</SortHeader>
          <SortHeader column="certified" sort={sort} onToggle={toggle}>Certified</SortHeader>
          <SortHeader column="delay" sort={sort} onToggle={toggle} className="num">
            Delay
          </SortHeader>
          <SortHeader column="status" sort={sort} onToggle={toggle}>Status</SortHeader>
        </tr>
      </thead>
      <tbody>
        {sorted.map((row) => (
          <tr key={row.id}>
            <td>
              <IdentityCell name={row.code} meta={row.name} />
            </td>
            <td>{row.scope_label ?? "Whole project"}</td>
            <td>{businessDate(row.planned_date)}</td>
            <td>
              <InlineEdit
                label={`Forecast date for ${row.code}`}
                type="date"
                value={row.forecast_date ?? ""}
                display={businessDate(row.forecast_date)}
                disabled={!canForecast}
                onSave={async (value) => {
                  try {
                    await construction.updateMilestone(projectId, row.id, { forecast_date: value || null });
                  } catch (caught) {
                    throw new Error(caught instanceof ApiError ? caught.message : "Could not save the forecast date.");
                  }
                  await load();
                }}
              />
            </td>
            <td>{businessDate(row.actual_achieved_date)}</td>
            <td>{businessDate(row.certified_date)}</td>
            <td
              className={
                row.delay_days && row.delay_days > 0
                  ? "num figure-danger"
                  : "num"
              }
            >
              {row.delay_days === null ? "—" : `${row.delay_days} d`}
            </td>
            <td>
              <Badge tone={milestoneTone(row.status)}>
                {milestoneLabel(row.status)}
              </Badge>
            </td>
          </tr>
        ))}
      </tbody>
    </TableScroll>
    </Card>
  );
}

// --------------------------------------------------------------------------- //
// Forecast
// --------------------------------------------------------------------------- //

/**
 * What the project now expects to spend.
 *
 * Optional forecast detail does not gate contract registration. The tone comes from one shared function so the sign cannot mean one
 * thing on this table and another on the overview above it.
 */
function ForecastSection({ projectId }: { projectId: string }) {
  const [detail, setDetail] = useState<ForecastDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [empty, setEmpty] = useState(false);

  const [retrying, setRetrying] = useState(false);
  const load = useCallback(async () => {
    setRetrying(true);
    try {
      const versions = await construction.forecasts(projectId);
      const current =
        versions.find((version) => version.status === "active") ?? versions[0];
      setEmpty(!current);
      if (!current) {
        setError(null);
        return;
      }
      setDetail(await construction.forecast(projectId, current.id));
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not load the forecast.",
      );
    } finally {
      setRetrying(false);
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  if (error) return <><Notice tone="error">{error}</Notice><Button disabled={retrying} onClick={() => void load()}>{retrying ? "Retrying…" : "Retry"}</Button></>;
  if (empty) {
    return (
      <EmptyState
        title="No forecast yet"
        hint="Nothing has been forecast for this development, so there is no estimate at completion to report."
      />
    );
  }
  if (!detail) return <Loading label="Loading the forecast" shape="rows" />;

  const code = detail.currency_code;

  return (
    <Card
      flush
      title={`Forecast version ${detail.version_number}`}
      description={`As at ${businessDate(detail.as_of_date)}. ${detail.change_reason}`}
      actions={
        <Badge tone={forecastTone(detail.status)}>
          {forecastLabel(detail.status)}
        </Badge>
      }
    >
      <TableScroll label="Forecast by cost code" fixedFirst>
        <thead>
          <tr>
            <th scope="col">Cost code</th>
            <th scope="col" className="num">
              Committed
            </th>
            <th scope="col" className="num">
              Certified
            </th>
            <th scope="col" className="num">
              Forecast remaining
            </th>
            <th scope="col" className="num">
              Estimate at completion
            </th>
          </tr>
        </thead>
        <tbody>
          {detail.lines.map((line) => (
            <tr key={line.cost_code_id}>
              <td>
                <IdentityCell
                  name={line.cost_code}
                  meta={
                    line.forecast_below_commitment
                      ? `Forecast under commitment by ${money(line.uncovered_commitment, code)}`
                      : line.cost_code_name
                  }
                />
              </td>
              <td className="num">
                {money(line.revised_commitment, code)}
              </td>
              <td className="num">{money(line.certified_to_date, code)}</td>
              <td className="num">
                {money(line.forecast_remaining_amount_ex_tax, code)}
              </td>
              <td className="num">
                {money(line.estimate_at_completion, code)}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">Project</th>
            <td className="num" />
            <td className="num">{money(detail.total_certified, code)}</td>
            <td className="num">
              {money(detail.total_forecast_remaining, code)}
            </td>
            <td className="num">
              {money(detail.total_estimate_at_completion, code)}
            </td>
          </tr>
        </tfoot>
      </TableScroll>
      <p className="footnote">
        Forecast figures exclude tax. This optional estimate does not block contracts or payments.
      </p>
    </Card>
  );
}
