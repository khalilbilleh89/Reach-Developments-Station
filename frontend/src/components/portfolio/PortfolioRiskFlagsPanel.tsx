/**
 * PortfolioRiskFlagsPanel — risk flags section for the portfolio dashboard.
 *
 * Renders the list of risk/alert signals from the backend. Severity badges
 * and descriptions are rendered as received. No scoring or ordering logic
 * is added here beyond what the backend provides.
 *
 * Renders a safe empty state when no risk flags exist.
 */

import React from "react";
import type { PortfolioRiskFlag } from "@/lib/portfolio-types";
import styles from "@/styles/portfolio.module.css";

interface PortfolioRiskFlagsPanelProps {
  riskFlags: PortfolioRiskFlag[];
}

function severityClass(severity: string): string {
  if (severity === "critical") return styles.severityCritical;
  return styles.severityWarning;
}

function severityLabel(severity: string): string {
  if (severity === "critical") return "Critical";
  return "Warning";
}

export function PortfolioRiskFlagsPanel({
  riskFlags,
}: PortfolioRiskFlagsPanelProps) {
  return (
    <div className={styles.panelCard}>
      <h2 className={styles.panelTitle}>Risk Flags</h2>

      {riskFlags.length === 0 ? (
        <p className={styles.panelEmpty}>No risk flags detected.</p>
      ) : (
        <ul className={styles.riskFlagList} aria-label="Portfolio risk flags">
          {riskFlags.map((flag, index) => (
            <li
              key={`${flag.flag_type}-${flag.affected_project_id ?? "portfolio"}-${index}`}
              className={styles.riskFlagItem}
            >
              <span
                className={`${styles.riskSeverityBadge} ${severityClass(flag.severity)}`}
              >
                {severityLabel(flag.severity)}
              </span>
              <div className={styles.riskFlagBody}>
                <span className={styles.riskFlagDescription}>
                  {flag.description}
                </span>
                {flag.affected_project_name && (
                  <span className={styles.riskFlagProject}>
                    {flag.affected_project_name}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
