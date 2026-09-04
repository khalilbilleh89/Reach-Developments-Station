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
  RateInput,
  SectionHeader,
  TableScroll,
} from "@/components/ui";
import { useAnswer } from "@/lib/answer";
import type { Answer } from "@/lib/answer";
import { construction } from "@/lib/api";
import type { CashflowForecastDetail, CashflowForecastVersion, CostCode } from "@/lib/api";
import { businessDate, money, percent } from "@/lib/format";

import {
  categoryLabel,
  checkLabel,
  FORECAST_OPEN_STATUSES,
  FORECAST_REFRESHABLE_STATUSES,
  DEVELOPMENT_CATEGORY_OPTIONS,
  FINANCING_TYPE_OPTIONS,
  forecastIsRefreshable,
  forecastLabel,
  forecastTone,
  sourceKindLabel,
} from "./labels";

/**
 * The governed statement of what the project expects to receive and spend.
 *
 * A forecast is a version with a ladder, not a spreadsheet: prepared, submitted,
 * approved by somebody other than the preparer, and put in force. What it was
 * measured against is pinned when it is created — the construction forecast
 * whose remaining cost it schedules, and the buyer schedule frozen underneath
 * it — so a version can be reopened years later and read exactly as it read
 * when it was approved.
 *
 * Every governance action here is offered on role and decided by the server.
 * The maker/checker rule in particular is enforced by user identifier, so a
 * refusal is shown in the server's own words rather than predicted here.
 */
