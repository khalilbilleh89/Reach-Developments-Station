"use client";

import React, { useEffect, useState } from "react";
import type { Phase } from "@/lib/phases-types";
import type { Project } from "@/lib/projects-types";
import { listPhases, createPhase, updatePhase, deletePhase } from "@/lib/phases-api";
import { ProjectPhasesTable } from "@/components/projects/ProjectPhasesTable";
import { ProjectOverview } from "@/components/projects/ProjectOverview";
import { CreatePhaseModal } from "@/app/(protected)/projects/[id]/create-phase-modal";
import type { PhaseCreate, PhaseUpdate } from "@/lib/phases-types";
import styles from "@/styles/projects.module.css";

interface ProjectDetailViewProps {
  project: Project;
  onBack: () => void;
}

type Tab = "overview" | "phases";

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
 * ProjectDetailView — shows a project summary card and its phases.
 *
 * Rendered by the projects page when a project is selected.
 */
export function ProjectDetailView({ project, onBack }: ProjectDetailViewProps) {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [phases, setPhases] = useState<Phase[]>([]);
  const [phasesLoading, setPhasesLoading] = useState(true);
  const [phasesError, setPhasesError] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [editPhase, setEditPhase] = useState<Phase | null>(null);
  const [deleteConfirmPhase, setDeleteConfirmPhase] = useState<Phase | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

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

  useEffect(() => {
    fetchPhases();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

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
      <div className={styles.tabBar} role="tablist" aria-label="Project sections">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "overview"}
          className={`${styles.tabButton} ${activeTab === "overview" ? styles.tabButtonActive : ""}`}
          onClick={() => setActiveTab("overview")}
        >
          Overview
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "phases"}
          className={`${styles.tabButton} ${activeTab === "phases" ? styles.tabButtonActive : ""}`}
          onClick={() => setActiveTab("phases")}
        >
          Phases
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

      {/* Delete confirmation modal */}
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
    </div>
  );
}
