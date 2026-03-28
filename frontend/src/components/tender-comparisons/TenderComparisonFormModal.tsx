/**
 * TenderComparisonFormModal — create / edit modal for a comparison set.
 *
 * When `set` is provided the modal operates in edit mode (pre-populated
 * fields, "Update" submit label).  When `set` is undefined it operates in
 * create mode.
 */

"use client";

import React, { useEffect, useState } from "react";
import type {
  ConstructionCostComparisonSetListItem,
  ConstructionCostComparisonSetCreate,
  ConstructionCostComparisonSetUpdate,
  ComparisonStage,
} from "@/lib/tender-comparison-types";
import { COMPARISON_STAGE_OPTIONS } from "@/lib/tender-comparison-types";
import styles from "@/styles/construction.module.css";

interface TenderComparisonFormModalProps {
  set?: ConstructionCostComparisonSetListItem;
  onSubmit: (
    data: ConstructionCostComparisonSetCreate | ConstructionCostComparisonSetUpdate,
  ) => Promise<void>;
  onClose: () => void;
}

export function TenderComparisonFormModal({
  set,
  onSubmit,
  onClose,
}: TenderComparisonFormModalProps) {
  const isEdit = Boolean(set);

  const [title, setTitle] = useState(set?.title ?? "");
  const [comparisonStage, setComparisonStage] = useState<ComparisonStage>(
    set?.comparison_stage ?? "baseline_vs_tender",
  );
  const [baselineLabel, setBaselineLabel] = useState(
    set?.baseline_label ?? "Baseline",
  );
  const [comparisonLabel, setComparisonLabel] = useState(
    set?.comparison_label ?? "Tender",
  );
  const [notes, setNotes] = useState(set?.notes ?? "");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setTitle(set?.title ?? "");
    setComparisonStage(set?.comparison_stage ?? "baseline_vs_tender");
    setBaselineLabel(set?.baseline_label ?? "Baseline");
    setComparisonLabel(set?.comparison_label ?? "Tender");
    setNotes(set?.notes ?? "");
    setError(null);
  }, [set]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Title is required.");
      return;
    }
    if (!baselineLabel.trim()) {
      setError("Baseline label is required.");
      return;
    }
    if (!comparisonLabel.trim()) {
      setError("Comparison label is required.");
      return;
    }

    setSubmitting(true);
    setError(null);

    const payload: ConstructionCostComparisonSetCreate | ConstructionCostComparisonSetUpdate =
      {
        title: title.trim(),
        comparison_stage: comparisonStage,
        baseline_label: baselineLabel.trim(),
        comparison_label: comparisonLabel.trim(),
        notes: notes.trim() || null,
      };

    try {
      await onSubmit(payload);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to save comparison set.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tc-set-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="tc-set-modal-title" className={styles.modalTitle}>
          {isEdit ? "Edit Comparison Set" : "New Comparison Set"}
        </h2>

        <form className={styles.modalForm} onSubmit={handleSubmit}>
          {/* Title */}
          <div className={styles.formField}>
            <label htmlFor="tc-title" className={styles.formLabel}>
              Title <span aria-hidden>*</span>
            </label>
            <input
              id="tc-title"
              type="text"
              className={styles.formInput}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Baseline vs Tender Q1 2026"
            />
          </div>

          {/* Comparison Stage */}
          <div className={styles.formField}>
            <label htmlFor="tc-stage" className={styles.formLabel}>
              Comparison Stage
            </label>
            <select
              id="tc-stage"
              className={styles.formSelect}
              value={comparisonStage}
              onChange={(e) =>
                setComparisonStage(e.target.value as ComparisonStage)
              }
            >
              {COMPARISON_STAGE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.formRow}>
            {/* Baseline Label */}
            <div className={styles.formField}>
              <label htmlFor="tc-baseline-label" className={styles.formLabel}>
                Baseline Label <span aria-hidden>*</span>
              </label>
              <input
                id="tc-baseline-label"
                type="text"
                maxLength={255}
                className={styles.formInput}
                value={baselineLabel}
                onChange={(e) => setBaselineLabel(e.target.value)}
                placeholder="Baseline"
              />
            </div>

            {/* Comparison Label */}
            <div className={styles.formField}>
              <label
                htmlFor="tc-comparison-label"
                className={styles.formLabel}
              >
                Comparison Label <span aria-hidden>*</span>
              </label>
              <input
                id="tc-comparison-label"
                type="text"
                maxLength={255}
                className={styles.formInput}
                value={comparisonLabel}
                onChange={(e) => setComparisonLabel(e.target.value)}
                placeholder="Tender"
              />
            </div>
          </div>

          {/* Notes */}
          <div className={styles.formField}>
            <label htmlFor="tc-notes" className={styles.formLabel}>
              Notes
            </label>
            <textarea
              id="tc-notes"
              className={styles.formTextarea}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional context notes"
            />
          </div>

          {error && (
            <div className={styles.modalError} role="alert">
              {error}
            </div>
          )}

          <div className={styles.modalActions}>
            <button
              type="button"
              className={styles.cancelButton}
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={styles.submitButton}
              disabled={submitting}
            >
              {submitting
                ? isEdit
                  ? "Updating…"
                  : "Creating…"
                : isEdit
                  ? "Update Set"
                  : "Create Set"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