export function CashflowForecasts({
  projectId,
  versions,
  detail,
  selected,
  onSelect,
  canPrepare,
  canApprove,
  canActivate,
  busy,
  error,
  currency,
  onCreate,
  onSubmit,
  onApprove,
  onReject,
  onDiscard,
  onActivate,
  onRefreshSnapshot,
  onSetLine,
}: {
  projectId: string;
  versions: Answer<CashflowForecastVersion[]>;
  detail: Answer<CashflowForecastDetail>;
  selected: string | null;
  onSelect: (versionId: string) => void;
  canPrepare: boolean;
  canApprove: boolean;
  canActivate: boolean;
  busy: boolean;
  error: string | null;
  currency: string | null;
  onCreate: (body: Record<string, unknown>) => void;
  onSubmit: (versionId: string) => void;
  onApprove: (versionId: string, reason: string) => void;
  onReject: (versionId: string, reason: string) => void;
  onDiscard: (versionId: string, reason: string) => void;
  onActivate: (versionId: string) => void;
  onRefreshSnapshot: (versionId: string) => void;
  onSetLine: (versionId: string, body: Record<string, unknown>) => void;
}) {
  const [creating, setCreating] = useState(false);
  /**
   * The version already occupying the project's one open slot, if the list says so.
   *
   * A convenience only: the server owns this rule and refuses regardless. What
   * the screen adds is telling a preparer *which* version is in the way, before
   * they fill in a form that cannot be saved.
   */
  const openVersion =
    versions.status === "ready"
      ? (versions.data.find((entry) => FORECAST_OPEN_STATUSES.has(entry.status)) ?? null)
      : null;
  const [reasonFor, setReasonFor] = useState<"approve" | "reject" | "withdraw" | "discard" | null>(null);

  return (
    <div className="stack">
      {error ? <Notice tone="error">{error}</Notice> : null}

      <Card
        title="Forecast versions"
        description="Each one states what it was measured against, and stays readable exactly as approved."
        actions={
          canPrepare ? (
            <Button small onClick={() => setCreating(true)} disabled={busy || openVersion !== null}>
              New forecast
            </Button>
          ) : undefined
        }
      >
      {canPrepare && openVersion ? (
          <Notice tone="info">
            Version {openVersion.version_number} ({forecastLabel(openVersion.status)}) is still open.
            Finish or close it before preparing another — two open forecasts are two answers to one
            question.
          </Notice>
        ) : null}
        {versions.status === "loading" ? <Loading label="Loading forecasts" shape="rows" /> : null}
        {versions.status === "denied" ? (
          <Notice tone="info">Forecasts are not available to your role.</Notice>
        ) : null}
        {versions.status === "failed" ? <Notice tone="error">{versions.message}</Notice> : null}
        {versions.status === "ready" ? (
          versions.data.length === 0 ? (
            <EmptyState
              title="No forecast has been prepared"
              hint="A forecast pins the construction forecast it schedules and freezes the buyer schedule it was built on. Until one is in force, only cash that has moved is reported."
            />
          ) : (
            <TableScroll label="Cashflow forecast versions" compact>
              <thead>
                <tr>
                  <th scope="col">Version</th>
                  <th scope="col">Status</th>
                  <th scope="col">As at</th>
                  <th scope="col">Horizon</th>
                  <th scope="col" className="num">Opening usable</th>
                  <th scope="col" className="num">Opening restricted</th>
                  <th scope="col" className="num">Discount rate</th>
                  <th scope="col">Construction basis</th>
                  <th scope="col" className="num">Instalments</th>
                  <th scope="col">Why</th>
                </tr>
              </thead>
              <tbody>
                {versions.data.map((version) => (
                  <tr key={version.id} aria-current={version.id === selected ? "true" : undefined}>
                    <th scope="row">
                      <button type="button" className="button-link" onClick={() => onSelect(version.id)}>
                        Version {version.version_number}
                      </button>
                    </th>
                    <td>
                      <Badge tone={forecastTone(version.status)}>
                        {forecastLabel(version.status)}
                      </Badge>
                    </td>
                    <td>{businessDate(version.as_of_date)}</td>
                    <td>
                      {businessDate(version.forecast_start_month)} —{" "}
                      {businessDate(version.forecast_end_month)}
                    </td>
                    <td className="num">
                      {money(version.opening_unrestricted_cash, version.currency_code ?? currency)}
                    </td>
                    <td className="num">
                      {money(version.opening_restricted_cash, version.currency_code ?? currency)}
                    </td>
                    <td className="num">{percent(version.discount_rate_per_period)}</td>
                    <td>
                      {version.construction_forecast_version_number === null
                        ? "—"
                        : `Version ${version.construction_forecast_version_number}`}
                    </td>
                    <td className="num">{version.installments_in_snapshot}</td>
                    <td className="cell-prose">{version.change_reason}</td>
                  </tr>
                ))}
              </tbody>
            </TableScroll>
          )
        ) : null}
      </Card>

      {selected ? (
        <ForecastDetail
          projectId={projectId}
          detail={detail}
          currency={currency}
          canPrepare={canPrepare}
          canApprove={canApprove}
          canActivate={canActivate}
          busy={busy}
          onSubmit={() => onSubmit(selected)}
          onAskApprove={() => setReasonFor("approve")}
          onAskReject={() => setReasonFor("reject")}
          onAskWithdraw={() => setReasonFor("withdraw")}
          onAskDiscard={() => setReasonFor("discard")}
          onActivate={() => onActivate(selected)}
          onRefreshSnapshot={() => onRefreshSnapshot(selected)}
          onSetLine={(body) => onSetLine(selected, body)}
        />
      ) : null}

      {creating ? (
        <CreateForecastDialog
          currency={currency}
          busy={busy}
          onCancel={() => setCreating(false)}
          onSubmit={(body) => {
            onCreate(body);
            setCreating(false);
          }}
        />
      ) : null}

      {reasonFor && selected ? (
        <PromptDialog
          title={REASON_WORDS[reasonFor].title}
          label={REASON_WORDS[reasonFor].label}
          hint={REASON_WORDS[reasonFor].hint}
          confirmLabel={REASON_WORDS[reasonFor].confirm}
          busy={busy}
          onCancel={() => setReasonFor(null)}
          onSubmit={(reason) => {
            // A withdrawal is the same act as a rejection to the server — this
            // version will not proceed — and a different one to the reader,
            // because the approval it is undoing really happened.
            if (reasonFor === "approve") onApprove(selected, reason);
            else if (reasonFor === "discard") onDiscard(selected, reason);
            else onReject(selected, reason);
            setReasonFor(null);
          }}
        />
      ) : null}
    </div>
  );
}

