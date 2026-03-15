"use client";

import React, { useEffect, useState } from "react";
import type { UnitCreateForFloor, UnitListItem, UnitStatus, UnitType, UnitUpdate } from "@/lib/units-types";
import styles from "@/styles/projects.module.css";

interface CreateUnitModalProps {
  /** If provided, the modal is in edit mode and pre-fills fields. */
  unit?: UnitListItem | null;
  onSubmit: (data: UnitCreateForFloor | UnitUpdate) => Promise<void>;
  onClose: () => void;
}

const UNIT_TYPE_OPTIONS: { value: UnitType; label: string }[] = [
  { value: "studio", label: "Studio" },
  { value: "one_bedroom", label: "1 Bedroom" },
  { value: "two_bedroom", label: "2 Bedroom" },
  { value: "three_bedroom", label: "3 Bedroom" },
  { value: "four_bedroom", label: "4 Bedroom" },
  { value: "villa", label: "Villa" },
  { value: "townhouse", label: "Townhouse" },
  { value: "retail", label: "Retail" },
  { value: "office", label: "Office" },
  { value: "penthouse", label: "Penthouse" },
];

const STATUS_OPTIONS: { value: UnitStatus; label: string }[] = [
  { value: "available", label: "Available" },
  { value: "reserved", label: "Reserved" },
  { value: "under_contract", label: "Under Contract" },
  { value: "registered", label: "Registered" },
];

/**
 * CreateUnitModal — modal form for creating or editing a unit.
 *
 * Used by the Project Detail Units tab to add or modify units under a floor.
 * Modal stays open on API failure and shows error inline.
 */
export function CreateUnitModal({ unit, onSubmit, onClose }: CreateUnitModalProps) {
  const isEdit = !!unit;

  const [unitNumber, setUnitNumber] = useState(unit?.unit_number ?? "");
  const [unitType, setUnitType] = useState<UnitType>(unit?.unit_type ?? "studio");
  const [status, setStatus] = useState<UnitStatus>(unit?.status ?? "available");
  const [internalArea, setInternalArea] = useState(
    unit?.internal_area !== undefined ? String(unit.internal_area) : "",
  );
  const [balconyArea, setBalconyArea] = useState(
    unit?.balcony_area != null ? String(unit.balcony_area) : "",
  );
  const [terraceArea, setTerraceArea] = useState(
    unit?.terrace_area != null ? String(unit.terrace_area) : "",
  );
  const [grossArea, setGrossArea] = useState(
    unit?.gross_area != null ? String(unit.gross_area) : "",
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setUnitNumber(unit?.unit_number ?? "");
    setUnitType(unit?.unit_type ?? "studio");
    setStatus(unit?.status ?? "available");
    setInternalArea(unit?.internal_area !== undefined ? String(unit.internal_area) : "");
    setBalconyArea(unit?.balcony_area != null ? String(unit.balcony_area) : "");
    setTerraceArea(unit?.terrace_area != null ? String(unit.terrace_area) : "");
    setGrossArea(unit?.gross_area != null ? String(unit.gross_area) : "");
    setError(null);
  }, [unit]);

  const parseOptionalFloat = (val: string): number | null => {
    const trimmed = val.trim();
    if (trimmed === "") return null;
    const n = parseFloat(trimmed);
    return isNaN(n) ? null : n;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!isEdit && !unitNumber.trim()) {
      setError("Unit number is required.");
      return;
    }

    const areaVal = parseFloat(internalArea);
    if (!internalArea.trim() || isNaN(areaVal) || areaVal <= 0) {
      setError("Internal area must be a positive number.");
      return;
    }

    const data: UnitCreateForFloor | UnitUpdate = isEdit
      ? ({
          unit_type: unitType,
          status,
          internal_area: areaVal,
          balcony_area: parseOptionalFloat(balconyArea),
          terrace_area: parseOptionalFloat(terraceArea),
          gross_area: parseOptionalFloat(grossArea),
        } as UnitUpdate)
      : ({
          unit_number: unitNumber.trim(),
          unit_type: unitType,
          status,
          internal_area: areaVal,
          balcony_area: parseOptionalFloat(balconyArea),
          terrace_area: parseOptionalFloat(terraceArea),
          gross_area: parseOptionalFloat(grossArea),
        } as UnitCreateForFloor);

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
      aria-labelledby="unit-modal-title"
    >
      <div className={styles.modal}>
        <h2 id="unit-modal-title" className={styles.modalTitle}>
          {isEdit ? "Edit Unit" : "Add Unit"}
        </h2>

        <form className={styles.modalForm} onSubmit={handleSubmit} noValidate>
          {error && (
            <div className={styles.modalError} role="alert">
              {error}
            </div>
          )}

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="unit-number" className={styles.formLabel}>
                Unit Number {!isEdit && <span aria-hidden="true">*</span>}
              </label>
              <input
                id="unit-number"
                type="text"
                className={styles.formInput}
                value={unitNumber}
                onChange={(e) => setUnitNumber(e.target.value)}
                maxLength={50}
                placeholder="e.g. 101"
                disabled={isEdit}
                required={!isEdit}
                autoFocus
              />
            </div>

            <div className={styles.formField}>
              <label htmlFor="unit-type" className={styles.formLabel}>
                Unit Type <span aria-hidden="true">*</span>
              </label>
              <select
                id="unit-type"
                className={styles.formSelect}
                value={unitType}
                onChange={(e) => setUnitType(e.target.value as UnitType)}
              >
                {UNIT_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="unit-internal-area" className={styles.formLabel}>
                Internal Area (sqm) <span aria-hidden="true">*</span>
              </label>
              <input
                id="unit-internal-area"
                type="number"
                className={styles.formInput}
                value={internalArea}
                onChange={(e) => setInternalArea(e.target.value)}
                min={0.01}
                step={0.01}
                placeholder="e.g. 75.5"
                required
              />
            </div>

            <div className={styles.formField}>
              <label htmlFor="unit-gross-area" className={styles.formLabel}>
                Gross Area (sqm)
              </label>
              <input
                id="unit-gross-area"
                type="number"
                className={styles.formInput}
                value={grossArea}
                onChange={(e) => setGrossArea(e.target.value)}
                min={0}
                step={0.01}
                placeholder="Optional"
              />
            </div>
          </div>

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="unit-balcony-area" className={styles.formLabel}>
                Balcony Area (sqm)
              </label>
              <input
                id="unit-balcony-area"
                type="number"
                className={styles.formInput}
                value={balconyArea}
                onChange={(e) => setBalconyArea(e.target.value)}
                min={0}
                step={0.01}
                placeholder="Optional"
              />
            </div>

            <div className={styles.formField}>
              <label htmlFor="unit-terrace-area" className={styles.formLabel}>
                Terrace Area (sqm)
              </label>
              <input
                id="unit-terrace-area"
                type="number"
                className={styles.formInput}
                value={terraceArea}
                onChange={(e) => setTerraceArea(e.target.value)}
                min={0}
                step={0.01}
                placeholder="Optional"
              />
            </div>
          </div>

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="unit-status" className={styles.formLabel}>
                Status
              </label>
              <select
                id="unit-status"
                className={styles.formSelect}
                value={status}
                onChange={(e) => setStatus(e.target.value as UnitStatus)}
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
              {submitting ? "Saving\u2026" : isEdit ? "Save Changes" : "Add Unit"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
