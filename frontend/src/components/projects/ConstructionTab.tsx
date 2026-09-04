"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  Badge,
  Card,
  DataToolbar,
  EmptyState,
  IdentityCell,
  Loading,
  Notice,
  PageHeader,
  Tabs,
  TableScroll,
  ToolbarFilter,
} from "@/components/ui";
import { ApiError, construction } from "@/lib/api";
import type {
  BudgetDetail,
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
  budgetLabel,
  budgetTone,
  certificateLabel,
  certificateTone,
  contractLabel,
  contractTone,
  forecastLabel,
  forecastTone,
  headroomTone,
  invoiceLabel,
  invoiceTone,
  milestoneLabel,
  milestoneTone,
  paymentLabel,
  paymentTone,
  varianceTone,
  variationLabel,
  variationTone,
} from "@/components/projects/construction/labels";

const SECTIONS = [
  { key: "overview", label: "Overview" },
  { key: "budget", label: "Budget" },
  { key: "contracts", label: "Contracts" },
  { key: "variations", label: "Variations" },
  { key: "certificates", label: "Certificates" },
  { key: "cash", label: "Invoices & Payments" },
  { key: "milestones", label: "Milestones" },
  { key: "forecast", label: "Forecast" },
];

/**
 * The construction workspace: budget, commitment, certification, cash, forecast.
 *
 * Eight sections in the order the control model runs, because that order is the
 * argument. A budget authorises; a contract commits against that authorisation;
 * a variation changes the commitment; a certificate turns work into cost; an
 * invoice turns cost into a liability; a payment settles it; a forecast says
 * where it all lands. Each is a separate truth with a separate governance
 * ladder, and this screen keeps them visibly separate rather than presenting a
 * single "spent" figure that would have to pick one and hide the rest.
 *
 * Nothing on this screen is computed. Every total, every variance, every
 * headroom and every net due arrives from the API on this request. The one
 * thing the browser decides is which rows to draw — and only ever as a subset
 * of the rows the server already narrowed by role and by phase.
 */
