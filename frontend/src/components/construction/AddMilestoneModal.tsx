/**
 * AddMilestoneModal — form modal for creating a new construction milestone.
 */

"use client";

import React, { useState } from "react";
import type { ConstructionMilestoneCreate, MilestoneStatus } from "@/lib/construction-types";
import styles from "@/styles/construction.module.css";

interface AddMilestoneModalProps {
  scopeId: string;
  nextSequence: number;
  onSubmit: (data: ConstructionMilestoneCreate) => Promise<void>;
  onClose: () => void;
}

export function AddMilestoneModal({
  scopeId,
  nextSequence,
  onSubmit,
  onClose,
}: AddMilestoneModalProps) {
  const [name, setName] = useState("");
  const [sequence, setSequence] = useState(String(nextSequence));
  const [status, setStatus] = useState<MilestoneStatus>("pending");
  const [targetDate, setTargetDate] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Name is required.");
      return;
    }
    const seq = parseInt(sequence, 10);
    if (!seq || seq < 1) {
      setError("Sequence must be a positive integer.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        scope_id: scopeId,
        name: name.trim(),
        sequence: seq,
        status,
        target_date: targetDate || null,
        notes: notes.trim() || null,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to add milestone.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <h2 className={styles.modalTitle}>Add Milestone</h2>
        <form className={styles.modalForm} onSubmit={handleSubmit}>
          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="ms-name" className={styles.formLabel}>
                Name <span aria-hidden>*</span>
              </label>
              <input
                id="ms-name"
                type="text"
                className={styles.formInput}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Foundation Complete"
                required
              />
            </div>
            <div className={styles.formField}>
              <label htmlFor="ms-sequence" className={styles.formLabel}>
                Sequence <span aria-hidden>*</span>
              </label>
              <input
                id="ms-sequence"
                type="number"
                min={1}
                className={styles.formInput}
                value={sequence}
                onChange={(e) => setSequence(e.target.value)}
                required
              />
            </div>
          </div>

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="ms-status" className={styles.formLabel}>
                Status
              </label>
              <select
                id="ms-status"
                className={styles.formSelect}
                value={status}
                onChange={(e) => setStatus(e.target.value as MilestoneStatus)}
              >
                <option value="pending">Pending</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
                <option value="delayed">Delayed</option>
              </select>
            </div>
            <div className={styles.formField}>
              <label htmlFor="ms-target-date" className={styles.formLabel}>
                Target Date
              </label>
              <input
                id="ms-target-date"
                type="date"
                className={styles.formInput}
                value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)}
              />
            </div>
          </div>

          <div className={styles.formField}>
            <label htmlFor="ms-notes" className={styles.formLabel}>
              Notes
            </label>
            <textarea
              id="ms-notes"
              className={styles.formTextarea}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional notes"
            />
          </div>

          {error && <div className={styles.modalError}>{error}</div>}

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
              {submitting ? "Adding…" : "Add Milestone"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
