"use client";

import React, { useEffect, useState } from "react";
import type { UnitEngineInputsSave, UnitPricingAttributes } from "@/lib/units-types";
import styles from "@/styles/projects.module.css";

interface EditEngineInputsModalProps {
  /** The unit ID whose engine inputs are being edited. */
  unitId: string;
  /** Unit number displayed in the modal title. */
  unitNumber: string;
  /** Existing engine inputs record (null when no record exists yet). */
  existing: UnitPricingAttributes | null;
  /** Called with the save payload when the form is submitted. */
  onSave: (unitId: string, data: UnitEngineInputsSave) => Promise<void>;
  onClose: () => void;
}

/**
 * EditEngineInputsModal — modal form for setting the numerical pricing engine inputs
 * for a unit (Layer 2 of the three-layer pricing model).
 *
 * These inputs drive the pricing engine calculation and determine pricing readiness.
 * When all required fields are set, the inspection page will show the unit as ready.
 *
 * Engine inputs managed here:
 *   • Base Price Per Sqm  (required — drives the base unit price)
 *   • Floor Premium       (fixed amount added for floor position)
 *   • View Premium        (fixed amount added for view type)
 *   • Corner Premium      (fixed amount added for corner units)
 *   • Size Adjustment     (positive or negative area-based adjustment)
 *   • Custom Adjustment   (positive or negative discretionary adjustment)
 *
 * These are distinct from:
 *   • Qualitative Attributes (view type, corner unit — edited via Edit Attributes)
 *   • Commercial Pricing Record (approved price, status — in the Pricing Record section)
 */
