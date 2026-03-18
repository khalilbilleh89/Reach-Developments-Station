/**
 * ScopeDetailView — shows a single construction scope with two workspaces:
 *
 *   Engineering  — technical tasks, deliverables, consultant cost tracking
 *   Contractor   — site execution milestones and progress tracking
 */

"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  listMilestones,
  createMilestone,
  updateMilestone,
  deleteMilestone,
  listEngineeringItems,
  createEngineeringItem,
  updateEngineeringItem,
  deleteEngineeringItem,
} from "@/lib/construction-api";
import type {
  ConstructionScope,
  ConstructionMilestone,
  ConstructionMilestoneCreate,
  ConstructionEngineeringItem,
  EngineeringItemCreate,
  EngineeringStatus,
  MilestoneStatus,
} from "@/lib/construction-types";
import { MilestonesTable } from "./MilestonesTable";
import { AddMilestoneModal } from "./AddMilestoneModal";
import { EngineeringItemsTable } from "./EngineeringItemsTable";
import { AddEngineeringItemModal } from "./AddEngineeringItemModal";
import styles from "@/styles/construction.module.css";

type WorkspaceTab = "engineering" | "contractor";

interface ScopeDetailViewProps {
  scope: ConstructionScope;
  onBack: () => void;
}

export function ScopeDetailView({ scope, onBack }: ScopeDetailViewProps) {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("engineering");

  // ── Engineering state ────────────────────────────────────────────────────
  const [engItems, setEngItems] = useState<ConstructionEngineeringItem[]>([]);
  const [engLoading, setEngLoading] = useState(true);
  const [engError, setEngError] = useState<string | null>(null);
  const [showAddEngItem, setShowAddEngItem] = useState(false);

  const fetchEngineeringItems = useCallback(() => {
    setEngLoading(true);
    listEngineeringItems(scope.id)
      .then((resp) => {
        setEngItems(resp.items);
        setEngError(null);
      })
      .catch((err: unknown) => {
        setEngError(
          err instanceof Error ? err.message : "Failed to load engineering items.",
        );
      })
      .finally(() => setEngLoading(false));
  }, [scope.id]);

  useEffect(() => {
    fetchEngineeringItems();
  }, [fetchEngineeringItems]);

  const handleAddEngineeringItem = useCallback(
    async (data: EngineeringItemCreate) => {
      await createEngineeringItem(scope.id, data);
      setShowAddEngItem(false);
      fetchEngineeringItems();
    },
    [scope.id, fetchEngineeringItems],
  );

  const handleUpdateEngStatus = useCallback(
    async (itemId: string, status: EngineeringStatus) => {
      try {
        await updateEngineeringItem(itemId, { status });
        fetchEngineeringItems();
      } catch (err: unknown) {
        setEngError(
          err instanceof Error ? err.message : "Failed to update engineering item.",
        );
      }
    },
    [fetchEngineeringItems],
  );

  const handleDeleteEngItem = useCallback(
    async (itemId: string) => {
      try {
        await deleteEngineeringItem(itemId);
        fetchEngineeringItems();
      } catch (err: unknown) {
        setEngError(
          err instanceof Error ? err.message : "Failed to delete engineering item.",
        );
      }
    },
    [fetchEngineeringItems],
  );

  // ── Contractor / milestone state ─────────────────────────────────────────
  const [milestones, setMilestones] = useState<ConstructionMilestone[]>([]);
  const [msLoading, setMsLoading] = useState(true);
  const [msError, setMsError] = useState<string | null>(null);
  const [showAddMilestone, setShowAddMilestone] = useState(false);

  const fetchMilestones = useCallback(() => {
    setMsLoading(true);
    listMilestones({ scope_id: scope.id })
      .then((resp) => {
        setMilestones(resp.items);
        setMsError(null);
      })
      .catch((err: unknown) => {
        setMsError(
          err instanceof Error ? err.message : "Failed to load milestones.",
        );
      })
      .finally(() => setMsLoading(false));
  }, [scope.id]);

  useEffect(() => {
    fetchMilestones();
  }, [fetchMilestones]);

  const handleAddMilestone = useCallback(
    async (data: ConstructionMilestoneCreate) => {
      await createMilestone(data);
      setShowAddMilestone(false);
      fetchMilestones();
    },
    [fetchMilestones],
  );

  const handleUpdateMilestoneStatus = useCallback(
    async (milestoneId: string, status: MilestoneStatus) => {
      try {
        await updateMilestone(milestoneId, { status });
        fetchMilestones();
      } catch (err: unknown) {
        setMsError(
          err instanceof Error ? err.message : "Failed to update milestone.",
        );
      }
    },
    [fetchMilestones],
  );

  const handleDeleteMilestone = useCallback(
    async (milestoneId: string) => {
      try {
        await deleteMilestone(milestoneId);
        fetchMilestones();
      } catch (err: unknown) {
        setMsError(
          err instanceof Error ? err.message : "Failed to delete milestone.",
        );
      }
    },
    [fetchMilestones],
  );

  const nextMilestoneSequence =
    milestones.length > 0
      ? Math.max(...milestones.map((m) => m.sequence)) + 1
      : 1;

  const completedMilestones = milestones.filter(
    (m) => m.status === "completed",
  ).length;

  const completedEngItems = engItems.filter(
    (i) => i.status === "completed",
  ).length;

  return (
    <>
      <button type="button" className={styles.backButton} onClick={onBack}>
        ← Back to Scopes
      </button>

      {/* Scope detail card */}
      <div className={styles.detailCard}>
        <div className={styles.detailGrid}>
          <div className={styles.detailField}>
            <span className={styles.detailLabel}>Name</span>
            <span className={styles.detailValue}>{scope.name}</span>
          </div>
          <div className={styles.detailField}>
            <span className={styles.detailLabel}>Status</span>
            <span className={styles.detailValue}>
              {scope.status.replace("_", " ")}
            </span>
          </div>
          <div className={styles.detailField}>
            <span className={styles.detailLabel}>Start Date</span>
            <span className={styles.detailValue}>{scope.start_date ?? "—"}</span>
          </div>
          <div className={styles.detailField}>
            <span className={styles.detailLabel}>Target End</span>
            <span className={styles.detailValue}>
              {scope.target_end_date ?? "—"}
            </span>
          </div>
          <div className={styles.detailField}>
            <span className={styles.detailLabel}>Engineering</span>
            <span className={styles.detailValue}>
              {completedEngItems} / {engItems.length} complete
            </span>
          </div>
          <div className={styles.detailField}>
            <span className={styles.detailLabel}>Contractor</span>
            <span className={styles.detailValue}>
              {completedMilestones} / {milestones.length} complete
            </span>
          </div>
          {scope.description && (
            <div className={styles.detailField}>
              <span className={styles.detailLabel}>Description</span>
              <span className={styles.detailValue}>{scope.description}</span>
            </div>
          )}
        </div>
      </div>

      {/* Tab bar */}
      <div className={styles.tabBar}>
        <button
          type="button"
          className={`${styles.tabButton} ${activeTab === "engineering" ? styles.tabButtonActive : ""}`}
          onClick={() => setActiveTab("engineering")}
        >
          📐 Engineering
        </button>
        <button
          type="button"
          className={`${styles.tabButton} ${activeTab === "contractor" ? styles.tabButtonActive : ""}`}
          onClick={() => setActiveTab("contractor")}
        >
          🏗️ Contractor Milestones
        </button>
      </div>

      {/* ── Engineering workspace ────────────────────────────────────────── */}
      {activeTab === "engineering" && (
        <>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>Engineering Items</h2>
            <button
              type="button"
              className={styles.addButton}
              onClick={() => setShowAddEngItem(true)}
            >
              + Add Engineering Item
            </button>
          </div>

          {engError && (
            <div className={styles.errorBanner} role="alert">
              {engError}
            </div>
          )}

          {engLoading && (
            <div className={styles.loadingText}>Loading engineering items…</div>
          )}

          {!engLoading && (
            <EngineeringItemsTable
              items={engItems}
              onUpdateStatus={handleUpdateEngStatus}
              onDeleteItem={handleDeleteEngItem}
            />
          )}

          {showAddEngItem && (
            <AddEngineeringItemModal
              onSubmit={handleAddEngineeringItem}
              onClose={() => setShowAddEngItem(false)}
            />
          )}
        </>
      )}

      {/* ── Contractor workspace ─────────────────────────────────────────── */}
      {activeTab === "contractor" && (
        <>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>Contractor Milestones</h2>
            <button
              type="button"
              className={styles.addButton}
              onClick={() => setShowAddMilestone(true)}
            >
              + Add Milestone
            </button>
          </div>

          {msError && (
            <div className={styles.errorBanner} role="alert">
              {msError}
            </div>
          )}

          {msLoading && (
            <div className={styles.loadingText}>Loading milestones…</div>
          )}

          {!msLoading && (
            <MilestonesTable
              milestones={milestones}
              onUpdateStatus={handleUpdateMilestoneStatus}
              onDeleteMilestone={handleDeleteMilestone}
            />
          )}

          {showAddMilestone && (
            <AddMilestoneModal
              scopeId={scope.id}
              nextSequence={nextMilestoneSequence}
              onSubmit={handleAddMilestone}
              onClose={() => setShowAddMilestone(false)}
            />
          )}
        </>
      )}
    </>
  );
}
