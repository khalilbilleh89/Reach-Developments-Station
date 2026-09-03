"use client";

import { useCallback, useEffect, useState } from "react";

import {
  Badge,
  Drawer,
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
  certificateLabel,
  certificateTone,
  contractLabel,
  contractTone,
  invoiceLabel,
  invoiceTone,
  paymentLabel,
  paymentTone,
  variationLabel,
  variationTone,
} from "./labels";

const TABS = [
  { key: "position", label: "Position" },
  { key: "lines", label: "Lines" },
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
  onClose,
}: {
  projectId: string;
  contractId: string;
  onClose: () => void;
}) {
  const [tab, setTab] = useState("position");
  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [variations, setVariations] = useState<Variation[] | null>(null);
  const [certificates, setCertificates] = useState<Certificate[] | null>(null);
  const [invoices, setInvoices] = useState<ConstructionInvoice[] | null>(null);
  const [payments, setPayments] = useState<ConstructionPayment[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [file, changes, valuations, claims, cash] = await Promise.all([
        construction.contract(projectId, contractId),
        construction.variations(projectId, contractId),
        construction.certificates(projectId, contractId),
        construction.invoices(projectId, contractId),
        construction.payments(projectId, contractId),
      ]);
      setContract(file);
      setVariations(changes);
      setCertificates(valuations);
      setInvoices(claims);
      setPayments(cash);
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not load this contract.",
      );
    }
  }, [projectId, contractId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  if (error) {
    return (
      <Drawer title="Contract" onClose={onClose}>
        <Notice tone="error">{error}</Notice>
      </Drawer>
    );
  }

  if (!contract) {
    return (
      <Drawer title="Contract" onClose={onClose}>
        <Loading label="Loading this contract" />
      </Drawer>
    );
  }

  const code = contract.currency_code;

  return (
    <Drawer
      eyebrow="Contract"
      title={contract.contract_number}
      subtitle={contract.vendor_name}
      meta={
        <Badge tone={contractTone(contract.status)}>
          {contractLabel(contract.status)}
        </Badge>
      }
      facts={[
        {
          label: "Revised commitment",
          value: money(contract.revised_commitment, code),
        },
        {
          label: "Certified to date",
          value: money(contract.certified_to_date, code),
        },
        { label: "Paid", value: money(contract.confirmed_paid, code) },
      ]}
      tabs={TABS}
      activeTab={tab}
      onSelectTab={setTab}
      onClose={onClose}
    >
      {tab === "position" ? (
        <div className="stack">
          <section className="stack stack-tight">
            <SectionHeader
              title="Commitment"
              description="Excluding tax. What the company has signed itself up to."
            />
            <Position compact>
              <PositionFigure
                label="Original value"
                value={money(contract.original_contract_value_ex_tax, code)}
                note="Never moves"
              />
              <PositionFigure
                label="Approved variations"
                value={money(contract.approved_variation_delta, code)}
                note="Only approved change counts"
              />
              <PositionFigure
                lead
                label="Revised commitment"
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
                label="Owed"
                value={money(contract.approved_invoice_payable, code)}
                note="Approved invoices"
              />
              <PositionFigure
                label="Outstanding"
                value={money(contract.invoice_outstanding, code)}
                note="Owed, less paid against it"
              />
              <PositionFigure
                label="Paid"
                value={money(contract.confirmed_paid, code)}
                note="Confirmed as gone"
              />
            </Position>
            <PositionSupport>
              <PositionSupportItem
                label="Disputed"
                value={money(contract.disputed_invoice_payable, code)}
              />
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
        </div>
      ) : null}

      {tab === "lines" ? (
        contract.lines.length === 0 ? (
          <EmptyState
            title="No lines"
            hint="This contract has not been broken down yet."
          />
        ) : (
          <TableScroll label="Contract lines">
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">Description</th>
                <th scope="col">Cost code</th>
                <th scope="col" className="numeric">
                  Original
                </th>
                <th scope="col" className="numeric">
                  Revised
                </th>
                <th scope="col" className="numeric">
                  Certified
                </th>
              </tr>
            </thead>
            <tbody>
              {contract.lines.map((line) => (
                <tr key={line.id}>
                  <td>{line.sequence}</td>
                  <td>{line.description}</td>
                  <td>{line.cost_code}</td>
                  <td className="numeric">
                    {money(line.original_amount_ex_tax, code)}
                  </td>
                  <td className="numeric">
                    {money(line.revised_commitment, code)}
                  </td>
                  <td className="numeric">
                    {money(line.certified_to_date, code)}
                  </td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        )
      ) : null}

      {tab === "variations" ? (
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
                <th scope="col" className="numeric">
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
                  <td className="numeric">
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

      {tab === "certificates" ? (
        !certificates || certificates.length === 0 ? (
          <EmptyState
            title="No certificates"
            hint="No work has been valued against this contract."
          />
        ) : (
          <TableScroll label="Certificates on this contract">
            <thead>
              <tr>
                <th scope="col">Number</th>
                <th scope="col">Period</th>
                <th scope="col" className="numeric">
                  Work
                </th>
                <th scope="col" className="numeric">
                  Net due
                </th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {certificates.map((certificate) => (
                <tr key={certificate.id}>
                  <td>{certificate.certificate_number}</td>
                  <td>
                    {businessDate(certificate.period_start)} to{" "}
                    {businessDate(certificate.period_end)}
                  </td>
                  <td className="numeric">
                    {money(certificate.current_work_value_ex_tax, code)}
                  </td>
                  <td className="numeric">
                    {money(certificate.net_due, code)}
                  </td>
                  <td>
                    <Badge tone={certificateTone(certificate.status)}>
                      {certificateLabel(certificate.status)}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        )
      ) : null}

      {tab === "cash" ? (
        <div className="stack">
          <section className="stack stack-tight">
            <SectionHeader title="Invoices" description="Including tax." />
            {!invoices || invoices.length === 0 ? (
              <EmptyState
                title="No invoices"
                hint="Nothing has been claimed."
              />
            ) : (
              <TableScroll label="Invoices on this contract">
                <thead>
                  <tr>
                    <th scope="col">Number</th>
                    <th scope="col">Type</th>
                    <th scope="col">Dated</th>
                    <th scope="col" className="numeric">
                      Payable
                    </th>
                    <th scope="col" className="numeric">
                      Outstanding
                    </th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((invoice) => (
                    <tr key={invoice.id}>
                      <td>{invoice.invoice_number}</td>
                      <td>{invoice.invoice_type}</td>
                      <td>{businessDate(invoice.invoice_date)}</td>
                      <td className="numeric">
                        {money(invoice.net_payable, code)}
                      </td>
                      <td className="numeric">
                        {money(invoice.outstanding, code)}
                      </td>
                      <td>
                        <Badge tone={invoiceTone(invoice.status)}>
                          {invoiceLabel(invoice.status)}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </TableScroll>
            )}
          </section>

          <section className="stack stack-tight">
            <SectionHeader
              title="Payments"
              description="Including tax. Cash out."
            />
            {!payments || payments.length === 0 ? (
              <EmptyState title="No payments" hint="Nothing has been paid." />
            ) : (
              <TableScroll label="Payments on this contract">
                <thead>
                  <tr>
                    <th scope="col">Reference</th>
                    <th scope="col">Dated</th>
                    <th scope="col" className="numeric">
                      Amount
                    </th>
                    <th scope="col" className="numeric">
                      Unallocated
                    </th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {payments.map((payment) => (
                    <tr key={payment.id}>
                      <td>{payment.payment_reference}</td>
                      <td>{businessDate(payment.payment_date)}</td>
                      <td className="numeric">
                        {money(payment.amount, payment.currency_code)}
                      </td>
                      <td className="numeric">
                        {money(payment.unallocated, payment.currency_code)}
                      </td>
                      <td>
                        <Badge tone={paymentTone(payment.status)}>
                          {paymentLabel(payment.status)}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </TableScroll>
            )}
          </section>
        </div>
      ) : null}
    </Drawer>
  );
}
