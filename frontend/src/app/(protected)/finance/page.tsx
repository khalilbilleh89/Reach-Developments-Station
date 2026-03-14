"use client";

import React, { useState, useCallback } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { FinanceSectionGrid } from "@/components/finance/FinanceSectionGrid";
import { FinanceKpiGrid } from "@/components/finance/FinanceKpiGrid";
import { CollectionsHealthCard } from "@/components/finance/CollectionsHealthCard";
import { CashflowHealthCard } from "@/components/finance/CashflowHealthCard";
import { CommissionExposureCard } from "@/components/finance/CommissionExposureCard";
import { SalesExceptionImpactCard } from "@/components/finance/SalesExceptionImpactCard";
import { RegistrationFinanceSignalCard } from "@/components/finance/RegistrationFinanceSignalCard";
import { FinanceHealthSummary } from "@/components/finance/FinanceHealthSummary";
import {
  getProjects,
  getProjectFinanceSummary,
  getProjectCashflowSummary,
  getProjectSalesExceptionsSummary,
  getProjectRegistrationSummary,
  getProjectCommissionSummary,
  type Project,
} from "@/lib/finance-dashboard-api";
import type {
  FinanceKpis,
  CollectionsHealth,
  CashflowHealth,
  CommissionExposure,
  SalesExceptionImpact,
  RegistrationFinanceSignal,
} from "@/lib/finance-dashboard-types";
import styles from "@/styles/finance-dashboard.module.css";

/**
 * Finance Dashboard page — executive financial decision view.
 *
 * This page is the single data orchestrator. It fetches all five backend
 * summary endpoints once per project selection and passes the results down
 * as props to presentational child components. No child card component
 * fetches independently.
 *
 * Sections displayed:
 *   - Finance health summary (derived display states)
 *   - Finance KPIs (headline metrics)
 *   - Collections health
 *   - Cashflow health
 *   - Commission exposure
 *   - Sales exception impact
 *   - Registration completion signal
 *
 * No financial calculations are performed in this page.
 */
