"use client";

import React, { useCallback, useEffect, useState } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { MetricCard } from "@/components/dashboard/MetricCard";
import {
  listProjectCases,
  getProjectSummary,
} from "@/lib/registry-api";
import { apiFetch } from "@/lib/api-client";
import type { RegistrationCase, CaseStatus } from "@/lib/registry-types";
import styles from "@/styles/demo-shell.module.css";
import selectorStyles from "@/styles/finance-dashboard.module.css";
import constructionStyles from "@/styles/construction.module.css";

// ---------------------------------------------------------------------------
// Project list (minimal shape — we only need id/name)
// ---------------------------------------------------------------------------

interface ProjectListItem {
  id: string;
  name: string;
  code: string;
}

interface ProjectListResponse {
  items: ProjectListItem[];
  total: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusBadgeClass(status: CaseStatus): string {
  switch (status) {
    case "completed":
      return styles.badgeGreen;
    case "submitted":
    case "under_review":
      return styles.badgeBlue;
    case "in_progress":
      return styles.badgePurple;
    case "awaiting_documents":
      return styles.badgeRed;
    case "draft":
      return styles.badgeGray;
    case "cancelled":
      return styles.badgeGray;
    default:
      return styles.badgeGray;
  }
}

function formatStatus(status: CaseStatus): string {
  switch (status) {
    case "draft":
      return "Draft";
    case "in_progress":
      return "In Progress";
    case "awaiting_documents":
      return "Awaiting Docs";
    case "submitted":
      return "Submitted";
    case "under_review":
      return "Under Review";
    case "completed":
      return "Completed";
    case "cancelled":
      return "Cancelled";
    default:
      return status;
  }
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  return dateStr;
}

function countMissingDocs(c: RegistrationCase): number {
  return c.documents.filter((d) => d.is_required && !d.is_received).length;
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

/**
 * Registry page — project-scoped conveyancing case tracker.
 *
 * Wired to the live /registry/* backend endpoints.
 * Select a project to view its registration cases and KPI summary.
 */
export default function Page() {
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState<string | null>(null);

  const [cases, setCases] = useState<RegistrationCase[]>([]);
  const [summary, setSummary] = useState<{
    total_sold_units: number;
    registration_cases_open: number;
    registration_cases_completed: number;
    sold_not_registered: number;
    registration_completion_ratio: number;
  } | null>(null);
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState<string | null>(null);

  // Load project list on mount
  useEffect(() => {
    setProjectsLoading(true);
    apiFetch<ProjectListResponse>("/projects?limit=200")
      .then((resp) => {
        setProjects(resp.items);
        if (resp.items.length > 0) {
          setSelectedProjectId(resp.items[0].id);
        }
      })
      .catch((err: unknown) => {
        setProjectsError(
          err instanceof Error ? err.message : "Failed to load projects.",
        );
      })
      .finally(() => setProjectsLoading(false));
  }, []);

  // Fetch cases and summary when project changes
  const fetchProjectData = useCallback((projectId: string) => {
    if (!projectId) return;
    setDataLoading(true);
    setDataError(null);
    setCases([]);
    setSummary(null);

    Promise.all([
      listProjectCases(projectId, { limit: 500 }),
      getProjectSummary(projectId),
    ])
      .then(([casesResp, summaryResp]) => {
        setCases(casesResp.items);
        setSummary(summaryResp);
      })
      .catch((err: unknown) => {
        setDataError(
          err instanceof Error ? err.message : "Failed to load registry data.",
        );
      })
      .finally(() => setDataLoading(false));
  }, []);

  useEffect(() => {
    if (selectedProjectId) {
      fetchProjectData(selectedProjectId);
    }
  }, [selectedProjectId, fetchProjectData]);

  const awaitingDocsCount = cases.filter(
    (c) => c.status === "awaiting_documents",
  ).length;
  const inProgressCount = cases.filter(
    (c) => c.status === "in_progress" || c.status === "under_review" || c.status === "submitted",
  ).length;
  const completedCount = cases.filter((c) => c.status === "completed").length;

  return (
    <PageContainer
      title="Registry"
      subtitle="Conveyancing cases, milestones, and document tracking."
    >
      {/* Project selector */}
      <div className={selectorStyles.selectorRow}>
        <label
          htmlFor="registry-project-selector"
          className={selectorStyles.selectorLabel}
        >
          Project
        </label>
        {projectsLoading ? (
          <span>Loading projects…</span>
        ) : projectsError ? (
          <span>{projectsError}</span>
        ) : projects.length === 0 ? (
          <span>No projects found.</span>
        ) : (
          <select
            id="registry-project-selector"
            className={selectorStyles.selectorSelect}
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            aria-label="Select project"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* KPI summary */}
      <div className={styles.kpiGrid}>
        <MetricCard
          title="Open Cases"
          value={dataLoading ? "…" : (summary?.registration_cases_open ?? 0)}
          subtitle="Active registration processes"
          icon="📂"
        />
        <MetricCard
          title="Awaiting Docs"
          value={dataLoading ? "…" : awaitingDocsCount}
          subtitle="Requires buyer action"
          icon="⚠️"
        />
        <MetricCard
          title="In Review"
          value={dataLoading ? "…" : inProgressCount}
          subtitle="Submitted or under processing"
          icon="🔍"
        />
        <MetricCard
          title="Completed"
          value={dataLoading ? "…" : completedCount}
          subtitle="Title transfer finalised"
          icon="✅"
        />
      </div>

      {/* Error */}
      {dataError && (
        <div className={constructionStyles.errorBanner} role="alert">
          {dataError}
        </div>
      )}

      {/* Case tracker table */}
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Registration Case Tracker</h2>
        {!dataLoading && (
          <span className={styles.sectionNote}>
            {cases.length} case{cases.length !== 1 ? "s" : ""}
            {summary
              ? ` · ${Math.round(summary.registration_completion_ratio * 100)}% complete`
              : ""}
          </span>
        )}
      </div>

      {dataLoading && (
        <div className={constructionStyles.loadingText}>
          Loading registry cases…
        </div>
      )}

      {!dataLoading && !dataError && cases.length === 0 && selectedProjectId && (
        <div className={constructionStyles.emptyState}>
          <p className={constructionStyles.emptyText}>No registry cases found.</p>
          <p className={constructionStyles.emptySubtext}>
            Cases are opened automatically when a sales contract is finalised
            and a registry case is submitted.
          </p>
        </div>
      )}

      {!dataLoading && cases.length > 0 && (
        <div className={styles.tableWrapper}>
          <table
            className={styles.table}
            aria-label="Registration case tracker"
          >
            <thead>
              <tr>
                <th scope="col">Case ID</th>
                <th scope="col">Unit</th>
                <th scope="col">Buyer</th>
                <th scope="col">Status</th>
                <th scope="col">Jurisdiction</th>
                <th scope="col">Opened</th>
                <th scope="col">Submitted</th>
                <th scope="col">Missing Docs</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id}>
                  <td
                    style={{
                      fontFamily: "monospace",
                      fontSize: "var(--font-size-xs)",
                    }}
                  >
                    {c.id.slice(0, 8)}…
                  </td>
                  <td
                    style={{
                      fontFamily: "monospace",
                      fontSize: "var(--font-size-xs)",
                    }}
                  >
                    {c.unit_id.slice(0, 8)}…
                  </td>
                  <td>{c.buyer_name}</td>
                  <td>
                    <span
                      className={`${styles.badge} ${statusBadgeClass(c.status)}`}
                    >
                      {formatStatus(c.status)}
                    </span>
                  </td>
                  <td>{c.jurisdiction ?? "—"}</td>
                  <td>{formatDate(c.opened_at)}</td>
                  <td>{formatDate(c.submitted_at)}</td>
                  <td style={{ textAlign: "center" }}>
                    {countMissingDocs(c) > 0 ? (
                      <span
                        className={`${styles.badge} ${styles.badgeRed}`}
                      >
                        {countMissingDocs(c)}
                      </span>
                    ) : (
                      <span style={{ color: "var(--color-text-muted)" }}>
                        —
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PageContainer>
  );
}
