"use client";

import {
  Badge,
  Card,
  EmptyState,
  KeyValue,
  KeyValueGrid,
  Loading,
  Notice,
  SubPanel,
  TableScroll,
} from "@/components/ui";
import type { Answer } from "@/lib/answer";
import type { CashflowAccuracy, CashflowManagement, CashflowReconciliation } from "@/lib/api";
import { businessDate, money, percent } from "@/lib/format";

import {
  accuracyGroupLabel,
  checkLabel,
  managementGroupLabel,
  sourceModuleLabel,
} from "./labels";

/**
 * The consolidated view, the controls behind it, and how well the last forecast held.
 *
 * Three questions a director asks after the position itself: what does the whole
 * project look like, does it reconcile, and was the last forecast any good.
 *
 * The reconciliation deliberately has no score. A blended "87% healthy" would
 * let a failed escrow ceiling average against a passing currency check, and
 * nobody would know which half was which — a single failed financial control is
 * actionable on its own.
 */
export function CashflowManagementView({
  management,
  reconciliation,
  accuracy,
  onOpenSource,
}: {
  management: Answer<CashflowManagement>;
  reconciliation: Answer<CashflowReconciliation>;
  accuracy: Answer<CashflowAccuracy>;
  onOpenSource: (sourceType: string) => void;
}) {
  return (
    <div className="stack">
      <Reconciliation answer={reconciliation} />
      <Management answer={management} onOpenSource={onOpenSource} />
      <Accuracy answer={accuracy} />
    </div>
  );
}

