/**
 * TenderComparisonLineFormModal — create / edit modal for a single
 * comparison line within a comparison set.
 *
 * When `line` is provided the modal operates in edit mode.
 * When `line` is undefined it operates in create mode.
 */

"use client";

import React, { useEffect, useState } from "react";
import type {
  ConstructionCostComparisonLine,
  ConstructionCostComparisonLineCreate,
  ConstructionCostComparisonLineUpdate,
  VarianceReason,
} from "@/lib/tender-comparison-types";
import { VARIANCE_REASON_OPTIONS } from "@/lib/tender-comparison-types";
import type { CostCategory } from "@/lib/construction-cost-types";
import { COST_CATEGORY_OPTIONS } from "@/lib/construction-cost-types";
import styles from "@/styles/construction.module.css";

interface TenderComparisonLineFormModalProps {
  line?: ConstructionCostComparisonLine;
  onSubmit: (
    data:
      | ConstructionCostComparisonLineCreate
      | ConstructionCostComparisonLineUpdate,
  ) => Promise<void>;
  onClose: () => void;
}

export function TenderComparisonLineFormModal({
  line,
  onSubmit,
  onClose,
}: TenderComparisonLineFormModalProps) {
  const isEdit = Boolean(line);

  const [costCategory, setCostCategory] = useState<CostCategory>(
    line?.cost_category ?? "hard_cost",
  );
  const [baselineAmount, setBaselineAmount] = useState(
    line != null ? String(line.baseline_amount) : "",
  );
  const [comparisonAmount, setComparisonAmount] = useState(
    line != null ? String(line.comparison_amount) : "",
  );
  const [varianceReason, setVarianceReason] = useState<VarianceReason>(
    line?.variance_reason ?? "other",
  );
  const [notes, setNotes] = useState(line?.notes ?? "");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setCostCategory(line?.cost_category ?? "hard_cost");
    setBaselineAmount(line != null ? String(line.baseline_amount) : "");
    setComparisonAmount(line != null ? String(line.comparison_amount) : "");
    setVarianceReason(line?.variance_reason ?? "other");
    setNotes(line?.notes ?? "");
    setError(null);
  }, [line]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const parsedBaseline = parseFloat(baselineAmount);
    const parsedComparison = parseFloat(comparisonAmount);
    if (baselineAmount.trim() === "" || isNaN(parsedBaseline)) {
      setError("A valid baseline amount is required.");
      return;
    }
    if (comparisonAmount.trim() === "" || isNaN(parsedComparison)) {
      setError("A valid comparison amount is required.");
      return;
    }

    setSubmitting(true);
    setError(null);

    const payload:
      | ConstructionCostComparisonLineCreate
      | ConstructionCostComparisonLineUpdate = {
      cost_category: costCategory,
      baseline_amount: parsedBaseline,
      comparison_amount: parsedComparison,
      variance_reason: varianceReason,
      notes: notes.trim() || null,
    };

    try {
      await onSubmit(payload);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to save comparison line.",
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
        aria-labelledby="tc-line-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="tc-line-modal-title" className={styles.modalTitle}>
          {isEdit ? "Edit Comparison Line" : "Add Comparison Line"}
        </h2>

        <form className={styles.modalForm} onSubmit={handleSubmit}>
          {/* Cost Category */}
          <div className={styles.formField}>
            <label htmlFor="tcl-category" className={styles.formLabel}>
              Cost Category
            </label>
            <select
              id="tcl-category"
              className={styles.formSelect}
              value={costCategory}
              onChange={(e) => setCostCategory(e.target.value as CostCategory)}
            >
              {COST_CATEGORY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.formRow}>
            {/* Baseline Amount */}
            <div className={styles.formField}>
              <label htmlFor="tcl-baseline" className={styles.formLabel}>
                Baseline Amount <span aria-hidden>*</span>
              </label>
              <input
                id="tcl-baseline"
                type="number"
                step="0.01"
                className={styles.formInput}
                value={baselineAmount}
                onChange={(e) => setBaselineAmount(e.target.value)}
                placeholder="0.00"
              />
            </div>

            {/* Comparison Amount */}
            <div className={styles.formField}>
              <label htmlFor="tcl-comparison" className={styles.formLabel}>
                Comparison Amount <span aria-hidden>*</span>
              </label>
              <input
                id="tcl-comparison"
                type="number"
                step="0.01"
                className={styles.formInput}
                value={comparisonAmount}
                onChange={(e) => setComparisonAmount(e.target.value)}
                placeholder="0.00"
              />
            </div>
          </div>

          {/* Variance Reason */}
          <div className={styles.formField}>
            <label htmlFor="tcl-reason" className={styles.formLabel}>
              Variance Reason
            </label>
            <select
              id="tcl-reason"
              className={styles.formSelect}
              value={varianceReason}
              onChange={(e) =>
                setVarianceReason(e.target.value as VarianceReason)
              }
            >
              {VARIANCE_REASON_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Notes */}
          <div className={styles.formField}>
            <label htmlFor="tcl-notes" className={styles.formLabel}>
              Notes
            </label>
            <textarea
              id="tcl-notes"
              className={styles.formTextarea}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional notes"
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
                  : "Adding…"
                : isEdit
                  ? "Update Line"
                  : "Add Line"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
