"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import { TenderComparisonSetList } from "@/components/tender-comparisons/TenderComparisonSetList";
import { TenderComparisonSummaryStrip } from "@/components/tender-comparisons/TenderComparisonSummaryStrip";
import { TenderComparisonLineTable } from "@/components/tender-comparisons/TenderComparisonLineTable";
import { TenderComparisonFormModal } from "@/components/tender-comparisons/TenderComparisonFormModal";
import { TenderComparisonLineFormModal } from "@/components/tender-comparisons/TenderComparisonLineFormModal";
import { BaselineApprovalConfirmModal } from "@/components/tender-comparisons/BaselineApprovalConfirmModal";
import {
  listProjectTenderComparisons,
  createTenderComparison,
  getTenderComparison,
  updateTenderComparison,
  getTenderComparisonSummary,
  createComparisonLine,
  updateComparisonLine,
  deleteComparisonLine,
  approveTenderBaseline,
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
 * form modal lifecycle, and approved-baseline governance (PR-V6-13).
 *
 * Data sources:
 *   GET  /api/v1/projects/{id}/tender-comparisons
 *   POST /api/v1/projects/{id}/tender-comparisons
 *   GET  /api/v1/tender-comparisons/{setId}
 *   PATCH /api/v1/tender-comparisons/{setId}
 *   GET  /api/v1/tender-comparisons/{setId}/summary
 *   POST /api/v1/tender-comparisons/{setId}/approve-baseline
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

  // ── Baseline approval modal (PR-V6-13) ────────────────────────────────────
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [approvingSetId, setApprovingSetId] = useState<string | null>(null);
  const [approvingSetTitle, setApprovingSetTitle] = useState("");
  const [approveSubmitting, setApproveSubmitting] = useState(false);
  const [approveError, setApproveError] = useState<string | null>(null);

  // ── Detail request race-condition guards ──────────────────────────────────
  // `latestDetailRequestId` tracks the most recently requested setId so that
  // stale Promise callbacks from superseded selections are silently discarded.
  //
  // `detailAbortController` holds an AbortController for the current in-flight
  // detail request so it can be cancelled (network-level) when the user switches
  // to a different set or the component unmounts, preventing unnecessary
  // traffic and potential memory leaks.
  const latestDetailRequestId = useRef<string | null>(null);
  const detailAbortController = useRef<AbortController | null>(null);

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

  // On unmount, abort any in-flight detail request and clear the request
  // tracker so pending callbacks are silently dropped.
  useEffect(() => {
    return () => {
      latestDetailRequestId.current = null;
      detailAbortController.current?.abort();
    };
  }, []);

  // ── Load selected set detail + summary ────────────────────────────────────
  const loadDetail = useCallback(
    (setId: string) => {
      // Abort the previous in-flight detail request to cancel unnecessary
      // network traffic before starting the new one.
      detailAbortController.current?.abort();
      const controller = new AbortController();
      detailAbortController.current = controller;

      // Record this as the latest requested setId so that responses from
      // earlier (now-superseded) requests are discarded when they settle.
      latestDetailRequestId.current = setId;

      setLoadingDetail(true);
      setDetailError(null);
      Promise.all([getTenderComparison(setId), getTenderComparisonSummary(setId)])
        .then(([detail, sum]) => {
          // Guard 1: network-level abort check.
          if (controller.signal.aborted) return;
          // Guard 2: only commit state if this is still the latest selection.
          // A slower earlier response must not overwrite a newer selection.
          if (latestDetailRequestId.current !== setId) return;
          setSelectedSet(detail);
          setSummary(sum);
        })
        .catch((err: unknown) => {
          // Discard errors from aborted or superseded requests to avoid
          // surfacing spurious error banners.
          if (controller.signal.aborted) return;
          if (latestDetailRequestId.current !== setId) return;
          setDetailError(
            err instanceof Error
              ? err.message
              : "Failed to load comparison detail.",
          );
        })
        .finally(() => {
          if (
            !controller.signal.aborted &&
            latestDetailRequestId.current === setId
          ) {
            setLoadingDetail(false);
          }
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

  // ── Baseline approval (PR-V6-13) ──────────────────────────────────────────
  const handleOpenApproveModal = () => {
    if (!selectedSet) return;
    setApproveError(null);
    setApprovingSetId(selectedSet.id);
    setApprovingSetTitle(selectedSet.title);
    setShowApproveModal(true);
  };

  const handleConfirmApprove = async () => {
    if (!approvingSetId) return;
    setApproveSubmitting(true);
    setApproveError(null);
    try {
      await approveTenderBaseline(approvingSetId);
      setShowApproveModal(false);
      setApprovingSetId(null);
      // Refresh both the list (badge updates) and the detail panel.
      loadList();
      loadDetail(approvingSetId);
    } catch (err: unknown) {
      setApproveError(
        err instanceof Error ? err.message : "Failed to approve baseline.",
      );
    } finally {
      setApproveSubmitting(false);
    }
  };

  // Determine whether there is already an approved baseline for this project
  // so the confirmation modal can show the replacement warning.
  const hasExistingBaseline = sets.some(
    (s) => s.is_approved_baseline && s.id !== approvingSetId,
  );

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
                {/* Set header with edit action and baseline approval */}
                <div className={styles.sectionHeader}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap" }}>
                      <h2 className={styles.sectionTitle}>
                        {selectedSet.title}
                      </h2>
                      {selectedSet.is_approved_baseline && (
                        <span
                          className={styles.badgeApprovedBaseline}
                          data-testid="detail-baseline-badge"
                        >
                          Approved Baseline
                        </span>
                      )}
                    </div>
                    <div className={styles.sectionNote}>
                      {selectedSet.baseline_label} →{" "}
                      {selectedSet.comparison_label}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
                    {!selectedSet.is_approved_baseline && (
                      <button
                        className={styles.approveButton}
                        onClick={handleOpenApproveModal}
                        data-testid="approve-baseline-button"
                      >
                        ✓ Approve as Baseline
                      </button>
                    )}
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
                </div>

                {/* Approved baseline metadata strip */}
                {selectedSet.is_approved_baseline && (
                  <div
                    className={styles.baselineMetaStrip}
                    data-testid="baseline-meta-strip"
                  >
                    <span>
                      <span className={styles.baselineMetaLabel}>
                        Approved on:
                      </span>
                      {selectedSet.approved_at
                        ? new Date(selectedSet.approved_at).toLocaleString()
                        : "—"}
                    </span>
                    <span>
                      <span className={styles.baselineMetaLabel}>
                        Approved by:
                      </span>
                      {selectedSet.approved_by_user_id ?? "—"}
                    </span>
                  </div>
                )}

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

      {/* Baseline approval confirmation modal */}
      {showApproveModal && approvingSetId && (
        <BaselineApprovalConfirmModal
          comparisonTitle={approvingSetTitle}
          hasExistingBaseline={hasExistingBaseline}
          isSubmitting={approveSubmitting}
          error={approveError}
          onConfirm={handleConfirmApprove}
          onClose={() => {
            setShowApproveModal(false);
            setApprovingSetId(null);
            setApproveError(null);
          }}
        />
      )}
    </PageContainer>
  );
}
