"use client";

import type { MilestoneTriggerOption, PlanInstallment } from "@/lib/api";
import {
  Badge,
  Button,
  MoneyInput,
  RateInput,
  TableScroll,
} from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, money, percent, percentInput } from "@/lib/format";
import {
  DATE_BASED_TRIGGERS,
  REFERENCE_TRIGGERS,
  TRIGGER_TYPES,
  triggerLabel,
  triggerStatusLabel,
  triggerStatusTone,
} from "@/components/projects/payments/labels";

/** One row as the builder holds it, before the server turns it into money. */
export type DraftRow = {
  key: string;
  sequence: number;
  label: string;
  trigger_type: string;
  trigger_reference: string;
  offset_days: string;
  contractual_due_date: string;
  forecast_due_date: string;
  grace_days: string;
  principal_fraction: string;
  principal_amount: string;
  tax_amount: string;
  fee_amount: string;
};

export function emptyRow(sequence: number): DraftRow {
  return {
    key: `row-${sequence}-${Math.random().toString(36).slice(2, 8)}`,
    sequence,
    label: `Instalment ${sequence}`,
    trigger_type: "fixed_date",
    trigger_reference: "",
    offset_days: "",
    contractual_due_date: "",
    forecast_due_date: "",
    grace_days: "0",
    principal_fraction: "",
    principal_amount: "",
    tax_amount: "",
    fee_amount: "",
  };
}

/** Turn a saved instalment back into an editable row. */
export function rowFrom(installment: PlanInstallment): DraftRow {
  return {
    key: installment.id,
    sequence: installment.sequence,
    label: installment.label,
    trigger_type: installment.trigger_type,
    trigger_reference: installment.trigger_reference ?? "",
    offset_days:
      installment.offset_days === null ? "" : String(installment.offset_days),
    contractual_due_date: installment.contractual_due_date ?? "",
    forecast_due_date: installment.forecast_due_date ?? "",
    grace_days: String(installment.grace_days),
    principal_fraction: percentInput(installment.principal_fraction),
    principal_amount: installment.principal_amount,
    tax_amount: installment.tax_amount,
    fee_amount: installment.fee_amount,
  };
}

/**
 * The draft schedule, as a grid.
 *
 * Each row shows only the fields its trigger actually uses: a fixed date wants
 * a date, a relative one wants a number of days, a milestone wants the
 * milestone's reference. Twelve empty inputs beside every row would be twelve
 * chances to fill in the wrong one.
 *
 * Nothing here calculates. The preparer types whichever figure the allocation
 * mode makes authoritative and the server derives the other; the amounts shown
 * beside it are last saved from the server, not computed in the browser.
 */
