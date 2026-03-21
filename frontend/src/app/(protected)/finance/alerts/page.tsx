"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { PageContainer } from "@/components/shell/PageContainer";
import { getPortfolioAlerts } from "@/lib/finance-api";
import type { PortfolioRiskResponse, ProjectRiskAlert, RiskAlertSeverity } from "@/lib/finance-types";
import styles from "@/styles/finance-dashboard.module.css";

/**
 * Finance — Financial Risk Alerts Dashboard.
 *
 * Displays the portfolio-wide risk alert summary produced by the
 * FinancialRiskAlertEngine.  Each alert row shows the project, alert type,
 * severity (colour-coded), observed metric value, threshold, and a
 * human-readable message.
 *
 * Data source:
 *   GET /finance/alerts/portfolio
 *
 * No financial calculations are performed on this page.
 */

// ---------------------------------------------------------------------------
// Severity badge
// ---------------------------------------------------------------------------

const SEVERITY_BADGE_STYLE: Record<RiskAlertSeverity, React.CSSProperties> = {
  HIGH: { background: "#fee2e2", color: "#991b1b", fontWeight: 600, borderRadius: 4, padding: "2px 8px" },
  MEDIUM: { background: "#ffedd5", color: "#9a3412", fontWeight: 600, borderRadius: 4, padding: "2px 8px" },
  LOW: { background: "#fef9c3", color: "#854d0e", fontWeight: 600, borderRadius: 4, padding: "2px 8px" },
};

function SeverityBadge({ severity }: { severity: RiskAlertSeverity }) {
  const style = SEVERITY_BADGE_STYLE[severity] ?? {};
  return <span style={style}>{severity}</span>;
}

// ---------------------------------------------------------------------------
// Portfolio alerts table
// ---------------------------------------------------------------------------

interface AlertsTableProps {
  alerts: ProjectRiskAlert[];
}

function AlertsTable({ alerts }: AlertsTableProps) {
  if (alerts.length === 0) {
    return <p>No risk alerts detected across the portfolio.</p>;
  }

  return (
    <table className={styles.dataTable ?? undefined} aria-label="Portfolio risk alerts table">
      <thead>
        <tr>
          <th scope="col">Project</th>
          <th scope="col">Alert Type</th>
          <th scope="col">Severity</th>
          <th scope="col">Metric Value</th>
          <th scope="col">Threshold</th>
          <th scope="col">Message</th>
        </tr>
      </thead>
      <tbody>
        {alerts.map((alert, idx) => (
          <tr key={`${alert.projectId}-${alert.alertType}-${idx}`}>
            <td>
              <Link href={`/projects/${encodeURIComponent(alert.projectId)}/financial`}>
                {alert.projectId.slice(0, 8)}…
              </Link>
            </td>
            <td>{alert.alertType}</td>
            <td>
              <SeverityBadge severity={alert.severity} />
            </td>
            <td>{alert.metricValue}</td>
            <td>{alert.threshold}</td>
            <td>{alert.message}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function FinanceAlertsPage() {
  const [data, setData] = useState<PortfolioRiskResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getPortfolioAlerts()
      .then(setData)
      .catch((err: unknown) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load portfolio risk alerts.",
        );
      })
      .finally(() => setLoading(false));
  }, []);

  const alertCount = data?.alerts.length ?? 0;

  return (
    <PageContainer
      title="Financial Risk Alerts"
      subtitle="Automatically detected financial risk conditions across all projects."
    >
      {loading && <p>Loading risk alerts…</p>}
      {error && <p className={styles.errorText}>{error}</p>}

      {data && (
        <>
          <div className={styles.kpiGrid}>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Total Alerts</div>
              <div className={styles.kpiValue}>{alertCount}</div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>High Severity</div>
              <div className={styles.kpiValue}>
                {data.alerts.filter((a) => a.severity === "HIGH").length}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Medium Severity</div>
              <div className={styles.kpiValue}>
                {data.alerts.filter((a) => a.severity === "MEDIUM").length}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Projects Affected</div>
              <div className={styles.kpiValue}>
                {new Set(data.alerts.map((a) => a.projectId)).size}
              </div>
            </div>
          </div>

          <h3 className={styles.sectionHeading}>Portfolio Alerts</h3>
          <AlertsTable alerts={data.alerts} />
        </>
      )}
    </PageContainer>
  );
}
