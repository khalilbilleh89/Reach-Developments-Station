"use client";

import React, { useEffect, useState } from "react";
import type { Phase } from "@/lib/phases-types";
import type { Project } from "@/lib/projects-types";
import type { Building } from "@/lib/buildings-types";
import { listPhases, createPhase, updatePhase, deletePhase } from "@/lib/phases-api";
import { listBuildings, createBuilding, updateBuilding, deleteBuilding } from "@/lib/buildings-api";
import { ProjectPhasesTable } from "@/components/projects/ProjectPhasesTable";
import { ProjectOverview } from "@/components/projects/ProjectOverview";
import { BuildingsTable } from "@/components/buildings/BuildingsTable";
import { CreatePhaseModal } from "@/app/(protected)/projects/[id]/create-phase-modal";
import { CreateBuildingModal } from "@/components/buildings/create-building-modal";
import type { PhaseCreate, PhaseUpdate } from "@/lib/phases-types";
import type { BuildingCreate, BuildingUpdate } from "@/lib/buildings-types";
import styles from "@/styles/projects.module.css";

interface ProjectDetailViewProps {
  project: Project;
  onBack: () => void;
}

type Tab = "overview" | "phases" | "buildings";

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
 * ProjectDetailView — shows a project summary card, its phases, and its buildings.
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

  useEffect(() => {
    fetchPhases();
    // Reset buildings state when project changes
    setSelectedPhaseId(null);
    setBuildings([]);
    setBuildingsError(null);
    setBuildingModalOpen(false);
    setEditBuilding(null);
    setDeleteConfirmBuilding(null);
    setDeleteBuildingError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  useEffect(() => {
    if (activeTab === "buildings" && selectedPhaseId) {
      fetchBuildings(selectedPhaseId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, selectedPhaseId]);

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
      </div>

      {/* Overview tab */}
      {activeTab === "overview" && <ProjectOverview project={project} />}

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
    </div>
  );
}
