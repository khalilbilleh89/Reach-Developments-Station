"use client";

import { useCallback, useEffect, useState } from "react";

import {
  Badge,
  Button,
  ButtonRow,
  EmptyState,
  Field,
  FieldRow,
  Form,
  FormActions,
  FormDialog,
  MoneyInput,
  Notice,
  PromptDialog,
  SubPanel,
  TableScroll,
} from "@/components/ui";
import { ApiError, cashflow, collections } from "@/lib/api";
import type {
  CollectionInstallmentRow,
  CollectionSaleSummary,
  Receipt,
  SuggestedAllocation,
} from "@/lib/api";
import { businessDate, isPositive, money, todayISO } from "@/lib/format";

import { allocationStatusLabel, allocationTone, receiptLabel, receiptTone } from "./labels";

/**
 * One sale's cash: recording it, confirming it, and applying it.
 *
 * The operator never types an identifier. The sale, the contract currency and
 * the instalments are all things this screen already knows, so the form asks
 * for the four facts only a person can supply — how much, when, the bank
 * reference and any note.
 *
 * The three figures on every receipt row are deliberate: the amount that
 * arrived, the amount applied to instalments, and what is left unapplied. A
 * receipt whose parts do not add up to its whole is the first sign of a ledger
 * problem, and it should be visible without opening anything.
 */
