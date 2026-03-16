"use client";

import React, { useEffect, useState } from "react";
import type {
  FloorPremiumCategory,
  Orientation,
  OutdoorAreaPremium,
  UnitQualitativeAttributes,
  UnitQualitativeAttributesSave,
  ViewType,
} from "@/lib/units-types";
import styles from "@/styles/projects.module.css";

interface EditAttributesModalProps {
  /** The unit ID whose attributes are being edited. */
  unitId: string;
  /** Unit number displayed in the modal title. */
  unitNumber: string;
  /** Existing attributes record (null when no record exists yet). */
  existing: UnitQualitativeAttributes | null;
  /** Called with the save payload when the form is submitted. */
  onSave: (unitId: string, data: UnitQualitativeAttributesSave) => Promise<void>;
  onClose: () => void;
}

const VIEW_TYPE_OPTIONS: { value: ViewType; label: string }[] = [
  { value: "city", label: "City" },
  { value: "sea", label: "Sea" },
  { value: "park", label: "Park" },
  { value: "interior", label: "Interior" },
];

const FLOOR_CATEGORY_OPTIONS: { value: FloorPremiumCategory; label: string }[] = [
  { value: "standard", label: "Standard" },
  { value: "premium", label: "Premium" },
  { value: "penthouse", label: "Penthouse" },
];

const ORIENTATION_OPTIONS: { value: Orientation; label: string }[] = [
  { value: "N", label: "North" },
  { value: "S", label: "South" },
  { value: "E", label: "East" },
  { value: "W", label: "West" },
  { value: "NE", label: "North-East" },
  { value: "NW", label: "North-West" },
  { value: "SE", label: "South-East" },
  { value: "SW", label: "South-West" },
];

const OUTDOOR_PREMIUM_OPTIONS: { value: OutdoorAreaPremium; label: string }[] = [
  { value: "none", label: "None" },
  { value: "balcony", label: "Balcony" },
  { value: "terrace", label: "Terrace" },
  { value: "roof_garden", label: "Roof Garden" },
];

/**
 * EditAttributesModal — modal form for editing qualitative pricing attributes.
 *
 * Captures view type, corner unit status, floor premium category, orientation,
 * outdoor area premium treatment, upgrade flag, and analyst notes.
 *
 * Attributes do not automatically adjust pricing — they provide structured
 * context for pricing decisions and future automation.
 */
