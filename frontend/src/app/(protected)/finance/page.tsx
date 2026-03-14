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
  type Project,
} from "@/lib/finance-dashboard-api";
import type {
  CollectionsHealth,
  CashflowHealth,
  SalesExceptionImpact,
  RegistrationFinanceSignal,
} from "@/lib/finance-dashboard-types";
import styles from "@/styles/finance-dashboard.module.css";

/**
 * Finance Dashboard page — executive financial decision view.
 *
 * Consolidates project-level financial posture into a single screen:
 *   - Headline finance KPIs
 *   - Collections / receivables health
 *   - Cashflow health
 *   - Commission exposure
 *   - Sales exception impact
 *   - Registration completion signal
 *   - Finance health summary
 *
 * All data is sourced from backend summary endpoints.
 * No financial calculations are performed in this page.
 */
export default function FinanceDashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState<string | null>(null);

  // Health summary state — populated as each section loads
  const [collections, setCollections] = useState<CollectionsHealth | null>(
    null,
  );
  const [cashflow, setCashflow] = useState<CashflowHealth | null>(null);
  const [exceptions, setExceptions] = useState<SalesExceptionImpact | null>(
    null,
  );
  const [registration, setRegistration] =
    useState<RegistrationFinanceSignal | null>(null);

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

  // Load health-summary data whenever the project changes
  React.useEffect(() => {
    if (!selectedProject) return;

    const id = selectedProject.id;

    setCollections(null);
    setCashflow(null);
    setExceptions(null);
    setRegistration(null);

    getProjectFinanceSummary(id)
      .then(({ collections: c }) => setCollections(c))
      .catch((err: unknown) => { console.error("Failed to load collections:", err); });

    getProjectCashflowSummary(id)
      .then(setCashflow)
      .catch((err: unknown) => { console.error("Failed to load cashflow:", err); });

    getProjectSalesExceptionsSummary(id)
      .then(setExceptions)
      .catch((err: unknown) => { console.error("Failed to load exceptions:", err); });

    getProjectRegistrationSummary(id)
      .then(setRegistration)
      .catch((err: unknown) => { console.error("Failed to load registration:", err); });
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
            <FinanceKpiGrid projectId={selectedProject.id} />
          </div>

          {/* Collections and cashflow — side by side */}
          <CollectionsHealthCard projectId={selectedProject.id} />
          <CashflowHealthCard projectId={selectedProject.id} />

          {/* Commission and exceptions — side by side */}
          <CommissionExposureCard projectId={selectedProject.id} />
          <SalesExceptionImpactCard projectId={selectedProject.id} />

          {/* Registration signal — full width */}
          <div className={styles.fullWidth}>
            <RegistrationFinanceSignalCard projectId={selectedProject.id} />
          </div>
        </FinanceSectionGrid>
      )}
    </PageContainer>
  );
}
