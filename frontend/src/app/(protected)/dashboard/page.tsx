"use client";

import React, { useState, useCallback } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { DashboardGrid } from "@/components/dashboard/DashboardGrid";
import { ProjectSelector } from "@/components/dashboard/ProjectSelector";
import { FinancialSummaryGrid } from "@/components/dashboard/FinancialSummaryGrid";
import { RegistrationProgressCard } from "@/components/dashboard/RegistrationProgressCard";
import { CashflowSnapshot } from "@/components/dashboard/CashflowSnapshot";
import { SalesExceptionImpact } from "@/components/dashboard/SalesExceptionImpact";
import { type Project } from "@/lib/dashboard-api";
import styles from "@/styles/dashboard.module.css";

/**
 * Dashboard page — project operational overview.
 *
 * 1. Loads the project list via ProjectSelector.
 * 2. Displays financial summary, registration progress, cashflow snapshot
 *    and sales exception impact for the selected project.
 *
 * All data is sourced directly from backend summary endpoints.
 * No financial calculations are performed here.
 */
export default function DashboardPage() {
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);

  const handleProjectSelect = useCallback((project: Project) => {
    setSelectedProject(project);
  }, []);

  return (
    <PageContainer
      title="Dashboard"
      subtitle="Project financial and operational overview."
    >
      <ProjectSelector
        onSelect={handleProjectSelect}
        selectedId={selectedProject?.id}
      />

      {!selectedProject ? (
        <div className={styles.emptyState}>
          <p className={styles.emptyStateTitle}>No project selected</p>
          <p className={styles.emptyStateBody}>
            Select a project above to view its dashboard.
          </p>
        </div>
      ) : (
        <DashboardGrid>
          {/* Financial summary — full width */}
          <div className={styles.fullWidth}>
            <FinancialSummaryGrid projectId={selectedProject.id} />
          </div>

          {/* Registration progress */}
          <RegistrationProgressCard projectId={selectedProject.id} />

          {/* Cashflow snapshot */}
          <CashflowSnapshot projectId={selectedProject.id} />

          {/* Sales exception impact — full width */}
          <div className={styles.fullWidth}>
            <SalesExceptionImpact projectId={selectedProject.id} />
          </div>
        </DashboardGrid>
      )}
    </PageContainer>
  );
}
