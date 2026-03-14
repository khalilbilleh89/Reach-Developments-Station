import React from "react";
import type { RegistrationFinanceSignal } from "@/lib/finance-dashboard-types";
import styles from "@/styles/finance-dashboard.module.css";

interface RegistrationFinanceSignalCardProps {
  signal: RegistrationFinanceSignal | null;
  loading: boolean;
  error: string | null;
}

/**
 * RegistrationFinanceSignalCard — commercial vs legal completion signal.
 *
 * Purely presentational. Receives pre-fetched registration data from the parent
 * page. Sold-but-not-registered units represent a gap between commercial and
 * legal completion that finance teams need to track.
 */
export function RegistrationFinanceSignalCard({
  signal,
  loading,
  error,
}: RegistrationFinanceSignalCardProps) {
  if (loading) {
    return (
      <div className={styles.loadingState}>Loading registration data…</div>
    );
  }

  if (error || !signal) {
    return (
      <div className={styles.loadingState}>
        {error ?? "Registration data unavailable."}
      </div>
    );
  }

  const completionPct = Math.min(
    Math.max(signal.completion_ratio * 100, 0),
    100,
  );

  return (
    <div className={styles.sectionCard}>
      <h2 className={styles.sectionTitle}>Registration Signal</h2>
      <div className={styles.metricsRow}>
        <div>
          <div className={styles.cardTitle}>Total Sold</div>
          <div className={styles.cardValue}>{signal.total_sold_units}</div>
        </div>
        <div>
          <div className={styles.cardTitle}>Completed</div>
          <div className={styles.cardValue}>
            {signal.registration_cases_completed}
          </div>
        </div>
        <div>
          <div className={styles.cardTitle}>Open Cases</div>
          <div className={styles.cardValue}>
            {signal.registration_cases_open}
          </div>
        </div>
        <div>
          <div className={styles.cardTitle}>Not Registered</div>
          <div className={styles.cardValue}>{signal.sold_not_registered}</div>
        </div>
      </div>

      <div className={styles.progressContainer}>
        <div className={styles.progressLabel}>
          <span>Registration completion</span>
          <span>{completionPct.toFixed(1)}%</span>
        </div>
        <div
          className={styles.progressTrack}
          role="progressbar"
          aria-valuenow={completionPct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Registration completion"
        >
          <div
            className={styles.progressFill}
            style={{ width: `${completionPct}%` }}
          />
        </div>
      </div>
    </div>
  );
}
