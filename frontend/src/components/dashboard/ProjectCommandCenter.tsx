"use client";

import type { ReactNode } from "react";

import {
  cashflow,
  collections,
  inventory,
  paymentPlans,
  pricing,
  sales,
  unitEconomics,
} from "@/lib/api";
import type {
  CashflowSummary,
  CollectionProjectSummary,
  PlanRegister,
  PriceRegister,
  PricingOverview,
  ProjectDetail,
  ProjectEconomics,
  SalesRegister,
  UnitRegister,
} from "@/lib/api";
import { useAnswer } from "@/lib/answer";
import type { Answer } from "@/lib/answer";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, isPositive, money, percent } from "@/lib/format";
import {
  CASHFLOW_READERS,
  COLLECTION_READERS,
  ECONOMICS_READERS,
  INTERNAL_PRICE_READERS,
  PLAN_READERS,
  SALES_READERS,
  hasAnyRole,
} from "@/lib/roles";
import type { Roles } from "@/lib/roles";
import type { ProjectSection } from "@/components/shell/navigation";
import {
  Breakdown,
  BreakdownRow,
  Button,
  Card,
  Distribution,
  DistributionBand,
  EmptyState,
  KeyValue,
  KeyValueGrid,
  Loading,
  Metric,
  MetricGroup,
  Notice,
  Position,
  PositionFigure,
  PositionSupport,
  PositionSupportItem,
  SectionHeader,
} from "@/components/ui";
import {
  AGING_BUCKETS,
  bucketHeatForAmount,
  bucketLabel,
} from "@/components/projects/collections/labels";
import { AttentionPanel } from "./AttentionPanel";
import type { AttentionItem } from "./AttentionPanel";
import { ProjectPlate } from "./ProjectPlate";

/**
 * The project's front page: what is happening in this development right now.
 *
 * Every figure is a value one of the module summary endpoints returned on
 * this request, laid out so related facts sit together — the economic
 * position beside the commercial one, collections beside development. Nothing
 * is added, averaged or projected in the browser; where a module cannot
 * produce a trustworthy figure — a project selling in two currencies has no
 * single contracted value — the card says so and shows none.
 *
 * Each card loads on its own. One module failing leaves the others standing,
 * with a precise notice where the gap is, rather than the whole page falling
 * over or quietly showing zero.
 */
