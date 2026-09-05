"use client";

import { useCallback, useEffect, useState } from "react";

import {
  Badge,
  Button,
  Drawer,
  EmptyState,
  KeyValue,
  KeyValueGrid,
  Loading,
  Notice,
  SectionHeader,
  TableScroll,
  Waterfall,
  WaterfallRow,
} from "@/components/ui";
import { ApiError, construction } from "@/lib/api";
import type { CertificateDetail } from "@/lib/api";
import { businessDate, money } from "@/lib/format";

import { certificateLabel, certificateTone } from "./labels";

/**
 * One certificate, and the waterfall that turns valued work into a net amount.
 *
 * The order of the deductions is the whole point, and it is the server's order,
 * not a layout choice: retention is withheld on this period's work, then a
 * release of retention withheld earlier is added back, then advance recovery
 * and any other deduction are taken off. Applying them in a different sequence
 * gives a different answer on the same inputs, so the rows here are read from
 * the server's figures in the server's order and nothing is recomputed.
 *
 * `net_due` in particular is never assembled in the browser. It is the figure a
 * contractor invoices against and the ceiling that invoice is approved within,
 * and a browser-side sum that disagreed with the server's by a cent would
 * present an approvable claim that the server then refuses.
 *
 * The lines below the waterfall carry three separate columns — previously
 * certified, this period, cumulative — because "certified" means a different
 * number in each, and a single column labelled "certified" would be read as
 * whichever one the reader expected.
 */
export function CertificateFile({
  projectId,
  certificateId,
  onClose,
  onOpenContract,
}: {
  projectId: string;
  certificateId: string;
  onClose: () => void;
  onOpenContract?: (contractId: string) => void;
}) {
  const [certificate, setCertificate] = useState<CertificateDetail | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setCertificate(await construction.certificate(projectId, certificateId));
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not load this certificate.",
      );
    }
  }, [projectId, certificateId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  if (error) {
    return (
      <Drawer title="Certificate" onClose={onClose}>
        <Notice tone="error">{error}</Notice>
      </Drawer>
    );
  }

  if (!certificate) {
    return (
      <Drawer title="Certificate" onClose={onClose}>
        <Loading label="Loading this certificate" />
      </Drawer>
    );
  }

  return (
    <Drawer
      eyebrow="Certificate"
      title={certificate.certificate_number}
      subtitle={
        onOpenContract ? (
          <button
            type="button"
            className="button-link"
            onClick={() => onOpenContract(certificate.contract_id)}
          >
            {certificate.contract_number}
          </button>
        ) : (
          certificate.contract_number
        )
      }
      meta={
        <Badge tone={certificateTone(certificate.status)}>
          {certificateLabel(certificate.status)}
        </Badge>
      }
      actions={
        onOpenContract ? (
          <Button
            variant="quiet"
            onClick={() => onOpenContract(certificate.contract_id)}
          >
            Open contract
          </Button>
        ) : undefined
      }
      facts={[
        {
          label: "Work this period",
          value: money(certificate.current_work_value_ex_tax),
        },
        { label: "Net due", value: money(certificate.net_due) },
        {
          label: "Still to invoice",
          value: money(certificate.uninvoiced_net_due),
        },
      ]}
      onClose={onClose}
    >
      <div className="stack">
        <section className="stack stack-tight">
          <SectionHeader
            title="What is due on this certificate"
            description="In the order the deductions are applied. Every figure is the server's."
          />
          <Waterfall>
            <WaterfallRow
              label="Work certified this period"
              note="Excluding tax"
              amount={money(certificate.current_work_value_ex_tax)}
            />
            <WaterfallRow
              label="Retention withheld"
              note="Held back on this period's work"
              amount={`(${money(certificate.retention_held_amount)})`}
            />
            <WaterfallRow
              label="Retention released"
              note="Withheld on an earlier certificate"
              amount={money(certificate.retention_release_amount)}
            />
            <WaterfallRow
              label="Advance recovered"
              note="Against advance cash already paid"
              amount={`(${money(certificate.advance_recovery_amount)})`}
            />
            <WaterfallRow
              label="Other deductions"
              amount={`(${money(certificate.other_deductions_amount)})`}
            />
            <WaterfallRow
              label="Tax"
              amount={money(certificate.tax_amount)}
              kind="subtotal"
            />
            <WaterfallRow
              label="Net due"
              amount={money(certificate.net_due)}
              kind="total"
            />
          </Waterfall>
          <p className="footnote">
            Retention and advance recovery change when money moves, not what the
            work cost. The cost of this period is the certified value above, at
            its full amount.
          </p>
        </section>

        <section className="stack stack-tight">
          <SectionHeader
            title="By cost code"
            description="Previously certified, this period, and cumulative — three different figures."
          />
          {certificate.lines.length === 0 ? (
            <EmptyState
              title="No lines"
              hint="This certificate values no work yet."
            />
          ) : (
            <TableScroll label="Certified work by cost code">
              <thead>
                <tr>
                  <th scope="col">Cost code</th>
                  <th scope="col" className="num">
                    Previously certified
                  </th>
                  <th scope="col" className="num">
                    This period
                  </th>
                  <th scope="col" className="num">
                    Cumulative
                  </th>
                  <th scope="col" className="num">
                    Revised commitment
                  </th>
                </tr>
              </thead>
              <tbody>
                {certificate.lines.map((line) => (
                  <tr key={line.cost_code_id}>
                    <td>{line.cost_code}</td>
                    <td className="num">
                      {money(line.previously_certified)}
                    </td>
                    <td className="num">
                      {money(line.current_work_value_ex_tax)}
                    </td>
                    <td className="num">
                      {money(line.cumulative_certified)}
                    </td>
                    <td className="num">
                      {money(line.revised_commitment)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </TableScroll>
          )}
        </section>

        <KeyValueGrid>
          <KeyValue
            label="Period"
            value={`${businessDate(certificate.period_start)} to ${businessDate(certificate.period_end)}`}
          />
          <KeyValue
            label="Certificate date"
            value={businessDate(certificate.certificate_date)}
          />
          <KeyValue
            label="Certifier"
            value={certificate.certifier_name ?? "—"}
          />
          <KeyValue
            label="Evidence"
            value={certificate.evidence_reference ?? "—"}
          />
          <KeyValue
            label="Rejected because"
            value={certificate.rejection_reason ?? "—"}
          />
          <KeyValue
            label="Reversed because"
            value={certificate.reversal_reason ?? "—"}
          />
        </KeyValueGrid>
      </div>
    </Drawer>
  );
}