export function EditEngineInputsModal({
  unitId,
  unitNumber,
  existing,
  onSave,
  onClose,
}: EditEngineInputsModalProps) {
  const [basePricePerSqm, setBasePricePerSqm] = useState(
    existing?.base_price_per_sqm != null ? String(existing.base_price_per_sqm) : "",
  );
  const [floorPremium, setFloorPremium] = useState(
    String(existing?.floor_premium ?? 0),
  );
  const [viewPremium, setViewPremium] = useState(
    String(existing?.view_premium ?? 0),
  );
  const [cornerPremium, setCornerPremium] = useState(
    String(existing?.corner_premium ?? 0),
  );
  const [sizeAdjustment, setSizeAdjustment] = useState(
    String(existing?.size_adjustment ?? 0),
  );
  const [customAdjustment, setCustomAdjustment] = useState(
    String(existing?.custom_adjustment ?? 0),
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Re-initialise when the existing record changes
  useEffect(() => {
    setBasePricePerSqm(
      existing?.base_price_per_sqm != null ? String(existing.base_price_per_sqm) : "",
    );
    setFloorPremium(String(existing?.floor_premium ?? 0));
    setViewPremium(String(existing?.view_premium ?? 0));
    setCornerPremium(String(existing?.corner_premium ?? 0));
    setSizeAdjustment(String(existing?.size_adjustment ?? 0));
    setCustomAdjustment(String(existing?.custom_adjustment ?? 0));
    setError(null);
  }, [existing]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const bpsq = parseFloat(basePricePerSqm);
    if (isNaN(bpsq) || bpsq <= 0) {
      setError("Base Price Per Sqm must be a positive number.");
      return;
    }
    const fp = parseFloat(floorPremium);
    const vp = parseFloat(viewPremium);
    const cp = parseFloat(cornerPremium);
    const sa = parseFloat(sizeAdjustment);
    const ca = parseFloat(customAdjustment);

    for (const [label, val] of [
      ["Floor Premium", fp],
      ["View Premium", vp],
      ["Corner Premium", cp],
      ["Size Adjustment", sa],
      ["Custom Adjustment", ca],
    ] as [string, number][]) {
      if (isNaN(val)) {
        setError(`${label} must be a valid number.`);
        return;
      }
    }

    setSubmitting(true);
    try {
      await onSave(unitId, {
        base_price_per_sqm: bpsq,
        floor_premium: fp,
        view_premium: vp,
        corner_premium: cp,
        size_adjustment: sa,
        custom_adjustment: ca,
      });
      onClose();
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to save engine inputs. Please try again.",
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
      aria-labelledby="eei-modal-title"
    >
      <div className={styles.modal} style={{ maxWidth: 600 }}>
        <h2 id="eei-modal-title" className={styles.modalTitle}>
          {existing ? "Edit Engine Inputs" : "Set Engine Inputs"} — Unit {unitNumber}
        </h2>
        <p style={{ margin: "0 0 1rem", color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          These numerical inputs drive the pricing engine calculation and determine
          pricing readiness. All missing fields will block the computed price.
        </p>

        <form onSubmit={handleSubmit} className={styles.modalForm} noValidate>
          {/* Base Price Per Sqm */}
          <div className={styles.formRow}>
            <div className={styles.formField} style={{ flex: "1 1 100%" }}>
              <label htmlFor="eei-base-price-sqm" className={styles.formLabel}>
                Base Price Per Sqm <span aria-hidden="true">*</span>
              </label>
              <input
                id="eei-base-price-sqm"
                type="number"
                min="0.01"
                step="0.01"
                className={styles.formInput}
                value={basePricePerSqm}
                onChange={(e) => setBasePricePerSqm(e.target.value)}
                placeholder="e.g. 5000"
                required
                disabled={submitting}
              />
              <small style={{ color: "var(--color-text-muted)", fontSize: "0.75rem" }}>
                Required. Multiplied by unit area to compute the base unit price.
              </small>
            </div>
          </div>

          {/* Floor Premium + View Premium */}
          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="eei-floor-premium" className={styles.formLabel}>
                Floor Premium
              </label>
              <input
                id="eei-floor-premium"
                type="number"
                min="0"
                step="0.01"
                className={styles.formInput}
                value={floorPremium}
                onChange={(e) => setFloorPremium(e.target.value)}
                placeholder="e.g. 10000"
                disabled={submitting}
              />
            </div>
            <div className={styles.formField}>
              <label htmlFor="eei-view-premium" className={styles.formLabel}>
                View Premium
              </label>
              <input
                id="eei-view-premium"
                type="number"
                min="0"
                step="0.01"
                className={styles.formInput}
                value={viewPremium}
                onChange={(e) => setViewPremium(e.target.value)}
                placeholder="e.g. 15000"
                disabled={submitting}
              />
            </div>
          </div>

          {/* Corner Premium + Size Adjustment */}
          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="eei-corner-premium" className={styles.formLabel}>
                Corner Premium
              </label>
              <input
                id="eei-corner-premium"
                type="number"
                min="0"
                step="0.01"
                className={styles.formInput}
                value={cornerPremium}
                onChange={(e) => setCornerPremium(e.target.value)}
                placeholder="e.g. 5000"
                disabled={submitting}
              />
            </div>
            <div className={styles.formField}>
              <label htmlFor="eei-size-adjustment" className={styles.formLabel}>
                Size Adjustment
              </label>
              <input
                id="eei-size-adjustment"
                type="number"
                step="0.01"
                className={styles.formInput}
                value={sizeAdjustment}
                onChange={(e) => setSizeAdjustment(e.target.value)}
                placeholder="e.g. 2000 or -1000"
                disabled={submitting}
              />
            </div>
          </div>

          {/* Custom Adjustment */}
          <div className={styles.formRow}>
            <div className={styles.formField} style={{ flex: "1 1 100%" }}>
              <label htmlFor="eei-custom-adjustment" className={styles.formLabel}>
                Custom Adjustment
              </label>
              <input
                id="eei-custom-adjustment"
                type="number"
                step="0.01"
                className={styles.formInput}
                value={customAdjustment}
                onChange={(e) => setCustomAdjustment(e.target.value)}
                placeholder="e.g. -1000 or 5000"
                disabled={submitting}
              />
              <small style={{ color: "var(--color-text-muted)", fontSize: "0.75rem" }}>
                Discretionary adjustment. Can be positive or negative.
              </small>
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
              className={styles.cancelBtn}
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={styles.submitBtn}
              disabled={submitting}
            >
              {submitting
                ? "Saving…"
                : existing
                  ? "Update Engine Inputs"
                  : "Set Engine Inputs"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