export function ProjectCommandCenter({
  project,
  roles,
  canEdit,
  onEdit,
  onNavigate,
  refreshKey,
}: {
  project: ProjectDetail;
  roles: Roles;
  canEdit: boolean;
  onEdit: () => void;
  onNavigate: (section: ProjectSection) => void;
  /** Bumped by the workspace after a change, so the cards reload. */
  refreshKey: number;
}) {
  const currencyCodeOf = useCurrencyCode();
  const id = project.id;
  const operational = project.status !== "setup";
  const seesPricing = hasAnyRole(roles, INTERNAL_PRICE_READERS);
  const seesSales = hasAnyRole(roles, SALES_READERS);
  const seesPlans = hasAnyRole(roles, PLAN_READERS);
  const seesCollections = hasAnyRole(roles, COLLECTION_READERS);
  const seesEconomics = hasAnyRole(roles, ECONOMICS_READERS);
  const seesCashflow = hasAnyRole(roles, CASHFLOW_READERS);

  // One request each, and only for the readers the server would answer. The
  // registers are asked for a single row: their counts cover the whole set.
  const units = useAnswer<UnitRegister>(operational, () => inventory.units(id, { limit: "1" }), [id, refreshKey]);
  const prices = useAnswer<PricingOverview>(operational && seesPricing, () => pricing.overview(id), [id, refreshKey]);
  const register = useAnswer<PriceRegister>(
    operational && seesPricing,
    () => pricing.register(id, { limit: "1" }),
    [id, refreshKey],
  );
  const deals = useAnswer<SalesRegister>(
    operational && seesSales,
    () => sales.register(id, { limit: "1" }),
    [id, refreshKey],
  );
  const plans = useAnswer<PlanRegister>(operational && seesPlans, () => paymentPlans.register(id), [id, refreshKey]);
  const cash = useAnswer<CollectionProjectSummary>(
    operational && seesCollections,
    () => collections.summary(id),
    [id, refreshKey],
  );
  const economics = useAnswer<ProjectEconomics>(
    operational && seesEconomics,
    () => unitEconomics.summary(id),
    [id, refreshKey],
  );
  // Asked only of a reader entitled to it. The request is never made and then
  // hidden on a 403: a role that may not read the project's cash never has its
  // figures reach the browser at all.
  const projectCash = useAnswer<CashflowSummary>(
    operational && seesCashflow,
    () => cashflow.summary(id),
    [id, refreshKey],
  );

  const attention: AttentionItem[] = [
    {
      key: "permits-overdue",
      count: project.overdue_permit_count,
      title: "Permits past their statutory period",
      hint: "The authority has had these longer than the law allows.",
      tone: "danger",
      section: "permits",
    },
    {
      key: "permits-blocking",
      count: project.blocking_permit_count,
      title: "Permits flagged as blocking",
      hint: "Consents management has marked as holding the programme.",
      tone: "warning",
      section: "permits",
    },
    ...(prices.status === "ready" && prices.data.configuration
      ? [
          {
            key: "repricing",
            count: prices.data.units_repricing_required,
            title: "Units that need repricing",
            hint: "A priced fact changed since the list price was set.",
            tone: "danger" as const,
            section: "pricing" as const,
          },
          {
            key: "not-priced",
            count: prices.data.units_not_priced,
            title: "Units without a live price",
            hint: "No approved, activated price version yet.",
            tone: "warning" as const,
            section: "pricing" as const,
          },
        ]
      : []),
    ...(deals.status === "ready"
      ? [
          {
            key: "cancellations",
            count: deals.data.totals.open_cancellations,
            title: "Cancellations in progress",
            hint: "Contracts being unwound. The unit stays committed until each completes.",
            tone: "warning" as const,
            section: "sales" as const,
          },
        ]
      : []),
    ...(cash.status === "ready"
      ? [
          {
            key: "overdue-accounts",
            count: cash.data.accounts_overdue,
            title: "Accounts overdue",
            hint: `Past grace as at ${businessDate(cash.data.as_of)}.`,
            tone: "danger" as const,
            section: "collections" as const,
          },
          {
            key: "disputed-accounts",
            count: cash.data.accounts_disputed,
            title: "Accounts with an open dispute",
            hint: "Contested, and still owed and still ageing.",
            tone: "danger" as const,
            section: "collections" as const,
          },
        ]
      : []),
    ...(economics.status === "ready"
      ? [
          {
            key: "loss",
            count: economics.data.negative_profit_count,
            title: "Loss-making units",
            hint: "Profit after finance below zero on the current basis.",
            tone: "danger" as const,
            section: "economics" as const,
          },
          {
            key: "below-threshold",
            count: economics.data.below_threshold_count,
            title: "Units below the minimum margin",
            hint: economics.data.threshold_fraction
              ? `Below the ${percent(economics.data.threshold_fraction)} threshold.`
              : "Below the configured threshold.",
            tone: "warning" as const,
            section: "economics" as const,
          },
          {
            key: "incomplete",
            count: economics.data.incomplete_count,
            title: "Units with incomplete economics",
            hint: "No approved price, or no cost basis governing them.",
            tone: "warning" as const,
            section: "economics" as const,
          },
          {
            key: "mismatch",
            count: economics.data.currency_mismatch_count,
            title: "Units in a different currency",
            hint: "Revenue and cost currencies differ; never combined.",
            tone: "warning" as const,
            section: "economics" as const,
          },
        ]
      : []),
  ];

  // Every request this page makes, so a failure anywhere is said in words
  // rather than leaving a figure quietly missing. A request that was never
  // enabled for this reader is "off" and is not a failure. When the pricing
  // overview and its register both fail, one sentence covers pricing.
  const sources: [string, Answer<unknown>][] = [
    ["Inventory", units],
    ["Pricing", prices],
    ...(prices.status === "failed" ? [] : [["Pricing register", register] as [string, Answer<unknown>]]),
    ["Sales", deals],
    ["Payment plans", plans],
    ["Collections", cash],
    ["Unit economics", economics],
  ];
  const problems = sources
    .filter(([, answer]) => answer.status === "failed")
    .map(([name]) => `${name} could not be loaded, so nothing from ${name === "Inventory" || name === "Sales" || name === "Collections" || name === "Pricing" ? "it" : "them"} is shown here.`);

  const loading = sources.some(([, answer]) => answer.status === "loading");

  // The financial position is the page's answer where Finance has given one.
  // Where it has not — the reader is not entitled to it, or no cost basis
  // governs the project yet — the composition falls back to what the
  // commercial modules did answer rather than showing an empty frame.
  const economic = economics.status === "ready" && economics.data.active_version !== null ? economics.data : null;
  const economicCode = economic ? currencyCodeOf(economic.currency_id) : null;
  const dealTotals = deals.status === "ready" ? deals.data.totals : null;
  const unitTotals = units.status === "ready" ? units.data : null;
  const priceTotals = prices.status === "ready" ? prices.data : null;
  const hasPosition = economic !== null || unitTotals !== null;

  return (
    <>
      <ProjectPlate
        project={project}
        actions={canEdit ? <Button onClick={onEdit}>Edit project</Button> : undefined}
      />

      <div className="stack">
      {!operational ? (
        <Notice tone="info">
          This project is still in setup. Inventory, pricing, sales and everything downstream
          open once the country and currency basis is confirmed and the project moves to
          Pre-development.
        </Notice>
      ) : null}

      {/* Two columns that stack on their own rather than a twelve-column grid.
          A grid row is as tall as its tallest card, so a project with eleven
          things needing attention would open a hand's depth of empty page
          under the position beside it. */}
      <div className="split">
        <div className="stack">
          {operational && hasPosition ? (
            <Card
              tone="command"
              title="Project position"
              description={
                economic
                  ? "Sold units on their frozen terms, unsold on today's price and basis."
                  : "Where the development stands across its units."
              }
              actions={
                economic ? (
                  <Button small variant="quiet" onClick={() => onNavigate("economics")}>
                    Unit economics
                  </Button>
                ) : (
                  <Button small variant="quiet" onClick={() => onNavigate("inventory")}>
                    Inventory
                  </Button>
                )
              }
            >
              {economic ? (
                <>
                  <Position>
                    {/* The project's own margin, in ink. Units below the
                        minimum are counted in Needs attention, and colouring
                        the whole development's margin for them would report a
                        problem this figure does not have. */}
                    <PositionFigure
                      lead
                      label="Margin"
                      value={percent(economic.margin_fraction)}
                      note={
                        economic.threshold_fraction
                          ? `Minimum ${percent(economic.threshold_fraction)}`
                          : undefined
                      }
                    />
                    <PositionFigure
                      label="Profit"
                      value={money(economic.profit_total, economicCode)}
                      tone={economic.profit_total.startsWith("-") ? "danger" : "neutral"}
                      note="After finance"
                    />
                    <PositionFigure label="Return on cost" value={percent(economic.return_on_cost_fraction)} />
                  </Position>
                  <PositionSupport>
                    {dealTotals ? (
                      <PositionSupportItem
                        label="Contracted"
                        value={`${dealTotals.contracted} of ${dealTotals.units} units`}
                      />
                    ) : null}
                    <PositionSupportItem label="Revenue" value={money(economic.revenue_total, economicCode)} />
                    <PositionSupportItem label="Total cost" value={money(economic.total_cost_total, economicCode)} />
                    <PositionSupportItem
                      label="Cost basis"
                      value={`v${economic.active_version?.version_number} · ${businessDate(
                        economic.active_version?.effective_from ?? null,
                      )}`}
                    />
                    <PositionSupportItem
                      label="Covered"
                      value={`${economic.comparable_unit_count} of ${economic.unit_count} units`}
                    />
                  </PositionSupport>
                  <SectionHeader
                    title="Cost composition"
                    description="The pools the server allocated, and the total it reached."
                  />
                  <Breakdown>
                    <BreakdownRow
                      label="Development"
                      note="Land, hard and soft"
                      amount={money(economic.development_cost_total, economicCode)}
                    />
                    <BreakdownRow
                      label="Commercial"
                      note="Selling and seller-borne"
                      amount={money(economic.commercial_cost_total, economicCode)}
                    />
                    <BreakdownRow label="Finance" amount={money(economic.finance_cost_total, economicCode)} />
                    <BreakdownRow total label="Total cost" amount={money(economic.total_cost_total, economicCode)} />
                  </Breakdown>
                </>
              ) : unitTotals ? (
                <>
                  <Position>
                    <PositionFigure lead label="Units" value={unitTotals.total} />
                    <PositionFigure label="Available" value={unitTotals.available_count} />
                    {dealTotals ? (
                      <PositionFigure
                        label="Contracted"
                        value={dealTotals.contracted}
                        note={`of ${dealTotals.units} units`}
                      />
                    ) : (
                      <PositionFigure label="Held" value={unitTotals.held_count} />
                    )}
                    {dealTotals && !dealTotals.mixed_currency ? (
                      <PositionFigure
                        label="Contracted value"
                        value={money(dealTotals.contracted_value, currencyCodeOf(dealTotals.currency_id))}
                        note="Live contracts, ex tax"
                      />
                    ) : (
                      <PositionFigure label="Unreleased" value={unitTotals.unreleased_count} />
                    )}
                  </Position>
                  <PositionSupport>
                    <PositionSupportItem label="Held" value={unitTotals.held_count} />
                    <PositionSupportItem label="Unreleased" value={unitTotals.unreleased_count} />
                    {priceTotals ? <PositionSupportItem label="Priced" value={priceTotals.units_priced} /> : null}
                    {plans.status === "ready" ? (
                      <PositionSupportItem label="Payment plans" value={plans.data.total} />
                    ) : null}
                  </PositionSupport>
                  {seesEconomics ? (
                    <p className="footnote">
                      No approved cost allocation version governs this project yet, so no margin,
                      profit or return can be stated.
                    </p>
                  ) : null}
                </>
              ) : null}
            </Card>
          ) : null}

          {operational ? (
            <Card
              title="Commercial position"
              description="Units, where they stand, and what has been agreed."
              actions={
                <Button small variant="quiet" onClick={() => onNavigate("inventory")}>
                  Inventory
                </Button>
              }
            >
              <Section answer={units} name="Inventory" off="Inventory opens after setup.">
                {(data) => (
                  <MetricGroup>
                    <Metric label="Units" value={data.total} />
                    <Metric label="Available" value={data.available_count} />
                    {dealTotals ? <Metric label="Contracted" value={dealTotals.contracted} /> : null}
                    <Metric label="Held" value={data.held_count} size="sm" />
                    <Metric label="Unreleased" value={data.unreleased_count} size="sm" />
                  </MetricGroup>
                )}
              </Section>
              {seesSales ? (
                <Section answer={deals} name="Sales" off="">
                  {(data) => (
                    <>
                      <SectionHeader title="Sales" />
                      <MetricGroup compact>
                        <Metric label="Live reservations" value={data.totals.active_reservations} size="sm" />
                        <Metric label="Contract pending" value={data.totals.contract_pending} size="sm" />
                        <Metric label="Active contracts" value={data.totals.active_contracts} size="sm" />
                        <Metric label="Returned" value={data.totals.returned} size="sm" />
                        <Metric
                          label="Contracted value"
                          value={
                            data.totals.mixed_currency
                              ? "Not summed"
                              : money(data.totals.contracted_value, currencyCodeOf(data.totals.currency_id))
                          }
                          note={data.totals.mixed_currency ? "Contracts in more than one currency" : undefined}
                          size="sm"
                        />
                        {plans.status === "ready" ? (
                          <Metric label="Payment plans" value={plans.data.total} size="sm" />
                        ) : null}
                      </MetricGroup>
                    </>
                  )}
                </Section>
              ) : null}
              {seesPricing ? (
                <Section answer={prices} name="Pricing" off="">
                  {(data) => (
                    <>
                      <SectionHeader
                        title="Pricing"
                        actions={
                          <Button small variant="quiet" onClick={() => onNavigate("pricing")}>
                            Pricing
                          </Button>
                        }
                      />
                      {data.configuration === null ? (
                        <EmptyState
                          compact
                          title="No active pricing configuration"
                          hint="Until a configuration is approved and activated, no unit in this project can be priced."
                          actions={
                            <Button small onClick={() => onNavigate("pricing")}>
                              Open pricing
                            </Button>
                          }
                        />
                      ) : (
                        <MetricGroup compact>
                          <Metric
                            label="Policy"
                            value={`v${data.configuration.version_number}`}
                            note={data.configuration.name}
                            size="sm"
                          />
                          <Metric
                            label="Base rate"
                            value={money(data.base_internal_rate, currencyCodeOf(data.currency_id))}
                            note="Per internal unit of area"
                            size="sm"
                          />
                          <Metric label="Priced" value={data.units_priced} size="sm" />
                          <Metric label="Not priced" value={data.units_not_priced} size="sm" />
                          <Metric
                            label="Need repricing"
                            value={data.units_repricing_required}
                            size="sm"
                            tone={data.units_repricing_required > 0 ? "danger" : "neutral"}
                          />
                        </MetricGroup>
                      )}
                    </>
                  )}
                </Section>
              ) : null}
            </Card>
          ) : null}
          {operational ? (
            <Card
              title="Development"
              description="The land, the consents, and the programme."
              actions={
                <Button small variant="quiet" onClick={() => onNavigate("permits")}>
                  Permits
                </Button>
              }
            >
              <MetricGroup compact>
                <Metric label="Parcels" value={project.parcel_count} size="sm" />
                <Metric label="Permits" value={project.permit_count} size="sm" />
                <Metric
                  label="Blocking"
                  value={project.blocking_permit_count}
                  size="sm"
                  tone={project.blocking_permit_count > 0 ? "warning" : "neutral"}
                />
                <Metric label="Critical path" value={project.critical_path_permit_count} size="sm" />
                <Metric
                  label="Past statutory period"
                  value={project.overdue_permit_count}
                  size="sm"
                  tone={project.overdue_permit_count > 0 ? "danger" : "neutral"}
                />
              </MetricGroup>
              <SectionHeader title="Programme" />
              <KeyValueGrid columns={4}>
                <KeyValue label="Planned start" mono value={businessDate(project.planned_start)} />
                <KeyValue label="Planned completion" mono value={businessDate(project.planned_completion)} />
                <KeyValue
                  label="Duration"
                  mono
                  value={project.planned_duration_days === null ? null : `${project.planned_duration_days} days`}
                />
                <KeyValue label="Fiscal year starts" value={`Month ${project.fiscal_year_start_month}`} />
              </KeyValueGrid>
            </Card>
          ) : null}
        </div>

        <div className="stack">
          <AttentionPanel items={attention} loading={loading} problems={problems} onNavigate={onNavigate} />
        </div>
      </div>

      {operational && seesCollections ? (
        <Card
          title="Collections"
          description="What has arrived, what is owed, and how old it is."
          actions={
            <Button small variant="quiet" onClick={() => onNavigate("collections")}>
              Collections
            </Button>
          }
        >
          <Section answer={cash} name="Collections" off="Opens after setup.">
            {(data) =>
              data.currencies.length === 0 ? (
                <EmptyState
                  compact
                  title="Nothing to collect yet"
                  hint="No sale in this project has an active payment schedule."
                />
              ) : (
                <>
                  {data.currencies.map((totals) => {
                    const code = currencyCodeOf(totals.currency_id);
                    // Each currency is its own position. A project selling in two
                    // currencies has two answers, and one figure covering both
                    // could only be produced by adding unlike money.
                    return (
                      <div key={totals.currency_id} className="currency-block">
                        {data.currencies.length > 1 ? (
                          <p className="currency-block-title">
                            {code ?? "Unknown currency"}
                            <span className="muted">· {totals.accounts} accounts</span>
                          </p>
                        ) : null}
                        <Position compact>
                          <PositionFigure lead label="Outstanding" value={money(totals.outstanding_total, code)} />
                          <PositionFigure label="Due now" value={money(totals.due_total, code)} />
                          <PositionFigure
                            label="Overdue"
                            value={money(totals.overdue_total, code)}
                            tone={isPositive(totals.overdue_total) ? "danger" : "neutral"}
                          />
                          <PositionFigure
                            label="Unapplied cash"
                            value={money(totals.unapplied_cash, code)}
                            tone={isPositive(totals.unapplied_cash) ? "warning" : "neutral"}
                            note="Received, not yet applied"
                          />
                        </Position>
                        <PositionSupport>
                          <PositionSupportItem
                            label="Confirmed receipts, lifetime"
                            value={money(totals.confirmed_receipts_total, code)}
                          />
                          <PositionSupportItem label="Accounts" value={totals.accounts} />
                        </PositionSupport>
                        <SectionHeader title="Ageing" />
                        <Distribution>
                          {AGING_BUCKETS.filter((bucket) => totals.buckets[bucket] !== undefined).map((bucket) => (
                            <DistributionBand
                              key={bucket}
                              label={bucketLabel(bucket)}
                              value={money(totals.buckets[bucket], code)}
                              heat={bucketHeatForAmount(bucket, totals.buckets[bucket])}
                            />
                          ))}
                        </Distribution>
                      </div>
                    );
                  })}
                  <MetricGroup compact>
                    <Metric label="Accounts" value={data.accounts} size="sm" />
                    <Metric
                      label="Overdue"
                      value={data.accounts_overdue}
                      size="sm"
                      tone={data.accounts_overdue > 0 ? "danger" : "neutral"}
                    />
                    <Metric
                      label="Disputed"
                      value={data.accounts_disputed}
                      size="sm"
                      tone={data.accounts_disputed > 0 ? "warning" : "neutral"}
                    />
                    <Metric label="Cleared" value={data.accounts_cleared} size="sm" />
                  </MetricGroup>
                  <p className="footnote">As at {businessDate(data.as_of)}.</p>
                </>
              )
            }
          </Section>
        </Card>
      ) : null}

      {seesCashflow ? (
        <Card
          title="Cash"
          description="What the project can spend, and what it must raise."
          actions={
            <Button small variant="quiet" onClick={() => onNavigate("cashflow")}>
              Cashflow
            </Button>
          }
        >
          <Section answer={projectCash} name="Cashflow" off="Opens after setup.">
            {(data) => <ProjectCashPosition summary={data} />}
          </Section>
        </Card>
      ) : null}
      </div>
    </>
  );
}

