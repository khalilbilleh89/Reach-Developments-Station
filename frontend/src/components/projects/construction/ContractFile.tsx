"use client";

import { useCallback, useEffect, useState } from "react";

import {
  Badge,
  Button,
  ButtonRow,
  Disclosure,
  RecordPage,
  EmptyState,
  KeyValue,
  KeyValueGrid,
  Loading,
  Notice,
  Position,
  PositionFigure,
  PositionSupport,
  PositionSupportItem,
  SectionHeader,
  TableScroll,
} from "@/components/ui";
import { ContractDocuments } from "./ContractDocuments";
import { ContractTransactions } from "./ContractTransactions";
import { DeleteRecordButton } from "../DeleteRecordButton";
import { hasAnyRole } from "@/lib/roles";
import { ContractWorkflow } from "./ContractWorkflow";
import { useRegisterFields } from "@/components/shell/registerState";
import { ApiError, construction } from "@/lib/api";
import type {
  Certificate,
  ConstructionInvoice,
  ConstructionPayment,
  ContractDetail,
  Variation,
} from "@/lib/api";
import { businessDate, money, percent } from "@/lib/format";

import {
  contractLabel,
  contractTone,
  variationLabel,
  variationTone,
} from "./labels";

const TABS = [
  { key: "position", label: "Contract & payments" },
  { key: "manage", label: "Contract details" },
  { key: "variations", label: "Variations" },
  { key: "certificates", label: "Certificates" },
  { key: "cash", label: "Invoices & payments" },
];

/**
 * One contract, and the six separate truths standing on it.
 *
 * The Position tab is the point of the record. Commitment, certification and
 * cash are three different questions with three different answers, and this is
 * the screen where somebody is most tempted to treat them as one: the
 * contractor has invoiced, so surely that is what we owe; we have certified, so
 * surely that is what we will pay. Neither follows, so the three appear as
 * three figures with their bases written beside them, and never as a
 * subtraction.
 *
 * Retention and advance appear under cash and not under cost. Both are timing
 * mechanics on when money moves, not reductions in what the work cost — a
 * screen that netted retention off the certified value would understate the
 * build by exactly the amount being held back.
 */
