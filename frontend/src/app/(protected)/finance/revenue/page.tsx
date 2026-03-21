"use client";

import React, { useEffect, useState, useCallback } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { getProjects } from "@/lib/finance-dashboard-api";
import type { Project } from "@/lib/finance-dashboard-api";
import {
  getProjectRevenueSummary,
  getRevenueOverview,
} from "@/lib/finance-api";
import type {
  ProjectRevenueSummary,
  RevenueRecognition,
  RevenueOverview,
} from "@/lib/finance-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/finance-dashboard.module.css";

/**
 * Finance Revenue Recognition page.
 *
 * Displays per-project and portfolio-wide recognized vs deferred revenue.
 *
 * Data sources:
 *   GET /finance/projects/{id}/revenue-summary  — project breakdown
 *   GET /finance/revenue/overview               — portfolio totals
 *
 * No financial calculations are performed on this page — all values are
 * sourced directly from the backend revenue recognition engine.
 */
export default function FinanceRevenuePage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState<string | null>(null);

  const [summary, setSummary] = useState<ProjectRevenueSummary | null>(null);
  const [overview, setOverview] = useState<RevenueOverview | null>(null);
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState<string | null>(null);

  // Load project list and portfolio overview on mount
  useEffect(() => {
    setProjectsLoading(true);
    setProjectsError(null);

    Promise.all([getProjects(), getRevenueOverview()])
      .then(([list, ov]) => {
        setProjects(list);
        setOverview(ov);
        if (list.length > 0) setSelectedProject(list[0]);
      })
      .catch((err: unknown) => {
        setProjectsError(
          err instanceof Error ? err.message : "Failed to load data.",
        );
      })
      .finally(() => setProjectsLoading(false));
  }, []);

  // Load project revenue summary whenever selected project changes
  const loadProjectRevenue = useCallback(async (projectId: string) => {
    setDataLoading(true);
    setDataError(null);
    setSummary(null);
    try {
      const data = await getProjectRevenueSummary(projectId);
      setSummary(data);
    } catch (err: unknown) {
      setDataError(
        err instanceof Error ? err.message : "Failed to load revenue data.",
      );
    } finally {
      setDataLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedProject) {
      loadProjectRevenue(selectedProject.id);
    }
  }, [selectedProject, loadProjectRevenue]);

  return (
    <PageContainer title="Revenue Recognition">
      {/* Portfolio overview */}
      {overview && (
        <div className={styles.kpiGrid}>
          <div className={styles.kpiCard}>
            <div className={styles.kpiLabel}>Total Contract Value</div>
            <div className={styles.kpiValue}>
              {formatCurrency(overview.totalContractValue)}
            </div>
          </div>
          <div className={styles.kpiCard}>
            <div className={styles.kpiLabel}>Recognized Revenue</div>
            <div className={styles.kpiValue}>
              {formatCurrency(overview.totalRecognizedRevenue)}
            </div>
          </div>
          <div className={styles.kpiCard}>
            <div className={styles.kpiLabel}>Deferred Revenue</div>
            <div className={styles.kpiValue}>
              {formatCurrency(overview.totalDeferredRevenue)}
            </div>
          </div>
          <div className={styles.kpiCard}>
            <div className={styles.kpiLabel}>Recognition %</div>
            <div className={styles.kpiValue}>
              {overview.overallRecognitionPercentage.toFixed(1)}%
            </div>
          </div>
        </div>
      )}

      {/* Project selector */}
      <div className={styles.projectSelector}>
        {projectsLoading && <p>Loading projects…</p>}
        {projectsError && <p className={styles.errorText}>{projectsError}</p>}
        {!projectsLoading && projects.length > 0 && (
          <select
            value={selectedProject?.id ?? ""}
            onChange={(e) => {
              const p = projects.find((x) => x.id === e.target.value) ?? null;
              setSelectedProject(p);
            }}
            aria-label="Select project"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.code})
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Project revenue summary */}
      {dataLoading && <p>Loading revenue data…</p>}
      {dataError && <p className={styles.errorText}>{dataError}</p>}

      {summary && (
        <>
          <div className={styles.kpiGrid}>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Contract Value</div>
              <div className={styles.kpiValue}>
                {formatCurrency(summary.totalContractValue)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Recognized</div>
              <div className={styles.kpiValue}>
                {formatCurrency(summary.totalRecognizedRevenue)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Deferred</div>
              <div className={styles.kpiValue}>
                {formatCurrency(summary.totalDeferredRevenue)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Recognition %</div>
              <div className={styles.kpiValue}>
                {summary.overallRecognitionPercentage.toFixed(1)}%
              </div>
            </div>
          </div>

          {/* Per-contract breakdown table */}
          {summary.contracts.length > 0 ? (
            <table className={styles.dataTable ?? undefined}>
              <thead>
                <tr>
                  <th>Contract ID</th>
                  <th>Contract Total</th>
                  <th>Recognized</th>
                  <th>Deferred</th>
                  <th>Recognition %</th>
                </tr>
              </thead>
              <tbody>
                {summary.contracts.map((c: RevenueRecognition) => (
                  <tr key={c.contract_id}>
                    <td>{c.contract_id}</td>
                    <td>{formatCurrency(c.contractTotal)}</td>
                    <td>{formatCurrency(c.recognizedRevenue)}</td>
                    <td>{formatCurrency(c.deferredRevenue)}</td>
                    <td>{c.recognitionPercentage.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>No contracts found for this project.</p>
          )}
        </>
      )}
    </PageContainer>
  );
}
