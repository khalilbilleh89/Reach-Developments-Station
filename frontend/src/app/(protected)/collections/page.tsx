"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { PageContainer } from "@/components/shell/PageContainer";
import { PaymentPlanFilters } from "@/components/payment-plans/PaymentPlanFilters";
import { PaymentPlansTable } from "@/components/payment-plans/PaymentPlansTable";
import {
  getProjects,
  getPaymentPlans,
  filterPaymentPlans,
} from "@/lib/payment-plans-api";
import type { Project } from "@/lib/units-types";
import type {
  PaymentPlanListItem,
  PaymentPlanFiltersState,
} from "@/lib/payment-plans-types";
import styles from "@/styles/payment-plans.module.css";

const DEFAULT_FILTERS: PaymentPlanFiltersState = {
  collectionStatus: "",
  contractStatus: "",
  minOutstanding: "",
  maxOutstanding: "",
};

/**
 * CollectionsPage — collections-focused queue page.
 *
 * Provides a simplified filtered view over the same underlying payment and
 * collection data as the payment plans queue. Shows all contracts that have
 * receivable data; use the filter controls to narrow by collection status or
 * contract status.
 *
 * For deeper collections operations, see the payment plan detail page
 * (/payment-plans/[contractId]).
 */
export default function CollectionsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState<string | null>(null);

  const [items, setItems] = useState<PaymentPlanListItem[]>([]);
  const [itemsLoading, setItemsLoading] = useState(false);
  const [itemsError, setItemsError] = useState<string | null>(null);

  const [filters, setFilters] = useState<PaymentPlanFiltersState>(DEFAULT_FILTERS);

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

  // Load payment plans whenever the selected project changes
  useEffect(() => {
    if (!selectedProjectId) return;

    let isCurrent = true;
    const project = projects.find((p) => p.id === selectedProjectId);
    const projectName = project ? project.name : "";

    setItemsLoading(true);
    setItemsError(null);
    setItems([]);

    getPaymentPlans(selectedProjectId, projectName)
      .then((list) => {
        if (!isCurrent) return;
        setItems(list);
      })
      .catch((err: unknown) => {
        if (!isCurrent) return;
        setItemsError(
          err instanceof Error ? err.message : "Failed to load collections data.",
        );
      })
      .finally(() => {
        if (isCurrent) setItemsLoading(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [selectedProjectId, projects]);

  const handleProjectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedProjectId(e.target.value);
    setFilters(DEFAULT_FILTERS);
  };

  const handleFiltersChange = useCallback((f: PaymentPlanFiltersState) => {
    setFilters(f);
  }, []);

  const filtered = filterPaymentPlans(items, filters);

  return (
    <PageContainer
      title="Collections"
      subtitle="Monitor payment receipts and receivable status across contracts."
    >
      {/* Link to full payment plans queue */}
      <p className={styles.resultsCount}>
        Detailed payment schedule view available in{" "}
        <Link href="/payment-plans" className={styles.contractLink}>
          Payment Plans
        </Link>
        .
      </p>

      {/* Project selector */}
      <div className={styles.selectorRow}>
        <label htmlFor="col-project-selector" className={styles.selectorLabel}>
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
            id="col-project-selector"
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
            Select a project above to view the collections queue.
          </p>
        </div>
      ) : (
        <>
          {/* Filters */}
          <PaymentPlanFilters filters={filters} onChange={handleFiltersChange} />

          {/* Results */}
          {itemsLoading ? (
            <div className={styles.loadingState}>Loading collections data…</div>
          ) : itemsError ? (
            <div className={styles.errorState}>{itemsError}</div>
          ) : (
            <>
              <p className={styles.resultsCount}>
                {filtered.length} contract{filtered.length !== 1 ? "s" : ""} shown
                {filtered.length !== items.length
                  ? ` (${items.length} total)`
                  : ""}
              </p>
              <PaymentPlansTable items={filtered} />
            </>
          )}
        </>
      )}
    </PageContainer>
  );
}
