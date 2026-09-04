"use client";

import { useState } from "react";

import {
  Badge,
  Button,
  ButtonRow,
  Card,
  EmptyState,
  Field,
  FieldRow,
  FormDialog,
  KeyValue,
  KeyValueGrid,
  Loading,
  MoneyInput,
  Notice,
  PromptDialog,
  SubPanel,
  TableScroll,
} from "@/components/ui";
import type { Answer } from "@/lib/answer";
import type { CashflowRestriction } from "@/lib/api";
import { businessDate, money } from "@/lib/format";

import { movementLabel, movementTone } from "./labels";

/**
 * Cash received, and cash the project may actually spend.
 *
 * A restriction takes buyer money out of the spendable pool without taking it
 * out of the bank; a release puts it back. Neither creates or destroys project
 * cash, and neither appears as an inflow.
 *
 * The subtle case this screen exists to get right: a restriction can stay
 * *confirmed* on the record and stop counting, because the receipt it was taken
 * from was reversed. An escrow over a transfer that no longer stands is holding
 * money the project never had. So `counts_as_restricted` and `receipt_stands`
 * are what the screen reports, never the persisted status on its own — and the
 * status is still shown, because what happened is not rewritten to tidy a
 * screen.
 */
export function CashflowEscrow({
  answer,
  canRecord,
  canConfirm,
  busy,
  onConfirmRestriction,
  onReverseRestriction,
  onRecordRelease,
  onConfirmRelease,
  onReverseRelease,
}: {
  answer: Answer<CashflowRestriction[]>;
  canRecord: boolean;
  canConfirm: boolean;
  busy: boolean;
  onConfirmRestriction: (restrictionId: string) => void;
  onReverseRestriction: (restrictionId: string, reason: string) => void;
  onRecordRelease: (restrictionId: string, body: Record<string, unknown>) => void;
  onConfirmRelease: (releaseId: string) => void;
  onReverseRelease: (releaseId: string, reason: string) => void;
}) {
  const [releasing, setReleasing] = useState<CashflowRestriction | null>(null);
  const [reversing, setReversing] = useState<{ kind: "restriction" | "release"; id: string } | null>(
    null,
  );

  if (answer.status === "loading") return <Loading label="Loading escrow" shape="rows" />;
  if (answer.status === "denied") {
    return <Notice tone="info">Escrow is not available to your role.</Notice>;
  }
  if (answer.status === "failed") return <Notice tone="error">{answer.message}</Notice>;
  if (answer.status === "off") return null;

  const restrictions = answer.data;
  const unbacked = restrictions.filter(
    (row) => row.status === "confirmed" && !row.receipt_stands,
  );

  return (
    <div className="stack">
      {unbacked.length > 0 ? (
        <Notice tone="warning">
          {unbacked.length === 1
            ? "One confirmed escrow is no longer backed by standing buyer cash: the receipt it was taken from has been reversed."
            : `${unbacked.length} confirmed escrows are no longer backed by standing buyer cash: the receipts they were taken from have been reversed.`}{" "}
          They have stopped counting towards restricted cash. Reverse them to
          clear the exception.
        </Notice>
      ) : null}

      <Card
        title="Escrow and restricted cash"
        description="Buyer money held against a receipt, and what has been released from it."
      >
        {restrictions.length === 0 ? (
          <EmptyState
            title="Nothing is held in escrow"
            hint="A restriction is recorded against a confirmed buyer receipt, from the Collections record it came from."
          />
        ) : (
          <div className="stack">
            {restrictions.map((restriction) => (
              <RestrictionCard
                key={restriction.id}
                restriction={restriction}
                canRecord={canRecord}
                canConfirm={canConfirm}
                busy={busy}
                onConfirm={() => onConfirmRestriction(restriction.id)}
                onReverse={() => setReversing({ kind: "restriction", id: restriction.id })}
                onRelease={() => setReleasing(restriction)}
                onConfirmRelease={onConfirmRelease}
                onReverseRelease={(releaseId) => setReversing({ kind: "release", id: releaseId })}
              />
            ))}
          </div>
        )}
      </Card>

      {releasing ? (
        <ReleaseDialog
          restriction={releasing}
          busy={busy}
          onCancel={() => setReleasing(null)}
          onSubmit={(body) => {
            onRecordRelease(releasing.id, body);
            setReleasing(null);
          }}
        />
      ) : null}

      {reversing ? (
        <PromptDialog
          title={reversing.kind === "restriction" ? "Reverse this escrow" : "Reverse this release"}
          label="Why is it being reversed?"
          hint="Kept on the record. The escrow is withdrawn, not deleted."
          confirmLabel="Reverse"
          busy={busy}
          onCancel={() => setReversing(null)}
          onSubmit={(reason) => {
            if (reversing.kind === "restriction") onReverseRestriction(reversing.id, reason);
            else onReverseRelease(reversing.id, reason);
            setReversing(null);
          }}
        />
      ) : null}
    </div>
  );
}

