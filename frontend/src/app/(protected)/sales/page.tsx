"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import { SalesFilters } from "@/components/sales/SalesFilters";
import { SalesCandidatesTable } from "@/components/sales/SalesCandidatesTable";
import {
  getProjects,
  getSalesCandidates,
  filterSalesCandidates,
} from "@/lib/sales-api";
import type { Project } from "@/lib/units-types";
import type { SalesCandidate, SalesFiltersState } from "@/lib/sales-types";
import styles from "@/styles/sales-workflow.module.css";

const DEFAULT_FILTERS: SalesFiltersState = {
  status: "",
  unit_type: "",
  has_approved_exception: "",
  contract_status: "",
  readiness: "",
  min_price: "",
  max_price: "",
};

/**
 * SalesPage — sales workflow landing page.
 *
 * Displays a filterable queue of sales candidates for the selected project.
 * Each candidate is enriched with pricing, exception, contract, and readiness
 * data sourced from the backend.
 *
 * Selecting a candidate navigates to the guided unit-level sales workflow.
 */
export default function SalesPage() {
  const router = useRouter();

  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState<string | null>(null);

  const [candidates, setCandidates] = useState<SalesCandidate[]>([]);
  const [candidatesLoading, setCandidatesLoading] = useState(false);
  const [candidatesError, setCandidatesError] = useState<string | null>(null);

  const [filters, setFilters] = useState<SalesFiltersState>(DEFAULT_FILTERS);

  // Load projects on mount
  useEffect(() => {
    setProjectsLoading(true);
    getProjects()
      .then((list) => {
        setProjects(list);
        if (list.length > 0) {
          setSelectedProjectId(list[0].id);
        }
      })
      .catch((err: unknown) => {
        setProjectsError(
          err instanceof Error ? err.message : "Failed to load projects.",
        );
      })
      .finally(() => setProjectsLoading(false));
  }, []);

  // Load candidates whenever the selected project changes
  useEffect(() => {
    if (!selectedProjectId) return;

    let isCurrent = true;

    setCandidatesLoading(true);
    setCandidatesError(null);
    setCandidates([]);

    getSalesCandidates(selectedProjectId)
      .then((list) => {
        if (!isCurrent) return;
        setCandidates(list);
      })
      .catch((err: unknown) => {
        if (!isCurrent) return;
        setCandidatesError(
          err instanceof Error ? err.message : "Failed to load sales data.",
        );
      })
      .finally(() => {
        if (isCurrent) setCandidatesLoading(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [selectedProjectId]);

  const handleProjectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedProjectId(e.target.value);
    setFilters(DEFAULT_FILTERS);
  };

  const handleFiltersChange = useCallback((f: SalesFiltersState) => {
    setFilters(f);
  }, []);

  const handleSelectUnit = useCallback(
    (unitId: string) => {
      router.push(`/sales/${unitId}`);
    },
    [router],
  );

  const filtered = filterSalesCandidates(candidates, filters);

  return (
    <PageContainer
      title="Sales"
      subtitle="Review commercial readiness and manage the sales pipeline."
    >
      {/* Project selector */}
      <div className={styles.selectorRow}>
        <label htmlFor="sales-project-selector" className={styles.selectorLabel}>
          Project
        </label>
        {projectsLoading ? (
          <span className={styles.loadingState}>Loading projects…</span>
        ) : projectsError ? (
          <span className={styles.errorState}>{projectsError}</span>
        ) : projects.length === 0 ? (
          <span className={styles.loadingState}>No projects found.</span>
        ) : (
          <select
            id="sales-project-selector"
            className={styles.selectorSelect}
            value={selectedProjectId}
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

      {!selectedProjectId ? (
        <div className={styles.emptyState}>
          <p className={styles.emptyStateTitle}>No project selected</p>
          <p className={styles.emptyStateBody}>
            Select a project above to view the sales queue.
          </p>
        </div>
      ) : (
        <>
          {/* Filters */}
          <SalesFilters filters={filters} onChange={handleFiltersChange} />

          {/* Results */}
          {candidatesLoading ? (
            <div className={styles.loadingState}>Loading sales data…</div>
          ) : candidatesError ? (
            <div className={styles.errorState}>{candidatesError}</div>
          ) : (
            <>
              <p className={styles.resultsCount}>
                {filtered.length} unit{filtered.length !== 1 ? "s" : ""} shown
                {filtered.length !== candidates.length
                  ? ` (${candidates.length} total)`
                  : ""}
              </p>
              <SalesCandidatesTable
                candidates={filtered}
                onSelectUnit={handleSelectUnit}
              />
            </>
          )}
        </>
      )}
    </PageContainer>
  );
}
