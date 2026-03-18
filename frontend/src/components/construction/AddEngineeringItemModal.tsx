/**
 * AddEngineeringItemModal — form modal for creating a new engineering item
 * within a construction scope.
 *
 * Engineering items represent technical tasks, consultant deliverables, and
 * consultant cost entries (the Engineering workspace).
 */

"use client";

import React, { useState } from "react";
import type { EngineeringItemCreate, EngineeringStatus } from "@/lib/construction-types";
import styles from "@/styles/construction.module.css";

interface AddEngineeringItemModalProps {
  scopeId: string;
  onSubmit: (data: EngineeringItemCreate) => Promise<void>;
  onClose: () => void;
}

export function AddEngineeringItemModal({
  scopeId,
  onSubmit,
  onClose,
}: AddEngineeringItemModalProps) {
  const [title, setTitle] = useState("");
  const [status, setStatus] = useState<EngineeringStatus>("pending");
  const [itemType, setItemType] = useState("");
  const [consultantName, setConsultantName] = useState("");
  const [consultantCost, setConsultantCost] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Title is required.");
      return;
    }
    if (consultantCost && Number(consultantCost) < 0) {
      setError("Consultant cost must be non-negative.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        title: title.trim(),
        status,
        item_type: itemType.trim() || null,
        consultant_name: consultantName.trim() || null,
        consultant_cost: consultantCost.trim() || null,
        target_date: targetDate || null,
        notes: notes.trim() || null,
      });
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to add engineering item.",
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
        aria-labelledby="add-eng-item-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="add-eng-item-title" className={styles.modalTitle}>
          Add Engineering Item
        </h2>
        <form className={styles.modalForm} onSubmit={handleSubmit}>
          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="eng-title" className={styles.formLabel}>
                Title <span aria-hidden>*</span>
              </label>
              <input
                id="eng-title"
                type="text"
                className={styles.formInput}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. IFC Drawing Issuance"
                required
              />
            </div>
            <div className={styles.formField}>
              <label htmlFor="eng-item-type" className={styles.formLabel}>
                Item Type
              </label>
              <input
                id="eng-item-type"
                type="text"
                className={styles.formInput}
                value={itemType}
                onChange={(e) => setItemType(e.target.value)}
                placeholder="e.g. deliverable, review, submission"
              />
            </div>
          </div>

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="eng-status" className={styles.formLabel}>
                Status
              </label>
              <select
                id="eng-status"
                className={styles.formSelect}
                value={status}
                onChange={(e) => setStatus(e.target.value as EngineeringStatus)}
              >
                <option value="pending">Pending</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
                <option value="delayed">Delayed</option>
                <option value="on_hold">On Hold</option>
              </select>
            </div>
            <div className={styles.formField}>
              <label htmlFor="eng-target-date" className={styles.formLabel}>
                Target Date
              </label>
              <input
                id="eng-target-date"
                type="date"
                className={styles.formInput}
                value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)}
              />
            </div>
          </div>

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="eng-consultant-name" className={styles.formLabel}>
                Consultant Name
              </label>
              <input
                id="eng-consultant-name"
                type="text"
                className={styles.formInput}
                value={consultantName}
                onChange={(e) => setConsultantName(e.target.value)}
                placeholder="e.g. XYZ Consulting"
              />
            </div>
            <div className={styles.formField}>
              <label htmlFor="eng-consultant-cost" className={styles.formLabel}>
                Consultant Cost
              </label>
              <input
                id="eng-consultant-cost"
                type="number"
                min={0}
                step="0.01"
                className={styles.formInput}
                value={consultantCost}
                onChange={(e) => setConsultantCost(e.target.value)}
                placeholder="0.00"
              />
            </div>
          </div>

          <div className={styles.formField}>
            <label htmlFor="eng-notes" className={styles.formLabel}>
              Notes
            </label>
            <textarea
              id="eng-notes"
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
              {submitting ? "Adding…" : "Add Engineering Item"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
