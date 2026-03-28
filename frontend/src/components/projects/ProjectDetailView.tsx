"use client";

import React, { useEffect, useState } from "react";
import type { Phase } from "@/lib/phases-types";
import type { Project } from "@/lib/projects-types";
import type { Building } from "@/lib/buildings-types";
import type { Floor } from "@/lib/floors-types";
import type { UnitListItem, UnitCreateForFloor, UnitUpdate } from "@/lib/units-types";
import type { Reservation, ReservationCreate } from "@/lib/units-types";
import { listPhases, createPhase, updatePhase, deletePhase } from "@/lib/phases-api";
import { listBuildings, createBuilding, updateBuilding, deleteBuilding } from "@/lib/buildings-api";
import { listFloors, createFloor, updateFloor, deleteFloor } from "@/lib/floors-api";
import { listUnitsByFloor, createUnit, updateUnit, deleteUnit } from "@/lib/units-api";
import { createReservation, listProjectReservations } from "@/lib/units-api";
import { ProjectPhasesTable } from "@/components/projects/ProjectPhasesTable";
import { ProjectOverview } from "@/components/projects/ProjectOverview";
import { ProjectLifecycleSummaryPanel } from "@/components/projects/ProjectLifecycleSummaryPanel";
import { ProjectAttributeConfig } from "@/components/projects/ProjectAttributeConfig";
import { ProjectAbsorptionPanel } from "@/components/feasibility/ProjectAbsorptionPanel";
import { ProjectPricingRecommendationsPanel } from "@/components/feasibility/ProjectPricingRecommendationsPanel";
import { BuildingsTable } from "@/components/buildings/BuildingsTable";
import { FloorsTable } from "@/components/floors/FloorsTable";
import { UnitsInventoryTable } from "@/components/units/UnitsInventoryTable";
import { CreatePhaseModal } from "@/app/(protected)/projects/[id]/create-phase-modal";
import { CreateBuildingModal } from "@/components/buildings/create-building-modal";
import { CreateFloorModal } from "@/components/floors/CreateFloorModal";
import { CreateUnitModal } from "@/components/units/CreateUnitModal";
import { ReserveUnitModal } from "@/components/units/ReserveUnitModal";
import type { PhaseCreate, PhaseUpdate } from "@/lib/phases-types";
import type { BuildingCreate, BuildingUpdate } from "@/lib/buildings-types";
import type { FloorCreate, FloorUpdate } from "@/lib/floors-types";
import styles from "@/styles/projects.module.css";

interface ProjectDetailViewProps {
  project: Project;
  onBack: () => void;
}

