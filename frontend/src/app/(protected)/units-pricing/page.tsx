"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import { UnitFilters } from "@/components/units/UnitFilters";
import { UnitsTable } from "@/components/units/UnitsTable";
import UnitPricingDetailView from "@/components/units/UnitPricingDetailView";
import { EditPricingModal } from "@/components/pricing/EditPricingModal";
import { EditAttributesModal } from "@/components/units/EditAttributesModal";
import {
  getProjects,
  getUnitsByProject,
  getProjectPricing,
  saveUnitPricingRecord,
  getProjectPricingAttributes,
  saveUnitQualitativeAttributes,
  listProjectReservations,
} from "@/lib/units-api";
import type {
  Project,
  Reservation,
  UnitFiltersState,
  UnitListItem,
  UnitPricingRecord,
  UnitPricingRecordSave,
  UnitQualitativeAttributes,
  UnitQualitativeAttributesSave,
} from "@/lib/units-types";
import styles from "@/styles/units-pricing.module.css";

const DEFAULT_FILTERS: UnitFiltersState = {
  status: "",
  unit_type: "",
  min_price: "",
  max_price: "",
};

interface UnitsPricingListProps {
  /** When navigating from a setup-state CTA, auto-open this action for the target unit. */
  initialAction: string;
  /** Unit ID to auto-open a modal for. */
  initialTargetId: string;
}

/**
 * UnitsPricingList — project-aware units inventory and pricing listing.
 *
 * Rendered by UnitsPricingPage when no ?unitId= query param is present.
 *
 * When `initialAction` + `initialTargetId` are present (e.g., from a setup-state
 * CTA on the pricing detail view), the appropriate modal is automatically opened
 * once the unit list and pricing data finish loading.
 */
