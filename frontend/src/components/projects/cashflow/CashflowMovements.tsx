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
  Loading,
  MoneyInput,
  Notice,
  PromptDialog,
  TableScroll,
} from "@/components/ui";
import type { Answer } from "@/lib/answer";
import type { CashflowDevelopmentMovement, CashflowFinancingMovement } from "@/lib/api";
import { businessDate, money } from "@/lib/format";

import {
  DEVELOPMENT_CATEGORY_OPTIONS,
  FINANCING_TYPE_OPTIONS,
  categoryLabel,
  movementLabel,
  movementTone,
} from "./labels";

type Movement = CashflowDevelopmentMovement | CashflowFinancingMovement;

/**
 * The cash this module owns: development spend, and financing in and out.
 *
 * Recording a movement is a claim one person made. Confirming it is the second
 * person saying the money actually moved, and only then does it reach a cash
 * position. The two must not look alike on screen — the whole maker/checker
 * control depends on a reader being able to tell "we say we paid this" from "we
 * paid this" at a glance — so the status is in words and the column that
 * matters is `counts_as_cash`.
 *
 * Whether *this* person may confirm *this* row is the server's decision: it
 * compares confirmer to recorder by user identifier, so one person holding both
 * Finance and Approver / CFO is still one person. The button is offered on
 * role; the refusal, when it comes, is shown as the server worded it.
 */
export function CashflowMovements({
  development,
  financing,
  currency,
  currencyId,
  canRecord,
  canConfirm,
  busy,
  error,
  onRecordDevelopment,
  onConfirmDevelopment,
  onReverseDevelopment,
  onRecordFinancing,
  onConfirmFinancing,
  onReverseFinancing,
}: {
  development: Answer<CashflowDevelopmentMovement[]>;
  financing: Answer<CashflowFinancingMovement[]>;
  currency: string | null;
  currencyId: string | null;
  canRecord: boolean;
  canConfirm: boolean;
  busy: boolean;
  error: string | null;
  onRecordDevelopment: (body: Record<string, unknown>) => void;
  onConfirmDevelopment: (movementId: string) => void;
  onReverseDevelopment: (movementId: string, reason: string) => void;
  onRecordFinancing: (body: Record<string, unknown>) => void;
  onConfirmFinancing: (movementId: string) => void;
  onReverseFinancing: (movementId: string, reason: string) => void;
}) {
  const [recording, setRecording] = useState<"development" | "financing" | null>(null);
  const [reversing, setReversing] = useState<{ kind: "development" | "financing"; id: string } | null>(
    null,
  );

  return (
    <div className="stack">
      {error ? <Notice tone="error">{error}</Notice> : null}

      <Card
        title="Development cash"
        description="Consultants, permits, marketing and the rest of the project's own spend."
        actions={
          canRecord ? (
            <Button small onClick={() => setRecording("development")} disabled={busy}>
              Record movement
            </Button>
          ) : undefined
        }
      >
        <MovementTable
          answer={development}
          currency={currency}
          canConfirm={canConfirm}
          busy={busy}
          emptyTitle="No development cash recorded"
          emptyHint="Consultants, permits and insurance paid by the developer are recorded here, then confirmed by a second person."
          onConfirm={onConfirmDevelopment}
          onReverse={(id) => setReversing({ kind: "development", id })}
          describe={(row) => categoryLabel((row as CashflowDevelopmentMovement).category)}
          direction={() => "Cash out"}
        />
      </Card>

      <Card
        title="Financing cash"
        description="Equity and debt, in and out. No amortisation, no covenants — only cash that moved."
        actions={
          canRecord ? (
            <Button small onClick={() => setRecording("financing")} disabled={busy}>
              Record movement
            </Button>
          ) : undefined
        }
      >
        <MovementTable
          answer={financing}
          currency={currency}
          canConfirm={canConfirm}
          busy={busy}
          emptyTitle="No financing cash recorded"
          emptyHint="Equity contributions, debt drawdowns and the payments back out are recorded here."
          onConfirm={onConfirmFinancing}
          onReverse={(id) => setReversing({ kind: "financing", id })}
          describe={(row) => categoryLabel((row as CashflowFinancingMovement).movement_type)}
          direction={(row) =>
            (row as CashflowFinancingMovement).flow_direction === "inflow" ? "Cash in" : "Cash out"
          }
        />
      </Card>

      {recording ? (
        <RecordMovementDialog
          kind={recording}
          currency={currency}
          currencyId={currencyId}
          busy={busy}
          onCancel={() => setRecording(null)}
          onSubmit={(body) => {
            if (recording === "development") onRecordDevelopment(body);
            else onRecordFinancing(body);
            setRecording(null);
          }}
        />
      ) : null}

      {reversing ? (
        <PromptDialog
          title="Reverse this movement"
          label="Why is it being reversed?"
          hint="Kept on the record. The movement is withdrawn from the cash position, not deleted."
          confirmLabel="Reverse"
          busy={busy}
          onCancel={() => setReversing(null)}
          onSubmit={(reason) => {
            if (reversing.kind === "development") onReverseDevelopment(reversing.id, reason);
            else onReverseFinancing(reversing.id, reason);
            setReversing(null);
          }}
        />
      ) : null}
    </div>
  );
}