export function ConstructionTab({ projectId }: { projectId: string }) {
  const [section, setSection] = useState("overview");
  const [summary, setSummary] = useState<ConstructionSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
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
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  return (
    <div className="stack">
      <PageHeader
        title="Construction"
        subtitle={sectionDescription("construction")}
        meta={
          summary ? (
            <>
              <Badge
                tone={
                  summary.controls.has_active_budget ? "success" : "neutral"
                }
              >
                {summary.controls.has_active_budget
                  ? `Budget v${summary.budget_version_number}`
                  : "No budget in force"}
              </Badge>
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

      {error ? <Notice tone="error">{error}</Notice> : null}

      <Tabs
        label="Construction sections"
        tabs={SECTIONS}
        active={section}
        onSelect={setSection}
        group="construction"
      />

      {section === "overview" ? (
        summary ? (
          <ConstructionSummaryView summary={summary} />
        ) : error ? null : (
          <Loading label="Loading the construction position" shape="metrics" />
        )
      ) : null}

      {section === "budget" ? <BudgetSection projectId={projectId} /> : null}
      {section === "contracts" ? (
        <ContractsSection projectId={projectId} />
      ) : null}
      {section === "variations" ? (
        <VariationsSection projectId={projectId} />
      ) : null}
      {section === "certificates" ? (
        <CertificatesSection projectId={projectId} />
      ) : null}
      {section === "cash" ? <CashSection projectId={projectId} /> : null}
      {section === "milestones" ? (
        <MilestonesSection projectId={projectId} />
      ) : null}
      {section === "forecast" ? (
        <ForecastSection projectId={projectId} />
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Budget
// --------------------------------------------------------------------------- //

/**
 * The authorisation in force, cost code by cost code.
 *
 * Headroom is the column somebody opens this for, and it is allowed to go
 * negative: a cost code committed beyond its budget reads as a negative number
 * in danger tone rather than as a zero. Clamping it at zero would render "we
 * are 400,000 over on structural steel" and "we have exactly nothing left"
 * identically, and only one of those is a problem.
 */
function BudgetSection({ projectId }: { projectId: string }) {
  const [detail, setDetail] = useState<BudgetDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [empty, setEmpty] = useState(false);

  const load = useCallback(async () => {
    try {
      const versions = await construction.budgets(projectId);
      const current =
        versions.find((version) => version.status === "active") ?? versions[0];
      if (!current) {
        setEmpty(true);
        return;
      }
      setDetail(await construction.budget(projectId, current.id));
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not load the budget.",
      );
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  if (error) return <Notice tone="error">{error}</Notice>;
  if (empty) {
    return (
      <EmptyState
        title="No budget yet"
        hint="Nothing has been authorised for this development. Until a budget is in force, no contract can be signed against it."
      />
    );
  }
  if (!detail) return <Loading label="Loading the budget" shape="rows" />;

  const code = detail.currency_code;

  return (
    <Card
      title={`Budget version ${detail.version_number}`}
      description={`Effective ${businessDate(detail.effective_date)}. ${detail.change_reason}`}
      actions={
        <Badge tone={budgetTone(detail.status)}>
          {budgetLabel(detail.status)}
        </Badge>
      }
    >
      <TableScroll label="Budget by cost code" fixedFirst>
        <thead>
          <tr>
            <th scope="col">Cost code</th>
            <th scope="col">Category</th>
            <th scope="col" className="numeric">
              Baseline
            </th>
            <th scope="col" className="numeric">
              Approved
            </th>
            <th scope="col" className="numeric">
              Contingency
            </th>
            <th scope="col" className="numeric">
              Control budget
            </th>
            <th scope="col" className="numeric">
              Committed
            </th>
            <th scope="col" className="numeric">
              Headroom
            </th>
          </tr>
        </thead>
        <tbody>
          {detail.lines.map((line) => (
            <tr key={line.cost_code_id}>
              <td>
                <IdentityCell
                  name={line.cost_code}
                  meta={line.cost_code_name}
                />
              </td>
              <td>{line.cost_category}</td>
              <td className="numeric">{money(line.baseline_amount, code)}</td>
              <td className="numeric">
                {money(line.approved_budget_amount, code)}
              </td>
              <td className="numeric">
                {money(line.contingency_amount, code)}
              </td>
              <td className="numeric">{money(line.control_budget, code)}</td>
              <td className="numeric">
                {money(line.revised_commitment, code)}
              </td>
              <td
                className={
                  headroomTone(line.headroom) === "danger"
                    ? "numeric figure-danger"
                    : "numeric"
                }
              >
                {money(line.headroom, code)}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row" colSpan={2}>
              Project
            </th>
            <td className="numeric">{money(detail.total_baseline, code)}</td>
            <td className="numeric">
              {money(detail.total_approved_budget, code)}
            </td>
            <td className="numeric">{money(detail.total_contingency, code)}</td>
            <td className="numeric">
              {money(detail.total_control_budget, code)}
            </td>
            <td className="numeric" />
            <td className="numeric" />
          </tr>
        </tfoot>
      </TableScroll>
    </Card>
  );
}

// --------------------------------------------------------------------------- //
// Contracts
// --------------------------------------------------------------------------- //

function ContractsSection({ projectId }: { projectId: string }) {
  const [rows, setRows] = useState<ConstructionContract[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await construction.contracts(projectId));
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not load the contracts.",
      );
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

  if (error) return <Notice tone="error">{error}</Notice>;
  if (!rows) return <Loading label="Loading the contracts" shape="rows" />;

  return (
    <div className="stack stack-tight">
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
        <TableScroll label="Contracts" fixedFirst>
          <thead>
            <tr>
              <th scope="col">Contract</th>
              <th scope="col">Vendor</th>
              <th scope="col" className="numeric">
                Original
              </th>
              <th scope="col" className="numeric">
                Variations
              </th>
              <th scope="col" className="numeric">
                Revised commitment
              </th>
              <th scope="col" className="numeric">
                Certified
              </th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((row) => (
              <tr
                key={row.id}
                onClick={() => setOpen(row.id)}
                className="row-clickable"
              >
                <td>
                  <IdentityCell
                    name={row.contract_number}
                    meta={row.contract_type}
                  />
                </td>
                <td>{row.vendor_name}</td>
                <td className="numeric">
                  {money(row.original_contract_value_ex_tax, row.currency_code)}
                </td>
                <td className="numeric">
                  {money(row.approved_variation_delta, row.currency_code)}
                </td>
                <td className="numeric">
                  {money(row.revised_commitment, row.currency_code)}
                </td>
                <td className="numeric">
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
      )}

      {open ? (
        <ContractFile
          projectId={projectId}
          contractId={open}
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
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");

  const load = useCallback(async () => {
    try {
      setRows(await construction.variations(projectId));
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not load the variations.",
      );
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

  if (error) return <Notice tone="error">{error}</Notice>;
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
        <TableScroll label="Variations" fixedFirst>
          <thead>
            <tr>
              <th scope="col">Variation</th>
              <th scope="col">Contract</th>
              <th scope="col">Description</th>
              <th scope="col">Requested</th>
              <th scope="col" className="numeric">
                Value
              </th>
              <th scope="col">Approval</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((row) => (
              <tr key={row.id}>
                <td>{row.variation_number}</td>
                <td>{row.contract_number}</td>
                <td>{row.description}</td>
                <td>{businessDate(row.requested_date)}</td>
                <td className="numeric">{money(row.total_value_ex_tax)}</td>
                <td>
                  {row.requires_escalation ? (
                    <Badge tone="warning">
                      Needs the Approver
                      {row.review_amount
                        ? ` (over ${money(row.review_amount)})`
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
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Certificates
// --------------------------------------------------------------------------- //

function CertificatesSection({ projectId }: { projectId: string }) {
  const [rows, setRows] = useState<Certificate[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [contract, setContract] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await construction.certificates(projectId));
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not load the certificates.",
      );
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

  if (error) return <Notice tone="error">{error}</Notice>;
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
        <TableScroll label="Certificates" fixedFirst>
          <thead>
            <tr>
              <th scope="col">Certificate</th>
              <th scope="col">Contract</th>
              <th scope="col">Period</th>
              <th scope="col" className="numeric">
                Work
              </th>
              <th scope="col" className="numeric">
                Retention held
              </th>
              <th scope="col" className="numeric">
                Net due
              </th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((row) => (
              <tr
                key={row.id}
                onClick={() => setOpen(row.id)}
                className="row-clickable"
              >
                <td>{row.certificate_number}</td>
                <td>{row.contract_number}</td>
                <td>
                  {businessDate(row.period_start)} to{" "}
                  {businessDate(row.period_end)}
                </td>
                <td className="numeric">
                  {money(row.current_work_value_ex_tax)}
                </td>
                <td className="numeric">{money(row.retention_held_amount)}</td>
                <td className="numeric">{money(row.net_due)}</td>
                <td>
                  <Badge tone={certificateTone(row.status)}>
                    {certificateLabel(row.status)}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      )}

      {open ? (
        <CertificateFile
          projectId={projectId}
          certificateId={open}
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
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [claims, cash] = await Promise.all([
        construction.invoices(projectId),
        construction.payments(projectId),
      ]);
      setInvoices(claims);
      setPayments(cash);
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not load the cash position.",
      );
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  if (error) return <Notice tone="error">{error}</Notice>;
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
                <th scope="col">Invoice</th>
                <th scope="col">Contract</th>
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
              {invoices.map((row) => (
                <tr key={row.id}>
                  <td>{row.invoice_number}</td>
                  <td>{row.contract_number}</td>
                  <td>{row.invoice_type}</td>
                  <td>{businessDate(row.invoice_date)}</td>
                  <td className="numeric">{money(row.net_payable)}</td>
                  <td className="numeric">{money(row.outstanding)}</td>
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
                <th scope="col">Reference</th>
                <th scope="col">Contract</th>
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
              {payments.map((row) => (
                <tr key={row.id}>
                  <td>{row.payment_reference}</td>
                  <td>{row.contract_number}</td>
                  <td>{businessDate(row.payment_date)}</td>
                  <td className="numeric">
                    {money(row.amount, row.currency_code)}
                  </td>
                  <td className="numeric">
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
function MilestonesSection({ projectId }: { projectId: string }) {
  const [rows, setRows] = useState<ConstructionMilestone[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await construction.milestones(projectId));
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not load the milestones.",
      );
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  if (error) return <Notice tone="error">{error}</Notice>;
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
    <TableScroll label="Milestones" fixedFirst>
      <thead>
        <tr>
          <th scope="col">Milestone</th>
          <th scope="col">Scope</th>
          <th scope="col">Planned</th>
          <th scope="col">Forecast</th>
          <th scope="col">Reported</th>
          <th scope="col">Certified</th>
          <th scope="col" className="numeric">
            Delay
          </th>
          <th scope="col">Status</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <td>
              <IdentityCell name={row.code} meta={row.name} />
            </td>
            <td>{row.scope_label ?? "Whole project"}</td>
            <td>{businessDate(row.planned_date)}</td>
            <td>{businessDate(row.forecast_date)}</td>
            <td>{businessDate(row.actual_achieved_date)}</td>
            <td>{businessDate(row.certified_date)}</td>
            <td
              className={
                row.delay_days && row.delay_days > 0
                  ? "numeric figure-danger"
                  : "numeric"
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
  );
}

// --------------------------------------------------------------------------- //
// Forecast
// --------------------------------------------------------------------------- //

/**
 * What the project now expects to spend, and how far off budget that is.
 *
 * **Positive variance is over budget**, here and everywhere else in the
 * product. The tone comes from one shared function so the sign cannot mean one
 * thing on this table and another on the overview above it.
 */
function ForecastSection({ projectId }: { projectId: string }) {
  const [detail, setDetail] = useState<ForecastDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [empty, setEmpty] = useState(false);

  const load = useCallback(async () => {
    try {
      const versions = await construction.forecasts(projectId);
      const current =
        versions.find((version) => version.status === "active") ?? versions[0];
      if (!current) {
        setEmpty(true);
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
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  if (error) return <Notice tone="error">{error}</Notice>;
  if (empty) {
    return (
      <EmptyState
        title="No forecast yet"
        hint="Nothing has been forecast for this development, so there is no estimate at completion and no variance to report."
      />
    );
  }
  if (!detail) return <Loading label="Loading the forecast" shape="rows" />;

  const code = detail.currency_code;

  return (
    <Card
      title={`Forecast version ${detail.version_number}`}
      description={`As at ${businessDate(detail.as_of_date)}, against budget version ${
        detail.budget_version_number ?? "—"
      }. ${detail.change_reason}`}
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
            <th scope="col" className="numeric">
              Control budget
            </th>
            <th scope="col" className="numeric">
              Committed
            </th>
            <th scope="col" className="numeric">
              Certified
            </th>
            <th scope="col" className="numeric">
              Forecast remaining
            </th>
            <th scope="col" className="numeric">
              Estimate at completion
            </th>
            <th scope="col" className="numeric">
              Variance
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
              <td className="numeric">{money(line.control_budget, code)}</td>
              <td className="numeric">
                {money(line.revised_commitment, code)}
              </td>
              <td className="numeric">{money(line.certified_to_date, code)}</td>
              <td className="numeric">
                {money(line.forecast_remaining_amount_ex_tax, code)}
              </td>
              <td className="numeric">
                {money(line.estimate_at_completion, code)}
              </td>
              <td
                className={
                  varianceTone(line.variance_at_completion) === "danger"
                    ? "numeric figure-danger"
                    : "numeric"
                }
              >
                {money(line.variance_at_completion, code)}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">Project</th>
            <td className="numeric">
              {money(detail.total_control_budget, code)}
            </td>
            <td className="numeric" />
            <td className="numeric">{money(detail.total_certified, code)}</td>
            <td className="numeric">
              {money(detail.total_forecast_remaining, code)}
            </td>
            <td className="numeric">
              {money(detail.total_estimate_at_completion, code)}
            </td>
            <td
              className={
                varianceTone(detail.total_variance_at_completion) === "danger"
                  ? "numeric figure-danger"
                  : "numeric"
              }
            >
              {money(detail.total_variance_at_completion, code)}
            </td>
          </tr>
        </tfoot>
      </TableScroll>
      <p className="footnote">
        A positive variance is over the control budget. Every figure above is
        the server&rsquo;s, excluding tax.
      </p>
    </Card>
  );
}
