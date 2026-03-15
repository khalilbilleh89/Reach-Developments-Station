"use client";

import React, { useEffect, useState } from "react";
import type { PricingStatus, UnitPricingRecord, UnitPricingRecordSave } from "@/lib/units-types";
import { pricingStatusLabel } from "@/lib/units-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/projects.module.css";

interface EditPricingModalProps {
  /** The unit ID to price. */
  unitId: string;
  /** Unit number displayed in the modal title. */
  unitNumber: string;
  /** Existing pricing record (null when no record exists yet). */
  existing: UnitPricingRecord | null;
  /** Called with the save payload when the form is submitted. */
  onSave: (unitId: string, data: UnitPricingRecordSave) => Promise<void>;
  onClose: () => void;
}

const STATUS_OPTIONS: { value: PricingStatus; label: string }[] = [
  { value: "draft", label: "Draft" },
  { value: "reviewed", label: "Reviewed" },
  { value: "approved", label: "Approved" },
];

const CURRENCY_OPTIONS = ["AED", "USD", "EUR", "GBP", "SAR"];

/**
 * EditPricingModal — modal form for creating or editing a per-unit pricing record.
 *
 * The backend computes final_price = base_price + manual_adjustment.
 * The UI previews the computed value client-side, but the backend result is
 * the authoritative value returned after save.
 *
 * Opening the modal with existing=null initializes a draft state (no record yet).
 */
export function EditPricingModal({
  unitId,
  unitNumber,
  existing,
  onSave,
  onClose,
}: EditPricingModalProps) {
  const [basePrice, setBasePrice] = useState(
    existing != null ? String(existing.base_price) : "",
  );
  const [adjustment, setAdjustment] = useState(
    existing != null ? String(existing.manual_adjustment) : "0",
  );
  const [currency, setCurrency] = useState(existing?.currency ?? "AED");
  const [pricingStatus, setPricingStatus] = useState<PricingStatus>(
    existing?.pricing_status ?? "draft",
  );
  const [notes, setNotes] = useState(existing?.notes ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Re-initialise when the existing record changes (e.g. after save)
  useEffect(() => {
    setBasePrice(existing != null ? String(existing.base_price) : "");
    setAdjustment(existing != null ? String(existing.manual_adjustment) : "0");
    setCurrency(existing?.currency ?? "AED");
    setPricingStatus(existing?.pricing_status ?? "draft");
    setNotes(existing?.notes ?? "");
    setError(null);
  }, [existing]);

  const parsedBase = parseFloat(basePrice) || 0;
  const parsedAdj = parseFloat(adjustment) || 0;
  const previewFinalPrice = parsedBase + parsedAdj;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const basePriceVal = parseFloat(basePrice);
    if (isNaN(basePriceVal) || basePriceVal < 0) {
      setError("Base price must be a non-negative number.");
      return;
    }
    const adjustmentVal = parseFloat(adjustment);
    if (isNaN(adjustmentVal)) {
      setError("Manual adjustment must be a valid number.");
      return;
    }
    if (basePriceVal + adjustmentVal < 0) {
      setError("Final price cannot be negative. Adjust base price or adjustment.");
      return;
    }

    setSubmitting(true);
    try {
      await onSave(unitId, {
        base_price: basePriceVal,
        manual_adjustment: adjustmentVal,
        currency,
        pricing_status: pricingStatus,
        notes: notes.trim() || null,
      });
      onClose();
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to save pricing. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.modalOverlay} role="dialog" aria-modal="true" aria-labelledby="ep-modal-title">
      <div className={styles.modal}>
        <h2 id="ep-modal-title" className={styles.modalTitle}>
          {existing ? "Edit Pricing" : "Set Pricing"} — Unit {unitNumber}
        </h2>

        <form onSubmit={handleSubmit} className={styles.modalForm} noValidate>
          {/* Base Price */}
          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="ep-base-price" className={styles.formLabel}>
                Base Price <span aria-hidden="true">*</span>
              </label>
              <input
                id="ep-base-price"
                type="number"
                min="0"
                step="0.01"
                className={styles.formInput}
                value={basePrice}
                onChange={(e) => setBasePrice(e.target.value)}
                placeholder="e.g. 500000"
                required
                disabled={submitting}
              />
            </div>

            {/* Currency */}
            <div className={styles.formField}>
              <label htmlFor="ep-currency" className={styles.formLabel}>
                Currency
              </label>
              <select
                id="ep-currency"
                className={styles.formSelect}
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                disabled={submitting}
              >
                {CURRENCY_OPTIONS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Manual Adjustment */}
          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="ep-adjustment" className={styles.formLabel}>
                Manual Adjustment
              </label>
              <input
                id="ep-adjustment"
                type="number"
                step="0.01"
                className={styles.formInput}
                value={adjustment}
                onChange={(e) => setAdjustment(e.target.value)}
                placeholder="e.g. -5000 or 10000"
                disabled={submitting}
              />
            </div>

            {/* Pricing Status */}
            <div className={styles.formField}>
              <label htmlFor="ep-status" className={styles.formLabel}>
                Pricing Status
              </label>
              <select
                id="ep-status"
                className={styles.formSelect}
                value={pricingStatus}
                onChange={(e) => setPricingStatus(e.target.value as PricingStatus)}
                disabled={submitting}
              >
                {STATUS_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Final price preview */}
          <div className={styles.formRow}>
            <div className={styles.formField}>
              <span className={styles.formLabel}>Computed Final Price</span>
              <p
                aria-live="polite"
                style={{
                  fontWeight: 600,
                  color: previewFinalPrice < 0 ? "#c0392b" : "inherit",
                  margin: "4px 0 0",
                }}
              >
                {previewFinalPrice < 0
                  ? "⚠ Negative — not allowed"
                  : formatCurrency(previewFinalPrice)}
              </p>
              <small style={{ color: "#888", fontSize: "0.75rem" }}>
                Preview only — final value is confirmed by the server.
              </small>
            </div>
          </div>

          {/* Notes */}
          <div className={styles.formRow}>
            <div className={styles.formField} style={{ flex: "1 1 100%" }}>
              <label htmlFor="ep-notes" className={styles.formLabel}>
                Notes
              </label>
              <textarea
                id="ep-notes"
                className={styles.formTextarea}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                placeholder="Optional notes about this pricing…"
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
              {submitting ? "Saving…" : existing ? "Update Pricing" : "Set Pricing"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
