"use client";

import { useCallback, useEffect, useState } from "react";

import {
  Badge,
  Button,
  EmptyState,
  Field,
  FilterBar,
  FormDialog,
  KeyValue,
  KeyValueGrid,
  Loading,
  Notice,
  PromptDialog,
  SectionHeader,
  Stat,
  StatRow,
  Tabs,
  TabPanel,
  TableScroll,
} from "@/components/ui";
import { ApiError, unitEconomics } from "@/lib/api";
import type {
  AllocationMethod,
  AllocationVersion,
  AllocationVersionDetail,
  CalculationPreview,
  PoolCategory,
  PoolScope,
  ProjectEconomics,
  UnitCost,
  UnitCostType,
  UnitEconomics as UnitEconomicsRow,
} from "@/lib/api";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, money, percent, todayISO } from "@/lib/format";

import {
  ALLOCATION_METHODS,
  DIRECT_COST_TYPES,
  POOL_CATEGORIES,
  POOL_SCOPES,
  PROFIT_EXPLANATIONS,
  SELLING_COST_TYPES,
  basisLabel,
  categoryLabel,
  costBasisLabel,
  costTypeLabel,
  methodLabel,
  profitabilityLabel,
  profitabilityTone,
  scopeLabel,
  versionLabel,
  versionTone,
} from "./economics/labels";

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "units", label: "Units" },
  { key: "versions", label: "Allocation versions" },
  { key: "costs", label: "Unit costs" },
];

/**
 * The project's unit economics: what each unit costs, and the basis that says so.
 *
 * Nothing on this screen is calculated in the browser. Allocation,
 * reconciliation, every profit layer and every ratio arrive from the API
 * already decided — the arithmetic is tested once, in `calculator.py`, and a
 * second implementation here would be a second answer.
 *
 * Two rules shape the presentation.
 *
 * **A missing figure says why.** Where profit cannot be calculated the row
 * carries a status and no number, and the reason is printed rather than being
 * rendered as a zero somebody would act on.
 *
 * **Excluded units are counted out loud.** A summary that quietly dropped the
 * units whose revenue is in another currency would be a summary of an unstated
 * subset, which is exactly the failure this platform refuses everywhere money is
 * added up.
 */
