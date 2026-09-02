"use client";

import type { ReactNode } from "react";

import { collections, inventory, paymentPlans, pricing, sales, unitEconomics } from "@/lib/api";
import type {
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
import { businessDate, money, percent } from "@/lib/format";
import {
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
  Badge,
  Button,
  Card,
  EmptyState,
  InlineMeta,
  InlineMetaItem,
  KeyValue,
  KeyValueGrid,
  Loading,
  Metric,
  MetricGroup,
  Notice,
} from "@/components/ui";
import { projectStatusLabel, projectStatusTone } from "@/components/projects/projectStatus";
import { AttentionPanel } from "./AttentionPanel";
import type { AttentionItem } from "./AttentionPanel";

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

  const baseCode = project.base_currency_code;

  return (
    <>
      <header className="identity">
        <div className="identity-main">
          <h1 className="identity-title">{project.name}</h1>
          <p className="identity-sub">
            {project.developer_entity}
            {project.city || project.location
              ? ` · ${[project.location, project.city].filter(Boolean).join(", ")}`
              : ""}
          </p>
          <InlineMeta>
            <InlineMetaItem label="Code">
              <span className="mono">{project.code}</span>
            </InlineMetaItem>
            <InlineMetaItem label="Status">
              <Badge tone={projectStatusTone(project.status)}>{projectStatusLabel(project.status)}</Badge>
            </InlineMetaItem>
            {project.project_type_code ? (
              <InlineMetaItem label="Type">{project.project_type_code}</InlineMetaItem>
            ) : null}
            <InlineMetaItem label="Programme">
              {project.planned_start || project.planned_completion
                ? `${businessDate(project.planned_start)} → ${businessDate(project.planned_completion)}`
                : "Not planned"}
            </InlineMetaItem>
            <InlineMetaItem label="Base">{baseCode ?? "—"}</InlineMetaItem>
            {project.reporting_currency_code && project.reporting_currency_code !== baseCode ? (
              <InlineMetaItem label="Reporting">{project.reporting_currency_code}</InlineMetaItem>
            ) : null}
            {project.project_manager_display_name ? (
              <InlineMetaItem label="Manager">{project.project_manager_display_name}</InlineMetaItem>
            ) : null}
          </InlineMeta>
        </div>
        {canEdit ? (
          <div className="identity-actions">
            <Button onClick={onEdit}>Edit project</Button>
          </div>
        ) : null}
      </header>

      {!operational ? (
        <Notice tone="info">
          This project is still in setup. Inventory, pricing, sales and everything downstream
          open once the country and currency basis is confirmed and the project moves to
          Pre-development.
        </Notice>
      ) : null}

      <div className="grid-12">
        <div className="span-4">
          <AttentionPanel items={attention} loading={loading} problems={problems} onNavigate={onNavigate} />
        </div>

        <div className="span-8">
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
                  <Metric label="Units" value={data.total} size="lg" />
                  <Metric label="Available" value={data.available_count} />
                  <Metric label="Held" value={data.held_count} />
                  <Metric label="Unreleased" value={data.unreleased_count} />
                </MetricGroup>
              )}
            </Section>
            {seesSales ? (
              <Section answer={deals} name="Sales" off="">
                {(data) => (
                  <>
                    <h3 className="section-heading">Sales</h3>
                    <MetricGroup>
                      <Metric label="Live reservations" value={data.totals.active_reservations} size="sm" />
                      <Metric label="Contract pending" value={data.totals.contract_pending} size="sm" />
                      <Metric label="Contracted" value={data.totals.contracted} size="sm" />
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
                    <h3 className="section-heading">Pricing</h3>
                    {data.configuration === null ? (
                      <p className="footnote">
                        No active pricing configuration, so no unit can be priced yet.
                      </p>
                    ) : (
                      <MetricGroup>
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
                        {register.status === "ready" ? (
                          <Metric label="In register" value={register.data.total} size="sm" />
                        ) : null}
                      </MetricGroup>
                    )}
                  </>
                )}
              </Section>
            ) : null}
          </Card>
        </div>

        {seesEconomics ? (
          <div className="span-6">
            <Card
              title="Economic position"
              description="Sold units on their frozen terms, unsold on today's price and basis."
              actions={
                <Button small variant="quiet" onClick={() => onNavigate("economics")}>
                  Unit economics
                </Button>
              }
            >
              <Section answer={economics} name="Unit economics" off="Opens after setup.">
                {(data) => {
                  const code = currencyCodeOf(data.currency_id);
                  return data.active_version === null ? (
                    <EmptyState
                      compact
                      title="No approved cost basis yet"
                      hint="Create the opening Finance allocation version before profitability can be calculated."
                    />
                  ) : (
                    <>
                      <MetricGroup>
                        <Metric label="Margin" value={percent(data.margin_fraction)} size="lg" />
                        <Metric label="Return on cost" value={percent(data.return_on_cost_fraction)} size="lg" />
                        <Metric
                          label="Profit"
                          value={money(data.profit_total, code)}
                          tone={data.profit_total.startsWith("-") ? "danger" : "neutral"}
                        />
                      </MetricGroup>
                      <MetricGroup>
                        <Metric label="Revenue" value={money(data.revenue_total, code)} size="sm" />
                        <Metric label="Total cost" value={money(data.total_cost_total, code)} size="sm" />
                        <Metric
                          label="Cost basis"
                          value={`v${data.active_version.version_number}`}
                          note={`Effective ${businessDate(data.active_version.effective_from)}`}
                          size="sm"
                        />
                        <Metric
                          label="Covered"
                          value={`${data.comparable_unit_count} of ${data.unit_count}`}
                          note="Units in these totals"
                          size="sm"
                        />
                      </MetricGroup>
                    </>
                  );
                }}
              </Section>
            </Card>
          </div>
        ) : null}

        {seesCollections ? (
          <div className="span-6">
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
                        return (
                          <div key={totals.currency_id} className="currency-block">
                            {data.currencies.length > 1 ? (
                              <p className="currency-block-title">
                                {code ?? "Unknown currency"}
                                <span className="muted">· {totals.accounts} accounts</span>
                              </p>
                            ) : null}
                            <MetricGroup>
                              <Metric label="Outstanding" value={money(totals.outstanding_total, code)} size="lg" />
                              <Metric label="Due now" value={money(totals.due_total, code)} />
                              <Metric
                                label="Overdue"
                                value={money(totals.overdue_total, code)}
                                tone={totals.overdue_total.replace(/[^1-9]/g, "") ? "danger" : "neutral"}
                              />
                              <Metric
                                label="Unapplied cash"
                                value={money(totals.unapplied_cash, code)}
                                tone={totals.unapplied_cash.replace(/[^1-9]/g, "") ? "warning" : "neutral"}
                              />
                            </MetricGroup>
                          </div>
                        );
                      })}
                      <MetricGroup compact>
                        <Metric label="Accounts" value={data.accounts} size="sm" />
                        <Metric label="Overdue" value={data.accounts_overdue} size="sm" />
                        <Metric label="Disputed" value={data.accounts_disputed} size="sm" />
                        <Metric label="Cleared" value={data.accounts_cleared} size="sm" />
                      </MetricGroup>
                      <p className="footnote">As at {businessDate(data.as_of)}.</p>
                    </>
                  )
                }
              </Section>
            </Card>
          </div>
        ) : null}

        <div className={seesEconomics || seesCollections ? "span-6" : "span-12"}>
          <Card
            title="Development"
            description="The land, the consents, and the programme."
            actions={
              <Button small variant="quiet" onClick={() => onNavigate("permits")}>
                Permits
              </Button>
            }
          >
            <MetricGroup>
              <Metric label="Parcels" value={project.parcel_count} />
              <Metric label="Permits" value={project.permit_count} />
              <Metric
                label="Blocking"
                value={project.blocking_permit_count}
                tone={project.blocking_permit_count > 0 ? "warning" : "neutral"}
              />
              <Metric label="Critical path" value={project.critical_path_permit_count} />
              <Metric
                label="Past statutory period"
                value={project.overdue_permit_count}
                tone={project.overdue_permit_count > 0 ? "danger" : "neutral"}
              />
            </MetricGroup>
            <h3 className="section-heading">Programme</h3>
            <KeyValueGrid columns={3}>
              <KeyValue label="Planned start" mono value={businessDate(project.planned_start)} />
              <KeyValue label="Planned completion" mono value={businessDate(project.planned_completion)} />
              <KeyValue
                label="Planned duration"
                mono
                value={project.planned_duration_days === null ? null : `${project.planned_duration_days} days`}
              />
              <KeyValue label="Fiscal year starts" value={`Month ${project.fiscal_year_start_month}`} />
              <KeyValue label="Country" value={project.country_code} />
              <KeyValue
                label="Coordinates"
                mono
                value={project.latitude && project.longitude ? `${project.latitude}, ${project.longitude}` : null}
              />
            </KeyValueGrid>
          </Card>
        </div>
      </div>
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
