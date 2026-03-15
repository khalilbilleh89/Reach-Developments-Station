"use client";

import React, { useEffect, useState } from "react";
import type { Project } from "@/lib/projects-types";
import type { ProjectSummary } from "@/lib/projects-types";
import { getProjectSummary } from "@/lib/projects-api";
import styles from "@/styles/projects.module.css";

interface ProjectOverviewProps {
  project: Project;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "\u2014";
  // Parse YYYY-MM-DD components directly to avoid UTC-to-local shift.
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString("en-GB", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/**
 * ProjectOverview — shows KPI cards and timeline summary for a project.
 *
 * Fetches and renders the project summary aggregation returned by
 * GET /api/v1/projects/{id}/summary.
 */
export function ProjectOverview({ project }: ProjectOverviewProps) {
  const [summary, setSummary] = useState<ProjectSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getProjectSummary(project.id)
      .then((s) => setSummary(s))
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load project summary.");
      })
      .finally(() => setLoading(false));
  }, [project.id]);

  if (loading) {
    return <div className={styles.loadingText}>Loading overview\u2026</div>;
  }

  if (error) {
    return (
      <div className={styles.errorBanner} role="alert">
        {error}
      </div>
    );
  }

  if (!summary) return null;

  return (
    <div>
      {/* KPI cards */}
      <div className={styles.overviewKpiGrid}>
        <div className={styles.kpiCard}>
          <span className={styles.kpiLabel}>Total Phases</span>
          <span className={styles.kpiValue}>{summary.total_phases}</span>
        </div>
        <div className={styles.kpiCard}>
          <span className={styles.kpiLabel}>Active Phases</span>
          <span className={`${styles.kpiValue} ${styles.kpiValueActive}`}>
            {summary.active_phases}
          </span>
        </div>
        <div className={styles.kpiCard}>
          <span className={styles.kpiLabel}>Planned Phases</span>
          <span className={styles.kpiValue}>{summary.planned_phases}</span>
        </div>
        <div className={styles.kpiCard}>
          <span className={styles.kpiLabel}>Completed Phases</span>
          <span className={`${styles.kpiValue} ${styles.kpiValueCompleted}`}>
            {summary.completed_phases}
          </span>
        </div>
      </div>

      {/* Timeline card */}
      <div className={styles.timelineCard}>
        <h3 className={styles.timelineTitle}>Development Timeline</h3>
        <div className={styles.timelineGrid}>
          <div className={styles.timelineField}>
            <span className={styles.timelineLabel}>Earliest Phase Start</span>
            <span className={styles.timelineValue}>
              {formatDate(summary.earliest_start_date)}
            </span>
          </div>
          <div className={styles.timelineField}>
            <span className={styles.timelineLabel}>Latest Target Completion</span>
            <span className={styles.timelineValue}>
              {formatDate(summary.latest_target_completion)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
