"use client";

import React, { useEffect, useState } from "react";
import type {
  FloorPremiumCategory,
  Orientation,
  OutdoorAreaPremium,
  UnitDetail,
  UnitDynamicAttributeValue,
  UnitDynamicAttributesSaveRequest,
  UnitQualitativeAttributes,
  UnitQualitativeAttributesSave,
  UnitUpdate,
  ViewType,
} from "@/lib/units-types";
import type { ProjectAttributeDefinition } from "@/lib/projects-types";
import styles from "@/styles/projects.module.css";

interface EditAttributesModalProps {
  /** The unit ID whose attributes are being edited. */
  unitId: string;
  /** Unit number displayed in the modal title. */
  unitNumber: string;
  /** Existing qualitative attributes record (null when no record exists yet). */
  existing: UnitQualitativeAttributes | null;
  /** Current unit data used to pre-populate apartment attribute fields. */
  unitData?: UnitDetail | null;
  /** Project-defined attribute definitions (with options) for this unit's project. */
  projectDefinitions?: ProjectAttributeDefinition[];
  /** Existing dynamic attribute values already saved for this unit. */
  existingDynamicValues?: UnitDynamicAttributeValue[];
  /** Called with the save payload when the qualitative attributes form is submitted. */
  onSave: (unitId: string, data: UnitQualitativeAttributesSave) => Promise<void>;
  /** Called with the unit update payload to save apartment master attributes. */
  onSaveUnit?: (unitId: string, data: UnitUpdate) => Promise<void>;
  /** Called with the dynamic attribute save payload (PR-033). */
  onSaveDynamicAttributes?: (
    unitId: string,
    data: UnitDynamicAttributesSaveRequest,
  ) => Promise<void>;
  onClose: () => void;
}

