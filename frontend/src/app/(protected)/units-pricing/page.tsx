"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import { UnitFilters } from "@/components/units/UnitFilters";
import { UnitsTable } from "@/components/units/UnitsTable";
import UnitPricingDetailView from "@/components/units/UnitPricingDetailView";
import { EditPricingModal } from "@/components/pricing/EditPricingModal";
import {
  getProjects,
  getUnitsByProject,
  getUnitPricing,
  getUnitPricingRecord,
  saveUnitPricingRecord,
} from "@/lib/units-api";
import type {
  Project,
  UnitFiltersState,
  UnitListItem,
  UnitPrice,
  UnitPricingRecord,
  UnitPricingRecordSave,
} from "@/lib/units-types";
import styles from "@/styles/units-pricing.module.css";

const DEFAULT_FILTERS: UnitFiltersState = {
  status: "",
  unit_type: "",
  min_price: "",
  max_price: "",
};

/**
 * UnitsPricingList — project-aware units inventory and pricing listing.
 *
 * Rendered by UnitsPricingPage when no ?unitId= query param is present.
 */
function UnitsPricingList() {
  const router = useRouter();

  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState<string | null>(null);

  const [units, setUnits] = useState<UnitListItem[]>([]);
  const [pricing, setPricing] = useState<Record<string, UnitPrice | undefined>>({});
  const [pricingRecords, setPricingRecords] = useState<Partial<Record<string, UnitPricingRecord>>>({});
  const [unitsLoading, setUnitsLoading] = useState(false);
  const [unitsError, setUnitsError] = useState<string | null>(null);

  const [filters, setFilters] = useState<UnitFiltersState>(DEFAULT_FILTERS);

  // Edit pricing modal state
  const [editingUnit, setEditingUnit] = useState<UnitListItem | null>(null);
  const [editingRecord, setEditingRecord] = useState<UnitPricingRecord | null>(null);

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

  // Load units whenever the selected project changes, with stale response guard
  useEffect(() => {
    if (!selectedProjectId) return;

    let isCurrent = true;

    setUnitsLoading(true);
    setUnitsError(null);
    setUnits([]);
    setPricing({});
    setPricingRecords({});

    getUnitsByProject(selectedProjectId)
      .then(async (unitList) => {
        if (!isCurrent) return;
        setUnits(unitList);

        // Fetch both engine pricing and formal pricing records in parallel
        const [pricingEntries, recordEntries] = await Promise.all([
          Promise.all(
            unitList.map(async (u) => {
              const p = await getUnitPricing(u.id);
              return p ? ([u.id, p] as [string, UnitPrice]) : null;
            }),
          ),
          Promise.all(
            unitList.map(async (u) => {
              const r = await getUnitPricingRecord(u.id);
              return r ? ([u.id, r] as [string, UnitPricingRecord]) : null;
            }),
          ),
        ]);

        if (!isCurrent) return;

        const pricingMap: Record<string, UnitPrice> = {};
        for (const entry of pricingEntries) {
          if (entry) pricingMap[entry[0]] = entry[1];
        }
        setPricing(pricingMap);

        const recordMap: Record<string, UnitPricingRecord> = {};
        for (const entry of recordEntries) {
          if (entry) recordMap[entry[0]] = entry[1];
        }
        setPricingRecords(recordMap);
      })
      .catch((err: unknown) => {
        if (!isCurrent) return;
        setUnitsError(
          err instanceof Error ? err.message : "Failed to load units.",
        );
      })
      .finally(() => {
        if (isCurrent) setUnitsLoading(false);
      });

    return () => {
      isCurrent = false;
    };
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
      router.push(`/units-pricing?unitId=${unitId}`);
    },
    [router],
  );

  const handleEditPricing = useCallback(
    (unit: UnitListItem) => {
      setEditingUnit(unit);
      setEditingRecord(pricingRecords[unit.id] ?? null);
    },
    [pricingRecords],
  );

  const handleSavePricing = useCallback(
    async (unitId: string, data: UnitPricingRecordSave) => {
      const saved = await saveUnitPricingRecord(unitId, data);
      setPricingRecords((prev) => ({ ...prev, [unitId]: saved }));
    },
    [],
  );

  const handleCloseModal = useCallback(() => {
    setEditingUnit(null);
    setEditingRecord(null);
  }, []);

  // Apply all client-side filters: status, unit_type, and price range
  const filteredUnits = units.filter((u) => {
    if (filters.status !== "" && u.status !== filters.status) return false;
    if (filters.unit_type !== "" && u.unit_type !== filters.unit_type) return false;
    if (filters.min_price !== "") {
      const min = parseFloat(filters.min_price);
      const r = pricingRecords[u.id];
      const p = pricing[u.id];
      const finalPrice = r ? r.final_price : p ? p.final_unit_price : null;
      if (finalPrice === null || finalPrice < min) return false;
    }
    if (filters.max_price !== "") {
      const max = parseFloat(filters.max_price);
      const r = pricingRecords[u.id];
      const p = pricing[u.id];
      const finalPrice = r ? r.final_price : p ? p.final_unit_price : null;
      if (finalPrice === null || finalPrice > max) return false;
    }
    return true;
  });

  return (
    <PageContainer
      title="Units & Pricing"
      subtitle="Browse unit inventory and manage per-unit pricing records."
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
                pricingRecords={pricingRecords}
                onViewUnit={handleViewUnit}
                onEditPricing={handleEditPricing}
              />
            </>
          )}
        </>
      )}

      {/* Edit Pricing Modal */}
      {editingUnit && (
        <EditPricingModal
          unitId={editingUnit.id}
          unitNumber={editingUnit.unit_number}
          existing={editingRecord}
          onSave={handleSavePricing}
          onClose={handleCloseModal}
        />
      )}
    </PageContainer>
  );
}

/**
 * UnitsPricingPage — renders the unit detail view when ?unitId= is present,
 * otherwise renders the filterable units list.
 */
export default function UnitsPricingPage() {
  const searchParams = useSearchParams();
  const unitId = searchParams.get("unitId");

  if (unitId) {
    return <UnitPricingDetailView />;
  }
  return <UnitsPricingList />;
}
