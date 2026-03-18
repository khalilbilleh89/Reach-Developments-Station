/**
 * CreateScopeModal — form modal for creating a new construction scope.
 */

"use client";

import React, { useState } from "react";
import type { ConstructionScopeCreate, ConstructionStatus } from "@/lib/construction-types";
import styles from "@/styles/construction.module.css";

interface CreateScopeModalProps {
  onSubmit: (data: ConstructionScopeCreate) => Promise<void>;
  onClose: () => void;
}

export function CreateScopeModal({ onSubmit, onClose }: CreateScopeModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [projectId, setProjectId] = useState("");
  const [status, setStatus] = useState<ConstructionStatus>("planned");
  const [startDate, setStartDate] = useState("");
  const [targetEndDate, setTargetEndDate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Name is required.");
      return;
    }
    if (!projectId.trim()) {
      setError("Project ID is required.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        name: name.trim(),
        description: description.trim() || null,
        project_id: projectId.trim(),
        status,
        start_date: startDate || null,
        target_end_date: targetEndDate || null,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create scope.");
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
        aria-labelledby="create-scope-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="create-scope-title" className={styles.modalTitle}>Create Construction Scope</h2>
        <form className={styles.modalForm} onSubmit={handleSubmit}>
          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="scope-name" className={styles.formLabel}>
                Name <span aria-hidden>*</span>
              </label>
              <input
                id="scope-name"
                type="text"
                className={styles.formInput}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Civil Works"
                required
              />
            </div>
            <div className={styles.formField}>
              <label htmlFor="scope-status" className={styles.formLabel}>
                Status
              </label>
              <select
                id="scope-status"
                className={styles.formSelect}
                value={status}
                onChange={(e) => setStatus(e.target.value as ConstructionStatus)}
              >
                <option value="planned">Planned</option>
                <option value="in_progress">In Progress</option>
                <option value="on_hold">On Hold</option>
                <option value="completed">Completed</option>
              </select>
            </div>
          </div>

          <div className={styles.formField}>
            <label htmlFor="scope-project-id" className={styles.formLabel}>
              Project ID <span aria-hidden>*</span>
            </label>
            <input
              id="scope-project-id"
              type="text"
              className={styles.formInput}
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              placeholder="Project UUID"
              required
            />
          </div>

          <div className={styles.formField}>
            <label htmlFor="scope-description" className={styles.formLabel}>
              Description
            </label>
            <textarea
              id="scope-description"
              className={styles.formTextarea}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
            />
          </div>

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="scope-start-date" className={styles.formLabel}>
                Start Date
              </label>
              <input
                id="scope-start-date"
                type="date"
                className={styles.formInput}
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div className={styles.formField}>
              <label htmlFor="scope-end-date" className={styles.formLabel}>
                Target End Date
              </label>
              <input
                id="scope-end-date"
                type="date"
                className={styles.formInput}
                value={targetEndDate}
                onChange={(e) => setTargetEndDate(e.target.value)}
              />
            </div>
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
              {submitting ? "Creating…" : "Create Scope"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
