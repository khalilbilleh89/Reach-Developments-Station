"use client";

import { useCallback, useEffect, useState } from "react";

import {
  Badge,
  Button,
  ButtonRow,
  Card,
  DataToolbar,
  EmptyState,
  Field,
  FieldRow,
  FormDialog,
  InlineMeta,
  InlineMetaItem,
  Loading,
  Metric,
  MetricGroup,
  MoneyInput,
  Notice,
  PageHeader,
  PromptDialog,
  StatusDot,
  Steps,
  TableScroll,
  TabPanel,
  Tabs,
  ToolbarFilter,
  Waterfall,
  WaterfallRow,
} from "@/components/ui";
import { ApiError, inventory, unitEconomics } from "@/lib/api";
import type {
  AllocationMethod,
  AllocationVersion,
  AllocationVersionDetail,
  AreaType,
  Building,
  CalculationPreview,
  Phase,
  PoolCategory,
  PoolScope,
  ProjectEconomics,
  UnitCost,
  UnitCostType,
  UnitEconomics as UnitEconomicsRow,
} from "@/lib/api";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, isPositive, money, percent, todayISO } from "@/lib/format";
import { sectionDescription } from "@/components/shell/navigation";

import {
  ALLOCATION_METHODS,
  DIRECT_COST_TYPES,
  POOL_CATEGORIES,
  POOL_SCOPES,
  SELLING_COST_TYPES,
  basisLabel,
  categoryLabel,
  costBasisLabel,
  costTypeLabel,
  methodLabel,
  profitTone,
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

const VERSION_SEQUENCE = ["draft", "submitted", "approved", "active"];

/**
 * The project's unit economics: what each unit costs, and the basis that says so.
 *
 * Nothing on this screen is calculated in the browser. Allocation,
 * reconciliation, every profit layer and every ratio arrive from the API
 * already decided — the arithmetic is tested once, on the server, and a second
 * implementation here would be a second answer.
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
export function UnitEconomicsTab({ projectId, roles }: { projectId: string; roles: Set<string> }) {
  const currencyCodeOf = useCurrencyCode();
  const [tab, setTab] = useState("overview");
  const [summary, setSummary] = useState<ProjectEconomics | null>(null);
  const [rows, setRows] = useState<UnitEconomicsRow[] | null>(null);
  const [versions, setVersions] = useState<AllocationVersion[] | null>(null);
  const [costs, setCosts] = useState<UnitCost[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [denied, setDenied] = useState(false);
  // Separate from `denied`, because these are two different answers. A reader
  // scoped to selected phases may see their units' economics and may not see
  // the project's allocation versions — a cost basis carries every phase's
  // pool amounts, so opening one would hand them the costs of phases they were
  // never granted.
  const [governanceDenied, setGovernanceDenied] = useState(false);
  const [busy, setBusy] = useState(false);

  const canWrite = roles.has("finance");
  const canApprove = roles.has("finance") || roles.has("approver_cfo");

  const load = useCallback(async () => {
    try {
      const [nextSummary, nextRows, nextCosts] = await Promise.all([
        unitEconomics.summary(projectId),
        unitEconomics.units(projectId),
        unitEconomics.unitCosts(projectId),
      ]);
      setSummary(nextSummary);
      setRows(nextRows);
      setCosts(nextCosts);
      // Loaded apart from the rest so that one refusal does not read as the
      // reader having no access to economics at all.
      try {
        setVersions(await unitEconomics.versions(projectId));
        setGovernanceDenied(false);
      } catch (governance) {
        if (governance instanceof ApiError && governance.isForbidden) {
          setVersions([]);
          setGovernanceDenied(true);
        } else {
          throw governance;
        }
      }
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

  const header = <PageHeader title="Unit Economics" subtitle={sectionDescription("economics")} compact />;

  if (denied) {
    return (
      <>
        {header}
        <Card>
          <EmptyState
            title="Not available to your role"
            hint="Unit cost and margin are restricted to Finance, the CFO, project management, executives and audit."
          />
        </Card>
      </>
    );
  }
  if (summary === null || rows === null || versions === null || costs === null) {
    return (
      <>
        {header}
        {error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading unit economics…" shape="metrics" />}
      </>
    );
  }

  const code = currencyCodeOf(summary.currency_id);

  return (
    <>
      {header}
      <div className="stack">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}

        <Tabs label="Unit economics sections" tabs={TABS} active={tab} onSelect={setTab} />
        <TabPanel group="Unit economics sections" tab={tab}>
          {tab === "overview" ? <Overview summary={summary} code={code} onOpenVersions={() => setTab("versions")} canWrite={canWrite} /> : null}
          {tab === "units" ? <UnitsRegister rows={rows} code={code} /> : null}
          {tab === "versions" ? (
            governanceDenied ? (
              <Card>
                <EmptyState
                  title="Not available at your phase scope"
                  hint="A cost basis covers the whole project, including phases outside your access. Your units' economics stay available."
                />
              </Card>
            ) : (
              <Versions
                projectId={projectId}
                versions={versions}
                code={code}
                canWrite={canWrite}
                canApprove={canApprove}
                busy={busy}
                onAct={act}
              />
            )
          ) : null}
          {tab === "costs" ? (
            <UnitCosts projectId={projectId} costs={costs} rows={rows} code={code} canWrite={canWrite} busy={busy} onAct={act} />
          ) : null}
        </TabPanel>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------------- */

function Overview({
  summary,
  code,
  canWrite,
  onOpenVersions,
}: {
  summary: ProjectEconomics;
  code: string | null;
  canWrite: boolean;
  onOpenVersions: () => void;
}) {
  const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? "" : "s"}`;

  if (summary.active_version === null) {
    return (
      <Card>
        <EmptyState
          title="No approved cost allocation basis yet"
          hint="Create the opening Finance allocation version, reconcile it to its cost pools, and make it current. Until then no unit's profitability can be calculated, and none is invented."
          actions={
            canWrite ? (
              <Button variant="primary" onClick={onOpenVersions}>
                Allocation versions
              </Button>
            ) : undefined
          }
        />
      </Card>
    );
  }

  const version = summary.active_version;

  return (
    <div className="grid-12">
      <div className="span-12">
        <Card>
          <MetricGroup>
            <Metric label="Revenue" value={money(summary.revenue_total, code)} size="lg" />
            <Metric label="Total cost" value={money(summary.total_cost_total, code)} size="lg" />
            <Metric
              label="Profit after finance"
              value={money(summary.profit_total, code)}
              size="lg"
              tone={summary.profit_total.startsWith("-") ? "danger" : "neutral"}
            />
            <Metric label="Margin" value={percent(summary.margin_fraction)} size="lg" />
            <Metric label="Return on cost" value={percent(summary.return_on_cost_fraction)} size="lg" />
          </MetricGroup>
          <p className="footnote">
            Totals cover {summary.comparable_unit_count} of {summary.unit_count} units: sold units on the
            frozen terms and basis they were sold under, unsold units on today&rsquo;s approved price and
            today&rsquo;s basis. Margin is total profit over total revenue and return on cost is total
            profit over total cost — weighted on the server, never the average of the unit ratios.
          </p>
          {summary.currency_mismatch_count > 0 ? (
            <Notice tone="warning">
              {plural(summary.currency_mismatch_count, "unit")} cannot be included because revenue and project
              cost currency differ. There is no exchange rate in this system, so those units are reported on
              their own and never added to these totals.
            </Notice>
          ) : null}
        </Card>
      </div>

      <div className="span-7">
        <Card title="Profit waterfall" description="Every line is the server's. Read top to bottom.">
          <Waterfall>
            <WaterfallRow label="Revenue" amount={money(summary.revenue_total, code)} kind="subtotal" />
            <WaterfallRow
              label="Development cost"
              note="Land, hard and soft pools allocated to units, plus direct unit costs"
              amount={money(summary.development_cost_total, code)}
            />
            <WaterfallRow label="Gross profit" amount={money(summary.gross_profit_total, code)} kind="subtotal" />
            <WaterfallRow
              label="Commercial cost"
              note="Variable selling costs and seller-borne concessions"
              amount={money(summary.commercial_cost_total, code)}
            />
            <WaterfallRow label="Contribution profit" amount={money(summary.contribution_profit_total, code)} kind="subtotal" />
            <WaterfallRow
              label="Finance cost"
              note={version.finance_treatment === "allocated" ? "Allocated to units on this basis" : "Excluded from this basis"}
              amount={money(summary.finance_cost_total, code)}
            />
            <WaterfallRow label="Profit after finance" amount={money(summary.profit_total, code)} kind="total" />
          </Waterfall>
        </Card>
      </div>

      <div className="span-5">
        <Card
          title="Allocation basis"
          description="The governed version turning shared project cost into unit cost."
          actions={
            <Button small variant="quiet" onClick={onOpenVersions}>
              Versions
            </Button>
          }
        >
          <InlineMeta>
            <InlineMetaItem label="Basis">v{version.version_number}</InlineMetaItem>
            <InlineMetaItem label="Status">
              <Badge tone={versionTone(version.status)}>{versionLabel(version.status)}</Badge>
            </InlineMetaItem>
            <InlineMetaItem label="Effective">{businessDate(version.effective_from)}</InlineMetaItem>
            <InlineMetaItem label="Finance cost">
              {version.finance_treatment === "allocated" ? "Allocated" : "Excluded"}
            </InlineMetaItem>
          </InlineMeta>
          <h3 className="section-heading">Units</h3>
          <MetricGroup compact>
            <Metric label="Sold basis" value={summary.sold_count} size="sm" />
            <Metric label="Forecast basis" value={summary.unsold_count} size="sm" />
            <Metric
              label="Loss-making"
              value={summary.negative_profit_count}
              size="sm"
              tone={summary.negative_profit_count > 0 ? "danger" : "neutral"}
              note="Profit after finance below zero"
            />
            <Metric
              label="Below minimum margin"
              value={summary.below_threshold_count}
              size="sm"
              tone={summary.below_threshold_count > 0 ? "warning" : "neutral"}
              note={summary.threshold_fraction ? `Threshold ${percent(summary.threshold_fraction)}` : "No threshold configured"}
            />
            <Metric
              label="Incomplete"
              value={summary.incomplete_count}
              size="sm"
              tone={summary.incomplete_count > 0 ? "warning" : "neutral"}
              note="No price or no cost basis"
            />
            <Metric
              label="Currency differs"
              value={summary.currency_mismatch_count}
              size="sm"
              tone={summary.currency_mismatch_count > 0 ? "warning" : "neutral"}
              note="Reported apart, never combined"
            />
          </MetricGroup>
        </Card>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------------- */

function UnitsRegister({ rows, code }: { rows: UnitEconomicsRow[]; code: string | null }) {
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
    if (only === "loss") return row.profit_after_finance !== null && row.profit_after_finance.startsWith("-");
    if (only === "below") return row.below_margin_threshold === true;
    if (only === "incomplete") return row.profitability_status !== "ready";
    return true;
  });

  return (
    <div className="stack">
      <DataToolbar
        search={{ value: search, onChange: setSearch, placeholder: "Unit reference", label: "Search units" }}
        count={{ shown: shown.length, total: rows.length, noun: "unit" }}
        onReset={
          search || only !== "all"
            ? () => {
                setSearch("");
                setOnly("all");
              }
            : undefined
        }
      >
        <ToolbarFilter label="Show">
          <select className="input" value={only} onChange={(event) => setOnly(event.target.value)}>
            <option value="all">Every unit</option>
            <option value="sold">Sold basis</option>
            <option value="unsold">Forecast basis</option>
            <option value="loss">Loss-making</option>
            <option value="below">Below minimum margin</option>
            <option value="incomplete">Incomplete economics</option>
          </select>
        </ToolbarFilter>
      </DataToolbar>

      <Card flush>
        {shown.length === 0 ? (
          <div className="card-body">
            <EmptyState title="No units match" hint="Widen the filter, or record a cost basis so units can be analysed." />
          </div>
        ) : (
          <TableScroll label="Unit economics" fixedFirst>
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
                      <span className="cell-secondary">v{row.allocation_version_number}</span>
                    )}
                  </td>
                  <td className="num">{money(row.revenue, currencyCodeOf(row.revenue_currency_id))}</td>
                  <td className="num">{money(row.land_cost, code)}</td>
                  <td className="num">{money(row.hard_cost, code)}</td>
                  <td className="num">{money(row.soft_cost, code)}</td>
                  <td className="num">{money(row.direct_cost, code)}</td>
                  <td className="num">
                    {money(row.variable_selling_cost, code)}
                    {isPositive(row.seller_cost) ? (
                      <span className="cell-secondary">+{money(row.seller_cost, code)} seller</span>
                    ) : null}
                  </td>
                  <td className="num">{money(row.finance_cost ?? row.allocated_finance_cost, code)}</td>
                  <td className="num">{money(row.total_cost, code)}</td>
                  <td className="num">
                    {row.profit_after_finance === null ? (
                      "—"
                    ) : (
                      <span className={profitTone(row.profit_after_finance) === "danger" ? "status-dot status-dot-danger" : undefined}>
                        {money(row.profit_after_finance, code)}
                      </span>
                    )}
                  </td>
                  <td className="num">{percent(row.margin_fraction)}</td>
                  <td className="num">{percent(row.return_on_cost_fraction)}</td>
                  <td className="cell-prose">
                    {row.profitability_status === "ready" ? (
                      <StatusDot tone="success">Calculated</StatusDot>
                    ) : (
                      <Badge tone={profitabilityTone(row.profitability_status)}>
                        {profitabilityLabel(row.profitability_status)}
                      </Badge>
                    )}
                    {row.below_margin_threshold ? <span className="cell-secondary">Below the minimum margin</span> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        )}
      </Card>
      <p className="footnote">
        Where a state is not &ldquo;Calculated&rdquo; the zeros beside it are missing figures, not a cost of
        nothing. Open the unit for the reason.
      </p>
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

  const after = (run: () => Promise<unknown>, done: string) => void onAct(run, done).then(() => void loadDetail());

  return (
    <div className="grid-12">
      <div className="span-4">
        <Card
          title="Versions"
          description="One governed basis at a time. A sold unit keeps the version that governed when its contract was signed."
          actions={
            canWrite ? (
              <Button variant="primary" small disabled={busy} onClick={() => setCreating(true)}>
                New version
              </Button>
            ) : undefined
          }
          flush
        >
          {versions.length === 0 ? (
            <div className="card-body">
              <EmptyState
                compact
                title="No cost basis yet"
                hint="Create the opening Finance allocation version to calculate unit profitability."
              />
            </div>
          ) : (
            <ul className="version-list" style={{ margin: 0, padding: "0.25rem 0" }}>
              {versions.map((version) => (
                <li key={version.id}>
                  <button
                    type="button"
                    className="switcher-option"
                    style={{ borderRadius: 0, padding: "0.625rem 1.5rem" }}
                    aria-current={version.id === open ? "true" : undefined}
                    onClick={() => {
                      setOpen(version.id);
                      setPreview(null);
                    }}
                  >
                    <span className="switcher-option-code">v{version.version_number}</span>
                    <span className="switcher-option-name">
                      {businessDate(version.effective_from)}
                      {version.effective_to ? ` – ${businessDate(version.effective_to)}` : ""}
                    </span>
                    <Badge tone={versionTone(version.status)}>{versionLabel(version.status)}</Badge>
                    <span className="switcher-option-meta">
                      {version.finance_treatment === "allocated" ? "Finance allocated" : "Finance excluded"}
                      {version.rejection_reason ? ` · ${version.rejection_reason}` : ""}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="span-8">
        {detail ? (
          <VersionFile
            projectId={projectId}
            detail={detail}
            preview={preview}
            code={code}
            canWrite={canWrite}
            canApprove={canApprove}
            busy={busy}
            onAddPool={() => setAddingPool(true)}
            onCalculate={() =>
              void onAct(async () => {
                setPreview(await unitEconomics.calculate(projectId, detail.version.id));
              }, "Allocation calculated.").then(() => void loadDetail())
            }
            onSubmit={() => after(() => unitEconomics.submitVersion(projectId, detail.version.id), "Cost basis submitted for approval.")}
            onApprove={() => after(() => unitEconomics.approveVersion(projectId, detail.version.id), "Cost basis approved.")}
            onReject={() => setRejecting(detail.version.id)}
            onActivate={() => after(() => unitEconomics.activateVersion(projectId, detail.version.id), "Cost basis is now current.")}
            onClone={() =>
              after(
                () =>
                  unitEconomics.cloneVersion(projectId, detail.version.id, {
                    effective_from: todayISO(),
                    change_reason: `Revision of version ${detail.version.version_number}`,
                  }),
                "Cloned to a new draft.",
              )
            }
            onRemovePool={(poolId) =>
              after(() => unitEconomics.removePool(projectId, detail.version.id, poolId), "Pool removed from the draft.")
            }
          />
        ) : versions.length > 0 ? (
          <Card>
            <Loading label="Loading the version…" shape="metrics" />
          </Card>
        ) : null}
      </div>

      {creating ? (
        <NewVersionDialog
          busy={busy}
          onCancel={() => setCreating(false)}
          onSubmit={(body) => {
            setCreating(false);
            void onAct(() => unitEconomics.createVersion(projectId, body), "Draft cost basis created.");
          }}
        />
      ) : null}

      {addingPool && detail ? (
        <NewPoolDialog
          projectId={projectId}
          code={code}
          busy={busy}
          onCancel={() => setAddingPool(false)}
          onSubmit={(body) => {
            setAddingPool(false);
            after(() => unitEconomics.addPool(projectId, detail.version.id, body), "Cost pool added.");
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
            after(() => unitEconomics.rejectVersion(projectId, target, reason), "Cost basis rejected.");
          }}
        />
      ) : null}
    </div>
  );
}

/**
 * One allocation version: its header, its lifecycle, its pools, and whether
 * the pools reconcile to what was allocated. A zero variance is calm; a
 * failure is impossible to miss.
 */
function VersionFile({
  projectId,
  detail,
  preview,
  code,
  canWrite,
  canApprove,
  busy,
  onAddPool,
  onCalculate,
  onSubmit,
  onApprove,
  onReject,
  onActivate,
  onClone,
  onRemovePool,
}: {
  projectId: string;
  detail: AllocationVersionDetail;
  preview: CalculationPreview | null;
  code: string | null;
  canWrite: boolean;
  canApprove: boolean;
  busy: boolean;
  onAddPool: () => void;
  onCalculate: () => void;
  onSubmit: () => void;
  onApprove: () => void;
  onReject: () => void;
  onActivate: () => void;
  onClone: () => void;
  onRemovePool: (poolId: string) => void;
}) {
  const currencyCodeOf = useCurrencyCode();
  const version = detail.version;
  const reconciliation = detail.reconciliation;
  const draft = version.status === "draft";
  void projectId;

  return (
    <Card
      title={`Cost basis v${version.version_number}`}
      description={version.change_reason}
      actions={
        <ButtonRow>
          {canWrite && draft ? (
            <>
              <Button disabled={busy} onClick={onAddPool}>
                Add pool
              </Button>
              <Button disabled={busy} onClick={onCalculate}>
                Calculate
              </Button>
              <Button variant="primary" disabled={busy} onClick={onSubmit}>
                Submit
              </Button>
            </>
          ) : null}
          {canApprove && version.status === "submitted" ? (
            <>
              <Button variant="primary" disabled={busy} onClick={onApprove}>
                Approve
              </Button>
              <Button variant="danger" disabled={busy} onClick={onReject}>
                Reject
              </Button>
            </>
          ) : null}
          {canWrite && version.status === "approved" ? (
            <Button variant="primary" disabled={busy} onClick={onActivate}>
              Make current
            </Button>
          ) : null}
          {canWrite && !draft ? (
            <Button disabled={busy} onClick={onClone}>
              Clone
            </Button>
          ) : null}
        </ButtonRow>
      }
    >
      <div className="stack stack-tight">
        <Steps
          label="Cost basis lifecycle"
          steps={VERSION_SEQUENCE.map((key) => ({
            key,
            label: versionLabel(key as AllocationVersion["status"]),
            state:
              key === version.status
                ? "current"
                : version.status === "superseded" || VERSION_SEQUENCE.indexOf(key) < VERSION_SEQUENCE.indexOf(version.status)
                  ? "done"
                  : "pending",
          }))}
        />
        <InlineMeta>
          <InlineMetaItem label="Status">
            <Badge tone={versionTone(version.status)}>{versionLabel(version.status)}</Badge>
          </InlineMetaItem>
          <InlineMetaItem label="Effective">
            {businessDate(version.effective_from)}
            {version.effective_to ? ` – ${businessDate(version.effective_to)}` : ""}
          </InlineMetaItem>
          <InlineMetaItem label="Currency">{currencyCodeOf(version.currency_id) ?? "—"}</InlineMetaItem>
          <InlineMetaItem label="Finance treatment">
            {version.finance_treatment === "allocated" ? "Allocated to units" : "Excluded from this basis"}
          </InlineMetaItem>
          {version.calculated_at ? (
            <InlineMetaItem label="Calculated">{version.calculated_at.slice(0, 10)}</InlineMetaItem>
          ) : null}
        </InlineMeta>
        {version.rejection_reason ? <Notice tone="error">Rejected: {version.rejection_reason}</Notice> : null}
      </div>

      {detail.stale_sources.length > 0 ? (
        <Notice tone="warning">
          This basis was calculated against sources that have since changed — {detail.stale_sources.join("; ")}.
          It cannot be made current until it is recalculated.
        </Notice>
      ) : null}

      <h3 className="section-heading">Reconciliation</h3>
      <MetricGroup>
        <Metric label="Source cost" value={money(reconciliation.source_cost_total, code)} />
        <Metric label="Allocated" value={money(reconciliation.allocated_cost_total, code)} />
        <Metric
          label="Variance"
          value={money(reconciliation.variance, code)}
          tone={reconciliation.reconciled ? "success" : "danger"}
        />
        <Metric label="Pools" value={reconciliation.pool_count} size="sm" />
        <Metric label="Allocations" value={reconciliation.allocation_count} size="sm" />
      </MetricGroup>
      <div className={reconciliation.reconciled ? "reconcile reconcile-ok" : "reconcile reconcile-fail"} role="status">
        <span className="reconcile-title">
          {reconciliation.reconciled ? "Reconciled." : "Does not reconcile."}
        </span>
        <span>
          {reconciliation.reconciled
            ? "Every pool is allocated to its units exactly, residual included."
            : reconciliation.unreconciled_pools.length > 0
              ? `Unreconciled: ${reconciliation.unreconciled_pools.join(", ")}. Calculate again, or fix the pools.`
              : "Calculate the basis to allocate its pools."}
        </span>
      </div>

      <h3 className="section-heading">Cost pools</h3>
      {detail.pools.length === 0 ? (
        <EmptyState
          compact
          title="No cost pools yet"
          hint="A basis must address land, hard and soft cost explicitly before it can be submitted. Record a zero pool where the cost is genuinely nil."
        />
      ) : (
        <TableScroll label="Cost pools" compact>
          <thead>
            <tr>
              <th scope="col">Pool</th>
              <th scope="col">Category</th>
              <th scope="col">Scope</th>
              <th scope="col">Method</th>
              <th scope="col" className="num">
                Amount
              </th>
              <th scope="col" className="num">
                Allocated
              </th>
              <th scope="col" className="num">
                Variance
              </th>
              {canWrite && draft ? (
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {detail.pools.map((pool) => {
              const line = preview?.pools.find((row) => row.pool_id === pool.id);
              return (
                <tr key={pool.id}>
                  <th scope="row">
                    <span className="mono">{pool.pool_number}</span>
                    <span className="cell-secondary">{pool.name}</span>
                  </th>
                  <td>{categoryLabel(pool.category)}</td>
                  <td>{scopeLabel(pool.scope_kind)}</td>
                  <td>{methodLabel(pool.allocation_method)}</td>
                  <td className="num">
                    {money(pool.amount, code)}
                    <span className="cell-secondary">
                      {pool.source_kind === "project_land" ? "From the land register" : "Forecast input"}
                    </span>
                  </td>
                  <td className="num">{line ? money(line.allocated_total, code) : "—"}</td>
                  <td className="num">
                    {line ? (
                      <StatusDot tone={isPositive(line.variance) || line.variance.startsWith("-") ? "danger" : "success"}>
                        {money(line.variance, code)}
                      </StatusDot>
                    ) : (
                      "—"
                    )}
                  </td>
                  {canWrite && draft ? (
                    <td>
                      <Button small variant="quiet" disabled={busy} onClick={() => onRemovePool(pool.id)}>
                        Remove
                      </Button>
                    </td>
                  ) : null}
                </tr>
              );
            })}
          </tbody>
        </TableScroll>
      )}
      {preview === null && draft ? (
        <p className="footnote">Allocated and variance per pool appear after Calculate.</p>
      ) : null}
    </Card>
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
      onSubmit={() => onSubmit({ effective_from: effectiveFrom, change_reason: reason.trim(), finance_treatment: treatment })}
    >
      <Field label="Effective from" hint="The date this basis starts governing.">
        <input
          className="input input-short"
          type="date"
          value={effectiveFrom}
          onChange={(event) => setEffectiveFrom(event.target.value)}
          required
        />
      </Field>
      <Field label="Reason">
        <textarea className="input" value={reason} onChange={(event) => setReason(event.target.value)} rows={3} required />
      </Field>
      <Field
        label="Finance cost"
        hint="Excluded is a statement, not an omission: the screens say finance cost is excluded rather than implying it is nil."
      >
        <select className="input" value={treatment} onChange={(event) => setTreatment(event.target.value)}>
          <option value="excluded">Excluded from this basis</option>
          <option value="allocated">Allocated to units</option>
        </select>
      </Field>
    </FormDialog>
  );
}

function NewPoolDialog({
  projectId,
  code,
  busy,
  onCancel,
  onSubmit,
}: {
  projectId: string;
  code: string | null;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (body: Record<string, unknown>) => void;
}) {
  const [poolNumber, setPoolNumber] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState<PoolCategory>("hard");
  const [amount, setAmount] = useState("0.00");
  const [scope, setScope] = useState<PoolScope>("project");
  const [phaseId, setPhaseId] = useState("");
  const [buildingId, setBuildingId] = useState("");
  const [method, setMethod] = useState<AllocationMethod>("unit_count");
  const [areaTypeId, setAreaTypeId] = useState("");
  const [phases, setPhases] = useState<Phase[]>([]);
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [areaTypes, setAreaTypes] = useState<AreaType[]>([]);

  // A scoped pool is the only way to close a coverage gap — a phase carrying
  // none of a category needs an explicit zero pool of its own — so the shapes
  // this form can express have to be the shapes the server accepts.
  useEffect(() => {
    void (async () => {
      try {
        const [nextPhases, nextBuildings, nextAreaTypes] = await Promise.all([
          inventory.phases(projectId),
          inventory.buildings(projectId),
          inventory.areaTypes(projectId),
        ]);
        setPhases(nextPhases);
        setBuildings(nextBuildings);
        setAreaTypes(nextAreaTypes);
      } catch {
        // The pickers stay empty and the scope stays project-wide. A failed
        // lookup must not stop somebody adding an ordinary pool.
      }
    })();
  }, [projectId]);

  // Land is the register's figure, always. There is no second land number to
  // type, and a project-wide scope is the only defensible one without a
  // governed parcel-to-phase attribution.
  const derived = category === "land";
  const scopeKind = derived ? "project" : scope;
  const needsArea = method === "raw_area";

  return (
    <FormDialog
      title="Add a cost pool"
      description="One shared amount and the rule for dividing it. Manual amounts are a current forecast allocation input, not a construction ledger."
      confirmLabel="Add pool"
      busy={busy}
      disabled={
        poolNumber.trim().length === 0 ||
        name.trim().length === 0 ||
        (scopeKind === "phase" && phaseId === "") ||
        (scopeKind === "building" && buildingId === "") ||
        (needsArea && areaTypeId === "")
      }
      onCancel={onCancel}
      onSubmit={() =>
        onSubmit({
          pool_number: poolNumber.trim(),
          name: name.trim(),
          category,
          source_kind: derived ? "project_land" : "manual",
          ...(derived ? {} : { amount }),
          scope_kind: scopeKind,
          ...(scopeKind === "phase" ? { phase_id: phaseId } : {}),
          ...(scopeKind === "building" ? { building_id: buildingId } : {}),
          allocation_method: method,
          ...(needsArea ? { area_type_id: areaTypeId } : {}),
        })
      }
    >
      <FieldRow columns={2}>
        <Field label="Reference">
          <input className="input" value={poolNumber} onChange={(event) => setPoolNumber(event.target.value)} placeholder="HARD-01" required />
        </Field>
        <Field label="Category">
          <select className="input" value={category} onChange={(event) => setCategory(event.target.value as PoolCategory)}>
            {POOL_CATEGORIES.map((value) => (
              <option key={value} value={value}>
                {categoryLabel(value)}
              </option>
            ))}
          </select>
        </Field>
      </FieldRow>
      <Field label="Name">
        <input className="input" value={name} onChange={(event) => setName(event.target.value)} required />
      </Field>
      {derived ? (
        <Notice tone="info">
          Land cost comes from this project&apos;s land register — the parcels&apos; purchase price and
          acquisition fees — and is re-derived when the basis is made current. There is no amount to enter.
        </Notice>
      ) : (
        <FieldRow columns={2}>
          <Field label="Amount">
            <MoneyInput code={code} value={amount} onChange={setAmount} required />
          </Field>
          <Field label="Scope" hint="A pool reaches the units in its scope and no others.">
            <select className="input" value={scope} onChange={(event) => setScope(event.target.value as PoolScope)}>
              {POOL_SCOPES.map((value) => (
                <option key={value} value={value}>
                  {scopeLabel(value)}
                </option>
              ))}
            </select>
          </Field>
        </FieldRow>
      )}
      {scopeKind === "phase" ? (
        <Field label="Phase">
          <select className="input" value={phaseId} onChange={(event) => setPhaseId(event.target.value)} required>
            <option value="">Choose a phase</option>
            {phases.map((phase) => (
              <option key={phase.id} value={phase.id}>
                {phase.code} — {phase.name}
              </option>
            ))}
          </select>
        </Field>
      ) : null}
      {scopeKind === "building" ? (
        <Field label="Building">
          <select className="input" value={buildingId} onChange={(event) => setBuildingId(event.target.value)} required>
            <option value="">Choose a building</option>
            {buildings.map((building) => (
              <option key={building.id} value={building.id}>
                {building.code} — {building.name}
              </option>
            ))}
          </select>
        </Field>
      ) : null}
      <Field
        label="Allocation method"
        hint="Weighted and raw area read the approved area schedule; revenue value reads the current approved price."
      >
        <select className="input" value={method} onChange={(event) => setMethod(event.target.value as AllocationMethod)}>
          {ALLOCATION_METHODS.map((value) => (
            <option key={value} value={value}>
              {methodLabel(value)}
            </option>
          ))}
        </select>
      </Field>
      {needsArea ? (
        <Field label="Area type" hint="Raw area divides by one measured area exactly as recorded, without the weighting the price uses.">
          <select className="input" value={areaTypeId} onChange={(event) => setAreaTypeId(event.target.value)} required>
            <option value="">Choose an area type</option>
            {areaTypes.map((areaType) => (
              <option key={areaType.id} value={areaType.id}>
                {areaType.code} — {areaType.label}
              </option>
            ))}
          </select>
        </Field>
      ) : null}
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
  const [search, setSearch] = useState("");
  const reference = new Map(rows.map((row) => [row.unit_id, row.unit_reference]));
  const needle = search.trim().toLowerCase();
  const shown = costs.filter(
    (cost) => !needle || `${reference.get(cost.unit_id) ?? ""} ${costTypeLabel(cost.cost_type)} ${cost.reference ?? ""}`.toLowerCase().includes(needle),
  );

  return (
    <div className="stack">
      <DataToolbar
        search={{ value: search, onChange: setSearch, placeholder: "Unit, cost type or reference", label: "Search unit costs" }}
        count={{ shown: shown.length, total: costs.length, noun: "cost" }}
        actions={
          canWrite ? (
            <Button variant="primary" disabled={busy} onClick={() => setRecording(true)}>
              Record a cost
            </Button>
          ) : undefined
        }
      />

      <Card flush>
        {shown.length === 0 ? (
          <div className="card-body">
            <EmptyState
              title={costs.length === 0 ? "No unit-specific costs recorded" : "No cost matches"}
              hint={
                costs.length === 0
                  ? "Upgrades, furniture, commissions and other costs belonging to a single unit are recorded here. Recorded, never edited; corrected by reversal and replacement."
                  : "Try another word."
              }
            />
          </div>
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
                {canWrite ? (
                  <th scope="col">
                    <span className="visually-hidden">Actions</span>
                  </th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {shown.map((cost) => (
                <tr key={cost.id}>
                  <th scope="row" className="mono">
                    {reference.get(cost.unit_id) ?? "—"}
                  </th>
                  <td>
                    {costTypeLabel(cost.cost_type)}
                    {cost.reference ? <span className="cell-secondary mono">{cost.reference}</span> : null}
                  </td>
                  <td>{cost.cost_class === "direct" ? "Development" : "Variable selling"}</td>
                  <td>{costBasisLabel(cost.basis)}</td>
                  <td className="figure">{businessDate(cost.effective_date)}</td>
                  <td className="num">{money(cost.amount, code)}</td>
                  <td>
                    {cost.status === "reversed" ? (
                      <StatusDot tone="danger">Reversed</StatusDot>
                    ) : (
                      <StatusDot tone="success">Counted</StatusDot>
                    )}
                    {cost.reversal_reason ? <span className="cell-secondary">{cost.reversal_reason}</span> : null}
                  </td>
                  {canWrite ? (
                    <td>
                      {cost.status === "active" ? (
                        <Button small variant="quiet" disabled={busy} onClick={() => setReversing(cost.id)}>
                          Reverse
                        </Button>
                      ) : null}
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </TableScroll>
        )}
      </Card>

      {recording ? (
        <RecordCostDialog
          rows={rows}
          code={code}
          busy={busy}
          onCancel={() => setRecording(false)}
          onSubmit={(unitId, body) => {
            setRecording(false);
            void onAct(() => unitEconomics.recordUnitCost(projectId, unitId, body), "Unit cost recorded.");
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
            void onAct(() => unitEconomics.reverseUnitCost(projectId, target, reason), "Unit cost reversed.");
          }}
        />
      ) : null}
    </div>
  );
}

function RecordCostDialog({
  rows,
  code,
  busy,
  onCancel,
  onSubmit,
}: {
  rows: UnitEconomicsRow[];
  code: string | null;
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
  const [chargeToDeal, setChargeToDeal] = useState(true);

  const chosen = rows.find((row) => row.unit_id === unitId);
  const saleId = chosen?.revenue_source === "sale_contract" ? chosen.revenue_source_id : null;
  const isSelling = SELLING_COST_TYPES.includes(costType);

  // Which contract a cost may name follows from its class, not from whether the
  // unit happens to be sold. A commission was incurred to win one buyer and must
  // name them, or it would be charged to the unit again after they walk away. A
  // rectification belongs to the building and may predate every buyer, so it may
  // be recorded with no contract at all.
  const attachSale = basis === "actual" && saleId !== null && (isSelling || chargeToDeal);
  const sellingNeedsASale = basis === "actual" && isSelling && saleId === null;

  return (
    <FormDialog
      title="Record a unit cost"
      description="The cost type decides whether this sits above or below gross profit. That is policy, not a choice on this form."
      confirmLabel="Record"
      busy={busy}
      disabled={unitId === "" || amount.trim() === "" || sellingNeedsASale}
      onCancel={onCancel}
      onSubmit={() =>
        onSubmit(unitId, {
          cost_type: costType,
          basis,
          amount: amount.trim(),
          effective_date: effectiveDate,
          ...(attachSale ? { sale_contract_id: saleId } : {}),
          ...(reference.trim() ? { reference: reference.trim() } : {}),
        })
      }
    >
      <FieldRow columns={2}>
        <Field label="Unit">
          <select className="input" value={unitId} onChange={(event) => setUnitId(event.target.value)}>
            {rows.map((row) => (
              <option key={row.unit_id} value={row.unit_id}>
                {row.unit_reference}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Cost type">
          <select className="input" value={costType} onChange={(event) => setCostType(event.target.value as UnitCostType)}>
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
      </FieldRow>
      <FieldRow columns={2}>
        <Field
          label="Basis"
          hint={saleId ? "Forecast is what the unit is expected to cost; actuals are what the deal is judged on." : "An unsold unit is analysed on forecast costs."}
        >
          <select className="input" value={basis} onChange={(event) => setBasis(event.target.value)}>
            <option value="forecast">Forecast</option>
            <option value="actual">Actual</option>
          </select>
        </Field>
        {basis === "actual" && saleId !== null && !isSelling ? (
          <Field label="Belongs to" hint="A cost incurred before this buyer arrived stays with the unit.">
            <select className="input" value={chargeToDeal ? "deal" : "unit"} onChange={(event) => setChargeToDeal(event.target.value === "deal")}>
              <option value="deal">This deal</option>
              <option value="unit">The unit itself</option>
            </select>
          </Field>
        ) : null}
      </FieldRow>
      {sellingNeedsASale ? (
        <Notice tone="warning">
          A selling cost is incurred to win one buyer, so it needs a live contract to record against. This unit has none.
        </Notice>
      ) : null}
      <FieldRow columns={2}>
        <Field label="Amount">
          <MoneyInput code={code} value={amount} onChange={setAmount} required />
        </Field>
        <Field label="Effective date">
          <input className="input input-short" type="date" value={effectiveDate} onChange={(event) => setEffectiveDate(event.target.value)} required />
        </Field>
      </FieldRow>
      <Field label="Reference" optional hint="An invoice or purchase order number.">
        <input className="input" value={reference} onChange={(event) => setReference(event.target.value)} />
      </Field>
    </FormDialog>
  );
}
