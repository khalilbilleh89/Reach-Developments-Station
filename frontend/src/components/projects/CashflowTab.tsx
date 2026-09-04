"use client";

import { useCallback, useState } from "react";

import { Field, Notice, PageHeader, Tabs } from "@/components/ui";
import { sectionDescription } from "@/components/shell/navigation";
import { CashflowDrilldown } from "@/components/projects/cashflow/CashflowDrilldown";
import type { DrilldownQuery } from "@/components/projects/cashflow/CashflowDrilldown";
import { CashflowEscrow } from "@/components/projects/cashflow/CashflowEscrow";
import { CashflowForecasts } from "@/components/projects/cashflow/CashflowForecasts";
import { CashflowManagementView } from "@/components/projects/cashflow/CashflowManagement";
import { CashflowMonthly } from "@/components/projects/cashflow/CashflowMonthly";
import { CashflowMovements } from "@/components/projects/cashflow/CashflowMovements";
import { CashflowOverview } from "@/components/projects/cashflow/CashflowOverview";
import { ApiError, cashflow } from "@/lib/api";
import type { ProjectDetail } from "@/lib/api";
import { useAnswer } from "@/lib/answer";
import { Loading } from "@/components/ui";
import {
  CASHFLOW_ACTIVATORS,
  CASHFLOW_APPROVERS,
  CASHFLOW_CONFIRMERS,
  CASHFLOW_PREPARERS,
  CASHFLOW_READERS,
  CASHFLOW_RECORDERS,
  hasAnyRole,
} from "@/lib/roles";
import type { Roles } from "@/lib/roles";

const SECTIONS = [
  { key: "overview", label: "Overview" },
  { key: "monthly", label: "Monthly cashflow" },
  { key: "forecast", label: "Forecast" },
  { key: "movements", label: "Development & financing" },
  { key: "escrow", label: "Escrow" },
  { key: "management", label: "Management" },
];

/**
 * The project's cash: what it holds, what it expects, and when it runs short.
 *
 * **Nothing on this screen is calculated.** Not the opening balance, not the
 * closing balance, not the funding requirement, not the NPV, not the equity
 * IRR, not a single variance. Every figure arrives finished from the API and is
 * only formatted here. That rule is not fastidiousness: money is serialised as
 * decimal strings precisely because a cash position put through a JavaScript
 * float comes back subtly different from the one Finance will act on, and the
 * difference lands in the least significant digit — exactly where a
 * reconciliation looks.
 *
 * Six sections in the order the questions get asked. Where does the cash stand;
 * what happens month by month; what is the governed forecast that says so; what
 * cash does this module itself own; how much of the balance is escrowed; and
 * does the whole thing reconcile.
 *
 * The as-of control at the top is the one input the workspace takes, and it is
 * applied to every reporting request together, so no two panels on screen can be
 * answering for different days.
 */