type Tab = "overview" | "phases" | "buildings" | "floors" | "units" | "attributes";

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "\u2014";
  return new Date(dateStr).toLocaleDateString("en-GB", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function statusLabel(status: string): string {
  switch (status) {
    case "on_hold":
      return "On Hold";
    default:
      return status.charAt(0).toUpperCase() + status.slice(1);
  }
}

/**
 * ProjectDetailView — shows a project summary card, its phases, buildings, floors, and units.
 *
 * Rendered by the projects page when a project is selected.
 */
export function ProjectDetailView({ project, onBack }: ProjectDetailViewProps) {
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  // Phases state
  const [phases, setPhases] = useState<Phase[]>([]);
  const [phasesLoading, setPhasesLoading] = useState(true);
  const [phasesError, setPhasesError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editPhase, setEditPhase] = useState<Phase | null>(null);
  const [deleteConfirmPhase, setDeleteConfirmPhase] = useState<Phase | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Buildings state
  const [selectedPhaseId, setSelectedPhaseId] = useState<string | null>(null);
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [buildingsLoading, setBuildingsLoading] = useState(false);
  const [buildingsError, setBuildingsError] = useState<string | null>(null);
  const [buildingModalOpen, setBuildingModalOpen] = useState(false);
  const [editBuilding, setEditBuilding] = useState<Building | null>(null);
  const [deleteConfirmBuilding, setDeleteConfirmBuilding] = useState<Building | null>(null);
  const [deleteBuildingError, setDeleteBuildingError] = useState<string | null>(null);

  // Floors state
  const [selectedBuildingId, setSelectedBuildingId] = useState<string | null>(null);
  const [allBuildings, setAllBuildings] = useState<Building[]>([]);
  const [floors, setFloors] = useState<Floor[]>([]);
  const [floorsLoading, setFloorsLoading] = useState(false);
  const [floorsError, setFloorsError] = useState<string | null>(null);
  const [floorModalOpen, setFloorModalOpen] = useState(false);
  const [editFloor, setEditFloor] = useState<Floor | null>(null);
  const [deleteConfirmFloor, setDeleteConfirmFloor] = useState<Floor | null>(null);
  const [deleteFloorError, setDeleteFloorError] = useState<string | null>(null);

  // Units state
  const [selectedFloorId, setSelectedFloorId] = useState<string | null>(null);
  const [allFloors, setAllFloors] = useState<Floor[]>([]);
  const [allFloorsLoading, setAllFloorsLoading] = useState(false);
  const [allFloorsError, setAllFloorsError] = useState<string | null>(null);
  const [units, setUnits] = useState<UnitListItem[]>([]);
  const [unitsLoading, setUnitsLoading] = useState(false);
  const [unitsError, setUnitsError] = useState<string | null>(null);
  const [unitModalOpen, setUnitModalOpen] = useState(false);
  const [editUnit, setEditUnit] = useState<UnitListItem | null>(null);
  const [deleteConfirmUnit, setDeleteConfirmUnit] = useState<UnitListItem | null>(null);
  const [deleteUnitError, setDeleteUnitError] = useState<string | null>(null);

  // Reservation state
  const [reserveUnit, setReserveUnit] = useState<UnitListItem | null>(null);
  const [activeReservations, setActiveReservations] = useState<Map<string, Reservation>>(new Map());
  const [reservationError, setReservationError] = useState<string | null>(null);

  const fetchPhases = () => {
    setPhasesLoading(true);
    setPhasesError(null);
    listPhases(project.id)
      .then((resp) => setPhases(resp.items))
      .catch((err: unknown) => {
        setPhasesError(err instanceof Error ? err.message : "Failed to load phases.");
      })
      .finally(() => setPhasesLoading(false));
  };

  const fetchBuildings = (phaseId: string) => {
    setBuildingsLoading(true);
    setBuildingsError(null);
    listBuildings(phaseId)
      .then((resp) => setBuildings(resp.items))
      .catch((err: unknown) => {
        setBuildingsError(err instanceof Error ? err.message : "Failed to load buildings.");
      })
      .finally(() => setBuildingsLoading(false));
  };

  const fetchAllBuildingsForProject = () => {
    Promise.all(phases.map((p) => listBuildings(p.id)))
      .then((results) => {
        setAllBuildings(results.flatMap((r) => r.items));
      })
      .catch(() => {
        setAllBuildings([]);
      });
  };

  const fetchFloors = (buildingId: string) => {
    setFloorsLoading(true);
    setFloorsError(null);
    listFloors(buildingId)
      .then((resp) => setFloors(resp.items))
      .catch((err: unknown) => {
        setFloorsError(err instanceof Error ? err.message : "Failed to load floors.");
      })
      .finally(() => setFloorsLoading(false));
  };

  const fetchAllFloorsForProject = () => {
    setAllFloorsLoading(true);
    setAllFloorsError(null);
    Promise.all(allBuildings.map((b) => listFloors(b.id)))
      .then((results) => {
        setAllFloors(results.flatMap((r) => r.items));
      })
      .catch(() => {
        setAllFloorsError("Failed to load floors. Please try again.");
        setAllFloors([]);
      })
      .finally(() => setAllFloorsLoading(false));
  };

  const fetchUnits = (floorId: string) => {
    setUnitsLoading(true);
    setUnitsError(null);
    listUnitsByFloor(floorId)
      .then((resp) => setUnits(resp.items))
      .catch((err: unknown) => {
        setUnitsError(err instanceof Error ? err.message : "Failed to load units.");
      })
      .finally(() => setUnitsLoading(false));
  };

  const fetchActiveReservations = (projectId: string) => {
    listProjectReservations(projectId)
      .then((resp) => {
        const map = new Map<string, Reservation>();
        for (const r of resp.items) {
          if (r.status === "active") {
            map.set(r.unit_id, r);
          }
        }
        setActiveReservations(map);
        setReservationError(null);
      })
      .catch((err: unknown) => {
        setReservationError(
          err instanceof Error ? err.message : "Failed to load reservation data."
        );
      });
  };

  useEffect(() => {
    fetchPhases();
    // Reset all dependent state when project changes
    setSelectedPhaseId(null);
    setBuildings([]);
    setBuildingsError(null);
    setBuildingModalOpen(false);
    setEditBuilding(null);
    setDeleteConfirmBuilding(null);
    setDeleteBuildingError(null);
    setSelectedBuildingId(null);
    setAllBuildings([]);
    setFloors([]);
    setFloorsLoading(false);
    setFloorsError(null);
    setFloorModalOpen(false);
    setEditFloor(null);
    setDeleteConfirmFloor(null);
    setDeleteFloorError(null);
    setSelectedFloorId(null);
    setAllFloors([]);
    setAllFloorsLoading(false);
    setAllFloorsError(null);
    setUnits([]);
    setUnitsLoading(false);
    setUnitsError(null);
    setUnitModalOpen(false);
    setEditUnit(null);
    setDeleteConfirmUnit(null);
    setDeleteUnitError(null);
    setReserveUnit(null);
    setActiveReservations(new Map());
    setReservationError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  useEffect(() => {
    if (activeTab === "buildings" && selectedPhaseId) {
      fetchBuildings(selectedPhaseId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, selectedPhaseId]);

  useEffect(() => {
    if ((activeTab === "floors" || activeTab === "units") && phases.length > 0) {
      fetchAllBuildingsForProject();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, phases]);

  useEffect(() => {
    if (activeTab === "floors" && selectedBuildingId) {
      fetchFloors(selectedBuildingId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, selectedBuildingId]);

  useEffect(() => {
    if (activeTab === "units" && allBuildings.length > 0) {
      fetchAllFloorsForProject();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, allBuildings]);

  useEffect(() => {
    if (activeTab === "units" && selectedFloorId) {
      fetchUnits(selectedFloorId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, selectedFloorId]);

  useEffect(() => {
    if (activeTab === "units") {
      fetchActiveReservations(project.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, project.id]);

  const handleCreatePhase = async (data: PhaseCreate | PhaseUpdate) => {
    await createPhase(project.id, data as PhaseCreate);
    setModalOpen(false);
    fetchPhases();
  };

  const handleUpdatePhase = async (data: PhaseCreate | PhaseUpdate) => {
    if (!editPhase) return;
    await updatePhase(editPhase.id, data as PhaseUpdate);
    setModalOpen(false);
    setEditPhase(null);
    fetchPhases();
  };

  const handleDeletePhase = async (phase: Phase) => {
    setDeleteError(null);
    try {
      await deletePhase(phase.id);
      setDeleteConfirmPhase(null);
      fetchPhases();
    } catch (err: unknown) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete phase.");
    }
  };

  const handleCreateBuilding = async (data: BuildingCreate | BuildingUpdate) => {
    if (!selectedPhaseId) return;
    await createBuilding(selectedPhaseId, data as BuildingCreate);
    setBuildingModalOpen(false);
    fetchBuildings(selectedPhaseId);
  };

  const handleUpdateBuilding = async (data: BuildingCreate | BuildingUpdate) => {
    if (!editBuilding) return;
    await updateBuilding(editBuilding.id, data as BuildingUpdate);
    setBuildingModalOpen(false);
    setEditBuilding(null);
    if (selectedPhaseId) fetchBuildings(selectedPhaseId);
  };

  const handleDeleteBuilding = async (building: Building) => {
    setDeleteBuildingError(null);
    try {
      await deleteBuilding(building.id);
      setDeleteConfirmBuilding(null);
      if (selectedPhaseId) fetchBuildings(selectedPhaseId);
    } catch (err: unknown) {
      setDeleteBuildingError(err instanceof Error ? err.message : "Failed to delete building.");
    }
  };

  const handleCreateFloor = async (data: FloorCreate | FloorUpdate) => {
    if (!selectedBuildingId) return;
    await createFloor(selectedBuildingId, data as FloorCreate);
    setFloorModalOpen(false);
    fetchFloors(selectedBuildingId);
  };

  const handleUpdateFloor = async (data: FloorCreate | FloorUpdate) => {
    if (!editFloor) return;
    await updateFloor(editFloor.id, data as FloorUpdate);
    setFloorModalOpen(false);
    setEditFloor(null);
    if (selectedBuildingId) fetchFloors(selectedBuildingId);
  };

  const handleDeleteFloor = async (floor: Floor) => {
    setDeleteFloorError(null);
    try {
      await deleteFloor(floor.id);
      setDeleteConfirmFloor(null);
      if (selectedBuildingId) fetchFloors(selectedBuildingId);
    } catch (err: unknown) {
      setDeleteFloorError(err instanceof Error ? err.message : "Failed to delete floor.");
    }
  };

  const handleCreateUnit = async (data: UnitCreateForFloor | UnitUpdate) => {
    if (!selectedFloorId) return;
    await createUnit(selectedFloorId, data as UnitCreateForFloor);
    setUnitModalOpen(false);
    fetchUnits(selectedFloorId);
  };

  const handleUpdateUnit = async (data: UnitCreateForFloor | UnitUpdate) => {
    if (!editUnit) return;
    await updateUnit(editUnit.id, data as UnitUpdate);
    setUnitModalOpen(false);
    setEditUnit(null);
    if (selectedFloorId) fetchUnits(selectedFloorId);
  };

  const handleDeleteUnit = async (unit: UnitListItem) => {
    setDeleteUnitError(null);
    try {
      await deleteUnit(unit.id);
      setDeleteConfirmUnit(null);
      if (selectedFloorId) fetchUnits(selectedFloorId);
    } catch (err: unknown) {
      setDeleteUnitError(err instanceof Error ? err.message : "Failed to delete unit.");
    }
  };

  const handleCreateReservation = async (data: ReservationCreate) => {
    setReservationError(null);
    await createReservation(data);
    setReserveUnit(null);
    fetchActiveReservations(project.id);
  };

  return (
    <div>
      {/* Back navigation */}
      <button type="button" className={styles.backButton} onClick={onBack}>
        ← Back to Projects
      </button>

      {/* Project summary card */}
      <div className={styles.detailCard}>
        <div className={styles.detailGrid}>
          <div className={styles.detailField}>
            <span className={styles.detailLabel}>Project</span>
            <span className={styles.detailValue}>
              {project.name}{" "}
              <span style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-xs)" }}>
                ({project.code})
              </span>
            </span>
          </div>
          <div className={styles.detailField}>
            <span className={styles.detailLabel}>Developer</span>
            <span className={styles.detailValue}>
              {project.developer_name ?? "\u2014"}
            </span>
          </div>
          <div className={styles.detailField}>
            <span className={styles.detailLabel}>Location</span>
            <span className={styles.detailValue}>
              {project.location ?? "\u2014"}
            </span>
          </div>
          <div className={styles.detailField}>
            <span className={styles.detailLabel}>Status</span>
            <span className={styles.detailValue}>{statusLabel(project.status)}</span>
          </div>
          <div className={styles.detailField}>
            <span className={styles.detailLabel}>Start Date</span>
            <span className={styles.detailValue}>{formatDate(project.start_date)}</span>
          </div>
          <div className={styles.detailField}>
            <span className={styles.detailLabel}>Target Completion</span>
            <span className={styles.detailValue}>{formatDate(project.target_end_date)}</span>
          </div>
        </div>
      </div>

      {/* Tab navigation */}
      <div className={styles.tabBar}>
        <button
          type="button"
          className={`${styles.tabButton} ${activeTab === "overview" ? styles.tabButtonActive : ""}`}
          onClick={() => setActiveTab("overview")}
        >
          Overview
        </button>
        <button
          type="button"
          className={`${styles.tabButton} ${activeTab === "phases" ? styles.tabButtonActive : ""}`}
          onClick={() => setActiveTab("phases")}
        >
          Phases
        </button>
        <button
          type="button"
          className={`${styles.tabButton} ${activeTab === "buildings" ? styles.tabButtonActive : ""}`}
          onClick={() => setActiveTab("buildings")}
        >
          Buildings
        </button>
        <button
          type="button"
          className={`${styles.tabButton} ${activeTab === "floors" ? styles.tabButtonActive : ""}`}
          onClick={() => setActiveTab("floors")}
        >
          Floors
        </button>
        <button
          type="button"
          className={`${styles.tabButton} ${activeTab === "units" ? styles.tabButtonActive : ""}`}
          onClick={() => setActiveTab("units")}
        >
          Units
        </button>
        <button
          type="button"
          className={`${styles.tabButton} ${activeTab === "attributes" ? styles.tabButtonActive : ""}`}
          onClick={() => setActiveTab("attributes")}
        >
          Attributes
        </button>
      </div>

      {/* Overview tab */}
      {activeTab === "overview" && (
        <>
          <ProjectLifecycleSummaryPanel projectId={project.id} />
          <ProjectAbsorptionPanel projectId={project.id} />
          <ProjectPricingRecommendationsPanel projectId={project.id} />
          <ProjectOverview project={project} />
        </>
      )}

      {/* Phases tab */}
      {activeTab === "phases" && (
        <div>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>Phases</h2>
            <button
              type="button"
              className={styles.addButton}
              onClick={() => {
                setEditPhase(null);
                setModalOpen(true);
              }}
            >
              + Add Phase
            </button>
          </div>

          {phasesError && (
            <div className={styles.errorBanner} role="alert">
              {phasesError}
            </div>
          )}
          {deleteError && (
            <div className={styles.errorBanner} role="alert">
              {deleteError}
            </div>
          )}

          {phasesLoading ? (
            <div className={styles.loadingText}>Loading phases\u2026</div>
          ) : (
            <ProjectPhasesTable
              phases={phases}
              onEdit={(phase) => {
                setEditPhase(phase);
                setModalOpen(true);
              }}
              onDelete={(phase) => setDeleteConfirmPhase(phase)}
            />
          )}
        </div>
      )}

      {/* Buildings tab */}
      {activeTab === "buildings" && (
        <div>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>Buildings</h2>
          </div>

          {/* Phase selector */}
          <div className={styles.buildingForm}>
            <label htmlFor="building-phase-select" className={styles.formLabel}>
              Phase
            </label>
            <select
              id="building-phase-select"
              className={styles.formSelect}
              value={selectedPhaseId ?? ""}
              onChange={(e) => {
                setSelectedPhaseId(e.target.value || null);
                setBuildings([]);
              }}
            >
              <option value="">— Select a phase —</option>
              {phases.map((phase) => (
                <option key={phase.id} value={phase.id}>
                  {phase.name}
                </option>
              ))}
            </select>
          </div>

          {selectedPhaseId && (
            <>
              <div className={styles.sectionHeader}>
                <span />
                <button
                  type="button"
                  className={styles.addButton}
                  onClick={() => {
                    setEditBuilding(null);
                    setBuildingModalOpen(true);
                  }}
                >
                  + Add Building
                </button>
              </div>

              {buildingsError && (
                <div className={styles.errorBanner} role="alert">
                  {buildingsError}
                </div>
              )}
              {deleteBuildingError && (
                <div className={styles.errorBanner} role="alert">
                  {deleteBuildingError}
                </div>
              )}

              {buildingsLoading ? (
                <div className={styles.loadingText}>Loading buildings\u2026</div>
              ) : (
                <BuildingsTable
                  buildings={buildings}
                  onEdit={(building) => {
                    setEditBuilding(building);
                    setBuildingModalOpen(true);
                  }}
                  onDelete={(building) => setDeleteConfirmBuilding(building)}
                />
              )}
            </>
          )}

          {!selectedPhaseId && phases.length === 0 && !phasesLoading && (
            <div className={styles.emptyState}>
              <div className={styles.emptyIcon}>🏗️</div>
              <div className={styles.emptyText}>No phases yet</div>
              <div className={styles.emptySubtext}>
                Create a phase first to start adding buildings.
              </div>
            </div>
          )}

          {!selectedPhaseId && phases.length > 0 && (
            <div className={styles.emptyState}>
              <div className={styles.emptyText}>Select a phase to view buildings</div>
            </div>
          )}
        </div>
      )}

      {/* Floors tab */}
      {activeTab === "floors" && (
        <div>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>Floors</h2>
            <button
              type="button"
              className={styles.addButton}
              disabled={!selectedBuildingId}
              aria-disabled={!selectedBuildingId}
              aria-label={!selectedBuildingId ? "Select a building before adding a floor" : "Add floor"}
              title={!selectedBuildingId ? "Select a building first" : undefined}
              onClick={() => {
                setEditFloor(null);
                setFloorModalOpen(true);
              }}
            >
              + Add Floor
            </button>
          </div>

          {/* Building selector */}
          <div className={styles.floorSelectorRow}>
            <label htmlFor="floor-building-select" className={styles.formLabel}>
              Building
            </label>
            <select
              id="floor-building-select"
              className={styles.formSelect}
              value={selectedBuildingId ?? ""}
              onChange={(e) => {
                setSelectedBuildingId(e.target.value || null);
                setFloors([]);
                setFloorsError(null);
              }}
            >
              <option value="">— Select a building —</option>
              {allBuildings.map((building) => (
                <option key={building.id} value={building.id}>
                  {building.name} ({building.code})
                </option>
              ))}
            </select>
          </div>

          {floorsError && (
            <div className={styles.errorBanner} role="alert">
              {floorsError}
            </div>
          )}
          {deleteFloorError && (
            <div className={styles.errorBanner} role="alert">
              {deleteFloorError}
            </div>
          )}

          {!selectedBuildingId && allBuildings.length === 0 && (
            <div className={styles.emptyState}>
              <div className={styles.emptyIcon}>🏢</div>
              <div className={styles.emptyText}>No buildings found</div>
              <div className={styles.emptySubtext}>
                Add buildings to your phases before creating floors.
              </div>
            </div>
          )}

          {!selectedBuildingId && allBuildings.length > 0 && (
            <div className={styles.emptyState}>
              <div className={styles.emptyText}>Select a building to view floors</div>
            </div>
          )}

          {selectedBuildingId && (
            floorsLoading ? (
              <div className={styles.loadingText}>Loading floors\u2026</div>
            ) : (
              <FloorsTable
                floors={floors}
                onEdit={(floor) => {
                  setEditFloor(floor);
                  setFloorModalOpen(true);
                }}
                onDelete={(floor) => setDeleteConfirmFloor(floor)}
              />
            )
          )}
        </div>
      )}

      {/* Units tab */}
      {activeTab === "units" && (
        <div>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>Units</h2>
            <button
              type="button"
              className={styles.addButton}
              disabled={!selectedFloorId}
              aria-disabled={!selectedFloorId}
              aria-label={!selectedFloorId ? "Select a floor before adding a unit" : "Add unit"}
              title={!selectedFloorId ? "Select a floor first" : undefined}
              onClick={() => {
                setEditUnit(null);
                setUnitModalOpen(true);
              }}
            >
              + Add Unit
            </button>
          </div>

          {/* Floor selector */}
          <div className={styles.floorSelectorRow}>
            <label htmlFor="unit-floor-select" className={styles.formLabel}>
              Floor
            </label>
            {allFloorsLoading ? (
              <div className={styles.loadingText}>Loading floors…</div>
            ) : (
              <select
                id="unit-floor-select"
                className={styles.formSelect}
                value={selectedFloorId ?? ""}
                onChange={(e) => {
                  setSelectedFloorId(e.target.value || null);
                  setUnits([]);
                  setUnitsError(null);
                }}
              >
                <option value="">— Select a floor —</option>
                {allFloors.map((floor) => (
                  <option key={floor.id} value={floor.id}>
                    {floor.name} ({floor.code})
                  </option>
                ))}
              </select>
            )}
          </div>

          {allFloorsError && (
            <div className={styles.errorBanner} role="alert">
              {allFloorsError}
            </div>
          )}

          {unitsError && (
            <div className={styles.errorBanner} role="alert">
              {unitsError}
            </div>
          )}
          {deleteUnitError && (
            <div className={styles.errorBanner} role="alert">
              {deleteUnitError}
            </div>
          )}
          {reservationError && (
            <div className={styles.errorBanner} role="alert">
              {reservationError}
            </div>
          )}

          {!allFloorsLoading && !allFloorsError && !selectedFloorId && allFloors.length === 0 && (
            <div className={styles.emptyState}>
              <div className={styles.emptyIcon}>🏠</div>
              <div className={styles.emptyText}>No floors found</div>
              <div className={styles.emptySubtext}>
                Add floors to your buildings before creating units.
              </div>
            </div>
          )}

          {!allFloorsLoading && !allFloorsError && !selectedFloorId && allFloors.length > 0 && (
            <div className={styles.emptyState}>
              <div className={styles.emptyText}>Select a floor to view units</div>
            </div>
          )}

          {selectedFloorId && (
            unitsLoading ? (
              <div className={styles.loadingText}>Loading units\u2026</div>
            ) : (
              <UnitsInventoryTable
                units={units}
                activeReservations={activeReservations}
                onEdit={(unit) => {
                  setEditUnit(unit);
                  setUnitModalOpen(true);
                }}
                onDelete={(unit) => setDeleteConfirmUnit(unit)}
                onReserve={(unit) => setReserveUnit(unit)}
              />
            )
          )}
        </div>
      )}

      {/* Attributes tab */}
      {activeTab === "attributes" && (
        <div style={{ padding: "var(--space-4) 0" }}>
          <ProjectAttributeConfig projectId={project.id} />
        </div>
      )}

      {/* Create/Edit Phase modal */}
      {modalOpen && (
        <CreatePhaseModal
          phase={editPhase}
          onSubmit={editPhase ? handleUpdatePhase : handleCreatePhase}
          onClose={() => {
            setModalOpen(false);
            setEditPhase(null);
          }}
        />
      )}

      {/* Delete confirmation modal for phases */}
      {deleteConfirmPhase && (
        <div className={styles.modalOverlay} role="dialog" aria-modal="true">
          <div className={styles.modal}>
            <h2 className={styles.modalTitle}>Delete Phase</h2>
            <p style={{ marginBottom: "var(--space-6)", color: "var(--color-text)" }}>
              Are you sure you want to delete{" "}
              <strong>{deleteConfirmPhase.name}</strong>? This action cannot be
              undone.
            </p>
            <div className={styles.modalActions}>
              <button
                type="button"
                className={styles.cancelButton}
                onClick={() => {
                  setDeleteConfirmPhase(null);
                  setDeleteError(null);
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className={`${styles.submitButton} ${styles.actionButtonDanger}`}
                onClick={() => handleDeletePhase(deleteConfirmPhase)}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create/Edit Building modal */}
      {buildingModalOpen && (
        <CreateBuildingModal
          building={editBuilding}
          onSubmit={editBuilding ? handleUpdateBuilding : handleCreateBuilding}
          onClose={() => {
            setBuildingModalOpen(false);
            setEditBuilding(null);
          }}
        />
      )}

      {/* Delete confirmation modal for buildings */}
      {deleteConfirmBuilding && (
        <div className={styles.modalOverlay} role="dialog" aria-modal="true">
          <div className={styles.modal}>
            <h2 className={styles.modalTitle}>Delete Building</h2>
            <p style={{ marginBottom: "var(--space-6)", color: "var(--color-text)" }}>
              Are you sure you want to delete{" "}
              <strong>{deleteConfirmBuilding.name}</strong>? This action cannot be
              undone.
            </p>
            <div className={styles.modalActions}>
              <button
                type="button"
                className={styles.cancelButton}
                onClick={() => {
                  setDeleteConfirmBuilding(null);
                  setDeleteBuildingError(null);
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className={`${styles.submitButton} ${styles.actionButtonDanger}`}
                onClick={() => handleDeleteBuilding(deleteConfirmBuilding)}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create/Edit Floor modal */}
      {floorModalOpen && (
        <CreateFloorModal
          floor={editFloor}
          onSubmit={editFloor ? handleUpdateFloor : handleCreateFloor}
          onClose={() => {
            setFloorModalOpen(false);
            setEditFloor(null);
          }}
        />
      )}

      {/* Delete confirmation modal for floors */}
      {deleteConfirmFloor && (
        <div className={styles.modalOverlay} role="dialog" aria-modal="true">
          <div className={styles.modal}>
            <h2 className={styles.modalTitle}>Delete Floor</h2>
            <p style={{ marginBottom: "var(--space-6)", color: "var(--color-text)" }}>
              Are you sure you want to delete{" "}
              <strong>{deleteConfirmFloor.name}</strong>? This action cannot be
              undone.
            </p>
            <div className={styles.modalActions}>
              <button
                type="button"
                className={styles.cancelButton}
                onClick={() => {
                  setDeleteConfirmFloor(null);
                  setDeleteFloorError(null);
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className={`${styles.submitButton} ${styles.actionButtonDanger}`}
                onClick={() => handleDeleteFloor(deleteConfirmFloor)}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create/Edit Unit modal */}
      {unitModalOpen && (
        <CreateUnitModal
          unit={editUnit}
          onSubmit={editUnit ? handleUpdateUnit : handleCreateUnit}
          onClose={() => {
            setUnitModalOpen(false);
            setEditUnit(null);
          }}
        />
      )}

      {/* Reserve Unit modal */}
      {reserveUnit && (
        <ReserveUnitModal
          unit={reserveUnit}
          onSubmit={handleCreateReservation}
          onClose={() => {
            setReserveUnit(null);
            setReservationError(null);
          }}
        />
      )}

      {/* Delete confirmation modal for units */}
      {deleteConfirmUnit && (
        <div className={styles.modalOverlay} role="dialog" aria-modal="true">
          <div className={styles.modal}>
            <h2 className={styles.modalTitle}>Delete Unit</h2>
            <p style={{ marginBottom: "var(--space-6)", color: "var(--color-text)" }}>
              Are you sure you want to delete unit{" "}
              <strong>{deleteConfirmUnit.unit_number}</strong>? This action cannot be
              undone.
            </p>
            <div className={styles.modalActions}>
              <button
                type="button"
                className={styles.cancelButton}
                onClick={() => {
                  setDeleteConfirmUnit(null);
                  setDeleteUnitError(null);
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className={`${styles.submitButton} ${styles.actionButtonDanger}`}
                onClick={() => handleDeleteUnit(deleteConfirmUnit)}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
