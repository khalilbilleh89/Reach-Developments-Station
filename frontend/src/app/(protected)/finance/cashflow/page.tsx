"use client";

import React, { useCallback, useEffect, useState } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { getProjects } from "@/lib/finance-dashboard-api";
import type { Project } from "@/lib/finance-dashboard-api";
import {
  getPortfolioCashflowForecast,
  getProjectCashflowForecast,
} from "@/lib/finance-api";
import type {
  MonthlyForecastEntry,
  PortfolioCashflowForecast,
  ProjectCashflowForecast,
} from "@/lib/finance-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/finance-dashboard.module.css";

/**
 * Finance Cashflow Forecasting Dashboard.
 *
 * Displays monthly projected cash inflows across the portfolio and for
 * individual projects, derived from outstanding installment schedules.
 *
 * Data sources:
 *   GET /finance/cashflow/forecast                        — portfolio forecast
 *   GET /finance/cashflow/forecast/project/{project_id}  — project forecast
 *
 * No financial calculations are performed on this page — all values are
 * sourced directly from the backend cashflow forecasting engine.
 */
export default function FinanceCashflowPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState<string | null>(null);

  const [portfolio, setPortfolio] =
    useState<PortfolioCashflowForecast | null>(null);
  const [portfolioError, setPortfolioError] = useState<string | null>(null);

  const [projectForecast, setProjectForecast] =
    useState<ProjectCashflowForecast | null>(null);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [forecastError, setForecastError] = useState<string | null>(null);

  // Load project list and portfolio forecast independently on mount.
  useEffect(() => {
    setProjectsLoading(true);
    setProjectsError(null);
    setPortfolioError(null);

    Promise.allSettled([getProjects(), getPortfolioCashflowForecast()]).then(
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
              : "Failed to load portfolio forecast.",
          );
        }

        setProjectsLoading(false);
      },
    );
  }, []);

  // Load project forecast whenever selected project changes.
  const loadProjectForecast = useCallback(async (projectId: string) => {
    setForecastLoading(true);
    setForecastError(null);
    setProjectForecast(null);
    try {
      const data = await getProjectCashflowForecast(projectId);
      setProjectForecast(data);
    } catch (err: unknown) {
      setForecastError(
        err instanceof Error ? err.message : "Failed to load project forecast.",
      );
    } finally {
      setForecastLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedProject) {
      loadProjectForecast(selectedProject.id);
    }
  }, [selectedProject, loadProjectForecast]);

  return (
    <PageContainer title="Cashflow Forecast">
      {/* Portfolio KPIs */}
      {portfolioError && <p className={styles.errorText}>{portfolioError}</p>}
      {portfolio && (
        <div className={styles.kpiGrid}>
          <div className={styles.kpiCard}>
            <div className={styles.kpiLabel}>Total Expected Inflows</div>
            <div className={styles.kpiValue}>
              {formatCurrency(portfolio.totalExpected)}
            </div>
          </div>
          <div className={styles.kpiCard}>
            <div className={styles.kpiLabel}>Projects with Forecasts</div>
            <div className={styles.kpiValue}>{portfolio.projectCount}</div>
          </div>
        </div>
      )}

      {/* Portfolio monthly forecast table */}
      {portfolio && portfolio.monthlyEntries.length > 0 && (
        <>
          <h3 className={styles.sectionHeading ?? undefined}>
            Portfolio Monthly Forecast
          </h3>
          <table className={styles.dataTable ?? undefined}>
            <thead>
              <tr>
                <th>Month</th>
                <th>Expected Collections</th>
                <th>Installments Due</th>
              </tr>
            </thead>
            <tbody>
              {portfolio.monthlyEntries.map((entry: MonthlyForecastEntry) => (
                <tr key={entry.month}>
                  <td>{entry.month}</td>
                  <td>{formatCurrency(entry.expectedCollections)}</td>
                  <td>{entry.installmentCount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
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

      {/* Project cashflow forecast */}
      {forecastLoading && <p>Loading project forecast…</p>}
      {forecastError && <p className={styles.errorText}>{forecastError}</p>}

      {projectForecast && (
        <>
          <div className={styles.kpiGrid}>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Project Expected Inflows</div>
              <div className={styles.kpiValue}>
                {formatCurrency(projectForecast.totalExpected)}
              </div>
            </div>
          </div>

          {projectForecast.monthlyEntries.length > 0 ? (
            <>
              <h3 className={styles.sectionHeading ?? undefined}>
                Project Monthly Forecast
              </h3>
              <table className={styles.dataTable ?? undefined}>
                <thead>
                  <tr>
                    <th>Month</th>
                    <th>Expected Collections</th>
                    <th>Installments Due</th>
                  </tr>
                </thead>
                <tbody>
                  {projectForecast.monthlyEntries.map(
                    (entry: MonthlyForecastEntry) => (
                      <tr key={entry.month}>
                        <td>{entry.month}</td>
                        <td>{formatCurrency(entry.expectedCollections)}</td>
                        <td>{entry.installmentCount}</td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </>
          ) : (
            <p>No outstanding installments found for this project.</p>
          )}
        </>
      )}
    </PageContainer>
  );
}