export function ScheduleEditor({
  rows,
  allocationMode,
  chargeMode,
  currencyId,
  milestones,
  onChange,
  onRemove,
}: {
  rows: DraftRow[];
  allocationMode: string;
  chargeMode: string;
  currencyId: string;
  /**
   * The construction milestones this project actually has, or null where the
   * caller could not read them.
   *
   * Null and empty mean different things and are presented differently. Null is
   * "this person cannot see the programme" — Collections can read the trigger
   * options and a Sales Advisor cannot — and falls back to the free-text field.
   * Empty is "there are no milestones", which is a real answer and one the
   * preparer needs to see rather than an empty dropdown they blame on the
   * software.
   */
  milestones: MilestoneTriggerOption[] | null;
  onChange: (key: string, field: keyof DraftRow, value: string) => void;
  onRemove: (key: string) => void;
}) {
  const currencyCodeOf = useCurrencyCode();
  const code = currencyCodeOf(currencyId);
  const byPercentage = allocationMode === "percentage";
  const manualCharges = chargeMode === "manual";

  return (
    <div className="schedule-editor">
      <table className="table">
        <caption className="visually-hidden">Draft instalments</caption>
        <thead>
          <tr>
            <th scope="col" className="num">
              #
            </th>
            <th scope="col">Label</th>
            <th scope="col">Trigger</th>
            <th scope="col">Trigger detail</th>
            <th scope="col" className="num">
              {byPercentage ? "Share" : "Principal"}
            </th>
            {manualCharges ? (
              <>
                <th scope="col" className="num">
                  Tax
                </th>
                <th scope="col" className="num">
                  Buyer fee
                </th>
              </>
            ) : null}
            <th scope="col" className="num">
              Grace days
            </th>
            <th scope="col">Remove</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              <th scope="row" className="sequence-cell">
                {row.sequence}
              </th>
              <td>
                <input
                  className="input input-label"
                  aria-label={`Label for instalment ${row.sequence}`}
                  value={row.label}
                  onChange={(event) =>
                    onChange(row.key, "label", event.target.value)
                  }
                />
              </td>
              <td>
                <select
                  className="input"
                  aria-label={`Trigger for instalment ${row.sequence}`}
                  value={row.trigger_type}
                  onChange={(event) =>
                    onChange(row.key, "trigger_type", event.target.value)
                  }
                >
                  {TRIGGER_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {triggerLabel(type)}
                    </option>
                  ))}
                </select>
              </td>
              <td>
                <TriggerDetail
                  row={row}
                  milestones={milestones}
                  onChange={onChange}
                />
              </td>
              <td className="num">
                {byPercentage ? (
                  <RateInput
                    aria-label={`Share for instalment ${row.sequence}`}
                    placeholder="25"
                    value={row.principal_fraction}
                    onChange={(value) =>
                      onChange(row.key, "principal_fraction", value)
                    }
                  />
                ) : (
                  <MoneyInput
                    code={code}
                    aria-label={`Principal for instalment ${row.sequence}`}
                    placeholder="0.00"
                    value={row.principal_amount}
                    onChange={(value) =>
                      onChange(row.key, "principal_amount", value)
                    }
                  />
                )}
              </td>
              {manualCharges ? (
                <>
                  <td className="num">
                    <MoneyInput
                      code={code}
                      aria-label={`Tax for instalment ${row.sequence}`}
                      value={row.tax_amount}
                      onChange={(value) =>
                        onChange(row.key, "tax_amount", value)
                      }
                    />
                  </td>
                  <td className="num">
                    <MoneyInput
                      code={code}
                      aria-label={`Buyer fee for instalment ${row.sequence}`}
                      value={row.fee_amount}
                      onChange={(value) =>
                        onChange(row.key, "fee_amount", value)
                      }
                    />
                  </td>
                </>
              ) : null}
              <td className="num">
                <input
                  className="input input-short"
                  inputMode="numeric"
                  aria-label={`Grace days for instalment ${row.sequence}`}
                  value={row.grace_days}
                  onChange={(event) =>
                    onChange(row.key, "grace_days", event.target.value)
                  }
                />
              </td>
              <td>
                <Button
                  small
                  variant="quiet"
                  aria-label={`Remove instalment ${row.sequence}`}
                  onClick={() => onRemove(row.key)}
                >
                  Remove
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {code ? (
        <p className="footnote">
          Amounts are denominated in {code}, taken from the contract. Shares are
          typed as percentages and sent as fractions of one. The server derives{" "}
          {byPercentage
            ? "each amount from its share"
            : "each share from its amount"}
          {manualCharges ? "" : ", and spreads tax and buyer fees pro rata"}.
        </p>
      ) : null}
    </div>
  );
}

/** Only the fields the chosen trigger actually uses. */
function TriggerDetail({
  row,
  milestones,
  onChange,
}: {
  row: DraftRow;
  milestones: MilestoneTriggerOption[] | null;
  onChange: (key: string, field: keyof DraftRow, value: string) => void;
}) {
  if (row.trigger_type === "days_after_spa") {
    return (
      <input
        className="input input-short"
        inputMode="numeric"
        aria-label={`Days after the SPA for instalment ${row.sequence}`}
        placeholder="30"
        value={row.offset_days}
        onChange={(event) =>
          onChange(row.key, "offset_days", event.target.value)
        }
      />
    );
  }
  if (DATE_BASED_TRIGGERS.has(row.trigger_type)) {
    return (
      <input
        className="input input-date"
        type="date"
        aria-label={`Due date for instalment ${row.sequence}`}
        value={row.contractual_due_date}
        onChange={(event) =>
          onChange(row.key, "contractual_due_date", event.target.value)
        }
      />
    );
  }
  const isMilestone = row.trigger_type === "construction_milestone";
  return (
    <div className="trigger-detail">
      {isMilestone && milestones !== null ? (
        <MilestoneSelector
          row={row}
          milestones={milestones}
          onChange={onChange}
        />
      ) : REFERENCE_TRIGGERS.has(row.trigger_type) ? (
        <input
          className="input input-label"
          aria-label={`Trigger reference for instalment ${row.sequence}`}
          placeholder={isMilestone ? "Milestone code" : "What must happen"}
          value={row.trigger_reference}
          onChange={(event) =>
            onChange(row.key, "trigger_reference", event.target.value)
          }
        />
      ) : null}
      <input
        className="input input-date"
        type="date"
        aria-label={`Forecast date for instalment ${row.sequence}`}
        value={row.forecast_due_date}
        onChange={(event) =>
          onChange(row.key, "forecast_due_date", event.target.value)
        }
      />
      <span className="field-hint">
        Forecast only. It never makes the amount due.
      </span>
    </div>
  );
}

