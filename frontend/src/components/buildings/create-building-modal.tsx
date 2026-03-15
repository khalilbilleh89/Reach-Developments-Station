"use client";

import React, { useEffect, useState } from "react";
import type {
  Building,
  BuildingCreate,
  BuildingStatus,
  BuildingUpdate,
} from "@/lib/buildings-types";
import styles from "@/styles/projects.module.css";

interface CreateBuildingModalProps {
  /** If provided, the modal is in edit mode and pre-fills fields. */
  building?: Building | null;
  onSubmit: (data: BuildingCreate | BuildingUpdate) => Promise<void>;
  onClose: () => void;
}

const STATUS_OPTIONS: { value: BuildingStatus; label: string }[] = [
  { value: "planned", label: "Planned" },
  { value: "under_construction", label: "Under Construction" },
  { value: "completed", label: "Completed" },
  { value: "on_hold", label: "On Hold" },
];

/**
 * CreateBuildingModal — modal form for creating or editing a building.
 *
 * Used by the Project Detail Buildings tab to add or modify buildings.
 */
export function CreateBuildingModal({
  building,
  onSubmit,
  onClose,
}: CreateBuildingModalProps) {
  const isEdit = !!building;

  const [name, setName] = useState(building?.name ?? "");
  const [code, setCode] = useState(building?.code ?? "");
  const [floorsCount, setFloorsCount] = useState(
    building?.floors_count !== undefined && building.floors_count !== null
      ? String(building.floors_count)
      : "",
  );
  const [status, setStatus] = useState<BuildingStatus>(
    building?.status ?? "planned",
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setName(building?.name ?? "");
    setCode(building?.code ?? "");
    setFloorsCount(
      building?.floors_count !== undefined && building.floors_count !== null
        ? String(building.floors_count)
        : "",
    );
    setStatus(building?.status ?? "planned");
    setError(null);
  }, [building]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError("Building name is required.");
      return;
    }
    if (!isEdit && !code.trim()) {
      setError("Building code is required.");
      return;
    }

    const floors =
      floorsCount.trim() !== "" ? parseInt(floorsCount, 10) : null;
    if (floorsCount.trim() !== "" && (isNaN(floors!) || floors! < 1)) {
      setError("Floors count must be a positive integer.");
      return;
    }

    const data: BuildingCreate | BuildingUpdate = isEdit
      ? ({
          name: name.trim(),
          floors_count: floors,
          status,
        } as BuildingUpdate)
      : ({
          name: name.trim(),
          code: code.trim(),
          floors_count: floors,
          status,
        } as BuildingCreate);

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
      aria-labelledby="building-modal-title"
    >
      <div className={styles.modal}>
        <h2 id="building-modal-title" className={styles.modalTitle}>
          {isEdit ? "Edit Building" : "Add Building"}
        </h2>

        <form className={styles.modalForm} onSubmit={handleSubmit} noValidate>
          {error && (
            <div className={styles.modalError} role="alert">
              {error}
            </div>
          )}

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="building-name" className={styles.formLabel}>
                Building Name <span aria-hidden="true">*</span>
              </label>
              <input
                id="building-name"
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
              <label htmlFor="building-code" className={styles.formLabel}>
                Code {!isEdit && <span aria-hidden="true">*</span>}
              </label>
              <input
                id="building-code"
                type="text"
                className={styles.formInput}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                maxLength={100}
                placeholder="e.g. TWR-A"
                disabled={isEdit}
                required={!isEdit}
              />
            </div>
          </div>

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="building-floors" className={styles.formLabel}>
                Total Floors
              </label>
              <input
                id="building-floors"
                type="number"
                className={styles.formInput}
                value={floorsCount}
                onChange={(e) => setFloorsCount(e.target.value)}
                min={1}
                step={1}
                placeholder="e.g. 20"
              />
            </div>

            <div className={styles.formField}>
              <label htmlFor="building-status" className={styles.formLabel}>
                Status
              </label>
              <select
                id="building-status"
                className={styles.formSelect}
                value={status}
                onChange={(e) => setStatus(e.target.value as BuildingStatus)}
              >
                {STATUS_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
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
                  : "Add Building"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
