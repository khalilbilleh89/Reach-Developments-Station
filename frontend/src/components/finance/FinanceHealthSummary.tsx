import React from "react";
import type {
  FinanceHealthState,
  FinanceHealthStatus,
  CollectionsHealth,
  CashflowHealth,
  SalesExceptionImpact,
  RegistrationFinanceSignal,
} from "@/lib/finance-dashboard-types";
import styles from "@/styles/finance-dashboard.module.css";

// ---------- Thresholds used for display-only state derivation ------------
// These are presentational thresholds only. No financial recalculation.

const COLLECTION_RATIO_WATCH = 0.5;
const COLLECTION_RATIO_CRITICAL = 0.25;
const REGISTRATION_LAG_THRESHOLD = 0;

interface FinanceHealthSummaryProps {
  collections: CollectionsHealth | null;
  cashflow: CashflowHealth | null;
  exceptions: SalesExceptionImpact | null;
  registration: RegistrationFinanceSignal | null;
}

/**
 * Derive the display-only health status for each finance dimension.
 *
 * Acceptable lightweight presentational derivations (no financial math):
 *   - collection_ratio below thresholds → watch / critical
 *   - net_cashflow negative → critical
 *   - sold_not_registered > 0 → watch
 *   - pending_exceptions > 0 → watch
 */
function deriveHealthState(
  collections: CollectionsHealth | null,
  cashflow: CashflowHealth | null,
  exceptions: SalesExceptionImpact | null,
  registration: RegistrationFinanceSignal | null,
): FinanceHealthState {
  let collectionsStatus: FinanceHealthStatus = "healthy";
  if (collections) {
    if (collections.collection_ratio < COLLECTION_RATIO_CRITICAL) {
      collectionsStatus = "critical";
    } else if (collections.collection_ratio < COLLECTION_RATIO_WATCH) {
      collectionsStatus = "watch";
    }
  }

  let cashflowStatus: FinanceHealthStatus = "healthy";
  if (cashflow && cashflow.net_cashflow < 0) {
    cashflowStatus = "critical";
  }

  let exceptionsStatus: FinanceHealthStatus = "healthy";
  if (exceptions && exceptions.pending_exceptions > 0) {
    exceptionsStatus = "watch";
  }

  let registrationStatus: FinanceHealthStatus = "healthy";
  if (
    registration &&
    registration.sold_not_registered > REGISTRATION_LAG_THRESHOLD
  ) {
    registrationStatus = "watch";
  }

  return {
    collections: collectionsStatus,
    cashflow: cashflowStatus,
    exceptions: exceptionsStatus,
    registration: registrationStatus,
  };
}

interface BadgeProps {
  label: string;
  status: FinanceHealthStatus;
}

function HealthBadge({ label, status }: BadgeProps) {
  const badgeClass =
    status === "healthy"
      ? styles.badgeHealthy
      : status === "watch"
        ? styles.badgeWatch
        : styles.badgeCritical;

  const icon =
    status === "healthy" ? "✅" : status === "watch" ? "⚠️" : "🔴";

  return (
    <span className={`${styles.healthBadge} ${badgeClass}`}>
      {icon} {label}
    </span>
  );
}

const STATUS_LABEL: Record<string, Record<FinanceHealthStatus, string>> = {
  collections: {
    healthy: "Collections healthy",
    watch: "Collections — watch",
    critical: "Collections critical",
  },
  cashflow: {
    healthy: "Cashflow positive",
    watch: "Cashflow — watch",
    critical: "Cashflow negative",
  },
  exceptions: {
    healthy: "Exceptions clear",
    watch: "Exceptions pending",
    critical: "Exceptions — review",
  },
  registration: {
    healthy: "Registration on track",
    watch: "Registration lag",
    critical: "Registration critical",
  },
};

/**
 * FinanceHealthSummary — high-level interpretive summary block.
 *
 * Derives display-only status badges from the backend-returned metrics.
 * No financial recalculation is performed — all status logic is based on
 * simple threshold comparisons on backend-provided values.
 */
export function FinanceHealthSummary({
  collections,
  cashflow,
  exceptions,
  registration,
}: FinanceHealthSummaryProps) {
  const health = deriveHealthState(
    collections,
    cashflow,
    exceptions,
    registration,
  );

  const dimensions = [
    { key: "collections", status: health.collections },
    { key: "cashflow", status: health.cashflow },
    { key: "exceptions", status: health.exceptions },
    { key: "registration", status: health.registration },
  ] as const;

  return (
    <div className={styles.healthSummaryCard}>
      <h2 className={styles.sectionTitle}>Finance Health Summary</h2>
      <div className={styles.healthBadgesRow}>
        {dimensions.map(({ key, status }) => (
          <HealthBadge
            key={key}
            label={STATUS_LABEL[key][status]}
            status={status}
          />
        ))}
      </div>
    </div>
  );
}
