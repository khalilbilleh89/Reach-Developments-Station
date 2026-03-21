"use client";

import React, { useCallback, useEffect, useState } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { getProjects } from "@/lib/finance-dashboard-api";
import type { Project } from "@/lib/finance-dashboard-api";
import { getPortfolioAging, getProjectAging } from "@/lib/finance-api";
import type {
  AgingBucketSummary,
  PortfolioAging,
  ProjectAging,
  ReceivableAgingBucket,
} from "@/lib/finance-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/finance-dashboard.module.css";

/**
 * Finance Collections — Receivables Aging Dashboard.
 *
 * Displays portfolio-wide aging KPIs and a per-project aging breakdown.
 *
 * Data sources:
 *   GET /finance/receivables/aging-overview  — portfolio aging totals
 *   GET /finance/projects/{id}/aging         — project-level aging
 *
 * Buckets: current | 1-30 | 31-60 | 61-90 | 90+
 *
 * No financial calculations are performed here — all values come from the
 * backend aging engine.
 */

const BUCKET_LABELS: Record<ReceivableAgingBucket, string> = {
  current: "Current",
  "1-30": "1–30 Days",
  "31-60": "31–60 Days",
  "61-90": "61–90 Days",
  "90+": "90+ Days",
};

function bucketLabel(bucket: ReceivableAgingBucket): string {
  return BUCKET_LABELS[bucket] ?? bucket;
}

export default function FinanceCollectionsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState<string | null>(null);

  const [portfolio, setPortfolio] = useState<PortfolioAging | null>(null);
  const [portfolioError, setPortfolioError] = useState<string | null>(null);

  const [projectAging, setProjectAging] = useState<ProjectAging | null>(null);
  const [agingLoading, setAgingLoading] = useState(false);
  const [agingError, setAgingError] = useState<string | null>(null);

  // Load project list and portfolio overview independently on mount.
  useEffect(() => {
    setProjectsLoading(true);
    setProjectsError(null);
    setPortfolioError(null);

    Promise.allSettled([getProjects(), getPortfolioAging()]).then(
      ([projectsResult, portfolioResult]) => {
        if (projectsResult.status === "fulfilled") {
          const list = projectsResult.value;
          setProjects(list);
          if (list.length > 0) setSelectedProject(list[0]);
        } else {
          setProjectsError(
            projectsResult.reason instanceof Error
              ? projectsResult.reason.message
              : "Failed to load projects.",
          );
        }

        if (portfolioResult.status === "fulfilled") {
          setPortfolio(portfolioResult.value);
        } else {
          setPortfolioError(
            portfolioResult.reason instanceof Error
              ? portfolioResult.reason.message
              : "Failed to load portfolio aging.",
          );
        }

        setProjectsLoading(false);
      },
    );
  }, []);

  // Load project aging whenever selected project changes.
  const loadProjectAging = useCallback(async (projectId: string) => {
    setAgingLoading(true);
    setAgingError(null);
    setProjectAging(null);
    try {
      const data = await getProjectAging(projectId);
      setProjectAging(data);
    } catch (err: unknown) {
      setAgingError(
        err instanceof Error ? err.message : "Failed to load aging data.",
      );
    } finally {
      setAgingLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedProject) {
      loadProjectAging(selectedProject.id);
    }
  }, [selectedProject, loadProjectAging]);

  return (
    <PageContainer
      title="Collections — Receivables Aging"
      subtitle="Monitor outstanding receivables by aging bucket across the portfolio."
    >
      {/* Portfolio aging KPIs */}
      {portfolioError && <p className={styles.errorText}>{portfolioError}</p>}
      {portfolio && (
        <div className={styles.kpiGrid}>
          <div className={styles.kpiCard}>
            <div className={styles.kpiLabel}>Total Outstanding</div>
            <div className={styles.kpiValue}>
              {formatCurrency(portfolio.totalOutstanding)}
            </div>
          </div>
          <div className={styles.kpiCard}>
            <div className={styles.kpiLabel}>Installments</div>
            <div className={styles.kpiValue}>{portfolio.installmentCount}</div>
          </div>
          <div className={styles.kpiCard}>
            <div className={styles.kpiLabel}>Projects</div>
            <div className={styles.kpiValue}>{portfolio.projectCount}</div>
          </div>
        </div>
      )}

      {/* Portfolio aging bucket distribution */}
      {portfolio && portfolio.agingBuckets.length > 0 && (
        <table className={styles.dataTable ?? undefined}>
          <thead>
            <tr>
              <th>Bucket</th>
              <th>Outstanding Amount</th>
              <th>Installments</th>
            </tr>
          </thead>
          <tbody>
            {portfolio.agingBuckets.map((b: AgingBucketSummary) => (
              <tr key={b.bucket}>
                <td>{bucketLabel(b.bucket)}</td>
                <td>{formatCurrency(b.amount)}</td>
                <td>{b.installmentCount}</td>
              </tr>
            ))}
          </tbody>
        </table>
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

      {/* Project aging breakdown */}
      {agingLoading && <p>Loading aging data…</p>}
      {agingError && <p className={styles.errorText}>{agingError}</p>}

      {projectAging && (
        <>
          <div className={styles.kpiGrid}>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Project Outstanding</div>
              <div className={styles.kpiValue}>
                {formatCurrency(projectAging.totalOutstanding)}
              </div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Installments</div>
              <div className={styles.kpiValue}>
                {projectAging.installmentCount}
              </div>
            </div>
          </div>

          {projectAging.agingBuckets.length > 0 ? (
            <table className={styles.dataTable ?? undefined}>
              <thead>
                <tr>
                  <th>Bucket</th>
                  <th>Outstanding Amount</th>
                  <th>Installments</th>
                </tr>
              </thead>
              <tbody>
                {projectAging.agingBuckets.map((b: AgingBucketSummary) => (
                  <tr key={b.bucket}>
                    <td>{bucketLabel(b.bucket)}</td>
                    <td>{formatCurrency(b.amount)}</td>
                    <td>{b.installmentCount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>No outstanding receivables for this project.</p>
          )}
        </>
      )}
    </PageContainer>
  );
}
