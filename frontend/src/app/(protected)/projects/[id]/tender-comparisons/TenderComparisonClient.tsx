"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import { TenderComparisonSetList } from "@/components/tender-comparisons/TenderComparisonSetList";
import { TenderComparisonSummaryStrip } from "@/components/tender-comparisons/TenderComparisonSummaryStrip";
import { TenderComparisonLineTable } from "@/components/tender-comparisons/TenderComparisonLineTable";
import { TenderComparisonFormModal } from "@/components/tender-comparisons/TenderComparisonFormModal";
import { TenderComparisonLineFormModal } from "@/components/tender-comparisons/TenderComparisonLineFormModal";
import {
  listProjectTenderComparisons,
  createTenderComparison,
  getTenderComparison,
  updateTenderComparison,
  getTenderComparisonSummary,
  createComparisonLine,
  updateComparisonLine,
  deleteComparisonLine,
} from "@/lib/tender-comparison-api";
import type {
  ConstructionCostComparisonSet,
  ConstructionCostComparisonSetCreate,
  ConstructionCostComparisonSetListItem,
  ConstructionCostComparisonSetUpdate,
  ConstructionCostComparisonLine,
  ConstructionCostComparisonLineCreate,
  ConstructionCostComparisonLineUpdate,
  ConstructionCostComparisonSummary,
} from "@/lib/tender-comparison-types";
import styles from "@/styles/construction.module.css";

/**
 * TenderComparisonClient
 *
 * Client component for the project tender comparisons page.
 * Handles data fetching, CRUD flows, loading / error / empty states,
 * and form modal lifecycle.
 *
 * Data sources:
 *   GET  /api/v1/projects/{id}/tender-comparisons
 *   POST /api/v1/projects/{id}/tender-comparisons
 *   GET  /api/v1/tender-comparisons/{setId}
 *   PATCH /api/v1/tender-comparisons/{setId}
 *   GET  /api/v1/tender-comparisons/{setId}/summary
 *   POST /api/v1/tender-comparisons/{setId}/lines
 *   PATCH /api/v1/tender-comparisons/lines/{lineId}
 *   DELETE /api/v1/tender-comparisons/lines/{lineId}
 */
