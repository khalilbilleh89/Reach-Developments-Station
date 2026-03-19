/**
 * ConstructionDashboard — project-level construction dashboard.
 *
 * Displays:
 *   - KPI strip with top-level totals
 *   - Scope summary table with per-scope engineering/milestone/cost signals
 *
 * Clicking a scope row navigates to the scope detail view.
 */

"use client";

import React, { useCallback, useEffect, useState } from "react";
import { getProjectConstructionDashboard } from "@/lib/construction-api";
import type { ConstructionDashboardResponse } from "@/lib/construction-types";
import { ConstructionDashboardKPIStrip } from "./ConstructionDashboardKPIStrip";
import { ConstructionScopeSummaryTable } from "./ConstructionScopeSummaryTable";
import styles from "@/styles/construction.module.css";

interface ConstructionDashboardProps {
  projectId: string;
  onSelectScope: (scopeId: string) => void;
}

export function ConstructionDashboard({
  projectId,
  onSelectScope,
}: ConstructionDashboardProps) {
  const [dashboard, setDashboard] =
    useState<ConstructionDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = useCallback(() => {
    setLoading(true);
    getProjectConstructionDashboard(projectId)
      .then((data) => {
        setDashboard(data);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load construction dashboard.",
        );
        setDashboard(null);
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  if (loading) {
    return (
      <div className={styles.loadingText}>Loading construction dashboard…</div>
    );
  }

  if (error) {
    return (
      <div className={styles.errorBanner} role="alert">
        {error}
      </div>
    );
  }

  if (!dashboard) {
    return null;
  }

  return (
    <div>
      <ConstructionDashboardKPIStrip dashboard={dashboard} />

      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Scope Summary</h2>
        <span className={styles.sectionNote}>
          {dashboard.scopes_total} scope
          {dashboard.scopes_total !== 1 ? "s" : ""}
          {dashboard.scopes_active > 0 &&
            ` · ${dashboard.scopes_active} active`}
        </span>
      </div>

      <ConstructionScopeSummaryTable
        scopes={dashboard.scopes}
        onSelectScope={onSelectScope}
      />
    </div>
  );
}