export function CashflowTab({
  project,
  roles,
}: {
  project: ProjectDetail;
  roles: Roles;
}) {
  const projectId = project.id;
  const [section, setSection] = useState("overview");
  const [asOf, setAsOf] = useState<string>("");
  const [selectedForecast, setSelectedForecast] = useState<string | null>(null);
  const [drilldown, setDrilldown] = useState<DrilldownQuery | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  // Bumped after any write, so every panel reloads from the server rather than
  // from an optimistic guess about what the write did.
  const [revision, setRevision] = useState(0);

  const canRead = hasAnyRole(roles, CASHFLOW_READERS);
  const canPrepare = hasAnyRole(roles, CASHFLOW_PREPARERS);
  const canRecord = hasAnyRole(roles, CASHFLOW_RECORDERS);
  const canConfirm = hasAnyRole(roles, CASHFLOW_CONFIRMERS);
  const canApprove = hasAnyRole(roles, CASHFLOW_APPROVERS);
  const canActivate = hasAnyRole(roles, CASHFLOW_ACTIVATORS);

  const query = asOf || undefined;

  const summary = useAnswer(canRead, () => cashflow.summary(projectId, { asOf: query }), [
    projectId,
    query,
    revision,
  ]);
  const monthly = useAnswer(
    canRead && section === "monthly",
    () => cashflow.monthly(projectId, { asOf: query }),
    [projectId, query, revision, section],
  );
  const versions = useAnswer(
    canRead && section === "forecast",
    () => cashflow.forecasts(projectId),
    [projectId, revision, section],
  );
  const detail = useAnswer(
    canRead && section === "forecast" && selectedForecast !== null,
    () => cashflow.forecast(projectId, selectedForecast as string),
    [projectId, selectedForecast, revision, section],
  );
  const development = useAnswer(
    canRead && section === "movements",
    () => cashflow.developmentMovements(projectId),
    [projectId, revision, section],
  );
  const financing = useAnswer(
    canRead && section === "movements",
    () => cashflow.financingMovements(projectId),
    [projectId, revision, section],
  );
  const restrictions = useAnswer(
    canRead && section === "escrow",
    () => cashflow.restrictions(projectId),
    [projectId, revision, section],
  );
  const management = useAnswer(
    canRead && section === "management",
    () => cashflow.management(projectId, { asOf: query }),
    [projectId, query, revision, section],
  );
  const reconciliation = useAnswer(
    canRead && section === "management",
    () => cashflow.reconciliation(projectId, { asOf: query }),
    [projectId, query, revision, section],
  );
  const accuracy = useAnswer(
    canRead && section === "management",
    () => cashflow.forecastAccuracy(projectId, { asOf: query }),
    [projectId, query, revision, section],
  );

  /**
   * Run a write, then reload from the server.
   *
   * The server's message is shown as it wrote it. A maker/checker refusal, a
   * stale-source refusal and an opening-month refusal each explain something the
   * browser could not have known, and paraphrasing them would lose the part that
   * says what to do next.
   */
  const run = useCallback(async (action: () => Promise<unknown>) => {
    setBusy(true);
    setActionError(null);
    try {
      await action();
      setRevision((current) => current + 1);
    } catch (caught) {
      setActionError(
        caught instanceof ApiError ? caught.message : "That could not be completed.",
      );
    } finally {
      setBusy(false);
    }
  }, []);

  if (!canRead) {
    return (
      <div className="stack">
        <PageHeader title="Cashflow" subtitle={sectionDescription("cashflow")} />
        <Notice tone="info">
          The project&rsquo;s cash position is not available to your role.
        </Notice>
      </div>
    );
  }

  const currency =
    summary.status === "ready"
      ? summary.data.basis.currency_code
      : (project.base_currency_code ?? null);

  return (
    <div className="stack">
      <PageHeader
        title="Cashflow"
        subtitle={sectionDescription("cashflow")}
        actions={
          <Field label="Position as at" className="toolbar-filter">
            <input
              className="input"
              type="date"
              value={asOf}
              max={undefined}
              onChange={(event) => setAsOf(event.target.value)}
            />
          </Field>
        }
      />

      {actionError ? <Notice tone="error">{actionError}</Notice> : null}

      <Tabs
        label="Cashflow sections"
        tabs={SECTIONS}
        active={section}
        onSelect={setSection}
        group="cashflow"
      />

      {section === "overview" ? (
        summary.status === "loading" ? (
          <Loading label="Loading the cash position" shape="metrics" />
        ) : summary.status === "failed" ? (
          <Notice tone="error">{summary.message}</Notice>
        ) : summary.status === "denied" ? (
          <Notice tone="info">The cash position is not available to your role.</Notice>
        ) : summary.status === "ready" ? (
          <CashflowOverview summary={summary.data} />
        ) : null
      ) : null}

      {section === "monthly" ? (
        <CashflowMonthly
          projectId={projectId}
          answer={monthly}
          asOf={asOf || null}
          onOpenMonth={(month) => setDrilldown({ periodMonth: month })}
        />
      ) : null}

      {section === "forecast" ? (
        <CashflowForecasts
          versions={versions}
          detail={detail}
          selected={selectedForecast}
          onSelect={setSelectedForecast}
          canPrepare={canPrepare}
          canApprove={canApprove}
          canActivate={canActivate}
          busy={busy}
          error={null}
          currency={currency}
          onCreate={(body) =>
            void run(async () => {
              const created = await cashflow.createForecast(projectId, body);
              setSelectedForecast(created.id);
            })
          }
          onSubmit={(id) => void run(() => cashflow.submitForecast(projectId, id))}
          onApprove={(id, reason) => void run(() => cashflow.approveForecast(projectId, id, reason))}
          onReject={(id, reason) => void run(() => cashflow.rejectForecast(projectId, id, reason))}
          onActivate={(id) => void run(() => cashflow.activateForecast(projectId, id))}
          onRefreshSnapshot={(id) =>
            void run(() => cashflow.refreshCustomerSnapshot(projectId, id))
          }
          onSetLine={(id, body) => void run(() => cashflow.setForecastLine(projectId, id, body))}
        />
      ) : null}

      {section === "movements" ? (
        <CashflowMovements
          development={development}
          financing={financing}
          currency={currency}
          currencyId={project.base_currency_id}
          canRecord={canRecord}
          canConfirm={canConfirm}
          busy={busy}
          error={null}
          onRecordDevelopment={(body) =>
            void run(() => cashflow.recordDevelopmentMovement(projectId, body))
          }
          onConfirmDevelopment={(id) =>
            void run(() => cashflow.confirmDevelopmentMovement(projectId, id))
          }
          onReverseDevelopment={(id, reason) =>
            void run(() => cashflow.reverseDevelopmentMovement(projectId, id, reason))
          }
          onRecordFinancing={(body) =>
            void run(() => cashflow.recordFinancingMovement(projectId, body))
          }
          onConfirmFinancing={(id) =>
            void run(() => cashflow.confirmFinancingMovement(projectId, id))
          }
          onReverseFinancing={(id, reason) =>
            void run(() => cashflow.reverseFinancingMovement(projectId, id, reason))
          }
        />
      ) : null}

      {section === "escrow" ? (
        <CashflowEscrow
          answer={restrictions}
          canRecord={canRecord}
          canConfirm={canConfirm}
          busy={busy}
          onConfirmRestriction={(id) => void run(() => cashflow.confirmRestriction(projectId, id))}
          onReverseRestriction={(id, reason) =>
            void run(() => cashflow.reverseRestriction(projectId, id, reason))
          }
          onRecordRelease={(id, body) => void run(() => cashflow.recordRelease(projectId, id, body))}
          onConfirmRelease={(id) => void run(() => cashflow.confirmRelease(projectId, id))}
          onReverseRelease={(id, reason) =>
            void run(() => cashflow.reverseRelease(projectId, id, reason))
          }
        />
      ) : null}

      {section === "management" ? (
        <CashflowManagementView
          management={management}
          reconciliation={reconciliation}
          accuracy={accuracy}
          onOpenSource={(sourceType) => setDrilldown({ sourceType })}
        />
      ) : null}

      {drilldown ? (
        <CashflowDrilldown
          key={JSON.stringify(drilldown)}
          projectId={projectId}
          asOf={asOf || null}
          query={drilldown}
          onClose={() => setDrilldown(null)}
        />
      ) : null}
    </div>
  );
}