export function UnitEconomicsTab({
  projectId,
  roles,
}: {
  projectId: string;
  roles: Set<string>;
}) {
  const currencyCodeOf = useCurrencyCode();
  const [tab, setTab] = useState("overview");
  const [summary, setSummary] = useState<ProjectEconomics | null>(null);
  const [rows, setRows] = useState<UnitEconomicsRow[] | null>(null);
  const [versions, setVersions] = useState<AllocationVersion[] | null>(null);
  const [costs, setCosts] = useState<UnitCost[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [denied, setDenied] = useState(false);
  const [busy, setBusy] = useState(false);

  const canWrite = roles.has("finance");
  const canApprove = roles.has("finance") || roles.has("approver_cfo");

  const load = useCallback(async () => {
    try {
      const [nextSummary, nextRows, nextVersions, nextCosts] = await Promise.all([
        unitEconomics.summary(projectId),
        unitEconomics.units(projectId),
        unitEconomics.versions(projectId),
        unitEconomics.unitCosts(projectId),
      ]);
      setSummary(nextSummary);
      setRows(nextRows);
      setVersions(nextVersions);
      setCosts(nextCosts);
      setError(null);
      setDenied(false);
    } catch (caught) {
      // Only a 403 is a role problem. Blaming the reader's role for a dropped
      // connection sends them to ask for a permission they already hold.
      setDenied(caught instanceof ApiError && caught.isForbidden);
      setError(
        caught instanceof ApiError && caught.isForbidden
          ? null
          : caught instanceof ApiError
            ? caught.message
            : "Could not load unit economics.",
      );
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const act = async (run: () => Promise<unknown>, done: string) => {
    setBusy(true);
    setError(null);
    try {
      await run();
      setNotice(done);
      await load();
    } catch (caught) {
      setNotice(null);
      setError(caught instanceof ApiError ? caught.message : "That did not work.");
    } finally {
      setBusy(false);
    }
  };

  if (denied) {
    return (
      <EmptyState
        title="Not available to your role"
        hint="Unit cost and margin are restricted to Finance, the CFO, project management, executives and audit."
      />
    );
  }
  if (summary === null || rows === null || versions === null || costs === null) {
    return error ? (
      <Notice tone="error">{error}</Notice>
    ) : (
      <Loading label="Loading unit economics" />
    );
  }

  const code = currencyCodeOf(summary.currency_id);

  return (
    <div className="stack">
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      <Tabs label="Unit economics sections" tabs={TABS} active={tab} onSelect={setTab} />
      <TabPanel group="Unit economics sections" tab={tab}>
        {tab === "overview" ? (
          <Overview summary={summary} code={code} />
        ) : null}
        {tab === "units" ? <UnitsRegister rows={rows} code={code} /> : null}
        {tab === "versions" ? (
          <Versions
            projectId={projectId}
            versions={versions}
            code={code}
            canWrite={canWrite}
            canApprove={canApprove}
            busy={busy}
            onAct={act}
          />
        ) : null}
        {tab === "costs" ? (
          <UnitCosts
            projectId={projectId}
            costs={costs}
            rows={rows}
            code={code}
            canWrite={canWrite}
            busy={busy}
            onAct={act}
          />
        ) : null}
      </TabPanel>
    </div>
  );
}

/* ------------------------------------------------------------------------- */

function Overview({
  summary,
  code,
}: {
  summary: ProjectEconomics;
  code: string | null;
}) {
  const plural = (count: number, word: string) =>
    `${count} ${word}${count === 1 ? "" : "s"}`;

  return (
    <div className="stack">
      <SectionHeader
        title="Current blended economics"
        description="Locked where sold, expected where not: sold units keep the terms and cost basis they were sold under, unsold units use today's approved price and today's basis."
      />

      {summary.active_version === null ? (
        <EmptyState
          title="No approved cost allocation basis exists yet"
          hint="Create the opening Finance allocation version to calculate unit profitability."
        />
      ) : null}

      <StatRow>
        <Stat label="Revenue" value={money(summary.revenue_total, code)} small />
        <Stat label="Total cost" value={money(summary.total_cost_total, code)} small />
        <Stat label="Profit" value={money(summary.profit_total, code)} small />
        <Stat label="Margin" value={percent(summary.margin_fraction)} small />
        <Stat
          label="Return on cost"
          value={percent(summary.return_on_cost_fraction)}
          small
        />
      </StatRow>

      <StatRow>
        <Stat label="Sold units" value={summary.sold_count} small />
        <Stat label="Unsold units" value={summary.unsold_count} small />
        <Stat
          label="Loss-making"
          value={summary.negative_profit_count}
          note="Profit after finance below zero"
          small
        />
        <Stat
          label="Below minimum margin"
          value={summary.below_threshold_count}
          note={
            summary.threshold_fraction
              ? `Threshold ${percent(summary.threshold_fraction)}`
              : "No threshold configured"
          }
          small
        />
        <Stat
          label="Incomplete"
          value={summary.incomplete_count}
          note="No price or no cost basis"
          small
        />
      </StatRow>

      {summary.currency_mismatch_count > 0 ? (
        <Notice tone="warning">
          {plural(summary.currency_mismatch_count, "unit")} cannot be included because
          revenue and project cost currency differ. There is no exchange rate in this
          system, so those units are reported on their own and never added to these
          totals.
        </Notice>
      ) : null}

      <p className="footnote">
        Totals cover {summary.comparable_unit_count} of {summary.unit_count} units.
        Margin is total profit over total revenue and return on cost is total profit
        over total cost — weighted, never the average of the unit ratios, which is a
        different number and not the developer&rsquo;s.
      </p>

      {summary.active_version ? (
        <KeyValueGrid columns={3}>
          <KeyValue
            label="Current cost basis"
            value={`v${summary.active_version.version_number}`}
          />
          <KeyValue
            label="Effective from"
            mono
            value={businessDate(summary.active_version.effective_from)}
          />
          <KeyValue
            label="Finance cost"
            value={
              summary.active_version.finance_treatment === "allocated"
                ? "Allocated to units"
                : "Excluded from this basis"
            }
          />
        </KeyValueGrid>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------------- */

function UnitsRegister({
  rows,
  code,
}: {
  rows: UnitEconomicsRow[];
  code: string | null;
}) {
  // `code` is the project's cost currency, which every cost column is in.
  // Revenue is not necessarily: a currency-mismatch unit earns in its own
  // denomination, and labelling that figure with the project's code would
  // assert an exchange rate this system does not have.
  const currencyCodeOf = useCurrencyCode();
  const [search, setSearch] = useState("");
  const [only, setOnly] = useState("all");

  const shown = rows.filter((row) => {
    const text = `${row.unit_reference} ${row.unit_number}`.toLowerCase();
    if (search && !text.includes(search.toLowerCase())) return false;
    if (only === "sold") return row.basis === "sold";
    if (only === "unsold") return row.basis === "forecast";
    if (only === "loss") {
      return row.profit_after_finance !== null && row.profit_after_finance.startsWith("-");
    }
    if (only === "below") return row.below_margin_threshold === true;
    if (only === "incomplete") return row.profitability_status !== "ready";
    return true;
  });

  return (
    <div className="stack">
      <FilterBar>
        <Field label="Search" grow>
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Unit reference"
          />
        </Field>
        <Field label="Show">
          <select value={only} onChange={(event) => setOnly(event.target.value)}>
            <option value="all">Every unit</option>
            <option value="sold">Sold</option>
            <option value="unsold">Unsold</option>
            <option value="loss">Loss-making</option>
            <option value="below">Below minimum margin</option>
            <option value="incomplete">Incomplete economics</option>
          </select>
        </Field>
      </FilterBar>

      {shown.length === 0 ? (
        <EmptyState
          title="No units match"
          hint="Widen the filter, or record a cost basis so units can be analysed."
        />
      ) : (
        <TableScroll label="Unit economics">
          <thead>
            <tr>
              <th scope="col">Unit</th>
              <th scope="col">Basis</th>
              <th scope="col" className="num">
                Revenue
              </th>
              <th scope="col" className="num">
                Land
              </th>
              <th scope="col" className="num">
                Hard
              </th>
              <th scope="col" className="num">
                Soft
              </th>
              <th scope="col" className="num">
                Direct
              </th>
              <th scope="col" className="num">
                Selling
              </th>
              <th scope="col" className="num">
                Finance
              </th>
              <th scope="col" className="num">
                Total cost
              </th>
              <th scope="col" className="num">
                Profit
              </th>
              <th scope="col" className="num">
                Margin
              </th>
              <th scope="col" className="num">
                ROC
              </th>
              <th scope="col">State</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((row) => (
              <tr key={row.unit_id}>
                <th scope="row" className="mono">
                  {row.unit_reference}
                </th>
                <td>
                  {basisLabel(row.basis)}
                  {row.allocation_version_number === null ? null : (
                    <p className="hint">v{row.allocation_version_number}</p>
                  )}
                </td>
                <td className="num mono">
                  {money(row.revenue, currencyCodeOf(row.revenue_currency_id))}
                </td>
                <td className="num mono">{money(row.land_cost, code)}</td>
                <td className="num mono">{money(row.hard_cost, code)}</td>
                <td className="num mono">{money(row.soft_cost, code)}</td>
                <td className="num mono">{money(row.direct_cost, code)}</td>
                <td className="num mono">
                  {money(row.variable_selling_cost, code)}
                  {row.seller_cost === "0.00" ? null : (
                    <p className="hint">+{money(row.seller_cost, code)} seller</p>
                  )}
                </td>
                <td className="num mono">
                  {money(row.finance_cost ?? row.allocated_finance_cost, code)}
                </td>
                <td className="num mono">{money(row.total_cost, code)}</td>
                <td className="num mono">{money(row.profit_after_finance, code)}</td>
                <td className="num mono">{percent(row.margin_fraction)}</td>
                <td className="num mono">{percent(row.return_on_cost_fraction)}</td>
                <td>
                  <Badge tone={profitabilityTone(row.profitability_status)}>
                    {profitabilityLabel(row.profitability_status)}
                  </Badge>
                  {row.profitability_status === "ready" ? null : (
                    <p className="hint">{PROFIT_EXPLANATIONS[row.profitability_status]}</p>
                  )}
                  {row.below_margin_threshold ? (
                    <p className="hint">Below the minimum margin.</p>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------------- */

type Act = (run: () => Promise<unknown>, done: string) => Promise<void>;

function Versions({
  projectId,
  versions,
  code,
  canWrite,
  canApprove,
  busy,
  onAct,
}: {
  projectId: string;
  versions: AllocationVersion[];
  code: string | null;
  canWrite: boolean;
  canApprove: boolean;
  busy: boolean;
  onAct: Act;
}) {
  const [open, setOpen] = useState<string | null>(versions[0]?.id ?? null);
  const [detail, setDetail] = useState<AllocationVersionDetail | null>(null);
  const [preview, setPreview] = useState<CalculationPreview | null>(null);
  const [creating, setCreating] = useState(false);
  const [addingPool, setAddingPool] = useState(false);
  const [rejecting, setRejecting] = useState<string | null>(null);

  const loadDetail = useCallback(async () => {
    if (open === null) {
      setDetail(null);
      return;
    }
    setDetail(await unitEconomics.version(projectId, open));
  }, [projectId, open]);

  useEffect(() => {
    void (async () => {
      await loadDetail();
    })();
  }, [loadDetail, versions]);

  const after = (run: () => Promise<unknown>, done: string) =>
    void onAct(run, done).then(() => void loadDetail());

  return (
    <div className="stack">
      <SectionHeader
        title="Allocation versions"
        description="Each version is one governed basis for turning shared project cost into unit cost. A sold unit keeps the version that governed when its contract was signed."
        actions={
          canWrite ? (
            <Button variant="primary" disabled={busy} onClick={() => setCreating(true)}>
              New version
            </Button>
          ) : null
        }
      />

      {versions.length === 0 ? (
        <EmptyState
          title="No approved cost allocation basis exists yet"
          hint="Create the opening Finance allocation version to calculate unit profitability."
        />
      ) : (
        <TableScroll label="Allocation versions">
          <thead>
            <tr>
              <th scope="col">Version</th>
              <th scope="col">Effective</th>
              <th scope="col">Finance cost</th>
              <th scope="col">Status</th>
              <th scope="col">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {versions.map((version) => (
              <tr key={version.id}>
                <th scope="row">v{version.version_number}</th>
                <td className="mono">
                  {businessDate(version.effective_from)}
                  {version.effective_to
                    ? ` – ${businessDate(version.effective_to)}`
                    : ""}
                </td>
                <td>
                  {version.finance_treatment === "allocated" ? "Allocated" : "Excluded"}
                </td>
                <td>
                  <Badge tone={versionTone(version.status)}>
                    {versionLabel(version.status)}
                  </Badge>
                  {version.rejection_reason ? (
                    <p className="hint">{version.rejection_reason}</p>
                  ) : null}
                </td>
                <td>
                  <Button
                    disabled={busy}
                    onClick={() => {
                      setOpen(version.id);
                      setPreview(null);
                    }}
                  >
                    Open
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      )}

      {detail ? (
        <>
          <SectionHeader
            title={`Version ${detail.version.version_number}`}
            description={detail.version.change_reason}
            actions={
              <>
                {canWrite && detail.version.status === "draft" ? (
                  <>
                    <Button disabled={busy} onClick={() => setAddingPool(true)}>
                      Add pool
                    </Button>
                    <Button
                      disabled={busy}
                      onClick={() =>
                        void onAct(async () => {
                          setPreview(
                            await unitEconomics.calculate(projectId, detail.version.id),
                          );
                        }, "Allocation calculated.").then(() => void loadDetail())
                      }
                    >
                      Calculate
                    </Button>
                    <Button
                      variant="primary"
                      disabled={busy}
                      onClick={() =>
                        after(
                          () => unitEconomics.submitVersion(projectId, detail.version.id),
                          "Cost basis submitted for approval.",
                        )
                      }
                    >
                      Submit
                    </Button>
                  </>
                ) : null}
                {canApprove && detail.version.status === "submitted" ? (
                  <>
                    <Button
                      variant="primary"
                      disabled={busy}
                      onClick={() =>
                        after(
                          () => unitEconomics.approveVersion(projectId, detail.version.id),
                          "Cost basis approved.",
                        )
                      }
                    >
                      Approve
                    </Button>
                    <Button
                      variant="danger"
                      disabled={busy}
                      onClick={() => setRejecting(detail.version.id)}
                    >
                      Reject
                    </Button>
                  </>
                ) : null}
                {canWrite && detail.version.status === "approved" ? (
                  <Button
                    variant="primary"
                    disabled={busy}
                    onClick={() =>
                      after(
                        () => unitEconomics.activateVersion(projectId, detail.version.id),
                        "Cost basis is now current.",
                      )
                    }
                  >
                    Make current
                  </Button>
                ) : null}
                {canWrite && detail.version.status !== "draft" ? (
                  <Button
                    disabled={busy}
                    onClick={() =>
                      after(
                        () =>
                          unitEconomics.cloneVersion(projectId, detail.version.id, {
                            effective_from: todayISO(),
                            change_reason: `Revision of version ${detail.version.version_number}`,
                          }),
                        "Cloned to a new draft.",
                      )
                    }
                  >
                    Clone
                  </Button>
                ) : null}
              </>
            }
          />

          {detail.stale_sources.length > 0 ? (
            <Notice tone="warning">
              This basis was calculated against sources that have since changed —{" "}
              {detail.stale_sources.join("; ")}. It cannot be made current until it is
              recalculated.
            </Notice>
          ) : null}

          <StatRow>
            <Stat
              label="Source cost"
              value={money(detail.reconciliation.source_cost_total, code)}
              small
            />
            <Stat
              label="Allocated"
              value={money(detail.reconciliation.allocated_cost_total, code)}
              small
            />
            <Stat
              label="Variance"
              value={money(detail.reconciliation.variance, code)}
              note={detail.reconciliation.reconciled ? "Reconciled" : "Does not reconcile"}
              small
            />
            <Stat label="Pools" value={detail.reconciliation.pool_count} small />
            <Stat
              label="Allocations"
              value={detail.reconciliation.allocation_count}
              small
            />
          </StatRow>

          {detail.pools.length === 0 ? (
            <EmptyState
              title="No cost pools yet"
              hint="A basis must address land, hard and soft cost explicitly before it can be submitted. Record a zero pool where the cost is genuinely nil."
            />
          ) : (
            <TableScroll label="Cost pools">
              <thead>
                <tr>
                  <th scope="col">Pool</th>
                  <th scope="col">Category</th>
                  <th scope="col" className="num">
                    Amount
                  </th>
                  <th scope="col">Scope</th>
                  <th scope="col">Method</th>
                  <th scope="col" className="num">
                    Allocated
                  </th>
                  <th scope="col" className="num">
                    Variance
                  </th>
                  <th scope="col">
                    <span className="visually-hidden">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {detail.pools.map((pool) => {
                  const line = preview?.pools.find((row) => row.pool_id === pool.id);
                  return (
                    <tr key={pool.id}>
                      <th scope="row" className="mono">
                        {pool.pool_number}
                        <p className="hint">{pool.name}</p>
                      </th>
                      <td>{categoryLabel(pool.category)}</td>
                      <td className="num mono">
                        {money(pool.amount, code)}
                        {pool.source_kind === "project_land" ? (
                          <p className="hint">From the land register</p>
                        ) : (
                          <p className="hint">Current forecast input</p>
                        )}
                      </td>
                      <td>{scopeLabel(pool.scope_kind)}</td>
                      <td>{methodLabel(pool.allocation_method)}</td>
                      <td className="num mono">
                        {line ? money(line.allocated_total, code) : "—"}
                      </td>
                      <td className="num mono">{line ? money(line.variance, code) : "—"}</td>
                      <td>
                        {canWrite && detail.version.status === "draft" ? (
                          <Button
                            variant="danger"
                            disabled={busy}
                            onClick={() =>
                              after(
                                () =>
                                  unitEconomics.removePool(
                                    projectId,
                                    detail.version.id,
                                    pool.id,
                                  ),
                                "Pool removed from the draft.",
                              )
                            }
                          >
                            Remove
                          </Button>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </TableScroll>
          )}
        </>
      ) : null}

      {creating ? (
        <NewVersionDialog
          busy={busy}
          onCancel={() => setCreating(false)}
          onSubmit={(body) => {
            setCreating(false);
            void onAct(
              () => unitEconomics.createVersion(projectId, body),
              "Draft cost basis created.",
            );
          }}
        />
      ) : null}

      {addingPool && detail ? (
        <NewPoolDialog
          busy={busy}
          onCancel={() => setAddingPool(false)}
          onSubmit={(body) => {
            setAddingPool(false);
            after(
              () => unitEconomics.addPool(projectId, detail.version.id, body),
              "Cost pool added.",
            );
          }}
        />
      ) : null}

      {rejecting ? (
        <PromptDialog
          title="Reject this cost basis"
          hint="It stays readable, with the reason on the record. Finance clones it to propose a correction."
          label="Reason"
          confirmLabel="Reject"
          busy={busy}
          onCancel={() => setRejecting(null)}
          onSubmit={(reason) => {
            const target = rejecting;
            setRejecting(null);
            after(
              () => unitEconomics.rejectVersion(projectId, target, reason),
              "Cost basis rejected.",
            );
          }}
        />
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------------- */

function NewVersionDialog({
  busy,
  onCancel,
  onSubmit,
}: {
  busy: boolean;
  onCancel: () => void;
  onSubmit: (body: Record<string, unknown>) => void;
}) {
  const [effectiveFrom, setEffectiveFrom] = useState(todayISO());
  const [reason, setReason] = useState("");
  const [treatment, setTreatment] = useState("excluded");

  return (
    <FormDialog
      title="New cost allocation basis"
      description="The currency is the project's base currency and is not a choice: there is no exchange rate in this system to make it one."
      confirmLabel="Create draft"
      busy={busy}
      disabled={reason.trim().length === 0}
      onCancel={onCancel}
      onSubmit={() =>
        onSubmit({
          effective_from: effectiveFrom,
          change_reason: reason.trim(),
          finance_treatment: treatment,
        })
      }
    >
      <Field label="Effective from" hint="The date this basis starts governing.">
        <input
          type="date"
          value={effectiveFrom}
          onChange={(event) => setEffectiveFrom(event.target.value)}
          required
        />
      </Field>
      <Field label="Reason">
        <textarea
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          rows={3}
          required
        />
      </Field>
      <Field
        label="Finance cost"
        hint="Excluded is a statement, not an omission: the screens will say finance cost is excluded rather than implying it is nil."
      >
        <select value={treatment} onChange={(event) => setTreatment(event.target.value)}>
          <option value="excluded">Excluded from this basis</option>
          <option value="allocated">Allocated to units</option>
        </select>
      </Field>
    </FormDialog>
  );
}

function NewPoolDialog({
  busy,
  onCancel,
  onSubmit,
}: {
  busy: boolean;
  onCancel: () => void;
  onSubmit: (body: Record<string, unknown>) => void;
}) {
  const [poolNumber, setPoolNumber] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState<PoolCategory>("hard");
  const [fromLandRegister, setFromLandRegister] = useState(false);
  const [amount, setAmount] = useState("0.00");
  const [scope, setScope] = useState<PoolScope>("project");
  const [method, setMethod] = useState<AllocationMethod>("unit_count");

  const derived = category === "land" && fromLandRegister;

  return (
    <FormDialog
      title="Add a cost pool"
      description="One shared amount and the rule for dividing it. Manual amounts are a current forecast allocation input, not a construction ledger."
      confirmLabel="Add pool"
      busy={busy}
      disabled={poolNumber.trim().length === 0 || name.trim().length === 0}
      onCancel={onCancel}
      onSubmit={() =>
        onSubmit({
          pool_number: poolNumber.trim(),
          name: name.trim(),
          category,
          source_kind: derived ? "project_land" : "manual",
          ...(derived ? {} : { amount }),
          scope_kind: scope,
          allocation_method: method,
        })
      }
    >
      <Field label="Reference">
        <input
          value={poolNumber}
          onChange={(event) => setPoolNumber(event.target.value)}
          placeholder="HARD-01"
          required
        />
      </Field>
      <Field label="Name">
        <input value={name} onChange={(event) => setName(event.target.value)} required />
      </Field>
      <Field label="Category">
        <select
          value={category}
          onChange={(event) => setCategory(event.target.value as PoolCategory)}
        >
          {POOL_CATEGORIES.map((value) => (
            <option key={value} value={value}>
              {categoryLabel(value)}
            </option>
          ))}
        </select>
      </Field>
      {category === "land" ? (
        <Field
          label="Source"
          hint="Derived from the parcels' purchase price and acquisition fees, and re-derived when the basis is made current."
        >
          <select
            value={fromLandRegister ? "register" : "manual"}
            onChange={(event) => setFromLandRegister(event.target.value === "register")}
          >
            <option value="manual">Enter an amount</option>
            <option value="register">From the land register</option>
          </select>
        </Field>
      ) : null}
      {derived ? null : (
        <Field label="Amount">
          <input
            inputMode="decimal"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            required
          />
        </Field>
      )}
      <Field label="Scope">
        <select
          value={scope}
          onChange={(event) => setScope(event.target.value as PoolScope)}
        >
          {POOL_SCOPES.filter((value) => value === "project").map((value) => (
            <option key={value} value={value}>
              {scopeLabel(value)}
            </option>
          ))}
        </select>
      </Field>
      <Field
        label="Allocation method"
        hint="Weighted and raw area read the approved area schedule; revenue value reads the current approved price."
      >
        <select
          value={method}
          onChange={(event) => setMethod(event.target.value as AllocationMethod)}
        >
          {ALLOCATION_METHODS.filter((value) => value !== "raw_area").map((value) => (
            <option key={value} value={value}>
              {methodLabel(value)}
            </option>
          ))}
        </select>
      </Field>
    </FormDialog>
  );
}

/* ------------------------------------------------------------------------- */

function UnitCosts({
  projectId,
  costs,
  rows,
  code,
  canWrite,
  busy,
  onAct,
}: {
  projectId: string;
  costs: UnitCost[];
  rows: UnitEconomicsRow[];
  code: string | null;
  canWrite: boolean;
  busy: boolean;
  onAct: Act;
}) {
  const [recording, setRecording] = useState(false);
  const [reversing, setReversing] = useState<string | null>(null);
  const reference = new Map(rows.map((row) => [row.unit_id, row.unit_reference]));

  return (
    <div className="stack">
      <SectionHeader
        title="Unit costs"
        description="Costs belonging to one unit rather than divided from a shared pool. Recorded, never edited; corrected by reversal and replacement."
        actions={
          canWrite ? (
            <Button variant="primary" disabled={busy} onClick={() => setRecording(true)}>
              Record a cost
            </Button>
          ) : null
        }
      />

      {costs.length === 0 ? (
        <EmptyState
          title="No unit-specific costs recorded"
          hint="Upgrades, furniture, commissions and other costs belonging to a single unit would appear here."
        />
      ) : (
        <TableScroll label="Unit costs">
          <thead>
            <tr>
              <th scope="col">Unit</th>
              <th scope="col">Cost</th>
              <th scope="col">Treatment</th>
              <th scope="col">Basis</th>
              <th scope="col">Date</th>
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
            {costs.map((cost) => (
              <tr key={cost.id}>
                <th scope="row" className="mono">
                  {reference.get(cost.unit_id) ?? "—"}
                </th>
                <td>{costTypeLabel(cost.cost_type)}</td>
                <td>
                  {cost.cost_class === "direct" ? "Development" : "Variable selling"}
                </td>
                <td>{costBasisLabel(cost.basis)}</td>
                <td>{businessDate(cost.effective_date)}</td>
                <td className="num mono">{money(cost.amount, code)}</td>
                <td>
                  <Badge tone={cost.status === "reversed" ? "danger" : "neutral"}>
                    {cost.status === "reversed" ? "Reversed" : "Counted"}
                  </Badge>
                  {cost.reversal_reason ? (
                    <p className="hint">{cost.reversal_reason}</p>
                  ) : null}
                </td>
                <td>
                  {canWrite && cost.status === "active" ? (
                    <Button disabled={busy} onClick={() => setReversing(cost.id)}>
                      Reverse
                    </Button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      )}

      {recording ? (
        <RecordCostDialog
          rows={rows}
          busy={busy}
          onCancel={() => setRecording(false)}
          onSubmit={(unitId, body) => {
            setRecording(false);
            void onAct(
              () => unitEconomics.recordUnitCost(projectId, unitId, body),
              "Unit cost recorded.",
            );
          }}
        />
      ) : null}

      {reversing ? (
        <PromptDialog
          title="Reverse this cost"
          hint="The row stays, reversed, and stops counting towards the unit's profit."
          label="Reason"
          confirmLabel="Reverse"
          busy={busy}
          onCancel={() => setReversing(null)}
          onSubmit={(reason) => {
            const target = reversing;
            setReversing(null);
            void onAct(
              () => unitEconomics.reverseUnitCost(projectId, target, reason),
              "Unit cost reversed.",
            );
          }}
        />
      ) : null}
    </div>
  );
}

function RecordCostDialog({
  rows,
  busy,
  onCancel,
  onSubmit,
}: {
  rows: UnitEconomicsRow[];
  busy: boolean;
  onCancel: () => void;
  onSubmit: (unitId: string, body: Record<string, unknown>) => void;
}) {
  const [unitId, setUnitId] = useState(rows[0]?.unit_id ?? "");
  const [costType, setCostType] = useState<UnitCostType>("finishes");
  const [basis, setBasis] = useState("forecast");
  const [amount, setAmount] = useState("");
  const [effectiveDate, setEffectiveDate] = useState(todayISO());
  const [reference, setReference] = useState("");

  const chosen = rows.find((row) => row.unit_id === unitId);
  const saleId = chosen?.revenue_source === "sale_contract" ? chosen.revenue_source_id : null;

  return (
    <FormDialog
      title="Record a unit cost"
      description="The cost type decides whether this sits above or below gross profit. That is policy, not a choice on this form."
      confirmLabel="Record"
      busy={busy}
      disabled={unitId === "" || amount.trim() === ""}
      onCancel={onCancel}
      onSubmit={() =>
        onSubmit(unitId, {
          cost_type: costType,
          basis,
          amount: amount.trim(),
          effective_date: effectiveDate,
          ...(basis === "actual" && saleId ? { sale_contract_id: saleId } : {}),
          ...(reference.trim() ? { reference: reference.trim() } : {}),
        })
      }
    >
      <Field label="Unit">
        <select value={unitId} onChange={(event) => setUnitId(event.target.value)}>
          {rows.map((row) => (
            <option key={row.unit_id} value={row.unit_id}>
              {row.unit_reference}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Cost type">
        <select
          value={costType}
          onChange={(event) => setCostType(event.target.value as UnitCostType)}
        >
          <optgroup label="Development cost">
            {DIRECT_COST_TYPES.map((value) => (
              <option key={value} value={value}>
                {costTypeLabel(value)}
              </option>
            ))}
          </optgroup>
          <optgroup label="Variable selling cost">
            {SELLING_COST_TYPES.map((value) => (
              <option key={value} value={value}>
                {costTypeLabel(value)}
              </option>
            ))}
          </optgroup>
        </select>
      </Field>
      <Field
        label="Basis"
        hint={
          saleId
            ? "An actual cost on this unit is recorded against its live contract."
            : "An unsold unit is analysed on forecast costs."
        }
      >
        <select value={basis} onChange={(event) => setBasis(event.target.value)}>
          <option value="forecast">Forecast</option>
          <option value="actual">Actual</option>
        </select>
      </Field>
      <Field label="Amount">
        <input
          inputMode="decimal"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          required
        />
      </Field>
      <Field label="Effective date">
        <input
          type="date"
          value={effectiveDate}
          onChange={(event) => setEffectiveDate(event.target.value)}
          required
        />
      </Field>
      <Field label="Reference" hint="An invoice or purchase order number, if there is one.">
        <input value={reference} onChange={(event) => setReference(event.target.value)} />
      </Field>
    </FormDialog>
  );
}
