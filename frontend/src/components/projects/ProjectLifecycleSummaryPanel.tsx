/**
 * ProjectLifecycleSummaryPanel — cross-module lifecycle readiness summary.
 *
 * Fetches and renders the project lifecycle summary returned by
 * GET /api/v1/projects/{id}/lifecycle-summary.
 *
 * Design principles:
 *   - All lifecycle stage values are sourced from the backend; no re-derivation here.
 *   - Renders an explicit blocked state when a prerequisite dependency is missing.
 *   - Next-step CTA is driven by backend-provided next_step_route.
 */

"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { getProjectLifecycleSummary } from "@/lib/projects-api";
import type {
  ProjectLifecycleSummary,
  ProjectLifecycleStage,
} from "@/lib/projects-types";
import styles from "@/styles/projects.module.css";

// ---------------------------------------------------------------------------
// Stage display helpers
// ---------------------------------------------------------------------------

const STAGE_LABELS: Record<ProjectLifecycleStage, string> = {
  land_defined: "Land Defined",
  scenario_defined: "Scenario Defined",
  feasibility_ready: "Feasibility Ready",
  feasibility_calculated: "Feasibility Calculated",
  structure_ready: "Structure Ready",
  construction_baseline_pending: "Baseline Pending",
  construction_monitored: "Construction Monitored",
  portfolio_visible: "Portfolio Visible",
};

const STAGE_ORDER: ProjectLifecycleStage[] = [
  "land_defined",
  "scenario_defined",
  "feasibility_ready",
  "feasibility_calculated",
  "structure_ready",
  "construction_baseline_pending",
  "construction_monitored",
  "portfolio_visible",
];

function stageLabel(stage: ProjectLifecycleStage): string {
  return STAGE_LABELS[stage] ?? stage;
}

function stageProgress(stage: ProjectLifecycleStage): number {
  const idx = STAGE_ORDER.indexOf(stage);
  if (idx < 0) return 0;
  return Math.round(((idx + 1) / STAGE_ORDER.length) * 100);
}

// ---------------------------------------------------------------------------
// Readiness flag row
// ---------------------------------------------------------------------------

interface FlagRowProps {
  label: string;
  present: boolean;
  count?: number;
}

function FlagRow({ label, present, count }: FlagRowProps) {
  return (
    <div className={styles.lifecycleFlagRow}>
      <span
        className={
          present ? styles.lifecycleFlagPresent : styles.lifecycleFlagMissing
        }
        aria-hidden="true"
      >
        {present ? "✓" : "○"}
      </span>
      <span className={styles.lifecycleFlagLabel}>{label}</span>
      {count !== undefined && count > 0 && (
        <span className={styles.lifecycleFlagCount}>{count}</span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface ProjectLifecycleSummaryPanelProps {
  projectId: string;
}

export function ProjectLifecycleSummaryPanel({
  projectId,
}: ProjectLifecycleSummaryPanelProps) {
  const [summary, setSummary] = useState<ProjectLifecycleSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    getProjectLifecycleSummary(projectId, controller.signal)
      .then((s) => {
        if (!controller.signal.aborted) {
          setSummary(s);
        }
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load lifecycle summary."
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [projectId]);

  if (loading) {
    return (
      <div className={styles.loadingText}>Loading lifecycle summary…</div>
    );
  }

  if (error) {
    return (
      <div className={styles.errorBanner} role="alert">
        {error}
      </div>
    );
  }

  if (!summary) return null;

  const progress = stageProgress(summary.current_stage);

  return (
    <div className={styles.lifecyclePanel}>
      {/* Stage header */}
      <div className={styles.lifecycleStageHeader}>
        <div className={styles.lifecycleStageInfo}>
          <span className={styles.lifecycleStageName}>
            {stageLabel(summary.current_stage)}
          </span>
          <span className={styles.lifecycleStageProgress}>
            {progress}% complete
          </span>
        </div>
        <div
          className={styles.lifecycleProgressBar}
          role="progressbar"
          aria-valuenow={progress}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Lifecycle progress: ${progress}%`}
        >
          <div
            className={styles.lifecycleProgressFill}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Readiness flags */}
      <div className={styles.lifecycleFlagsGrid}>
        <FlagRow
          label="Scenario"
          present={summary.has_scenarios}
          count={summary.scenario_count}
        />
        <FlagRow
          label="Active Scenario"
          present={summary.has_active_scenario}
        />
        <FlagRow
          label="Feasibility Run"
          present={summary.has_feasibility_runs}
          count={summary.feasibility_run_count}
        />
        <FlagRow
          label="Feasibility Calculated"
          present={summary.has_calculated_feasibility}
        />
        <FlagRow label="Structure / Phases" present={summary.has_phases} />
        <FlagRow
          label="Construction Records"
          present={summary.has_construction_records}
          count={summary.construction_record_count}
        />
        <FlagRow
          label="Approved Baseline"
          present={summary.has_approved_tender_baseline}
        />
      </div>

      {/* Blocked reason */}
      {summary.blocked_reason && (
        <div className={styles.lifecycleBlockedBanner} role="alert">
          <strong>Blocked: </strong>
          {summary.blocked_reason}
        </div>
      )}

      {/* Next step */}
      <div className={styles.lifecycleNextStep}>
        <p className={styles.lifecycleNextStepText}>
          {summary.recommended_next_step}
        </p>
        {summary.next_step_route && (
          <Link
            href={summary.next_step_route}
            className={styles.lifecycleNextStepCta}
          >
            Continue →
          </Link>
        )}
      </div>
    </div>
  );
}