const STATIC_VIEW_TYPE_OPTIONS: { value: ViewType; label: string }[] = [
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
 * EditAttributesModal — modal form for editing qualitative pricing attributes
 * and apartment master attributes (Layer A).
 *
 * The modal is split into two clearly separated sections:
 *   1. Apartment Attributes — physical unit characteristics (bedrooms, bathrooms,
 *      floor level, areas, roof garden). Saved via onSaveUnit to the unit record.
 *   2. Pricing Qualitative Attributes — descriptive/categorical pricing context
 *      (view type, corner unit, floor premium category, orientation, outdoor premium,
 *      upgrade flag, notes). Saved via onSave to the qualitative attributes record.
 *
 * When projectDefinitions are provided and the project defines a view_type attribute:
 *   - The view_type dropdown shows project-configured options instead of the static list.
 *   - The selected value is saved via onSaveDynamicAttributes to the normalised
 *     unit_dynamic_attribute_values layer (PR-033).
 *   - The static qualitative view_type field remains editable as a fallback when no
 *     project-defined view_type definition is configured.
 *
 * Attributes do not automatically adjust pricing — they provide structured
 * context for pricing decisions and future automation.
 */
export function EditAttributesModal({
  unitId,
  unitNumber,
  existing,
  unitData,
  projectDefinitions,
  existingDynamicValues,
  onSave,
  onSaveUnit,
  onSaveDynamicAttributes,
  onClose,
}: EditAttributesModalProps) {
  // Resolve project-defined view_type definition (if any)
  const projectViewTypeDef = projectDefinitions?.find(
    (d) => d.key === "view_type" && d.is_active,
  ) ?? null;

  // Active options for the project-defined view_type
  const projectViewTypeOptions = projectViewTypeDef
    ? projectViewTypeDef.options.filter((o) => o.is_active)
    : [];

  // Current dynamic value for view_type (if already saved)
  const existingViewTypeDynamic = existingDynamicValues?.find(
    (v) => v.definition_key === "view_type",
  ) ?? null;

  // ── Apartment Attributes (Layer A) ──────────────────────────────────────
  const [bedrooms, setBedrooms] = useState<string>(
    unitData?.bedrooms != null ? String(unitData.bedrooms) : "",
  );
  const [bathrooms, setBathrooms] = useState<string>(
    unitData?.bathrooms != null ? String(unitData.bathrooms) : "",
  );
  const [floorLevel, setFloorLevel] = useState<string>(
    unitData?.floor_level ?? "",
  );
  const [livableArea, setLivableArea] = useState<string>(
    unitData?.livable_area != null ? String(unitData.livable_area) : "",
  );
  const [hasRoofGarden, setHasRoofGarden] = useState<boolean | null>(
    unitData?.has_roof_garden ?? null,
  );
  const [balconyArea, setBalconyArea] = useState<string>(
    unitData?.balcony_area != null ? String(unitData.balcony_area) : "",
  );

  // ── Project-defined view type (dynamic layer, PR-033) ─────────────────
  const [dynamicViewOptionId, setDynamicViewOptionId] = useState<string>(
    existingViewTypeDynamic?.option_id ?? "",
  );

  // ── Qualitative Pricing Attributes (Layer B) ─────────────────────────
  const [viewType, setViewType] = useState<ViewType | "">(
    existing?.view_type ?? "",
  );
  const [cornerUnit, setCornerUnit] = useState<boolean | null>(
    existing?.corner_unit ?? null,
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
  const [upgradeFlag, setUpgradeFlag] = useState<boolean | null>(
    existing?.upgrade_flag ?? null,
  );
  const [notes, setNotes] = useState(existing?.notes ?? "");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Re-initialise state when the existing record changes
  useEffect(() => {
    setBedrooms(unitData?.bedrooms != null ? String(unitData.bedrooms) : "");
    setBathrooms(unitData?.bathrooms != null ? String(unitData.bathrooms) : "");
    setFloorLevel(unitData?.floor_level ?? "");
    setLivableArea(unitData?.livable_area != null ? String(unitData.livable_area) : "");
    setHasRoofGarden(unitData?.has_roof_garden ?? null);
    setBalconyArea(unitData?.balcony_area != null ? String(unitData.balcony_area) : "");
  }, [unitData]);

  useEffect(() => {
    setViewType(existing?.view_type ?? "");
    setCornerUnit(existing?.corner_unit ?? null);
    setFloorCategory(existing?.floor_premium_category ?? "");
    setOrientation(existing?.orientation ?? "");
    setOutdoorPremium(existing?.outdoor_area_premium ?? "");
    setUpgradeFlag(existing?.upgrade_flag ?? null);
    setNotes(existing?.notes ?? "");
    setError(null);
  }, [existing]);

  useEffect(() => {
    setDynamicViewOptionId(existingViewTypeDynamic?.option_id ?? "");
  }, [existingViewTypeDynamic]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      // Save apartment master attributes to unit record (if handler provided)
      if (onSaveUnit) {
        const unitPayload: UnitUpdate = {
          bedrooms: bedrooms !== "" ? parseInt(bedrooms, 10) : null,
          bathrooms: bathrooms !== "" ? parseInt(bathrooms, 10) : null,
          floor_level: floorLevel.trim() || null,
          livable_area: livableArea !== "" ? parseFloat(livableArea) : null,
          has_roof_garden: hasRoofGarden,
          balcony_area: balconyArea !== "" ? parseFloat(balconyArea) : null,
        };
        await onSaveUnit(unitId, unitPayload);
      }

      // Save project-defined dynamic attribute value for view_type (PR-033)
      if (projectViewTypeDef && dynamicViewOptionId && onSaveDynamicAttributes) {
        await onSaveDynamicAttributes(unitId, {
          attributes: [
            {
              definition_id: projectViewTypeDef.id,
              option_id: dynamicViewOptionId,
            },
          ],
        });
      }

      // Save qualitative pricing attributes
      const qualPayload: UnitQualitativeAttributesSave = {
        view_type: viewType || null,
        corner_unit: cornerUnit,
        floor_premium_category: floorCategory || null,
        orientation: orientation || null,
        outdoor_area_premium: outdoorPremium || null,
        upgrade_flag: upgradeFlag,
        notes: notes.trim() || null,
      };
      await onSave(unitId, qualPayload);
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
      <div className={styles.modal} style={{ maxWidth: 640 }}>
        <h2 id="ea-modal-title" className={styles.modalTitle}>
          {existing ? "Edit Attributes" : "Set Attributes"} — Unit {unitNumber}
        </h2>

        <form onSubmit={handleSubmit} className={styles.modalForm} noValidate>

          {/* ── Section 1: Apartment Attributes ─────────────────────────── */}
          <fieldset className={styles.formSection}>
            <legend className={styles.formSectionLegend}>Apartment Attributes</legend>

            {/* Bedrooms + Bathrooms */}
            <div className={styles.formRow}>
              <div className={styles.formField}>
                <label htmlFor="ea-bedrooms" className={styles.formLabel}>
                  Bedrooms
                </label>
                <input
                  id="ea-bedrooms"
                  type="number"
                  min={0}
                  step={1}
                  className={styles.formInput}
                  value={bedrooms}
                  onChange={(e) => setBedrooms(e.target.value)}
                  placeholder="e.g. 2"
                  disabled={submitting}
                />
              </div>
              <div className={styles.formField}>
                <label htmlFor="ea-bathrooms" className={styles.formLabel}>
                  Bathrooms
                </label>
                <input
                  id="ea-bathrooms"
                  type="number"
                  min={0}
                  step={1}
                  className={styles.formInput}
                  value={bathrooms}
                  onChange={(e) => setBathrooms(e.target.value)}
                  placeholder="e.g. 2"
                  disabled={submitting}
                />
              </div>
            </div>

            {/* Floor Level + Livable Area */}
            <div className={styles.formRow}>
              <div className={styles.formField}>
                <label htmlFor="ea-floor-level" className={styles.formLabel}>
                  Floor Level
                </label>
                <input
                  id="ea-floor-level"
                  type="text"
                  className={styles.formInput}
                  value={floorLevel}
                  onChange={(e) => setFloorLevel(e.target.value)}
                  placeholder="e.g. 3"
                  maxLength={50}
                  disabled={submitting}
                />
              </div>
              <div className={styles.formField}>
                <label htmlFor="ea-livable-area" className={styles.formLabel}>
                  Livable Area (sqm)
                </label>
                <input
                  id="ea-livable-area"
                  type="number"
                  min={0}
                  step={0.01}
                  className={styles.formInput}
                  value={livableArea}
                  onChange={(e) => setLivableArea(e.target.value)}
                  placeholder="e.g. 85.0"
                  disabled={submitting}
                />
              </div>
            </div>

            {/* Balcony Area + Has Roof Garden */}
            <div className={styles.formRow}>
              <div className={styles.formField}>
                <label htmlFor="ea-balcony-area" className={styles.formLabel}>
                  Balcony Area (sqm)
                </label>
                <input
                  id="ea-balcony-area"
                  type="number"
                  min={0}
                  step={0.01}
                  className={styles.formInput}
                  value={balconyArea}
                  onChange={(e) => setBalconyArea(e.target.value)}
                  placeholder="e.g. 10.0"
                  disabled={submitting}
                />
              </div>
              <div className={styles.formField}>
                <label htmlFor="ea-has-roof-garden" className={styles.formLabel}>
                  Has Roof Garden
                </label>
                <select
                  id="ea-has-roof-garden"
                  className={styles.formSelect}
                  value={hasRoofGarden === null ? "" : hasRoofGarden ? "true" : "false"}
                  onChange={(e) => {
                    const v = e.target.value;
                    setHasRoofGarden(v === "" ? null : v === "true");
                  }}
                  disabled={submitting}
                >
                  <option value="">— Not set —</option>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              </div>
            </div>
          </fieldset>

          {/* ── Section 2: Project-Defined Attributes (PR-033) ─────────────── */}
          {projectViewTypeDef && projectViewTypeOptions.length > 0 && (
            <fieldset className={`${styles.formSection} ${styles.formSectionSpaced}`}>
              <legend className={styles.formSectionLegend}>
                Project-Defined Attributes
              </legend>
              <div className={styles.formRow}>
                <div className={styles.formField}>
                  <label htmlFor="ea-dynamic-view-type" className={styles.formLabel}>
                    {projectViewTypeDef.label}
                  </label>
                  <select
                    id="ea-dynamic-view-type"
                    className={styles.formSelect}
                    value={dynamicViewOptionId}
                    onChange={(e) => setDynamicViewOptionId(e.target.value)}
                    disabled={submitting}
                  >
                    {!existingViewTypeDynamic && (
                      <option value="">— Select —</option>
                    )}
                    {projectViewTypeOptions.map((opt) => (
                      <option key={opt.id} value={opt.id}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </fieldset>
          )}

          {/* ── Section 3: Pricing Qualitative Attributes ─────────────────── */}
          <fieldset className={`${styles.formSection} ${styles.formSectionSpaced}`}>
            <legend className={styles.formSectionLegend}>Pricing Qualitative Attributes</legend>

            {/* View Type + Floor Premium Category */}
            <div className={styles.formRow}>
              {/* Show static view_type only when no project-defined definition is available */}
              {!projectViewTypeDef && (
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
                    {STATIC_VIEW_TYPE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}

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

            {/* Corner Unit + Upgrade Flag tri-state selects */}
            <div className={styles.formRow}>
              <div className={styles.formField}>
                <label htmlFor="ea-corner-unit" className={styles.formLabel}>
                  Corner Unit
                </label>
                <select
                  id="ea-corner-unit"
                  className={styles.formSelect}
                  value={cornerUnit === null ? "" : cornerUnit ? "true" : "false"}
                  onChange={(e) => {
                    const v = e.target.value;
                    setCornerUnit(v === "" ? null : v === "true");
                  }}
                  disabled={submitting}
                >
                  <option value="">— Not set —</option>
                  <option value="true">Yes — corner unit</option>
                  <option value="false">No — standard position</option>
                </select>
              </div>

              <div className={styles.formField}>
                <label htmlFor="ea-upgrade-flag" className={styles.formLabel}>
                  Upgrade Flag
                </label>
                <select
                  id="ea-upgrade-flag"
                  className={styles.formSelect}
                  value={upgradeFlag === null ? "" : upgradeFlag ? "true" : "false"}
                  onChange={(e) => {
                    const v = e.target.value;
                    setUpgradeFlag(v === "" ? null : v === "true");
                  }}
                  disabled={submitting}
                >
                  <option value="">— Not set —</option>
                  <option value="true">Yes — upgraded finishes</option>
                  <option value="false">No — standard finishes</option>
                </select>
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
          </fieldset>

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
