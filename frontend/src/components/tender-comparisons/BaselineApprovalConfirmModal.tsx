/**
 * BaselineApprovalConfirmModal — confirmation dialog before approving a
 * tender comparison as the official project baseline (PR-V6-13).
 *
 * Displayed when the user clicks "Approve as Baseline" on a comparison set.
 * Requires explicit acknowledgement before the state-mutation is submitted.
 */

"use client";

import React from "react";
import styles from "@/styles/construction.module.css";

interface BaselineApprovalConfirmModalProps {
  comparisonTitle: string;
  hasExistingBaseline: boolean;
  isSubmitting: boolean;
  error: string | null;
  onConfirm: () => void;
  onClose: () => void;
}

export function BaselineApprovalConfirmModal({
  comparisonTitle,
  hasExistingBaseline,
  isSubmitting,
  error,
  onConfirm,
  onClose,
}: BaselineApprovalConfirmModalProps) {
  return (
    <div
      className={styles.modalOverlay}
      role="dialog"
      aria-modal="true"
      aria-labelledby="baseline-confirm-title"
      data-testid="baseline-approval-modal"
    >
      <div className={styles.modal}>
        <h2
          className={styles.modalTitle}
          id="baseline-confirm-title"
        >
          Approve as Baseline
        </h2>

        <div className={styles.modalForm}>
          <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--color-text)" }}>
            This will mark{" "}
            <strong>&ldquo;{comparisonTitle}&rdquo;</strong> as the official
            project baseline.
          </p>

          {hasExistingBaseline && (
            <p
              style={{
                margin: 0,
                fontSize: "var(--font-size-sm)",
                color: "#92400e",
                background: "#fef3c7",
                padding: "var(--space-3)",
                borderRadius: "var(--card-radius)",
                border: "1px solid #fcd34d",
              }}
              data-testid="replace-baseline-warning"
            >
              ⚠ An existing approved baseline will be replaced. This action
              will be recorded for audit history.
            </p>
          )}

          {!hasExistingBaseline && (
            <p
              style={{
                margin: 0,
                fontSize: "var(--font-size-sm)",
                color: "var(--color-text-muted)",
              }}
            >
              Once approved, this comparison set becomes the control baseline
              for downstream construction monitoring and variance reporting.
              The approval will be recorded with your user ID and timestamp.
            </p>
          )}

          {error && (
            <div className={styles.modalError} role="alert">
              {error}
            </div>
          )}
        </div>

        <div className={styles.modalActions}>
          <button
            className={styles.cancelButton}
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button
            className={styles.submitButton}
            onClick={onConfirm}
            disabled={isSubmitting}
            data-testid="confirm-approve-baseline"
          >
            {isSubmitting ? "Approving…" : "Confirm Approval"}
          </button>
        </div>
      </div>
    </div>
  );
}