export function ContractFile({
  projectId,
  contractId,
  roles = new Set<string>(),
  onClose,
  onChanged = async () => {},
}: {
  projectId: string;
  contractId: string;
  roles?: Set<string>;
  onClose: () => void;
  onChanged?: () => Promise<void>;
}) {
  const [view, setView] = useRegisterFields({ contractTab: "position" });
  const tab = TABS.some(item => item.key === view.contractTab) ? view.contractTab : "position";
  const setTab = (contractTab: string) => setView({ contractTab });
  const [reading, setReading] = useState(false);
  const [supportError, setSupportError] = useState<string | null>(null);
  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [variations, setVariations] = useState<Variation[] | null>(null);
  const [certificates, setCertificates] = useState<Certificate[] | null>(null);
  const [invoices, setInvoices] = useState<ConstructionInvoice[] | null>(null);
  const [payments, setPayments] = useState<ConstructionPayment[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setReading(true);
    try {
      const file = await construction.contract(projectId, contractId);
      setContract(file); setError(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not refresh this contract. Retry before taking action.");
    }
    const support = await Promise.allSettled([
      construction.variations(projectId, contractId), construction.certificates(projectId, contractId),
      construction.invoices(projectId, contractId), construction.payments(projectId, contractId),
    ]);
    const [changes, valuations, claims, cash] = support;
    setVariations(changes.status === "fulfilled" ? changes.value : null);
    setCertificates(valuations.status === "fulfilled" ? valuations.value : null);
    setInvoices(claims.status === "fulfilled" ? claims.value : null);
    setPayments(cash.status === "fulfilled" ? cash.value : null);
    setSupportError(support.some(item => item.status === "rejected") ? "Some related records could not be loaded. Retry to recover the related tabs." : null);
    setReading(false);
  }, [projectId, contractId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  if (error && !contract) {
    return (
      <RecordPage title="Contract" onClose={onClose}>
        <Notice tone="error">{error}</Notice><Button disabled={reading} onClick={() => void load()}>Retry contract</Button>
      </RecordPage>
    );
  }

  if (!contract) {
    return (
      <RecordPage title="Contract" onClose={onClose}>
        <Loading label="Loading this contract" />
      </RecordPage>
    );
  }

  const code = contract.currency_code;
  const uncommitted = ["draft", "submitted", "cancelled"].includes(contract.status);

  return (
    <RecordPage
      eyebrow="Contract" icon="building"
      title={contract.contract_number}
      subtitle={contract.vendor_name}
      meta={
        <Badge tone={contractTone(contract.status)}>
          {contractLabel(contract.status)}
        </Badge>
      }
      strip={{
        lead: {
          label: uncommitted ? "Proposed value" : "Revised commitment",
          value: money(contract.revised_commitment, code),
          note: uncommitted ? "Not yet committed" : "Original plus approved variations",
        },
        items: [
          { label: "Certified to date", value: money(contract.certified_to_date, code) },
          { label: "Paid", value: money(contract.confirmed_paid, code), note: "Confirmed payments" },
          { label: "Invoices outstanding", value: money(contract.invoice_outstanding, code) },
        ],
      }}
      next={{
        text: uncommitted
          ? `This contract is ${contractLabel(contract.status).toLowerCase()}: complete its details before any work is certified against it.`
          : `Certified ${money(contract.certified_to_date, code)} to date; ${money(contract.invoice_outstanding, code)} of invoices outstanding.`,
        action: <Button small onClick={() => setTab(uncommitted ? "manage" : "cash")}>{uncommitted ? "Contract details" : "Invoices & payments"}</Button>,
      }}
      tabs={TABS}
      activeTab={tab}
      onSelectTab={setTab}
      onClose={onClose}
    >
      {error ? <Notice tone="error">The last displayed record could not be refreshed: {error}</Notice> : null}
      {supportError ? <Notice tone="warning">{supportError}</Notice> : null}
      <ButtonRow><Button small disabled={reading} onClick={() => void load()}>{reading ? "Refreshing…" : "Refresh contract and related records"}</Button></ButtonRow>
      {tab === "manage" && hasAnyRole(roles, new Set(["finance", "project_manager"])) && ["draft", "submitted", "active"].includes(contract.status) ? <DeleteRecordButton label="unused contract" recordName={contract.contract_number} description="Unused drafts are removed. Signed entries are cancelled with their history retained. Any linked variation, certificate, invoice or payment blocks removal." confirmLabel="Remove unused contract" onDelete={reason => construction.deleteUnusedContract(projectId, contract.id, reason)} onDeleted={async () => { onClose(); await onChanged(); }} /> : null}
      {tab === "manage" || (uncommitted && tab === "position") ? <ContractWorkflow projectId={projectId} detail={contract} reading={reading} unavailable={!!error} onRefresh={load} onChanged={async () => { await load(); await onChanged(); }} /> : null}
      {uncommitted && tab !== "manage" && tab !== "position" ? <Notice tone="info">Draft values do not commit funds. If the agreement is already signed, open Contract details and choose Activate signed contract. Cancelled agreements remain as history.</Notice> : null}
      {tab === "position" ? (
        <div className="stack">
          <Position compact layout="split">
            <PositionFigure lead label="Remaining contract balance" value={money(contract.remaining_contract_balance, code)} note={uncommitted ? "No standing contract balance for a draft, submitted or cancelled agreement." : contract.remaining_contract_balance === null ? "Unavailable until the contract tax rate is stated." : "Including the stated contract tax, less all confirmed payments. A negative balance is an overpayment / credit."} />
            <PositionFigure label="Revised contract including tax" value={money(contract.revised_contract_value_inc_tax, code)} />
            <PositionFigure label="Paid to date" value={money(contract.confirmed_paid, code)} />
          </Position>
          <KeyValueGrid><KeyValue label="Invoices outstanding" value={money(contract.invoice_outstanding, code)} /><KeyValue label="Retention held" value={money(contract.retention_outstanding, code)} /><KeyValue label="Advance still to recover" value={money(contract.advance_outstanding, code)} /></KeyValueGrid>
          <ButtonRow><Button onClick={() => setTab("certificates")}>Completion certificates</Button><Button onClick={() => setTab("cash")}>Invoices and outstanding amounts</Button></ButtonRow>
          {reading ? <Loading label="Refreshing transactions" /> : <ContractTransactions projectId={projectId} contract={contract} roles={roles} invoices={invoices} variations={variations} payments={payments} unavailable={!!error || reading} onChanged={async () => { await load(); await onChanged(); }} />}
          <Disclosure title="Contract reconciliation and terms">
          <section className="stack stack-tight">
            <SectionHeader
              title={uncommitted ? "Proposed contract" : "Commitment"}
              description={uncommitted ? "Excluding tax. These terms have not become a commitment." : "Excluding tax. What the company has signed itself up to."}
            />
            <Position compact>
              <PositionFigure
                label="Original value"
                value={money(contract.original_contract_value_ex_tax, code)}
                note={uncommitted ? "Frozen on submission" : "Never moves"}
              />
              <PositionFigure
                label="Approved additions"
                value={money(contract.approved_additions, code)}
                note="Added to the signed amount"
              />
              <PositionFigure
                label="Approved reductions"
                value={money(contract.approved_reductions, code)}
                note="Client-supplied items and omitted scope"
              />
              <PositionFigure
                lead
                label={uncommitted ? "Proposed value" : "Revised commitment"}
                value={money(contract.revised_commitment, code)}
                note="The limit certification is measured against"
              />
            </Position>
          </section>

          <section className="stack stack-tight">
            <SectionHeader
              title="Certification"
              description="Excluding tax. What has been formally certified as done."
            />
            <Position compact>
              <PositionFigure
                label="Certified to date"
                value={money(contract.certified_to_date, code)}
                note="Cost, at its full value"
              />
            </Position>
          </section>

          <section className="stack stack-tight">
            <SectionHeader
              title="Cash"
              description="Including tax. What is owed, what has gone, and what is held."
            />
            <Position compact>
              <PositionFigure
                label="Approved payable"
                value={money(contract.approved_invoice_payable, code)}
                note="Invoices a second person has approved"
              />
              <PositionFigure
                label="Disputed payable"
                value={money(contract.disputed_invoice_payable, code)}
                note="Under argument, and still owed"
              />
              <PositionFigure
                label="Standing outstanding"
                value={money(contract.invoice_outstanding, code)}
                note="Approved and disputed invoices, less payments allocated to them"
              />
              <PositionFigure
                label="Paid"
                value={money(contract.confirmed_paid, code)}
                note="Confirmed as gone"
              />
            </Position>
            <p className="footnote">
              A dispute blocks payment; it does not reduce the obligation, so
              outstanding includes disputed invoices. Direct contract payments reduce the contract balance; they do not automatically settle a specific invoice.
            </p>
            <PositionSupport>
              <PositionSupportItem
                label="Retention held"
                value={money(contract.retention_held, code)}
              />
              <PositionSupportItem
                label="Retention released"
                value={money(contract.retention_released, code)}
              />
              <PositionSupportItem
                label="Retention outstanding"
                value={money(contract.retention_outstanding, code)}
              />
              <PositionSupportItem
                label="Advance paid"
                value={money(contract.advance_paid, code)}
              />
              <PositionSupportItem
                label="Advance recovered"
                value={money(contract.advance_recovered, code)}
              />
              <PositionSupportItem
                label="Advance outstanding"
                value={money(contract.advance_outstanding, code)}
              />
            </PositionSupport>
          </section>

          <KeyValueGrid>
            <KeyValue label="Type" value={contract.contract_type} />
            <KeyValue label="Currency" value={code ?? "—"} />
            <KeyValue
              label="Retention rate"
              value={percent(contract.retention_rate_fraction)}
            />
            <KeyValue
              label="Tax rate"
              value={percent(contract.tax_rate_fraction)}
            />
            <KeyValue
              label="Advance entitlement"
              value={money(contract.advance_entitlement_amount, code)}
            />
            <KeyValue
              label="Payment terms"
              value={contract.payment_terms ?? "—"}
            />
            <KeyValue
              label="Planned start"
              value={businessDate(contract.planned_start_date)}
            />
            <KeyValue
              label="Planned completion"
              value={businessDate(contract.planned_completion_date)}
            />
            <KeyValue
              label="Actual start"
              value={businessDate(contract.actual_start_date)}
            />
            <KeyValue
              label="Actual completion"
              value={businessDate(contract.actual_completion_date)}
            />
            <KeyValue
              label="Vendor registration"
              value={contract.vendor_registration_reference ?? "—"}
            />
            <KeyValue
              label="Vendor tax reference"
              value={contract.vendor_tax_reference ?? "—"}
            />
          </KeyValueGrid>
          </Disclosure>
        </div>
      ) : null}

      {tab === "variations" && variations ? (
        !variations || variations.length === 0 ? (
          <EmptyState
            title="No variations"
            hint="Nothing has changed this contract."
          />
        ) : (
          <TableScroll label="Variations on this contract">
            <thead>
              <tr>
                <th scope="col">Number</th>
                <th scope="col">Description</th>
                <th scope="col">Requested</th>
                <th scope="col" className="num">
                  Value
                </th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {variations.map((variation) => (
                <tr key={variation.id}>
                  <td>{variation.variation_number}</td>
                  <td>{variation.description}</td>
                  <td>{businessDate(variation.requested_date)}</td>
                  <td className="num">
                    {money(variation.total_value_ex_tax, code)}
                  </td>
                  <td>
                    <Badge tone={variationTone(variation.status)}>
                      {variationLabel(variation.status)}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        )
      ) : null}

      {tab === "certificates" || tab === "cash" ? <ContractDocuments projectId={projectId} contract={contract} roles={roles} certificates={certificates} invoices={invoices} mode={tab === "certificates" ? "certificates" : "invoices"} unavailable={!!error || reading} onChanged={async () => { await load(); await onChanged(); }} /> : null}
    </RecordPage>
  );
}