export function TenderComparisonClient() {
  const params = useParams<{ id: string }>();
  const projectId = params?.id ?? "";

  // ── Set list state ─────────────────────────────────────────────────────────
  const [sets, setSets] = useState<ConstructionCostComparisonSetListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  // ── Selected set detail state ─────────────────────────────────────────────
  const [selectedSet, setSelectedSet] =
    useState<ConstructionCostComparisonSet | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [summary, setSummary] =
    useState<ConstructionCostComparisonSummary | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  // ── Action error ───────────────────────────────────────────────────────────
  const [actionError, setActionError] = useState<string | null>(null);

  // ── Set form modal ─────────────────────────────────────────────────────────
  const [showSetModal, setShowSetModal] = useState(false);
  const [editingSet, setEditingSet] =
    useState<ConstructionCostComparisonSetListItem | null>(null);

  // ── Line form modal ────────────────────────────────────────────────────────
  const [showLineModal, setShowLineModal] = useState(false);
  const [editingLine, setEditingLine] =
    useState<ConstructionCostComparisonLine | null>(null);
  const [deletingLineId, setDeletingLineId] = useState<string | null>(null);

  // ── Load set list ──────────────────────────────────────────────────────────
  const loadList = useCallback(
    (signal?: AbortSignal) => {
      if (!projectId || projectId === "_") {
        setLoadingList(false);
        return;
      }
      setLoadingList(true);
      setListError(null);
      listProjectTenderComparisons(projectId)
        .then((result) => {
          if (signal?.aborted) return;
          setSets(result.items);
          setTotal(result.total);
        })
        .catch((err: unknown) => {
          if (signal?.aborted) return;
          setListError(
            err instanceof Error
              ? err.message
              : "Failed to load tender comparisons.",
          );
        })
        .finally(() => {
          if (!signal?.aborted) setLoadingList(false);
        });
    },
    [projectId],
  );

  useEffect(() => {
    const controller = new AbortController();
    loadList(controller.signal);
    return () => controller.abort();
  }, [loadList]);

  // ── Load selected set detail + summary ────────────────────────────────────
  const loadDetail = useCallback(
    (setId: string, signal?: AbortSignal) => {
      setLoadingDetail(true);
      setDetailError(null);
      Promise.all([getTenderComparison(setId), getTenderComparisonSummary(setId)])
        .then(([detail, sum]) => {
          if (signal?.aborted) return;
          setSelectedSet(detail);
          setSummary(sum);
        })
        .catch((err: unknown) => {
          if (signal?.aborted) return;
          setDetailError(
            err instanceof Error
              ? err.message
              : "Failed to load comparison detail.",
          );
        })
        .finally(() => {
          if (!signal?.aborted) setLoadingDetail(false);
        });
    },
    [],
  );

  const handleSelectSet = (set: ConstructionCostComparisonSetListItem) => {
    setSelectedId(set.id);
    setDetailError(null);
    loadDetail(set.id);
  };

  // ── Set CRUD ───────────────────────────────────────────────────────────────
  const handleOpenCreateSet = () => {
    setEditingSet(null);
    setActionError(null);
    setShowSetModal(true);
  };

  const handleOpenEditSet = (set: ConstructionCostComparisonSetListItem) => {
    setEditingSet(set);
    setActionError(null);
    setShowSetModal(true);
  };

  const handleSubmitSet = async (
    data: ConstructionCostComparisonSetCreate | ConstructionCostComparisonSetUpdate,
  ) => {
    setActionError(null);
    if (editingSet) {
      await updateTenderComparison(
        editingSet.id,
        data as ConstructionCostComparisonSetUpdate,
      );
    } else {
      await createTenderComparison(
        projectId,
        data as ConstructionCostComparisonSetCreate,
      );
    }
    setShowSetModal(false);
    setEditingSet(null);
    loadList();
    // Refresh detail if the edited set is currently selected
    if (editingSet && selectedId === editingSet.id) {
      loadDetail(editingSet.id);
    }
  };

  // ── Line CRUD ──────────────────────────────────────────────────────────────
  const handleOpenCreateLine = () => {
    setEditingLine(null);
    setActionError(null);
    setShowLineModal(true);
  };

  const handleOpenEditLine = (line: ConstructionCostComparisonLine) => {
    setEditingLine(line);
    setActionError(null);
    setShowLineModal(true);
  };

  const handleSubmitLine = async (
    data:
      | ConstructionCostComparisonLineCreate
      | ConstructionCostComparisonLineUpdate,
  ) => {
    setActionError(null);
    if (!selectedId) return;
    if (editingLine) {
      await updateComparisonLine(
        editingLine.id,
        data as ConstructionCostComparisonLineUpdate,
      );
    } else {
      await createComparisonLine(
        selectedId,
        data as ConstructionCostComparisonLineCreate,
      );
    }
    setShowLineModal(false);
    setEditingLine(null);
    loadDetail(selectedId);
  };

  const handleDeleteLine = async (line: ConstructionCostComparisonLine) => {
    if (!selectedId) return;
    setDeletingLineId(line.id);
    setActionError(null);
    try {
      await deleteComparisonLine(line.id);
      loadDetail(selectedId);
    } catch (err: unknown) {
      setActionError(
        err instanceof Error ? err.message : "Failed to delete line.",
      );
    } finally {
      setDeletingLineId(null);
    }
  };

  return (
    <PageContainer
      title="Tender Comparisons"
      subtitle={
        projectId && projectId !== "_"
          ? `Project ${projectId} · ${total} comparison set${total !== 1 ? "s" : ""}`
          : "Manage tender comparison sets"
      }
    >
      {/* Action bar */}
      {!loadingList && !listError && (
        <div className={styles.actionBar}>
          <button
            className={styles.primaryButton}
            onClick={handleOpenCreateSet}
          >
            + New Comparison Set
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
      {loadingList && (
        <div className={styles.loadingState} data-testid="loading-state">
          Loading tender comparisons…
        </div>
      )}

      {/* List error */}
      {!loadingList && listError && (
        <div
          className={styles.errorState}
          role="alert"
          data-testid="error-state"
        >
          {listError}
        </div>
      )}

      {!loadingList && !listError && (
        <div className={styles.splitLayout}>
          {/* Set list panel */}
          <div className={styles.splitLeft}>
            <TenderComparisonSetList
              sets={sets}
              selectedId={selectedId}
              onSelect={handleSelectSet}
            />
          </div>

          {/* Detail panel */}
          <div className={styles.splitRight}>
            {selectedId === null && (
              <div
                className={styles.emptyState}
                data-testid="select-prompt"
              >
                <p className={styles.emptyStateTitle}>
                  Select a comparison set to view details.
                </p>
              </div>
            )}

            {selectedId !== null && loadingDetail && (
              <div
                className={styles.loadingState}
                data-testid="detail-loading-state"
              >
                Loading comparison detail…
              </div>
            )}

            {selectedId !== null && !loadingDetail && detailError && (
              <div
                className={styles.errorState}
                role="alert"
                data-testid="detail-error-state"
              >
                {detailError}
              </div>
            )}

            {selectedId !== null && !loadingDetail && !detailError && selectedSet && (
              <>
                {/* Set header with edit action */}
                <div className={styles.sectionHeader}>
                  <div>
                    <h2 className={styles.sectionTitle}>
                      {selectedSet.title}
                    </h2>
                    <div className={styles.sectionNote}>
                      {selectedSet.baseline_label} →{" "}
                      {selectedSet.comparison_label}
                    </div>
                  </div>
                  <button
                    className={styles.actionButton}
                    onClick={() => {
                      const listItem = sets.find(
                        (s) => s.id === selectedSet.id,
                      );
                      if (listItem) handleOpenEditSet(listItem);
                    }}
                  >
                    Edit Set
                  </button>
                </div>

                {/* Summary strip */}
                {summary && <TenderComparisonSummaryStrip summary={summary} />}

                {/* Line actions */}
                <div className={styles.actionBar}>
                  <button
                    className={styles.primaryButton}
                    onClick={handleOpenCreateLine}
                  >
                    + Add Line
                  </button>
                </div>

                {/* Line table */}
                <TenderComparisonLineTable
                  lines={selectedSet.lines}
                  baselineLabel={selectedSet.baseline_label}
                  comparisonLabel={selectedSet.comparison_label}
                  onEdit={handleOpenEditLine}
                  onDelete={handleDeleteLine}
                  deletingId={deletingLineId}
                />
              </>
            )}
          </div>
        </div>
      )}

      {/* Set create / edit modal */}
      {showSetModal && (
        <TenderComparisonFormModal
          set={editingSet ?? undefined}
          onSubmit={handleSubmitSet}
          onClose={() => {
            setShowSetModal(false);
            setEditingSet(null);
          }}
        />
      )}

      {/* Line create / edit modal */}
      {showLineModal && (
        <TenderComparisonLineFormModal
          line={editingLine ?? undefined}
          onSubmit={handleSubmitLine}
          onClose={() => {
            setShowLineModal(false);
            setEditingLine(null);
          }}
        />
      )}
    </PageContainer>
  );
}