export function ReceiptPanel({
  projectId,
  saleId,
  summary,
  currencyCode,
  canRecord,
  canConfirm,
  canRestrictCash,
  onChanged,
}: {
  projectId: string;
  saleId: string;
  summary: CollectionSaleSummary;
  currencyCode: string | null;
  canRecord: boolean;
  canConfirm: boolean;
  /**
   * Whether this reader may hold buyer cash back as escrow.
   *
   * Finance alone, and not because they can read Collections: restricting cash
   * is a Cashflow act recorded against the receipt, so the role that governs it
   * is the Cashflow recorder set rather than anything this module owns.
   */
  canRestrictCash: boolean;
  onChanged: () => void;
}) {
  const [receipts, setReceipts] = useState<Receipt[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [form, setForm] = useState({
    amount: "",
    receipt_date: todayISO(),
    bank_reference: "",
    notes: "",
  });
  const [applying, setApplying] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<SuggestedAllocation[]>([]);
  const [allocation, setAllocation] = useState({ installment_id: "", amount: "" });
  const [reversing, setReversing] = useState<{ kind: "receipt" | "allocation"; id: string } | null>(
    null,
  );
  const [restricting, setRestricting] = useState<Receipt | null>(null);

  const load = useCallback(async () => {
    try {
      setReceipts(await collections.receipts(projectId, saleId));
      setError(null);
    } catch (caught) {
      setReceipts(null);
      setError(caught instanceof ApiError ? caught.message : "Could not load the receipts.");
    }
  }, [projectId, saleId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const refresh = async () => {
    await load();
    onChanged();
  };

  const act = async (run: () => Promise<unknown>, done: string) => {
    setBusy(true);
    setError(null);
    try {
      await run();
      setNotice(done);
      await refresh();
    } catch (caught) {
      setNotice(null);
      setError(caught instanceof ApiError ? caught.message : "That did not work.");
    } finally {
      setBusy(false);
    }
  };

  const openAllocation = async (receipt: Receipt) => {
    setApplying(receipt.id);
    setAllocation({ installment_id: "", amount: "" });
    try {
      setSuggestions(await collections.suggestions(projectId, receipt.id));
    } catch {
      setSuggestions([]);
    }
  };

  const outstandingOf = (installmentId: string): CollectionInstallmentRow | undefined =>
    summary.installments.find((row) => row.installment_id === installmentId);

  return (
    <div className="stack">
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      {canRecord ? (
        <SubPanel
          title="Record cash"
          actions={
            <Button onClick={() => setRecording((open) => !open)}>
              {recording ? "Cancel" : "Record a receipt"}
            </Button>
          }
        >
          {recording ? (
            <Form
              onSubmit={(event) => {
                event.preventDefault();
                void act(
                  () =>
                    collections.recordReceipt(projectId, saleId, {
                      amount: form.amount,
                      receipt_date: form.receipt_date,
                      bank_reference: form.bank_reference || null,
                      notes: form.notes || null,
                    }),
                  "Receipt recorded. It counts as cash once Finance confirms it.",
                ).then(() => {
                  setRecording(false);
                  setForm({
                    amount: "",
                    receipt_date: todayISO(),
                    bank_reference: "",
                    notes: "",
                  });
                });
              }}
            >
              <FieldRow columns={3}>
                <Field label="Amount" hint="In the contract's currency. Nothing is converted.">
                  <MoneyInput
                    code={currencyCode}
                    value={form.amount}
                    onChange={(value) => setForm({ ...form, amount: value })}
                    required
                  />
                </Field>
                <Field label="Date received" hint="The day the money arrived. Not a future date.">
                  <input
                    className="input"
                    type="date"
                    value={form.receipt_date}
                    max={todayISO()}
                    onChange={(event) => setForm({ ...form, receipt_date: event.target.value })}
                    required
                  />
                </Field>
                <Field label="Bank reference" optional>
                  <input
                    className="input"
                    value={form.bank_reference}
                    onChange={(event) => setForm({ ...form, bank_reference: event.target.value })}
                  />
                </Field>
              </FieldRow>
              <Field label="Notes">
                <textarea
                  className="input"
                  value={form.notes}
                  rows={2}
                  onChange={(event) => setForm({ ...form, notes: event.target.value })}
                />
              </Field>
              <FormActions>
                <Button type="submit" variant="primary" disabled={busy}>
                  Record receipt
                </Button>
              </FormActions>
            </Form>
          ) : (
            <p className="hint">
              A recorded receipt is a claim that money arrived. It appears here immediately and
              changes no balance until Finance confirms it.
            </p>
          )}
        </SubPanel>
      ) : null}

      {receipts === null ? null : receipts.length === 0 ? (
        <EmptyState
          title="No cash recorded"
          hint="No cash has been recorded for this sale yet."
        />
      ) : (
        <TableScroll label="Receipts">
          <thead>
            <tr>
              <th scope="col">Receipt</th>
              <th scope="col">Date</th>
              <th scope="col" className="num">
                Amount
              </th>
              <th scope="col" className="num">
                Unapplied
              </th>
              <th scope="col">State</th>
              <th scope="col">Reference</th>
              <th scope="col">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {receipts.map((receipt) => (
              <tr key={receipt.id}>
                  <th scope="row" className="mono">
                    {receipt.receipt_number}
                  </th>
                  <td>{businessDate(receipt.receipt_date)}</td>
                  <td className="num">{money(receipt.amount, currencyCode)}</td>
                  <td className="num">
                    {money(receipt.unapplied_amount, currencyCode)}
                  </td>
                  <td>
                    <Badge tone={receiptTone(receipt.status)}>
                      {receiptLabel(receipt.status)}
                    </Badge>
                    {!receipt.counts_as_cash && receipt.status === "recorded" ? (
                      <p className="hint">Not counted as cash yet</p>
                    ) : null}
                    {receipt.reversal_reason ? (
                      <p className="hint">{receipt.reversal_reason}</p>
                    ) : null}
                  </td>
                  <td>{receipt.bank_reference ?? "—"}</td>
                  <td>
                    <ButtonRow>
                      {canConfirm && receipt.status === "recorded" ? (
                        <Button
                          disabled={busy}
                          onClick={() =>
                            void act(
                              () => collections.confirmReceipt(projectId, receipt.id),
                              `${receipt.receipt_number} confirmed. It is now cash.`,
                            )
                          }
                        >
                          Confirm
                        </Button>
                      ) : null}
                      {canConfirm && receipt.status === "confirmed" ? (
                        <Button
                          disabled={busy}
                          onClick={() => setReversing({ kind: "receipt", id: receipt.id })}
                        >
                          Reverse
                        </Button>
                      ) : null}
                      {canRecord && receipt.status !== "reversed" ? (
                        <Button disabled={busy} onClick={() => void openAllocation(receipt)}>
                          Apply
                        </Button>
                      ) : null}
                      {canRestrictCash && receipt.status === "confirmed" ? (
                        <Button disabled={busy} onClick={() => setRestricting(receipt)}>
                          Restrict cash
                        </Button>
                      ) : null}
                    </ButtonRow>
                  </td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      )}

      {receipts?.some((receipt) => receipt.allocations.length > 0) ? (
        <SubPanel title="Where the cash went">
          <TableScroll label="Allocations">
            <thead>
              <tr>
                <th scope="col">Receipt</th>
                <th scope="col">Instalment</th>
                <th scope="col" className="num">
                  Amount
                </th>
                <th scope="col">State</th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {receipts.flatMap((receipt) =>
                receipt.allocations.map((row) => {
                  const target = outstandingOf(row.installment_id);
                  return (
                    <tr key={row.id}>
                      <th scope="row" className="mono">
                        {receipt.receipt_number}
                      </th>
                      <td>
                        {target ? `${target.sequence}. ${target.label}` : "Superseded schedule"}
                      </td>
                      <td className="num">{money(row.amount, currencyCode)}</td>
                      <td>
                        <Badge tone={allocationTone(row.status)}>
                          {allocationStatusLabel(row.status)}
                        </Badge>
                        {row.reversal_reason ? (
                          <p className="hint">{row.reversal_reason}</p>
                        ) : null}
                      </td>
                      <td>
                        {canRecord && row.status === "active" ? (
                          <Button
                            disabled={busy}
                            onClick={() => setReversing({ kind: "allocation", id: row.id })}
                          >
                            Reverse
                          </Button>
                        ) : null}
                      </td>
                    </tr>
                  );
                }),
              )}
            </tbody>
          </TableScroll>
        </SubPanel>
      ) : null}

      {applying ? (
        <SubPanel
          title="Apply this receipt"
          actions={<Button onClick={() => setApplying(null)}>Cancel</Button>}
        >
          {suggestions.length > 0 ? (
            <div className="stack">
              <p className="hint">
                Suggested, oldest actionable instalment first. Change anything you like — the
                rows you post are what counts, not the suggestion.
              </p>
              <TableScroll label="Suggested allocation">
                <thead>
                  <tr>
                    <th scope="col">Instalment</th>
                    <th scope="col">Due</th>
                    <th scope="col" className="num">
                      Outstanding
                    </th>
                    <th scope="col" className="num">
                      Suggested
                    </th>
                    <th scope="col">
                      <span className="visually-hidden">Use</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {suggestions.map((row) => (
                    <tr key={row.installment_id}>
                      <th scope="row">
                        {row.sequence}. {row.label}
                      </th>
                      <td>{businessDate(row.due_date)}</td>
                      <td className="num">{money(row.outstanding, currencyCode)}</td>
                      <td className="num">{money(row.amount, currencyCode)}</td>
                      <td>
                        <Button
                          onClick={() =>
                            setAllocation({
                              installment_id: row.installment_id,
                              amount: row.amount,
                            })
                          }
                        >
                          Use
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </TableScroll>
            </div>
          ) : (
            <p className="hint">All of this receipt is applied, or nothing is outstanding.</p>
          )}

          <Form
            onSubmit={(event) => {
              event.preventDefault();
              void act(
                () =>
                  collections.allocate(projectId, applying, {
                    installment_id: allocation.installment_id,
                    amount: allocation.amount,
                  }),
                "Cash applied.",
              ).then(() => setAllocation({ installment_id: "", amount: "" }));
            }}
          >
            <Field label="Instalment">
              <select
                className="input"
                value={allocation.installment_id}
                onChange={(event) =>
                  setAllocation({ ...allocation, installment_id: event.target.value })
                }
                required
              >
                <option value="">Choose an instalment</option>
                {summary.installments
                  .filter((row) => isPositive(row.outstanding))
                  .map((row) => (
                    <option key={row.installment_id} value={row.installment_id}>
                      {row.sequence}. {row.label} — {money(row.outstanding, currencyCode)}{" "}
                      outstanding
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="Amount" hint="Anything left over stays unapplied and visible.">
              <MoneyInput
                code={currencyCode}
                value={allocation.amount}
                onChange={(value) => setAllocation({ ...allocation, amount: value })}
                required
              />
            </Field>
            <FormActions>
              <Button type="submit" variant="primary" disabled={busy}>
                Apply cash
              </Button>
            </FormActions>
          </Form>
        </SubPanel>
      ) : null}

      {reversing ? (
        <PromptDialog
          title={reversing.kind === "receipt" ? "Reverse this receipt" : "Reverse this allocation"}
          hint={
            reversing.kind === "receipt"
              ? "The receipt stays on the record, reversed, and every allocation from it is reversed with it. The receivable reopens."
              : "The receipt stays confirmed. This amount goes back to unapplied cash, where it can be applied somewhere else."
          }
          label="Reason"
          confirmLabel="Reverse"
          busy={busy}
          onCancel={() => setReversing(null)}
          onSubmit={(reason) => {
            const target = reversing;
            setReversing(null);
            void act(
              () =>
                target.kind === "receipt"
                  ? collections.reverseReceipt(projectId, target.id, reason)
                  : collections.reverseAllocation(projectId, target.id, reason),
              "Reversed.",
            );
          }}
        />
      ) : null}

      {restricting ? (
        <RestrictCashDialog
          receipt={restricting}
          currencyCode={currencyCode}
          busy={busy}
          onCancel={() => setRestricting(null)}
          onSubmit={(body) => {
            const target = restricting;
            setRestricting(null);
            void act(
              () => cashflow.recordRestriction(projectId, target.id, body),
              `Escrow recorded against ${target.receipt_number}. It holds cash back once Finance confirms it.`,
            );
          }}
        />
      ) : null}
    </div>
  );
}

/**
 * Holding part of a confirmed receipt back as escrow.
 *
 * Started from the receipt rather than from the Cashflow workspace, because the
 * receipt is the thing that owns the cash: the operator picks a row they can
 * see and supplies the two facts only a person knows — how much is held and
 * under what instrument. The identifier travels with the row and is never typed
 * or shown.
 *
 * Every rule about the amount belongs to the server and is left there. It knows
 * the receipt still stands, what it was worth, and what is already held against
 * it; a ceiling copied into this form would be a second opinion that drifts.
 */
function RestrictCashDialog({
  receipt,
  currencyCode,
  busy,
  onCancel,
  onSubmit,
}: {
  receipt: Receipt;
  currencyCode: string | null;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (body: Record<string, unknown>) => void;
}) {
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [sourceReference, setSourceReference] = useState("");
  const [notes, setNotes] = useState("");

  return (
    <FormDialog
      title={`Restrict cash from ${receipt.receipt_number}`}
      description="Escrowed cash stays in the project's total. It leaves the balance the developer may spend, which is the figure the workspace leads on."
      confirmLabel="Record escrow"
      busy={busy}
      disabled={!amount || !reason.trim()}
      onCancel={onCancel}
      onSubmit={() =>
        onSubmit({
          restricted_amount: amount,
          reason: reason.trim(),
          source_reference: sourceReference.trim() || null,
          notes: notes.trim() || null,
        })
      }
    >
      <FieldRow>
        <Field
          label="Amount held"
          hint={`Out of ${money(receipt.amount, currencyCode)} received on ${businessDate(receipt.receipt_date)}.`}
        >
          <MoneyInput code={currencyCode} value={amount} onChange={setAmount} />
        </Field>
        <Field label="Reference" optional hint="The escrow account or trust deed, if there is one.">
          <input
            className="input"
            value={sourceReference}
            onChange={(event) => setSourceReference(event.target.value)}
          />
        </Field>
      </FieldRow>
      <Field label="Reason" hint="Why this cash may not be spent. An auditor reads this.">
        <input className="input" value={reason} onChange={(event) => setReason(event.target.value)} />
      </Field>
      <Field label="Notes" optional>
        <textarea
          className="input"
          rows={2}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
        />
      </Field>
    </FormDialog>
  );
}
