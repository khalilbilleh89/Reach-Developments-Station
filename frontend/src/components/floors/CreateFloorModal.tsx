"use client";

import React, { useEffect, useState } from "react";
import type { Floor, FloorCreate, FloorStatus, FloorUpdate } from "@/lib/floors-types";
import styles from "@/styles/projects.module.css";

interface CreateFloorModalProps {
  /** If provided, the modal is in edit mode and pre-fills fields. */
  floor?: Floor | null;
  onSubmit: (data: FloorCreate | FloorUpdate) => Promise<void>;
  onClose: () => void;
}

const STATUS_OPTIONS: { value: FloorStatus; label: string }[] = [
  { value: "planned", label: "Planned" },
  { value: "active", label: "Active" },
  { value: "completed", label: "Completed" },
  { value: "on_hold", label: "On Hold" },
];

/**
 * CreateFloorModal — modal form for creating or editing a floor.
 *
 * Used by the Project Detail Floors tab to add or modify floors.
 * Modal stays open on API failure and shows error inline.
 */
export function CreateFloorModal({ floor, onSubmit, onClose }: CreateFloorModalProps) {
  const isEdit = !!floor;

  const [name, setName] = useState(floor?.name ?? "");
  const [code, setCode] = useState(floor?.code ?? "");
  const [sequenceNumber, setSequenceNumber] = useState(
    floor?.sequence_number !== undefined ? String(floor.sequence_number) : "",
  );
  const [levelNumber, setLevelNumber] = useState(
    floor?.level_number !== undefined && floor.level_number !== null
      ? String(floor.level_number)
      : "",
  );
  const [status, setStatus] = useState<FloorStatus>(floor?.status ?? "planned");
  const [description, setDescription] = useState(floor?.description ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setName(floor?.name ?? "");
    setCode(floor?.code ?? "");
    setSequenceNumber(
      floor?.sequence_number !== undefined ? String(floor.sequence_number) : "",
    );
    setLevelNumber(
      floor?.level_number !== undefined && floor.level_number !== null
        ? String(floor.level_number)
        : "",
    );
    setStatus(floor?.status ?? "planned");
    setDescription(floor?.description ?? "");
    setError(null);
  }, [floor]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError("Floor name is required.");
      return;
    }
    if (!isEdit && !code.trim()) {
      setError("Floor code is required.");
      return;
    }
    if (!isEdit) {
      const seqNum = Number(sequenceNumber);
      if (!sequenceNumber.trim() || !Number.isInteger(seqNum) || seqNum < 1) {
        setError("Sequence number must be a positive integer (≥ 1).");
        return;
      }
    }

    const levelNum =
      levelNumber.trim() !== "" ? Number(levelNumber) : null;
    if (
      levelNumber.trim() !== "" &&
      (levelNum === null || !Number.isInteger(levelNum))
    ) {
      setError("Level number must be an integer.");
      return;
    }

    const data: FloorCreate | FloorUpdate = isEdit
      ? ({
          name: name.trim(),
          level_number: levelNum,
          status,
          description: description.trim() || null,
        } as FloorUpdate)
      : ({
          name: name.trim(),
          code: code.trim(),
          sequence_number: Number(sequenceNumber),
          level_number: levelNum,
          status,
          description: description.trim() || null,
        } as FloorCreate);

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
    <div
      className={styles.modalOverlay}
      role="dialog"
      aria-modal="true"
      aria-labelledby="floor-modal-title"
    >
      <div className={styles.modal}>
        <h2 id="floor-modal-title" className={styles.modalTitle}>
          {isEdit ? "Edit Floor" : "Add Floor"}
        </h2>

        <form className={styles.modalForm} onSubmit={handleSubmit} noValidate>
          {error && (
            <div className={styles.modalError} role="alert">
              {error}
            </div>
          )}

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="floor-name" className={styles.formLabel}>
                Floor Name <span aria-hidden="true">*</span>
              </label>
              <input
                id="floor-name"
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
              <label htmlFor="floor-code" className={styles.formLabel}>
                Code {!isEdit && <span aria-hidden="true">*</span>}
              </label>
              <input
                id="floor-code"
                type="text"
                className={styles.formInput}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                maxLength={100}
                placeholder="e.g. FL-01"
                disabled={isEdit}
                required={!isEdit}
              />
            </div>
          </div>

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="floor-sequence" className={styles.formLabel}>
                Sequence Number {!isEdit && <span aria-hidden="true">*</span>}
              </label>
              <input
                id="floor-sequence"
                type="number"
                className={styles.formInput}
                value={sequenceNumber}
                onChange={(e) => setSequenceNumber(e.target.value)}
                min={1}
                step={1}
                placeholder="e.g. 1"
                disabled={isEdit}
                required={!isEdit}
              />
            </div>

            <div className={styles.formField}>
              <label htmlFor="floor-level" className={styles.formLabel}>
                Level Number
              </label>
              <input
                id="floor-level"
                type="number"
                className={styles.formInput}
                value={levelNumber}
                onChange={(e) => setLevelNumber(e.target.value)}
                step={1}
                placeholder="e.g. 0 for Ground"
              />
            </div>
          </div>

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="floor-status" className={styles.formLabel}>
                Status
              </label>
              <select
                id="floor-status"
                className={styles.formSelect}
                value={status}
                onChange={(e) => setStatus(e.target.value as FloorStatus)}
              >
                {STATUS_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className={styles.formField}>
            <label htmlFor="floor-description" className={styles.formLabel}>
              Description
            </label>
            <textarea
              id="floor-description"
              className={styles.formTextarea}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
              rows={3}
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
              {submitting
                ? "Saving\u2026"
                : isEdit
                  ? "Save Changes"
                  : "Add Floor"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