function MovementTable({
  answer,
  currency,
  canConfirm,
  busy,
  emptyTitle,
  emptyHint,
  onConfirm,
  onReverse,
  describe,
  direction,
}: {
  answer: Answer<Movement[]>;
  currency: string | null;
  canConfirm: boolean;
  busy: boolean;
  emptyTitle: string;
  emptyHint: string;
  onConfirm: (movementId: string) => void;
  onReverse: (movementId: string) => void;
  describe: (row: Movement) => string;
  direction: (row: Movement) => string;
}) {
  if (answer.status === "loading") return <Loading label="Loading movements" shape="rows" />;
  if (answer.status === "denied") {
    return <Notice tone="info">These movements are not available to your role.</Notice>;
  }
  if (answer.status === "failed") return <Notice tone="error">{answer.message}</Notice>;
  if (answer.status === "off") return null;
  if (answer.data.length === 0) return <EmptyState title={emptyTitle} hint={emptyHint} />;

  return (
    <TableScroll label={emptyTitle} compact>
      <thead>
        <tr>
          <th scope="col">Reference</th>
          <th scope="col">What</th>
          <th scope="col">Direction</th>
          <th scope="col">Date</th>
          <th scope="col" className="num">Amount</th>
          <th scope="col">Status</th>
          <th scope="col">Counts as cash</th>
          <th scope="col">Evidence</th>
          <th scope="col" />
        </tr>
      </thead>
      <tbody>
        {answer.data.map((row) => (
          <tr key={row.id}>
            <th scope="row">{row.movement_reference}</th>
            <td>{describe(row)}</td>
            <td>{direction(row)}</td>
            <td>{businessDate(row.movement_date)}</td>
            <td className="num">{money(row.amount, row.currency_code ?? currency)}</td>
            <td>
              <Badge tone={movementTone(row.status)}>{movementLabel(row.status)}</Badge>
            </td>
            <td>{row.counts_as_cash ? "Yes" : "No"}</td>
            <td className="cell-prose">{row.evidence_reference ?? row.bank_reference ?? "—"}</td>
            <td>
              <ButtonRow>
                {canConfirm && row.status === "recorded" ? (
                  <Button small onClick={() => onConfirm(row.id)} disabled={busy}>
                    Confirm
                  </Button>
                ) : null}
                {canConfirm && row.status === "confirmed" ? (
                  <Button small variant="danger" onClick={() => onReverse(row.id)} disabled={busy}>
                    Reverse
                  </Button>
                ) : null}
              </ButtonRow>
            </td>
          </tr>
        ))}
      </tbody>
    </TableScroll>
  );
}

function RecordMovementDialog({
  kind,
  currency,
  currencyId,
  busy,
  onCancel,
  onSubmit,
}: {
  kind: "development" | "financing";
  currency: string | null;
  currencyId: string | null;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (body: Record<string, unknown>) => void;
}) {
  const options = kind === "development" ? DEVELOPMENT_CATEGORY_OPTIONS : FINANCING_TYPE_OPTIONS;
  const [what, setWhat] = useState(options[0]?.value ?? "");
  const [amount, setAmount] = useState("");
  const [movementDate, setMovementDate] = useState("");
  const [counterparty, setCounterparty] = useState("");
  const [bankReference, setBankReference] = useState("");

  return (
    <FormDialog
      title={kind === "development" ? "Record development cash" : "Record financing cash"}
      description="Recording is a claim, not cash. A second person confirms it before it reaches any position."
      confirmLabel="Record"
      busy={busy}
      disabled={!what || !amount || !movementDate || !currencyId}
      onCancel={onCancel}
      onSubmit={() =>
        onSubmit({
          ...(kind === "development" ? { category: what } : { movement_type: what }),
          amount,
          movement_date: movementDate,
          currency_id: currencyId,
          counterparty_reference: counterparty || null,
          bank_reference: bankReference || null,
        })
      }
    >
      {currencyId ? null : (
        <Notice tone="error">
          This project&rsquo;s base currency could not be resolved, so a movement
          cannot be recorded against it.
        </Notice>
      )}
      <Field label={kind === "development" ? "Category" : "Type"}>
        <select className="input" value={what} onChange={(event) => setWhat(event.target.value)}>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </Field>
      <FieldRow>
        <Field label="Amount">
          <MoneyInput code={currency} value={amount} onChange={setAmount} />
        </Field>
        <Field label="Movement date">
          <input
            className="input"
            type="date"
            value={movementDate}
            onChange={(event) => setMovementDate(event.target.value)}
          />
        </Field>
      </FieldRow>
      <FieldRow>
        <Field label="Counterparty" optional>
          <input
            className="input"
            value={counterparty}
            onChange={(event) => setCounterparty(event.target.value)}
          />
        </Field>
        <Field label="Bank reference" optional>
          <input
            className="input"
            value={bankReference}
            onChange={(event) => setBankReference(event.target.value)}
          />
        </Field>
      </FieldRow>
    </FormDialog>
  );
}