export function EditAttributesModal({
  unitId,
  unitNumber,
  existing,
  onSave,
  onClose,
}: EditAttributesModalProps) {
  const [viewType, setViewType] = useState<ViewType | "">(
    existing?.view_type ?? "",
  );
  const [cornerUnit, setCornerUnit] = useState<boolean>(
    existing?.corner_unit ?? false,
  );
  const [floorCategory, setFloorCategory] = useState<FloorPremiumCategory | "">(
    existing?.floor_premium_category ?? "",
  );
  const [orientation, setOrientation] = useState<Orientation | "">(
    existing?.orientation ?? "",
  );
  const [outdoorPremium, setOutdoorPremium] = useState<OutdoorAreaPremium | "">(
    existing?.outdoor_area_premium ?? "",
  );
  const [upgradeFlag, setUpgradeFlag] = useState<boolean>(
    existing?.upgrade_flag ?? false,
  );
  const [notes, setNotes] = useState(existing?.notes ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Re-initialise state when the existing record changes
  useEffect(() => {
    setViewType(existing?.view_type ?? "");
    setCornerUnit(existing?.corner_unit ?? false);
    setFloorCategory(existing?.floor_premium_category ?? "");
    setOrientation(existing?.orientation ?? "");
    setOutdoorPremium(existing?.outdoor_area_premium ?? "");
    setUpgradeFlag(existing?.upgrade_flag ?? false);
    setNotes(existing?.notes ?? "");
    setError(null);
  }, [existing]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    const payload: UnitQualitativeAttributesSave = {
      view_type: viewType || null,
      corner_unit: cornerUnit,
      floor_premium_category: floorCategory || null,
      orientation: orientation || null,
      outdoor_area_premium: outdoorPremium || null,
      upgrade_flag: upgradeFlag,
      notes: notes.trim() || null,
    };

    try {
      await onSave(unitId, payload);
      onClose();
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to save attributes. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className={styles.modalOverlay}
      role="dialog"
      aria-modal="true"
      aria-labelledby="ea-modal-title"
    >
      <div className={styles.modal} style={{ maxWidth: 600 }}>
        <h2 id="ea-modal-title" className={styles.modalTitle}>
          {existing ? "Edit Attributes" : "Set Attributes"} — Unit {unitNumber}
        </h2>

        <form onSubmit={handleSubmit} className={styles.modalForm} noValidate>
          {/* View Type + Floor Premium Category */}
          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="ea-view-type" className={styles.formLabel}>
                View Type
              </label>
              <select
                id="ea-view-type"
                className={styles.formSelect}
                value={viewType}
                onChange={(e) => setViewType(e.target.value as ViewType | "")}
                disabled={submitting}
              >
                <option value="">— Not set —</option>
                {VIEW_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div className={styles.formField}>
              <label htmlFor="ea-floor-category" className={styles.formLabel}>
                Floor Category
              </label>
              <select
                id="ea-floor-category"
                className={styles.formSelect}
                value={floorCategory}
                onChange={(e) =>
                  setFloorCategory(e.target.value as FloorPremiumCategory | "")
                }
                disabled={submitting}
              >
                <option value="">— Not set —</option>
                {FLOOR_CATEGORY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Orientation + Outdoor Area Premium */}
          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="ea-orientation" className={styles.formLabel}>
                Orientation
              </label>
              <select
                id="ea-orientation"
                className={styles.formSelect}
                value={orientation}
                onChange={(e) =>
                  setOrientation(e.target.value as Orientation | "")
                }
                disabled={submitting}
              >
                <option value="">— Not set —</option>
                {ORIENTATION_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div className={styles.formField}>
              <label htmlFor="ea-outdoor-premium" className={styles.formLabel}>
                Outdoor Premium
              </label>
              <select
                id="ea-outdoor-premium"
                className={styles.formSelect}
                value={outdoorPremium}
                onChange={(e) =>
                  setOutdoorPremium(e.target.value as OutdoorAreaPremium | "")
                }
                disabled={submitting}
              >
                <option value="">— Not set —</option>
                {OUTDOOR_PREMIUM_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Corner Unit + Upgrade Flag toggles */}
          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label className={styles.formLabel}>Corner Unit</label>
              <label
                style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}
              >
                <input
                  type="checkbox"
                  checked={cornerUnit}
                  onChange={(e) => setCornerUnit(e.target.checked)}
                  disabled={submitting}
                />
                {cornerUnit ? "Yes — corner unit" : "No — standard position"}
              </label>
            </div>

            <div className={styles.formField}>
              <label className={styles.formLabel}>Upgrade Flag</label>
              <label
                style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}
              >
                <input
                  type="checkbox"
                  checked={upgradeFlag}
                  onChange={(e) => setUpgradeFlag(e.target.checked)}
                  disabled={submitting}
                />
                {upgradeFlag ? "Yes — upgraded finishes" : "No — standard finishes"}
              </label>
            </div>
          </div>

          {/* Notes */}
          <div className={styles.formRow}>
            <div className={styles.formField} style={{ flex: "1 1 100%", gridColumn: "1 / -1" }}>
              <label htmlFor="ea-notes" className={styles.formLabel}>
                Notes
              </label>
              <textarea
                id="ea-notes"
                className={styles.formTextarea}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                maxLength={2000}
                placeholder="Optional analyst notes about this unit's pricing attributes…"
                disabled={submitting}
              />
            </div>
          </div>

          {error && (
            <p className={styles.modalError} role="alert">
              {error}
            </p>
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
                ? "Saving…"
                : existing
                  ? "Update Attributes"
                  : "Set Attributes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