/**
 * Which construction milestone this instalment waits on.
 *
 * A selector rather than a text box, and it stores the milestone's **code** —
 * the value construction's certification looks the schedule up by. A typed
 * reference is a trigger that silently never fires: the milestone is certified,
 * nothing matches "Foundations complete" against `FOUNDATION`, and the
 * instalment sits at awaiting while the buyer believes it is due. That failure
 * is invisible until somebody chases a payment that was never raised.
 *
 * A code already on the row that is no longer offered is kept and marked,
 * because a saved schedule must not silently lose its trigger when a milestone
 * is renamed or retired. The person edits it deliberately or leaves it alone.
 *
 * The options carry no cost, no contract and no vendor. Preparing a buyer's
 * schedule is not a reason to see what the build costs, and the server's
 * endpoint is shaped to make sure it cannot be.
 */
function MilestoneSelector({
  row,
  milestones,
  onChange,
}: {
  row: DraftRow;
  milestones: MilestoneTriggerOption[];
  onChange: (key: string, field: keyof DraftRow, value: string) => void;
}) {
  const known = milestones.some(
    (option) => option.code === row.trigger_reference,
  );
  if (milestones.length === 0) {
    return (
      <span className="field-hint">
        This development has no construction milestones yet, so nothing can wait
        on one.
      </span>
    );
  }
  return (
    <select
      className="input"
      aria-label={`Construction milestone for instalment ${row.sequence}`}
      value={row.trigger_reference}
      onChange={(event) =>
        onChange(row.key, "trigger_reference", event.target.value)
      }
    >
      <option value="">Choose a milestone</option>
      {row.trigger_reference && !known ? (
        <option value={row.trigger_reference}>
          {row.trigger_reference} — no longer in the programme
        </option>
      ) : null}
      {milestones.map((option) => (
        <option key={option.code} value={option.code}>
          {option.code} — {option.name}
          {option.is_certified ? " (certified)" : ""}
        </option>
      ))}
    </select>
  );
}

/**
 * A settled schedule, read-only.
 *
 * Three date columns because they are three different facts: what the contract
 * says, what somebody expects, and what has actually happened. Collapsing them
 * into one "due date" is how a forecast becomes a receivable.
 */
export function ScheduleTable({
  installments,
  currencyId,
}: {
  installments: PlanInstallment[];
  currencyId: string;
}) {
  const currencyCodeOf = useCurrencyCode();
  const code = currencyCodeOf(currencyId);

  return (
    <TableScroll label="Instalment schedule" fixedFirst compact>
      <thead>
        <tr>
          <th scope="col" className="num">
            #
          </th>
          <th scope="col">Instalment</th>
          <th scope="col">Trigger</th>
          <th scope="col">Contractual</th>
          <th scope="col">Forecast</th>
          <th scope="col">Due</th>
          <th scope="col" className="num">
            Share
          </th>
          <th scope="col" className="num">
            Principal
          </th>
          <th scope="col" className="num">
            Tax
          </th>
          <th scope="col" className="num">
            Fee
          </th>
          <th scope="col" className="num">
            Total
          </th>
          <th scope="col">Standing</th>
        </tr>
      </thead>
      <tbody>
        {installments.map((row) => (
          <tr key={row.id}>
            <th scope="row" className="sequence-cell">
              {row.sequence}
            </th>
            <td>{row.label}</td>
            <td>
              {triggerLabel(row.trigger_type)}
              {row.trigger_reference ? (
                <>
                  {" "}
                  <span className="subtle">{row.trigger_reference}</span>
                </>
              ) : null}
              {row.offset_days !== null ? (
                <>
                  {" "}
                  <span className="subtle">+{row.offset_days}d</span>
                </>
              ) : null}
            </td>
            <td className="figure">{businessDate(row.contractual_due_date)}</td>
            <td className="figure">{businessDate(row.forecast_due_date)}</td>
            <td className="figure">{businessDate(row.actual_due_date)}</td>
            <td className="num">{percent(row.principal_fraction)}</td>
            <td className="num">{money(row.principal_amount, code)}</td>
            <td className="num">{money(row.tax_amount, code)}</td>
            <td className="num">{money(row.fee_amount, code)}</td>
            <td className="num">{money(row.total_scheduled_amount, code)}</td>
            <td>
              <Badge tone={triggerStatusTone(row.trigger_status)}>
                {triggerStatusLabel(row.trigger_status)}
              </Badge>
            </td>
          </tr>
        ))}
      </tbody>
    </TableScroll>
  );
}