function Reconciliation({ answer }: { answer: Answer<CashflowReconciliation> }) {
  if (answer.status === "loading") {
    return <Loading label="Loading the reconciliation" shape="rows" />;
  }
  if (answer.status === "denied") {
    return <Notice tone="info">The reconciliation is not available to your role.</Notice>;
  }
  if (answer.status === "failed") return <Notice tone="error">{answer.message}</Notice>;
  if (answer.status === "off") return null;

  const { checks, failed_count: failed, basis } = answer.data;
  const failing = checks.filter((check) => !check.passed);

  return (
    <Card
      title="Reconciliation"
      description="Every control answered on its own. No score, because one failure is actionable whatever the rest say."
      tone={failed > 0 ? "attention" : undefined}
    >
      {failed === 0 ? (
        <Notice tone="success">
          All {checks.length} checks reconcile as at {businessDate(basis.as_of_date)}.
        </Notice>
      ) : (
        <Notice tone="error">
          {failed === 1 ? "One check does not reconcile." : `${failed} checks do not reconcile.`}{" "}
          Each is a correction somebody owes, not a number to be averaged away.
        </Notice>
      )}

      {failing.length > 0 ? (
        <TableScroll label="Checks that do not reconcile" compact>
          <thead>
            <tr>
              <th scope="col">Check</th>
              <th scope="col" className="num">Expected</th>
              <th scope="col" className="num">Found</th>
              <th scope="col">What it means</th>
            </tr>
          </thead>
          <tbody>
            {failing.map((check) => (
              <tr key={check.name}>
                <th scope="row">{checkLabel(check.name)}</th>
                <td className="num">{check.expected ?? "—"}</td>
                <td className="num">{check.actual ?? "—"}</td>
                <td className="cell-prose">{check.detail}</td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      ) : null}

      <details>
        <summary>All {checks.length} checks</summary>
        <TableScroll label="Every reconciliation check" compact>
          <thead>
            <tr>
              <th scope="col">Check</th>
              <th scope="col">Result</th>
              <th scope="col" className="num">Expected</th>
              <th scope="col" className="num">Found</th>
            </tr>
          </thead>
          <tbody>
            {checks.map((check) => (
              <tr key={check.name}>
                <th scope="row">{checkLabel(check.name)}</th>
                <td>
                  <Badge tone={check.passed ? "success" : "danger"}>
                    {check.passed ? "Reconciles" : "Does not reconcile"}
                  </Badge>
                </td>
                <td className="num">{check.expected ?? "—"}</td>
                <td className="num">{check.actual ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      </details>
    </Card>
  );
}

/**
 * The project on one page, with every figure naming the module that owns it.
 *
 * The `source_module` is on screen rather than implied. A consolidated report
 * whose figures have lost their provenance is a report nobody can correct.
 */
function Management({
  answer,
  onOpenSource,
}: {
  answer: Answer<CashflowManagement>;
  onOpenSource: (sourceType: string) => void;
}) {
  if (answer.status === "loading") {
    return <Loading label="Loading the management view" shape="metrics" />;
  }
  if (answer.status === "denied") {
    return <Notice tone="info">The management view is not available to your role.</Notice>;
  }
  if (answer.status === "failed") return <Notice tone="error">{answer.message}</Notice>;
  if (answer.status === "off") return null;

  const { groups, basis } = answer.data;

  return (
    <Card
      title="Management view"
      description="The consolidated project position, with each figure attributed to the module that governs it."
    >
      {groups.length === 0 ? (
        <EmptyState title="Nothing to report yet" hint="This project has no governed figures." />
      ) : (
        <div className="stack">
          {groups.map((group) => (
            <SubPanel key={group.group} title={managementGroupLabel(group.group)}>
              <TableScroll label={`${managementGroupLabel(group.group)} figures`} compact>
                <thead>
                  <tr>
                    <th scope="col">Figure</th>
                    <th scope="col" className="num">Value</th>
                    <th scope="col">Owned by</th>
                    <th scope="col" />
                  </tr>
                </thead>
                <tbody>
                  {group.metrics.map((metric) => (
                    <tr key={metric.key}>
                      <th scope="row">{metric.label}</th>
                      <td className="num">
                        {metric.unit === "money"
                          ? money(metric.value, basis.currency_code)
                          : metric.unit === "fraction"
                            ? percent(metric.value)
                            : metric.unit === "month" && metric.value
                              ? businessDate(metric.value)
                              : (metric.value ?? "—")}
                      </td>
                      <td>{sourceModuleLabel(metric.source_module)}</td>
                      <td>
                        {metric.drilldown_source_type ? (
                          <button
                            type="button"
                            className="button-link"
                            onClick={() => onOpenSource(metric.drilldown_source_type as string)}
                          >
                            Transactions
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </TableScroll>
            </SubPanel>
          ))}
        </div>
      )}
      <p className="footnote">
        As at {businessDate(basis.as_of_date)}
        {basis.currency_code ? `, in ${basis.currency_code}` : ""}. Figures owned
        by another module are read from it and never copied here.
      </p>
    </Card>
  );
}

/**
 * How well the governed forecast held, month by month and group by group.
 *
 * No blended accuracy score: collections running twenty per cent ahead and
 * construction twenty per cent behind would average into a project on plan, and
 * the two facts a reader needs are exactly the two the average destroys.
 *
 * A variance rate against a zero forecast is null and says so. Rendering 0% or
 * 100% there would be a claim nobody made.
 */
function Accuracy({ answer }: { answer: Answer<CashflowAccuracy> }) {
  if (answer.status === "loading") return <Loading label="Loading forecast accuracy" shape="rows" />;
  if (answer.status === "denied") {
    return <Notice tone="info">Forecast accuracy is not available to your role.</Notice>;
  }
  if (answer.status === "failed") return <Notice tone="error">{answer.message}</Notice>;
  if (answer.status === "off") return null;

  const { rows, basis } = answer.data;

  return (
    <Card
      title="Forecast accuracy"
      description="What the forecast in force said would happen, against what did."
    >
      {rows.length === 0 ? (
        <EmptyState
          title="Nothing to measure yet"
          hint="A forecast is measured against the months that have finished since it was cut. A version taken this month has no finished month behind it."
        />
      ) : (
        <TableScroll label="Forecast against actual" compact>
          <thead>
            <tr>
              <th scope="col">Month</th>
              <th scope="col">What</th>
              <th scope="col" className="num">Forecast</th>
              <th scope="col" className="num">Actual</th>
              <th scope="col" className="num">Variance</th>
              <th scope="col" className="num">Variance rate</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.period_month}-${row.category_group}`}>
                <th scope="row">{businessDate(row.period_month)}</th>
                <td>{accuracyGroupLabel(row.category_group)}</td>
                <td className="num">{money(row.variance.forecast_amount, basis.currency_code)}</td>
                <td className="num">{money(row.variance.actual_amount, basis.currency_code)}</td>
                <td className="num">{money(row.variance.variance_amount, basis.currency_code)}</td>
                <td className="num">
                  {row.variance.variance_rate === null
                    ? "Not meaningful against a zero forecast"
                    : percent(row.variance.variance_rate)}
                </td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      )}
      <KeyValueGrid columns={3}>
        <KeyValue
          label="Forecast measured"
          value={
            basis.forecast_version_number === null
              ? "None in force"
              : `Version ${basis.forecast_version_number}`
          }
        />
        <KeyValue
          label="Taken as at"
          value={basis.forecast_as_of_date ? businessDate(basis.forecast_as_of_date) : "—"}
        />
        <KeyValue label="Measured to" value={businessDate(basis.as_of_date)} />
      </KeyValueGrid>
    </Card>
  );
}