export default function FinanceDashboardPage() {
  // Project list state
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState<string | null>(null);

  // Section data — all fetched once per project selection
  const [kpis, setKpis] = useState<FinanceKpis | null>(null);
  const [collections, setCollections] = useState<CollectionsHealth | null>(null);
  const [cashflow, setCashflow] = useState<CashflowHealth | null>(null);
  const [commission, setCommission] = useState<CommissionExposure | null>(null);
  const [exceptions, setExceptions] = useState<SalesExceptionImpact | null>(null);
  const [registration, setRegistration] = useState<RegistrationFinanceSignal | null>(null);

  // Shared loading flag — true while any section fetch is in flight
  const [dataLoading, setDataLoading] = useState(false);

  // Per-section error state so one failed fetch doesn't hide the rest
  const [financeSummaryError, setFinanceSummaryError] = useState<string | null>(null);
  const [cashflowError, setCashflowError] = useState<string | null>(null);
  const [commissionError, setCommissionError] = useState<string | null>(null);
  const [exceptionsError, setExceptionsError] = useState<string | null>(null);
  const [registrationError, setRegistrationError] = useState<string | null>(null);

  // Load project list on mount
  React.useEffect(() => {
    setProjectsLoading(true);
    setProjectsError(null);
    getProjects()
      .then((list) => {
        setProjects(list);
        if (list.length > 0) {
          setSelectedProject(list[0]);
        }
      })
      .catch((err: unknown) => {
        setProjectsError(
          err instanceof Error ? err.message : "Failed to load projects.",
        );
      })
      .finally(() => setProjectsLoading(false));
  }, []);

  // Fetch all section summaries once whenever the selected project changes.
  // Each fetch has its own error handler so a single failure does not block others.
  React.useEffect(() => {
    if (!selectedProject) return;

    const id = selectedProject.id;

    // Reset all section state before starting new fetches
    setKpis(null);
    setCollections(null);
    setCashflow(null);
    setCommission(null);
    setExceptions(null);
    setRegistration(null);
    setFinanceSummaryError(null);
    setCashflowError(null);
    setCommissionError(null);
    setExceptionsError(null);
    setRegistrationError(null);
    setDataLoading(true);

    const fetchFinanceSummary = getProjectFinanceSummary(id)
      .then(({ kpis: k, collections: c }) => {
        setKpis(k);
        setCollections(c);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : "Failed to load financial data.";
        setFinanceSummaryError(msg);
        console.error("Failed to load finance summary:", err);
      });

    const fetchCashflow = getProjectCashflowSummary(id)
      .then(setCashflow)
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : "Failed to load cashflow data.";
        setCashflowError(msg);
        console.error("Failed to load cashflow:", err);
      });

    const fetchCommission = getProjectCommissionSummary(id)
      .then(setCommission)
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : "Failed to load commission data.";
        setCommissionError(msg);
        console.error("Failed to load commission:", err);
      });

    const fetchExceptions = getProjectSalesExceptionsSummary(id)
      .then(setExceptions)
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : "Failed to load exception data.";
        setExceptionsError(msg);
        console.error("Failed to load exceptions:", err);
      });

    const fetchRegistration = getProjectRegistrationSummary(id)
      .then(setRegistration)
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : "Failed to load registration data.";
        setRegistrationError(msg);
        console.error("Failed to load registration:", err);
      });

    // Clear the shared loading flag only after all fetches have settled
    Promise.allSettled([
      fetchFinanceSummary,
      fetchCashflow,
      fetchCommission,
      fetchExceptions,
      fetchRegistration,
    ]).then(() => setDataLoading(false));
  }, [selectedProject]);

  const handleProjectChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const project = projects.find((p) => p.id === e.target.value);
      if (project) {
        setSelectedProject(project);
      }
    },
    [projects],
  );

  return (
    <PageContainer
      title="Finance"
      subtitle="Project financial posture — consolidated decision view."
    >
      {/* Project selector */}
      <div className={styles.selectorRow}>
        <label htmlFor="finance-project-selector" className={styles.selectorLabel}>
          Project
        </label>
        {projectsLoading ? (
          <span className={styles.emptyMessage}>Loading projects…</span>
        ) : projectsError ? (
          <span className={styles.emptyMessage}>{projectsError}</span>
        ) : projects.length === 0 ? (
          <span className={styles.emptyMessage}>No projects found.</span>
        ) : (
          <select
            id="finance-project-selector"
            className={styles.selectorSelect}
            value={selectedProject?.id ?? ""}
            onChange={handleProjectChange}
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

      {!selectedProject ? (
        <div className={styles.emptyState}>
          <p className={styles.emptyStateTitle}>No project selected</p>
          <p className={styles.emptyStateBody}>
            Select a project above to view its financial dashboard.
          </p>
        </div>
      ) : (
        <FinanceSectionGrid>
          {/* Finance health summary — full width, top */}
          <div className={styles.fullWidth}>
            <FinanceHealthSummary
              collections={collections}
              cashflow={cashflow}
              exceptions={exceptions}
              registration={registration}
            />
          </div>

          {/* KPI grid — full width */}
          <div className={styles.fullWidth}>
            <FinanceKpiGrid
              kpis={kpis}
              loading={dataLoading}
              error={financeSummaryError}
            />
          </div>

          {/* Collections and cashflow — side by side */}
          <CollectionsHealthCard
            collections={collections}
            loading={dataLoading}
            error={financeSummaryError}
          />
          <CashflowHealthCard
            cashflow={cashflow}
            loading={dataLoading}
            error={cashflowError}
          />

          {/* Commission and exceptions — side by side */}
          <CommissionExposureCard
            commission={commission}
            loading={dataLoading}
            error={commissionError}
          />
          <SalesExceptionImpactCard
            exceptions={exceptions}
            loading={dataLoading}
            error={exceptionsError}
          />

          {/* Registration signal — full width */}
          <div className={styles.fullWidth}>
            <RegistrationFinanceSignalCard
              signal={registration}
              loading={dataLoading}
              error={registrationError}
            />
          </div>
        </FinanceSectionGrid>
      )}
    </PageContainer>
  );
}
