"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import { ConstructionCostSummaryStrip } from "@/components/construction-costs/ConstructionCostSummaryStrip";
import { ConstructionCostRecordTable } from "@/components/construction-costs/ConstructionCostRecordTable";
import { ConstructionCostRecordFormModal } from "@/components/construction-costs/ConstructionCostRecordFormModal";
import { ConstructionScorecardPanel } from "@/components/construction-costs/ConstructionScorecardPanel";
import {
  listProjectConstructionCostRecords,
  createConstructionCostRecord,
  updateConstructionCostRecord,
  archiveConstructionCostRecord,
  getConstructionCostSummary,
} from "@/lib/construction-cost-api";
import type {
  ConstructionCostRecord,
  ConstructionCostRecordCreate,
  ConstructionCostRecordUpdate,
  ConstructionCostSummary,
} from "@/lib/construction-cost-types";
import styles from "@/styles/construction.module.css";

/**
 * ConstructionCostsClient
 *
 * Client component for the project construction cost records page.
 * Handles data fetching, CRUD flows, loading / error / empty states, and
 * form modal lifecycle.
 *
 * Separated from page.tsx so that the server route entry can export
 * `generateStaticParams` / `dynamicParams` without mixing server and
 * client module boundaries (App Router requirement).
 *
 * Data sources:
 *   GET  /api/v1/projects/{id}/construction-cost-records
 *   GET  /api/v1/projects/{id}/construction-cost-records/summary
 *   GET  /api/v1/projects/{id}/construction-scorecard
 *   POST /api/v1/projects/{id}/construction-cost-records
 *   PATCH /api/v1/construction-cost-records/{recordId}
 *   POST  /api/v1/construction-cost-records/{recordId}/archive
 */
export function ConstructionCostsClient() {
  const params = useParams<{ id: string }>();
  const projectId = params?.id ?? "";

  const [records, setRecords] = useState<ConstructionCostRecord[]>([]);
  const [summary, setSummary] = useState<ConstructionCostSummary | null>(null);
  const [total, setTotal] = useState(0);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [showModal, setShowModal] = useState(false);
  const [editingRecord, setEditingRecord] =
    useState<ConstructionCostRecord | null>(null);
  const [archivingId, setArchivingId] = useState<string | null>(null);

  // scorecardKey is bumped after mutations to force the scorecard to refresh
  const [scorecardKey, setScorecardKey] = useState(0);

  const load = useCallback(
    (signal?: AbortSignal) => {
      if (!projectId || projectId === "_") {
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      Promise.all([
        listProjectConstructionCostRecords(projectId),
        getConstructionCostSummary(projectId),
      ])
        .then(([list, sum]) => {
          if (signal?.aborted) return;
          setRecords(list.items);
          setTotal(list.total);
          setSummary(sum);
        })
        .catch((err: unknown) => {
          if (signal?.aborted) return;
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load construction cost records.",
          );
        })
        .finally(() => {
          if (!signal?.aborted) setLoading(false);
        });
    },
    [projectId],
  );

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const handleOpenCreate = () => {
    setEditingRecord(null);
    setActionError(null);
    setShowModal(true);
  };

  const handleOpenEdit = (record: ConstructionCostRecord) => {
    setEditingRecord(record);
    setActionError(null);
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setEditingRecord(null);
  };

  const handleSubmit = async (
    data: ConstructionCostRecordCreate | ConstructionCostRecordUpdate,
  ) => {
    setActionError(null);
    if (editingRecord) {
      await updateConstructionCostRecord(
        editingRecord.id,
        data as ConstructionCostRecordUpdate,
      );
    } else {
      await createConstructionCostRecord(
        projectId,
        data as ConstructionCostRecordCreate,
      );
    }
    setShowModal(false);
    setEditingRecord(null);
    load();
    setScorecardKey((k) => k + 1);
  };

  const handleArchive = async (record: ConstructionCostRecord) => {
    setArchivingId(record.id);
    setActionError(null);
    try {
      await archiveConstructionCostRecord(record.id);
      load();
      setScorecardKey((k) => k + 1);
    } catch (err: unknown) {
      setActionError(
        err instanceof Error ? err.message : "Failed to archive record.",
      );
    } finally {
      setArchivingId(null);
    }
  };

  return (
    <PageContainer
      title="Construction Cost Records"
      subtitle={
        projectId && projectId !== "_"
          ? `Project ${projectId} · ${total} record${total !== 1 ? "s" : ""}`
          : "Manage project-level construction cost records"
      }
    >
      {/* Construction Health Scorecard */}
      {projectId && projectId !== "_" && (
        <ConstructionScorecardPanel
          key={scorecardKey}
          projectId={projectId}
        />
      )}

      {/* Action bar */}
      {!loading && !error && (
        <div className={styles.actionBar}>
          <button className={styles.primaryButton} onClick={handleOpenCreate}>
            + Add Cost Record
          </button>
        </div>
      )}

      {/* Action error */}
      {actionError && (
        <div className={styles.errorBanner} role="alert">
          {actionError}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className={styles.loadingState} data-testid="loading-state">
          Loading construction cost records…
        </div>
      )}

      {/* Error state */}
      {!loading && error && (
        <div className={styles.errorState} role="alert" data-testid="error-state">
          {error}
        </div>
      )}

      {/* Content */}
      {!loading && !error && (
        <>
          {summary && summary.active_record_count > 0 && (
            <ConstructionCostSummaryStrip summary={summary} />
          )}

          <ConstructionCostRecordTable
            records={records}
            onEdit={handleOpenEdit}
            onArchive={handleArchive}
            archivingId={archivingId}
          />
        </>
      )}

      {/* Create / Edit Modal */}
      {showModal && (
        <ConstructionCostRecordFormModal
          record={editingRecord ?? undefined}
          onSubmit={handleSubmit}
          onClose={handleCloseModal}
        />
      )}
    </PageContainer>
  );
}
