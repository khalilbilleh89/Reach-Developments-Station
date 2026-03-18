/**
 * ScopeDetailView — shows a single construction scope with its milestones.
 */

"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  listMilestones,
  createMilestone,
  updateMilestone,
  deleteMilestone,
} from "@/lib/construction-api";
import type {
  ConstructionScope,
  ConstructionMilestone,
  ConstructionMilestoneCreate,
  MilestoneStatus,
} from "@/lib/construction-types";
import { MilestonesTable } from "./MilestonesTable";
import { AddMilestoneModal } from "./AddMilestoneModal";
import styles from "@/styles/construction.module.css";

interface ScopeDetailViewProps {
  scope: ConstructionScope;
  onBack: () => void;
}

export function ScopeDetailView({ scope, onBack }: ScopeDetailViewProps) {
  const [milestones, setMilestones] = useState<ConstructionMilestone[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddMilestone, setShowAddMilestone] = useState(false);

  const fetchMilestones = useCallback(() => {
    setLoading(true);
    listMilestones({ scope_id: scope.id })
      .then((resp) => {
        setMilestones(resp.items);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load milestones.");
      })
      .finally(() => setLoading(false));
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

  const handleUpdateStatus = useCallback(
    async (milestoneId: string, status: MilestoneStatus) => {
      try {
        await updateMilestone(milestoneId, { status });
        fetchMilestones();
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to update milestone.");
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
        setError(err instanceof Error ? err.message : "Failed to delete milestone.");
      }
    },
    [fetchMilestones],
  );

  const nextSequence = milestones.length > 0
    ? Math.max(...milestones.map((m) => m.sequence)) + 1
    : 1;

  const completedCount = milestones.filter((m) => m.status === "completed").length;

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
            <span className={styles.detailValue}>{scope.status.replace("_", " ")}</span>
          </div>
          <div className={styles.detailField}>
            <span className={styles.detailLabel}>Start Date</span>
            <span className={styles.detailValue}>{scope.start_date ?? "—"}</span>
          </div>
          <div className={styles.detailField}>
            <span className={styles.detailLabel}>Target End</span>
            <span className={styles.detailValue}>{scope.target_end_date ?? "—"}</span>
          </div>
          <div className={styles.detailField}>
            <span className={styles.detailLabel}>Milestones</span>
            <span className={styles.detailValue}>
              {completedCount} / {milestones.length} complete
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

      {/* Milestones section */}
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Milestones</h2>
        <button
          type="button"
          className={styles.addButton}
          onClick={() => setShowAddMilestone(true)}
        >
          + Add Milestone
        </button>
      </div>

      {error && (
        <div className={styles.errorBanner} role="alert">
          {error}
        </div>
      )}

      {loading && (
        <div className={styles.loadingText}>Loading milestones…</div>
      )}

      {!loading && (
        <MilestonesTable
          milestones={milestones}
          onUpdateStatus={handleUpdateStatus}
          onDeleteMilestone={handleDeleteMilestone}
        />
      )}

      {showAddMilestone && (
        <AddMilestoneModal
          scopeId={scope.id}
          nextSequence={nextSequence}
          onSubmit={handleAddMilestone}
          onClose={() => setShowAddMilestone(false)}
        />
      )}
    </>
  );
}