function RestrictionCard({
  restriction,
  canRecord,
  canConfirm,
  busy,
  onConfirm,
  onReverse,
  onRelease,
  onConfirmRelease,
  onReverseRelease,
}: {
  restriction: CashflowRestriction;
  canRecord: boolean;
  canConfirm: boolean;
  busy: boolean;
  onConfirm: () => void;
  onReverse: () => void;
  onRelease: () => void;
  onConfirmRelease: (releaseId: string) => void;
  onReverseRelease: (releaseId: string) => void;
}) {
  const lostBacking = restriction.status === "confirmed" && !restriction.receipt_stands;
  return (
    <SubPanel
      title={`Receipt ${restriction.receipt_number ?? "—"}`}
      actions={
        <ButtonRow>
          {canConfirm && restriction.status === "recorded" ? (
            <Button small onClick={onConfirm} disabled={busy}>
              Confirm
            </Button>
          ) : null}
          {canRecord && restriction.counts_as_restricted ? (
            <Button small onClick={onRelease} disabled={busy}>
              Release
            </Button>
          ) : null}
          {canConfirm && restriction.status !== "reversed" ? (
            <Button small variant="danger" onClick={onReverse} disabled={busy}>
              Reverse
            </Button>
          ) : null}
        </ButtonRow>
      }
    >
      <div className="button-row">
        <Badge tone={movementTone(restriction.status)}>{movementLabel(restriction.status)}</Badge>
        <Badge tone={restriction.counts_as_restricted ? "success" : "neutral"}>
          {restriction.counts_as_restricted ? "Counted as restricted" : "Not currently counted"}
        </Badge>
        {lostBacking ? <Badge tone="danger">Underlying receipt reversed</Badge> : null}
      </div>

      {lostBacking ? (
        <p className="footnote">
          This escrow was properly confirmed and is kept on the record as such.
          It no longer holds project cash, because the buyer receipt behind it
          was reversed — there is nothing left for it to hold.
        </p>
      ) : null}

      <KeyValueGrid columns={3}>
        <KeyValue label="Receipt amount" value={money(restriction.receipt_amount, null)} mono />
        <KeyValue label="Restricted" value={money(restriction.restricted_amount, null)} mono />
        <KeyValue label="Released" value={money(restriction.released_amount, null)} mono />
        <KeyValue
          label="Still held"
          value={money(restriction.outstanding_restricted, null)}
          mono
        />
        <KeyValue label="Reason" value={restriction.reason} />
        <KeyValue label="Reference" value={restriction.source_reference ?? "—"} />
      </KeyValueGrid>

      {restriction.releases.length > 0 ? (
        <TableScroll label={`Releases against receipt ${restriction.receipt_number ?? ""}`} compact>
          <thead>
            <tr>
              <th scope="col">Released</th>
              <th scope="col" className="num">Amount</th>
              <th scope="col">Status</th>
              <th scope="col">Currently freeing</th>
              <th scope="col">Certification</th>
              <th scope="col" />
            </tr>
          </thead>
          <tbody>
            {restriction.releases.map((release) => (
              <tr key={release.id}>
                <td>{businessDate(release.release_date)}</td>
                <td className="num">{money(release.amount, null)}</td>
                <td>
                  <Badge tone={movementTone(release.status)}>{movementLabel(release.status)}</Badge>
                </td>
                <td>
                  {release.counts_as_released ? (
                    "Yes"
                  ) : release.status === "confirmed" && !release.restriction_counts ? (
                    <span>No — the escrow it frees no longer stands</span>
                  ) : (
                    "No"
                  )}
                </td>
                <td className="cell-prose">{release.certification_reference ?? "—"}</td>
                <td>
                  <ButtonRow>
                    {canConfirm && release.status === "recorded" ? (
                      <Button small onClick={() => onConfirmRelease(release.id)} disabled={busy}>
                        Confirm
                      </Button>
                    ) : null}
                    {canConfirm && release.status !== "reversed" ? (
                      <Button
                        small
                        variant="danger"
                        onClick={() => onReverseRelease(release.id)}
                        disabled={busy}
                      >
                        Reverse
                      </Button>
                    ) : null}
                  </ButtonRow>
                </td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      ) : null}
    </SubPanel>
  );
}

function ReleaseDialog({
  restriction,
  busy,
  onCancel,
  onSubmit,
}: {
  restriction: CashflowRestriction;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (body: Record<string, unknown>) => void;
}) {
  const [amount, setAmount] = useState("");
  const [releaseDate, setReleaseDate] = useState("");
  const [certification, setCertification] = useState("");

  return (
    <FormDialog
      title="Release from escrow"
      description={`Up to ${money(restriction.outstanding_restricted, null)} is still held against this receipt. The server re-proves that ceiling under lock.`}
      confirmLabel="Record release"
      busy={busy}
      disabled={!amount || !releaseDate}
      onCancel={onCancel}
      onSubmit={() =>
        onSubmit({
          amount,
          release_date: releaseDate,
          certification_reference: certification || null,
        })
      }
    >
      <FieldRow>
        <Field label="Amount">
          <MoneyInput code={null} value={amount} onChange={setAmount} />
        </Field>
        <Field label="Release date">
          <input
            className="input"
            type="date"
            value={releaseDate}
            onChange={(event) => setReleaseDate(event.target.value)}
          />
        </Field>
      </FieldRow>
      <Field label="Certification reference" optional>
        <input
          className="input"
          value={certification}
          onChange={(event) => setCertification(event.target.value)}
        />
      </Field>
    </FormDialog>
  );
}
