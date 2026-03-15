"use client";

import React, { useEffect, useState } from "react";
import type { Phase, PhaseCreate, PhaseStatus, PhaseUpdate } from "@/lib/phases-types";
import styles from "@/styles/projects.module.css";

interface CreatePhaseModalProps {
  /** If provided, the modal is in edit mode and pre-fills fields. */
  phase?: Phase | null;
  onSubmit: (data: PhaseCreate | PhaseUpdate) => Promise<void>;
  onClose: () => void;
}

const STATUS_OPTIONS: { value: PhaseStatus; label: string }[] = [
  { value: "planned", label: "Planned" },
  { value: "active", label: "Active" },
  { value: "completed", label: "Completed" },
];

/**
 * CreatePhaseModal — modal form for creating or editing a phase.
 *
 * Used by the Project Detail page to add or modify phases.
 */
export function CreatePhaseModal({
  phase,
  onSubmit,
  onClose,
}: CreatePhaseModalProps) {
  const isEdit = !!phase;

  const [name, setName] = useState(phase?.name ?? "");
  const [code, setCode] = useState(phase?.code ?? "");
  const [sequence, setSequence] = useState(
    phase?.sequence !== undefined ? String(phase.sequence) : "",
  );
  const [status, setStatus] = useState<PhaseStatus>(
    phase?.status ?? "planned",
  );
  const [startDate, setStartDate] = useState(phase?.start_date ?? "");
  const [endDate, setEndDate] = useState(phase?.end_date ?? "");
  const [description, setDescription] = useState(phase?.description ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync fields when switching between phases in edit mode
  useEffect(() => {
    setName(phase?.name ?? "");
    setCode(phase?.code ?? "");
    setSequence(phase?.sequence !== undefined ? String(phase.sequence) : "");
    setStatus(phase?.status ?? "planned");
    setStartDate(phase?.start_date ?? "");
    setEndDate(phase?.end_date ?? "");
    setDescription(phase?.description ?? "");
    setError(null);
  }, [phase]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError("Phase name is required.");
      return;
    }
    const seq = parseInt(sequence, 10);
    if (!sequence || isNaN(seq) || seq < 1) {
      setError("Sequence must be a positive integer.");
      return;
    }
    if (startDate && endDate && endDate < startDate) {
      setError("End date must be on or after start date.");
      return;
    }

    const data: PhaseCreate = {
      name: name.trim(),
      code: code.trim() || null,
      sequence: seq,
      status,
      start_date: startDate || null,
      end_date: endDate || null,
      description: description.trim() || null,
    };

    setSubmitting(true);
    try {
      await onSubmit(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An error occurred.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.modalOverlay} role="dialog" aria-modal="true" aria-labelledby="phase-modal-title">
      <div className={styles.modal}>
        <h2 id="phase-modal-title" className={styles.modalTitle}>
          {isEdit ? "Edit Phase" : "Add Phase"}
        </h2>

        <form className={styles.modalForm} onSubmit={handleSubmit} noValidate>
          {error && <div className={styles.modalError} role="alert">{error}</div>}

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="phase-name" className={styles.formLabel}>
                Phase Name <span aria-hidden="true">*</span>
              </label>
              <input
                id="phase-name"
                type="text"
                className={styles.formInput}
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={255}
                required
                autoFocus
              />
            </div>

            <div className={styles.formField}>
              <label htmlFor="phase-code" className={styles.formLabel}>
                Code
              </label>
              <input
                id="phase-code"
                type="text"
                className={styles.formInput}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                maxLength={100}
                placeholder="e.g. PH-01"
              />
            </div>
          </div>

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="phase-sequence" className={styles.formLabel}>
                Sequence <span aria-hidden="true">*</span>
              </label>
              <input
                id="phase-sequence"
                type="number"
                className={styles.formInput}
                value={sequence}
                onChange={(e) => setSequence(e.target.value)}
                min={1}
                step={1}
                required
              />
            </div>

            <div className={styles.formField}>
              <label htmlFor="phase-status" className={styles.formLabel}>
                Status
              </label>
              <select
                id="phase-status"
                className={styles.formSelect}
                value={status}
                onChange={(e) => setStatus(e.target.value as PhaseStatus)}
              >
                {STATUS_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="phase-start" className={styles.formLabel}>
                Launch Date
              </label>
              <input
                id="phase-start"
                type="date"
                className={styles.formInput}
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>

            <div className={styles.formField}>
              <label htmlFor="phase-end" className={styles.formLabel}>
                Target Completion
              </label>
              <input
                id="phase-end"
                type="date"
                className={styles.formInput}
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
          </div>

          <div className={styles.formField}>
            <label htmlFor="phase-description" className={styles.formLabel}>
              Description
            </label>
            <textarea
              id="phase-description"
              className={styles.formTextarea}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description of this phase…"
            />
          </div>

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
              {submitting ? "Saving…" : isEdit ? "Save Changes" : "Add Phase"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