/**
 * The four cash figures worth putting on a project's front page.
 *
 * Usable cash leads, because it is the only one of the balances a developer can
 * spend. The ninety-day requirement and the peak deficit are the two questions
 * that follow it, and both arrive computed — this component adds nothing.
 */
function ProjectCashPosition({ summary }: { summary: CashflowSummary }) {
  const code = summary.basis.currency_code;
  const ninety = summary.funding_windows.find((window) => window.days === 90);
  return (
    <>
      <Position compact>
        <PositionFigure
          lead
          label="Usable cash"
          value={money(summary.position.unrestricted_cash, code)}
          tone={isPositive(summary.position.unrestricted_cash) ? "neutral" : "danger"}
          note="Spendable today"
        />
        <PositionFigure label="Restricted" value={money(summary.position.restricted_cash, code)} note="Held in escrow" />
        {ninety ? (
          <PositionFigure
            label="Funding required, 90 days"
            value={money(ninety.funding_requirement, code)}
            tone={isPositive(ninety.funding_requirement) ? "danger" : "neutral"}
          />
        ) : null}
        <PositionFigure
          label="Peak funding requirement"
          value={money(summary.peak_deficit.peak_funding_deficit, code)}
          tone={isPositive(summary.peak_deficit.peak_funding_deficit) ? "danger" : "neutral"}
          note={
            summary.peak_deficit.peak_deficit_month
              ? `Expected ${businessDate(summary.peak_deficit.peak_deficit_month)}`
              : "No month runs short"
          }
        />
      </Position>
      <PositionSupport>
        <PositionSupportItem label="Total cash" value={money(summary.position.total_cash, code)} />
        <PositionSupportItem
          label="Forecast in force"
          value={
            summary.has_active_forecast && summary.basis.forecast_version_number !== null
              ? `Version ${summary.basis.forecast_version_number}`
              : "None"
          }
        />
      </PositionSupport>
      <p className="footnote">As at {businessDate(summary.basis.as_of_date)}.</p>
    </>
  );
}

/**
 * Draw one module's answer, or say why it is not drawn.
 *
 * A refusal draws nothing, because the reader was never entitled to the card.
 * A failure is said in words. A module that is off because the project is
 * still in setup says that. Only a real answer is rendered as figures.
 */
function Section<T>({
  answer,
  name,
  off,
  children,
}: {
  answer: Answer<T>;
  name: string;
  off: string;
  children: (data: T) => ReactNode;
}) {
  if (answer.status === "off") return off ? <p className="footnote">{off}</p> : null;
  if (answer.status === "loading") return <Loading label={`Loading ${name.toLowerCase()}…`} shape="metrics" />;
  if (answer.status === "denied") return null;
  if (answer.status === "failed") return <Notice tone="warning">{name}: {answer.message}</Notice>;
  return <>{children(answer.data)}</>;
}