function ForecastDetail({
  projectId,
  detail,
  currency,
  canPrepare,
  canApprove,
  canActivate,
  busy,
  onSubmit,
  onAskApprove,
  onAskReject,
  onAskWithdraw,
  onAskDiscard,
  onActivate,
  onRefreshSnapshot,
  onSetLine,
}: {
  projectId: string;
  detail: Answer<CashflowForecastDetail>;
  currency: string | null;
  canPrepare: boolean;
  canApprove: boolean;
  canActivate: boolean;
  busy: boolean;
  onSubmit: () => void;
  onAskApprove: () => void;
  onAskReject: () => void;
  onAskWithdraw: () => void;
  onAskDiscard: () => void;
  onActivate: () => void;
  onRefreshSnapshot: () => void;
  onSetLine: (body: Record<string, unknown>) => void;
}) {
  const [editingLine, setEditingLine] = useState(false);

  if (detail.status === "loading") return <Loading label="Loading the forecast" shape="rows" />;
  if (detail.status === "denied") {
    return <Notice tone="info">This forecast is not available to your role.</Notice>;
  }
  if (detail.status === "failed") return <Notice tone="error">{detail.message}</Notice>;
  if (detail.status === "off") return null;

  const version = detail.data;
  // Three different permissions, and none of them is "not yet finished". A line
  // may be edited on a draft alone. The buyer schedule may be re-pinned while
  // the version is still refreshable — draft or submitted, never approved,
  // because re-reading a schedule under a recorded signature changes what was
  // signed for. And an approved version that can no longer be activated needs a
  // way out, or it holds the project's one open slot with nothing able to move
  // it. Rejected, active and superseded are history and offer nothing.
  const isDraft = version.status === "draft";
  const isRefreshable = forecastIsRefreshable(version.status);
  const isApproved = version.status === "approved";
  const failedChecks = version.construction_reconciliation.filter((check) => !check.passed);

  return (
    <Card
      title={`Version ${version.version_number}`}
      description={version.change_reason}
      actions={
        <ButtonRow>
          {canPrepare && isDraft ? (
            <Button small onClick={() => setEditingLine(true)} disabled={busy}>
              Add or change a line
            </Button>
          ) : null}
          {canPrepare && isRefreshable ? (
            <Button small variant="quiet" onClick={onRefreshSnapshot} disabled={busy}>
              Refresh buyer schedule
            </Button>
          ) : null}
          {canPrepare && isDraft ? (
            <Button small onClick={onSubmit} disabled={busy}>
              Submit
            </Button>
          ) : null}
          {canPrepare && isDraft ? (
            <Button small variant="danger" onClick={onAskDiscard} disabled={busy}>
              Discard draft
            </Button>
          ) : null}
          {canApprove && version.status === "submitted" ? (
            <>
              <Button small onClick={onAskApprove} disabled={busy}>
                Approve
              </Button>
              <Button small variant="danger" onClick={onAskReject} disabled={busy}>
                Reject
              </Button>
            </>
          ) : null}
          {canActivate && isApproved ? (
            <Button small onClick={onActivate} disabled={busy}>
              Put in force
            </Button>
          ) : null}
          {canApprove && isApproved ? (
            <Button small variant="danger" onClick={onAskWithdraw} disabled={busy}>
              Withdraw approval
            </Button>
          ) : null}
        </ButtonRow>
      }
    >
      <div className="button-row">
        <Badge tone={forecastTone(version.status)}>{forecastLabel(version.status)}</Badge>
      </div>

      <Staleness staleness={version.staleness} status={version.status} />

      <KeyValueGrid columns={3}>
        <KeyValue label="Taken as at" value={businessDate(version.as_of_date)} />
        <KeyValue
          label="Horizon"
          value={`${businessDate(version.forecast_start_month)} — ${businessDate(version.forecast_end_month)}`}
        />
        <KeyValue
          label="Discount rate per period"
          value={percent(version.discount_rate_per_period)}
          mono
        />
        <KeyValue
          label="Opening usable cash"
          value={money(version.opening_unrestricted_cash, currency)}
          mono
        />
        <KeyValue
          label="Opening restricted cash"
          value={money(version.opening_restricted_cash, currency)}
          mono
        />
        <KeyValue label="Opening total cash" value={money(version.opening_total_cash, currency)} mono />
      </KeyValueGrid>

      <SectionHeader title="Construction reconciliation" />
      {version.construction_reconciliation.length === 0 ? (
        <p className="footnote">
          This forecast names no construction forecast, so there is nothing to
          reconcile its build schedule against.
        </p>
      ) : (
        <>
          {failedChecks.length > 0 ? (
            <Notice tone="warning">
              {failedChecks.length === 1
                ? "One check does not reconcile."
                : `${failedChecks.length} checks do not reconcile.`}{" "}
              Every cost code the construction forecast carries must appear here,
              and its months must total its remaining cost exactly.
            </Notice>
          ) : null}
          <TableScroll label="Construction reconciliation checks" compact>
            <thead>
              <tr>
                <th scope="col">Check</th>
                <th scope="col">Result</th>
                <th scope="col" className="num">Expected</th>
                <th scope="col" className="num">Scheduled</th>
                <th scope="col">What it means</th>
              </tr>
            </thead>
            <tbody>
              {version.construction_reconciliation.map((check) => (
                <tr key={check.name}>
                  <th scope="row">{checkLabel(check.name)}</th>
                  <td>
                    <Badge tone={check.passed ? "success" : "danger"}>
                      {check.passed ? "Reconciles" : "Does not reconcile"}
                    </Badge>
                  </td>
                  <td className="num">{check.expected ?? "—"}</td>
                  <td className="num">{check.actual ?? "—"}</td>
                  <td className="cell-prose">{check.detail}</td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        </>
      )}

      <SectionHeader title="Forecast lines" />
      {version.lines.length === 0 ? (
        <EmptyState
          title="Nothing scheduled yet"
          hint="A forecast says when the project expects cash to move. Construction lines must name the cost code they schedule."
        />
      ) : (
        <TableScroll label="Forecast lines" compact>
          <thead>
            <tr>
              <th scope="col">Month</th>
              <th scope="col">Source</th>
              <th scope="col">What</th>
              <th scope="col">Cost code</th>
              <th scope="col">Direction</th>
              <th scope="col" className="num">Amount</th>
              <th scope="col">Note</th>
            </tr>
          </thead>
          <tbody>
            {version.lines.map((line) => (
              <tr key={line.id}>
                <th scope="row">{businessDate(line.period_month)}</th>
                <td>{sourceKindLabel(line.source_kind)}</td>
                <td>{categoryLabel(line.category)}</td>
                <td>{line.construction_cost_code ?? "—"}</td>
                <td>{line.flow_direction === "inflow" ? "Cash in" : "Cash out"}</td>
                <td className="num">{money(line.amount, currency)}</td>
                <td className="cell-prose">{line.note ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      )}
      <p className="footnote">
        These are the amounts as approved. A live report shows what is still
        expected against each of them — the governed figure less what has already
        been paid or received since this forecast was cut.
      </p>

      <SectionHeader title="Buyer schedule frozen underneath this version" />
      {version.customer_schedule.length === 0 ? (
        <p className="footnote">No governing buyer instalments were in force at this cutoff.</p>
      ) : (
        <TableScroll label="Frozen buyer schedule" compact>
          <thead>
            <tr>
              <th scope="col">Expected</th>
              <th scope="col" className="num">Amount</th>
              <th scope="col">Trigger</th>
              <th scope="col">Standing</th>
              <th scope="col">Contractual date</th>
            </tr>
          </thead>
          <tbody>
            {version.customer_schedule.map((row) => (
              <tr key={row.installment_id}>
                <th scope="row">{businessDate(row.chosen_forecast_date)}</th>
                <td className="num">{money(row.amount, currency)}</td>
                <td>{row.trigger_type.replace(/_/g, " ")}</td>
                <td>{row.trigger_status.replace(/_/g, " ")}</td>
                <td>{row.contractual_due_date ? businessDate(row.contractual_due_date) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      )}

      {editingLine ? (
        <ForecastLineDialog
          projectId={projectId}
          currency={currency}
          busy={busy}
          onCancel={() => setEditingLine(false)}
          onSubmit={(body) => {
            onSetLine(body);
            setEditingLine(false);
          }}
        />
      ) : null}
    </Card>
  );
}

/**
 * Whether the sources underneath this version have moved, and which one.
 *
 * Two independent things can change while a forecast waits for a signature, and
 * they need different answers: a customer schedule can be refreshed here, while
 * a construction forecast that has been superseded needs a new cashflow version
 * built on the current one. Saying only "Stale" would leave a preparer with no
 * idea which.
 */
function Staleness({
  staleness,
  status,
}: {
  staleness: CashflowForecastDetail["staleness"];
  status: string;
}) {
  if (!staleness.is_stale) return null;
  // The remedy depends on where the version stands, and the wrong one is worse
  // than none: telling the preparer of a draft that a newer source "changes what
  // was approved" describes a signature nobody gave, and telling an approver to
  // refresh sends them at a refusal.
  const approved = status === "approved";
  const refreshable = FORECAST_REFRESHABLE_STATUSES.has(status);
  return (
    <Notice tone="warning">
      <strong>The sources this version was built on have changed.</strong> Its own
      figures are unchanged{approved ? " and are still reported exactly as approved" : ""}.
      {staleness.construction_is_stale ? (
        <>
          {" "}
          It schedules construction forecast version{" "}
          {staleness.pinned_construction_version_number ?? "—"}, and version{" "}
          {staleness.active_construction_version_number ?? "—"} is now in force. The
          pin is fixed when a version is created, so the build schedule here can no
          longer be reconciled against what construction expects to spend —{" "}
          {approved
            ? "withdraw the approval and prepare a forecast on the current one."
            : refreshable
              ? "this version cannot be submitted, and a forecast on the current construction forecast has to be prepared instead."
              : "a later version was prepared on the current one."}
        </>
      ) : null}
      {staleness.customer_schedule_is_stale ? (
        <>
          {" "}
          The governing buyer schedules have changed since this version froze them.{" "}
          {approved
            ? "They cannot be re-read under the approval this version carries: withdraw the approval, and the replacement is reviewed against the schedule as it now stands."
            : refreshable
              ? "Refreshing is a deliberate act, not something that happens on its own."
              : "This version keeps the schedule it was governed on."}
        </>
      ) : null}
    </Notice>
  );
}

function CreateForecastDialog({
  currency,
  busy,
  onCancel,
  onSubmit,
}: {
  currency: string | null;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (body: Record<string, unknown>) => void;
}) {
  const [asOfDate, setAsOfDate] = useState("");
  const [endMonth, setEndMonth] = useState("");
  const [openingUnrestricted, setOpeningUnrestricted] = useState("");
  const [openingRestricted, setOpeningRestricted] = useState("");
  const [rate, setRate] = useState("");
  const [reason, setReason] = useState("");

  // The opening balance is cash at the start of the month the forecast is taken
  // in, so the start month is that month and is not a separate decision. The
  // server refuses any other pairing; offering the field would only invite a
  // rejection.
  const startMonth = asOfDate ? `${asOfDate.slice(0, 7)}-01` : "";

  return (
    <FormDialog
      title="Prepare a cashflow forecast"
      description="It pins the construction forecast in force and freezes today's buyer schedule underneath it."
      confirmLabel="Create draft"
      busy={busy}
      disabled={!asOfDate || !endMonth || !openingUnrestricted || !openingRestricted || !reason}
      onCancel={onCancel}
      onSubmit={() =>
        onSubmit({
          as_of_date: asOfDate,
          forecast_start_month: startMonth,
          forecast_end_month: endMonth,
          opening_unrestricted_cash: openingUnrestricted,
          opening_restricted_cash: openingRestricted,
          discount_rate_per_period: rate || "0.000000",
          change_reason: reason,
        })
      }
    >
      <FieldRow>
        <Field
          label="Taken as at"
          hint="The cutoff. Transactions confirmed after it are not inside this version."
        >
          <input
            className="input"
            type="date"
            value={asOfDate}
            onChange={(event) => setAsOfDate(event.target.value)}
          />
        </Field>
        <Field
          label="Horizon ends"
          hint="The last month this forecast says anything about."
        >
          <input
            className="input"
            type="month"
            value={endMonth ? endMonth.slice(0, 7) : ""}
            onChange={(event) =>
              setEndMonth(event.target.value ? `${event.target.value}-01` : "")
            }
          />
        </Field>
      </FieldRow>
      <p className="footnote">
        The horizon opens in {startMonth ? businessDate(startMonth) : "the month of the cutoff"},
        because the opening balances below state cash held at the start of that month.
      </p>
      <FieldRow>
        <Field label="Opening usable cash" hint="Spendable cash at the start of that month.">
          <MoneyInput code={currency} value={openingUnrestricted} onChange={setOpeningUnrestricted} />
        </Field>
        <Field label="Opening restricted cash" hint="Held in escrow at the start of that month.">
          <MoneyInput code={currency} value={openingRestricted} onChange={setOpeningRestricted} />
        </Field>
      </FieldRow>
      <Field
        label="Discount rate per period"
        hint="Per month, not per year. The NPV is discounted at exactly this rate."
        optional
      >
        <RateInput value={rate} onChange={setRate} />
      </Field>
      <Field label="Why this forecast is being prepared">
        <input className="input" value={reason} onChange={(event) => setReason(event.target.value)} />
      </Field>
    </FormDialog>
  );
}

/**
 * What each governance prompt asks for, in the words that fit the act.
 *
 * Withdrawal and rejection reach the same endpoint. Calling both of them
 * "Reject" on screen would tell a reader the version was refused, when in fact
 * a CFO approved it and the basis moved afterwards — and the record keeps the
 * approval precisely because it happened.
 */
const REASON_WORDS: Record<
  "approve" | "reject" | "withdraw" | "discard",
  { title: string; label: string; hint: string; confirm: string }
> = {
  approve: {
    title: "Approve this forecast",
    label: "What was reviewed?",
    hint: "Kept on the record against the version.",
    confirm: "Approve",
  },
  reject: {
    title: "Reject this forecast",
    label: "Why is it being rejected?",
    hint: "Kept on the record against the version.",
    confirm: "Reject",
  },
  discard: {
    title: "Discard this draft",
    label: "Why is this draft being discarded?",
    hint: "The draft stays in history. It will no longer occupy the project's open forecast slot.",
    confirm: "Discard draft",
  },
  withdraw: {
    title: "Withdraw this approval",
    label: "Why is the approval being withdrawn?",
    hint: "The approval stays on the record. This is written beside it, not over it, and the version closes so a replacement can be prepared.",
    confirm: "Withdraw approval",
  },
};

const LINE_SOURCE_KINDS = [
  { value: "construction", label: "Construction" },
  { value: "development", label: "Development" },
  { value: "financing", label: "Financing" },
  { value: "unsold_customer", label: "Unsold stock" },
];

/**
 * One cell of a forecast: a month, a source, a category and an amount.
 *
 * Everything the server governs is offered as a governed choice. A preparer
 * types a figure and a note; they never type a category code and never type an
 * identifier. The previous form asked for both, which meant the only way to
 * schedule external works was to know a cost code's UUID — a question no
 * finance controller can answer, and one the product already knows.
 *
 * There is deliberately no direction control. Whether a financing line is cash
 * in or cash out follows from the movement type — an equity contribution is
 * money arriving, always — so the server derives it and refuses a stated
 * direction that disagrees. Offering the choice invited a preparer to state a
 * fact and be told they were wrong about it.
 */
function ForecastLineDialog({
  projectId,
  currency,
  busy,
  onCancel,
  onSubmit,
}: {
  projectId: string;
  currency: string | null;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (body: Record<string, unknown>) => void;
}) {
  const [sourceKind, setSourceKind] = useState("construction");
  const [category, setCategory] = useState("construction");
  const [periodMonth, setPeriodMonth] = useState("");
  const [amount, setAmount] = useState("");
  const [costCode, setCostCode] = useState("");
  const [note, setNote] = useState("");

  const needsCostCode = sourceKind === "construction";
  const needsCategory = sourceKind === "development" || sourceKind === "financing";
  const categoryOptions =
    sourceKind === "development" ? DEVELOPMENT_CATEGORY_OPTIONS : FINANCING_TYPE_OPTIONS;

  // Asked only when a construction line is being written, and re-asked if the
  // preparer comes back to construction — the codes are a small list and this
  // keeps the workspace's rule that nothing is fetched before it is needed.
  const costCodes = useAnswer(
    needsCostCode,
    () => construction.costCodes(projectId),
    [projectId, needsCostCode],
  );

  const complete =
    Boolean(periodMonth) &&
    Boolean(amount) &&
    (!needsCategory || Boolean(category)) &&
    (!needsCostCode || Boolean(costCode));

  return (
    <FormDialog
      title="Set a forecast line"
      description="One figure per month, per source and per category. Writing the same cell again replaces it."
      confirmLabel="Save line"
      busy={busy}
      disabled={!complete}
      onCancel={onCancel}
      onSubmit={() =>
        onSubmit({
          period_month: periodMonth,
          source_kind: sourceKind,
          category,
          amount,
          // `flow_direction` is omitted on purpose: the server derives it from
          // the movement type, and sending a guess can only ever agree or be
          // refused.
          ...(needsCostCode ? { construction_cost_code_id: costCode } : {}),
          note: note || null,
        })
      }
    >
      <FieldRow>
        <Field label="What kind of cash">
          <select
            className="input"
            value={sourceKind}
            onChange={(event) => {
              setSourceKind(event.target.value);
              setCategory(
                event.target.value === "construction"
                  ? "construction"
                  : event.target.value === "unsold_customer"
                    ? "customer_collection"
                    : "",
              );
              setCostCode("");
            }}
          >
            {LINE_SOURCE_KINDS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Month">
          <input
            className="input"
            type="month"
            value={periodMonth ? periodMonth.slice(0, 7) : ""}
            onChange={(event) =>
              setPeriodMonth(event.target.value ? `${event.target.value}-01` : "")
            }
          />
        </Field>
      </FieldRow>

      {needsCategory ? (
        <Field
          label={sourceKind === "development" ? "Category" : "Financing movement type"}
          hint="The same set the actual movement will be recorded under, so the two can be compared."
        >
          <select
            className="input"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="">Choose one</option>
            {categoryOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>
      ) : null}

      {needsCostCode ? <CostCodeField answer={costCodes} value={costCode} onChange={setCostCode} /> : null}

      <FieldRow>
        <Field label="Amount">
          <MoneyInput code={currency} value={amount} onChange={setAmount} />
        </Field>
        <Field label="Note" optional>
          <input className="input" value={note} onChange={(event) => setNote(event.target.value)} />
        </Field>
      </FieldRow>
    </FormDialog>
  );
}

/**
 * The cost code a construction line schedules, chosen by name.
 *
 * A project with no cost codes cannot have a construction schedule prepared
 * against it, and saying so is more use than an empty control: the preparer has
 * to open Construction and author them before this line means anything.
 */
function CostCodeField({
  answer,
  value,
  onChange,
}: {
  answer: Answer<CostCode[]>;
  value: string;
  onChange: (value: string) => void;
}) {
  const label = "Construction cost code";
  const hint =
    "A construction line has to name the code it schedules, or there is nothing to reconcile it against.";

  if (answer.status === "loading") {
    return (
      <Field label={label} hint={hint}>
        <Loading label="Loading the cost codes" shape="rows" />
      </Field>
    );
  }
  if (answer.status === "failed") {
    return <Notice tone="error">{answer.message}</Notice>;
  }
  if (answer.status === "denied") {
    return <Notice tone="info">The construction cost codes are not available to your role.</Notice>;
  }
  if (answer.status === "off") return null;

  if (answer.data.length === 0) {
    return (
      <Notice tone="info">
        This project has no construction cost codes yet. A construction line schedules cash against
        one, so the codes have to be authored in Construction before this forecast can carry one.
      </Notice>
    );
  }

  const codes = [...answer.data].sort((left, right) => left.code.localeCompare(right.code));

  return (
    <Field label={label} hint={hint}>
      <select className="input" value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Choose one</option>
        {codes.map((code) => (
          <option key={code.id} value={code.id}>
            {code.code} — {code.name}
            {code.is_active ? "" : " (retired)"}
          </option>
        ))}
      </select>
    </Field>
  );
}