function UnitsPricingList({ initialAction, initialTargetId }: UnitsPricingListProps) {
  const router = useRouter();

  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState<string | null>(null);

  const [units, setUnits] = useState<UnitListItem[]>([]);
  const [pricingRecords, setPricingRecords] = useState<Partial<Record<string, UnitPricingRecord>>>({});
  const [attributesRecords, setAttributesRecords] = useState<Partial<Record<string, UnitQualitativeAttributes>>>({});
  const [reservations, setReservations] = useState<Partial<Record<string, Reservation>>>({});
  const [unitsLoading, setUnitsLoading] = useState(false);
  const [unitsError, setUnitsError] = useState<string | null>(null);

  const [filters, setFilters] = useState<UnitFiltersState>(DEFAULT_FILTERS);

  // Edit pricing modal state
  const [editingUnit, setEditingUnit] = useState<UnitListItem | null>(null);
  const [editingRecord, setEditingRecord] = useState<UnitPricingRecord | null>(null);

  // Edit attributes modal state
  const [editingAttrsUnit, setEditingAttrsUnit] = useState<UnitListItem | null>(null);
  const [editingAttrsRecord, setEditingAttrsRecord] = useState<UnitQualitativeAttributes | null>(null);

  // Guard: only auto-open once per mount so the modal doesn't reopen after close
  const hasAutoOpened = useRef(false);

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
    setPricingRecords({});
    setAttributesRecords({});
    setReservations({});

    getUnitsByProject(selectedProjectId)
      .then(async (unitList) => {
        if (!isCurrent) return;
        setUnits(unitList);

        // Fetch pricing records, qualitative attributes, and reservations in parallel
        // (3 requests total regardless of unit count)
        const [recordMap, attrsMap, reservationsData] = await Promise.all([
          getProjectPricing(selectedProjectId),
          getProjectPricingAttributes(selectedProjectId),
          listProjectReservations(selectedProjectId),
        ]);

        if (!isCurrent) return;

        setPricingRecords(recordMap);
        setAttributesRecords(attrsMap);

        // Build a per-unit reservation map with deterministic selection:
        //   1. Prefer an active reservation over any non-active one.
        //   2. Among reservations with the same activeness, keep the most recent
        //      (compare updated_at, fall back to created_at).
        //   3. When timestamps are absent on both sides, keep the existing entry
        //      so the result stays stable regardless of API ordering.
        const isActive = (r: Reservation) => r.status === "active";
        const tsOf = (r: Reservation): number => {
          const s = r.updated_at ?? r.created_at;
          return s ? new Date(s).getTime() : -1;
        };
        const preferredReservation = (a: Reservation, b: Reservation): Reservation => {
          const aActive = isActive(a);
          const bActive = isActive(b);
          // Different activeness — active wins.
          if (aActive !== bActive) return aActive ? a : b;
          // Same activeness — prefer the more recent one.
          const tsDiff = tsOf(b) - tsOf(a);
          if (tsDiff !== 0) return tsDiff > 0 ? b : a;
          // Timestamps identical or both absent — keep existing (a).
          return a;
        };
        const reservationMap: Record<string, Reservation> = {};
        for (const reservation of reservationsData.items) {
          const existing = reservationMap[reservation.unit_id];
          reservationMap[reservation.unit_id] = existing
            ? preferredReservation(existing, reservation)
            : reservation;
        }
        setReservations(reservationMap);
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

  // Auto-open the appropriate modal once data is ready (from setup-state CTAs)
  useEffect(() => {
    if (
      hasAutoOpened.current ||
      !initialAction ||
      !initialTargetId ||
      unitsLoading ||
      units.length === 0
    ) return;

    const targetUnit = units.find((u) => u.id === initialTargetId);
    if (!targetUnit) return;

    hasAutoOpened.current = true;

    if (initialAction === "editAttributes") {
      setEditingAttrsUnit(targetUnit);
      setEditingAttrsRecord(attributesRecords[targetUnit.id] ?? null);
    } else if (initialAction === "editPricing") {
      setEditingUnit(targetUnit);
      setEditingRecord(pricingRecords[targetUnit.id] ?? null);
    }
  }, [initialAction, initialTargetId, units, unitsLoading, pricingRecords, attributesRecords]);

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

  const handleEditAttributes = useCallback(
    (unit: UnitListItem) => {
      setEditingAttrsUnit(unit);
      setEditingAttrsRecord(attributesRecords[unit.id] ?? null);
    },
    [attributesRecords],
  );

  const handleSaveAttributes = useCallback(
    async (unitId: string, data: UnitQualitativeAttributesSave) => {
      const saved = await saveUnitQualitativeAttributes(unitId, data);
      setAttributesRecords((prev) => ({ ...prev, [unitId]: saved }));
    },
    [],
  );

  const handleCloseAttrsModal = useCallback(() => {
    setEditingAttrsUnit(null);
    setEditingAttrsRecord(null);
  }, []);

  // Apply all client-side filters: status, unit_type, and price range
  const filteredUnits = units.filter((u) => {
    if (filters.status !== "" && u.status !== filters.status) return false;
    if (filters.unit_type !== "" && u.unit_type !== filters.unit_type) return false;
    if (filters.min_price !== "") {
      const min = parseFloat(filters.min_price);
      const r = pricingRecords[u.id];
      const finalPrice = r ? r.final_price : null;
      if (finalPrice === null || finalPrice < min) return false;
    }
    if (filters.max_price !== "") {
      const max = parseFloat(filters.max_price);
      const r = pricingRecords[u.id];
      const finalPrice = r ? r.final_price : null;
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
                pricingRecords={pricingRecords}
                attributesRecords={attributesRecords}
                reservations={reservations}
                onViewUnit={handleViewUnit}
                onEditPricing={handleEditPricing}
                onEditAttributes={handleEditAttributes}
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

      {/* Edit Attributes Modal */}
      {editingAttrsUnit && (
        <EditAttributesModal
          unitId={editingAttrsUnit.id}
          unitNumber={editingAttrsUnit.unit_number}
          existing={editingAttrsRecord}
          onSave={handleSaveAttributes}
          onClose={handleCloseAttrsModal}
        />
      )}
    </PageContainer>
  );
}

/**
 * UnitsPricingPage — renders the unit detail view when ?unitId= is present,
 * otherwise renders the filterable units list.
 *
 * Reads optional `action` and `target` query params forwarded from the
 * pricing detail view's setup-state CTAs, and passes them to UnitsPricingList
 * so the appropriate modal is auto-opened once data finishes loading.
 */
export default function UnitsPricingPage() {
  const searchParams = useSearchParams();
  const unitId = searchParams.get("unitId");
  const action = searchParams.get("action") ?? "";
  const target = searchParams.get("target") ?? "";

  if (unitId) {
    return <UnitPricingDetailView />;
  }
  return <UnitsPricingList initialAction={action} initialTargetId={target} />;
}
