"use client";

import React, { useEffect, useState } from "react";
import { getRegistrationSummary, type RegistrationSummary } from "@/lib/dashboard-api";
import styles from "@/styles/dashboard.module.css";

interface RegistrationProgressCardProps {
  projectId: string;
}

/**
 * RegistrationProgressCard — shows legal registration / conveyancing status.
 *
 * Fetches /registration/projects/{id}/summary and renders a progress bar
 * plus key registration counts.
 */
export function RegistrationProgressCard({
  projectId,
}: RegistrationProgressCardProps) {
  const [summary, setSummary] = useState<RegistrationSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getRegistrationSummary(projectId)
      .then(setSummary)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load registration data.");
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return <div className={styles.loadingState}>Loading registration data…</div>;
  }

  if (error || !summary) {
    return (
      <div className={styles.loadingState}>
        {error ?? "Registration data unavailable."}
      </div>
    );
  }

  const pct = Math.min(Math.max(summary.registration_progress_pct, 0), 100);

  return (
    <div className={styles.sectionCard}>
      <h2 className={styles.sectionTitle}>Registration Progress</h2>

      <div className={styles.metricsRow}>
        <div>
          <div className={styles.cardTitle}>Total Cases</div>
          <div className={styles.cardValue}>{summary.total_cases}</div>
        </div>
        <div>
          <div className={styles.cardTitle}>Registered</div>
          <div className={styles.cardValue}>{summary.registered}</div>
        </div>
        <div>
          <div className={styles.cardTitle}>In Progress</div>
          <div className={styles.cardValue}>{summary.in_progress}</div>
        </div>
        <div>
          <div className={styles.cardTitle}>Pending</div>
          <div className={styles.cardValue}>{summary.pending}</div>
        </div>
      </div>

      <div className={styles.progressContainer}>
        <div className={styles.progressLabel}>
          <span>Registration progress</span>
          <span>{pct.toFixed(1)}%</span>
        </div>
        <div
          className={styles.progressTrack}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Registration progress"
        >
          <div
            className={styles.progressFill}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
}
