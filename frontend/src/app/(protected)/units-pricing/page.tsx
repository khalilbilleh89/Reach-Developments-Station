"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import { UnitFilters } from "@/components/units/UnitFilters";
import { UnitsTable } from "@/components/units/UnitsTable";
import {
  getProjects,
  getUnitsByProject,
  getUnitPricing,
} from "@/lib/units-api";
import type {
  Project,
  UnitFiltersState,
  UnitListItem,
  UnitPrice,
} from "@/lib/units-types";
import styles from "@/styles/units-pricing.module.css";

const DEFAULT_FILTERS: UnitFiltersState = {
  status: "",
  unit_type: "",
  min_price: "",
  max_price: "",
};

/**
 * UnitsPricingPage — project-aware units inventory and pricing listing.
 *
 * 1. Loads the project list and allows the user to switch projects.
 * 2. Fetches all units for the selected project.
 * 3. Fetches pricing data for each unit in parallel (failures are tolerated).
 * 4. Renders a filterable/sortable table of units with inline pricing data.
 *
 * All pricing values are sourced from the backend pricing engine.
 * No financial calculations are performed on the frontend.
 */
export default function UnitsPricingPage() {
  const router = useRouter();

  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState<string | null>(null);

  const [units, setUnits] = useState<UnitListItem[]>([]);
  const [pricing, setPricing] = useState<Record<string, UnitPrice>>({});
  const [unitsLoading, setUnitsLoading] = useState(false);
  const [unitsError, setUnitsError] = useState<string | null>(null);

  const [filters, setFilters] = useState<UnitFiltersState>(DEFAULT_FILTERS);

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

  // Load units whenever the selected project changes
  useEffect(() => {
    if (!selectedProjectId) return;

    setUnitsLoading(true);
    setUnitsError(null);
    setUnits([]);
    setPricing({});

    getUnitsByProject(selectedProjectId)
      .then(async (unitList) => {
        setUnits(unitList);
        // Fetch pricing for all units in parallel; tolerate individual failures
        const pricingEntries = await Promise.all(
          unitList.map(async (u) => {
            const p = await getUnitPricing(u.id);
            return p ? ([u.id, p] as [string, UnitPrice]) : null;
          }),
        );
        const pricingMap: Record<string, UnitPrice> = {};
        for (const entry of pricingEntries) {
          if (entry) pricingMap[entry[0]] = entry[1];
        }
        setPricing(pricingMap);
      })
      .catch((err: unknown) => {
        setUnitsError(
          err instanceof Error ? err.message : "Failed to load units.",
        );
      })
      .finally(() => setUnitsLoading(false));
  }, [selectedProjectId]);

  const handleProjectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedProjectId(e.target.value);
    setFilters(DEFAULT_FILTERS);
  };

  const handleFiltersChange = useCallback((f: UnitFiltersState) => {
    setFilters(f);
  }, []);

  const handleViewUnit = useCallback(
    (unitId: string) => {
      router.push(`/units-pricing/${unitId}`);
    },
    [router],
  );

  // Apply client-side price filters
  const filteredUnits = units.filter((u) => {
    if (filters.min_price !== "") {
      const min = parseFloat(filters.min_price);
      const p = pricing[u.id];
      if (!p || p.final_unit_price < min) return false;
    }
    if (filters.max_price !== "") {
      const max = parseFloat(filters.max_price);
      const p = pricing[u.id];
      if (!p || p.final_unit_price > max) return false;
    }
    return true;
  });

  return (
    <PageContainer
      title="Units & Pricing"
      subtitle="Browse unit inventory and inspect pricing at unit level."
    >
      {/* Project selector */}
      <div className={styles.selectorRow}>
        <label htmlFor="up-project-selector" className={styles.selectorLabel}>
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
            id="up-project-selector"
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
            Select a project above to view its units.
          </p>
        </div>
      ) : (
        <>
          {/* Filters */}
          <UnitFilters filters={filters} onChange={handleFiltersChange} />

          {/* Results */}
          {unitsLoading ? (
            <div className={styles.loadingState}>Loading units…</div>
          ) : unitsError ? (
            <div className={styles.errorState}>{unitsError}</div>
          ) : (
            <>
              <p className={styles.resultsCount}>
                {filteredUnits.length} unit
                {filteredUnits.length !== 1 ? "s" : ""} shown
                {filteredUnits.length !== units.length
                  ? ` (${units.length} total)`
                  : ""}
              </p>
              <UnitsTable
                units={filteredUnits}
                pricing={pricing}
                onViewUnit={handleViewUnit}
              />
            </>
          )}
        </>
      )}
    </PageContainer>
  );
}
