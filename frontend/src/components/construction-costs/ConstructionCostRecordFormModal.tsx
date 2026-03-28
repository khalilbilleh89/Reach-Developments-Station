/**
 * ConstructionCostRecordFormModal — create / edit form modal for construction
 * cost records.
 *
 * When `record` is provided the modal operates in edit mode (pre-populated
 * fields, "Update" submit label).  When `record` is undefined it operates in
 * create mode.
 */

"use client";

import React, { useEffect, useState } from "react";
import type {
  ConstructionCostRecord,
  ConstructionCostRecordCreate,
  ConstructionCostRecordUpdate,
  CostCategory,
  CostSource,
  CostStage,
} from "@/lib/construction-cost-types";
import {
  COST_CATEGORY_OPTIONS,
  COST_SOURCE_OPTIONS,
  COST_STAGE_OPTIONS,
} from "@/lib/construction-cost-types";
import styles from "@/styles/construction.module.css";

interface ConstructionCostRecordFormModalProps {
  record?: ConstructionCostRecord;
  onSubmit: (
    data: ConstructionCostRecordCreate | ConstructionCostRecordUpdate,
  ) => Promise<void>;
  onClose: () => void;
}

export function ConstructionCostRecordFormModal({
  record,
  onSubmit,
  onClose,
}: ConstructionCostRecordFormModalProps) {
  const isEdit = Boolean(record);

  const [title, setTitle] = useState(record?.title ?? "");
  const [costCategory, setCostCategory] = useState<CostCategory>(
    record?.cost_category ?? "hard_cost",
  );
  const [costSource, setCostSource] = useState<CostSource>(
    record?.cost_source ?? "estimate",
  );
  const [costStage, setCostStage] = useState<CostStage>(
    record?.cost_stage ?? "construction",
  );
  const [amount, setAmount] = useState(
    record != null ? String(record.amount) : "",
  );
  const [currency, setCurrency] = useState(record?.currency ?? "AED");
  const [effectiveDate, setEffectiveDate] = useState(record?.effective_date ?? "");
  const [referenceNumber, setReferenceNumber] = useState(
    record?.reference_number ?? "",
  );
  const [notes, setNotes] = useState(record?.notes ?? "");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync fields if record prop changes (e.g. opening a different record)
  useEffect(() => {
    setTitle(record?.title ?? "");
    setCostCategory(record?.cost_category ?? "hard_cost");
    setCostSource(record?.cost_source ?? "estimate");
    setCostStage(record?.cost_stage ?? "construction");
    setAmount(record != null ? String(record.amount) : "");
    setCurrency(record?.currency ?? "AED");
    setEffectiveDate(record?.effective_date ?? "");
    setReferenceNumber(record?.reference_number ?? "");
    setNotes(record?.notes ?? "");
    setError(null);
  }, [record]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Title is required.");
      return;
    }
    const parsedAmount = parseFloat(amount);
    if (amount.trim() === "" || isNaN(parsedAmount)) {
      setError("A valid amount is required.");
      return;
    }

    setSubmitting(true);
    setError(null);

    const payload: ConstructionCostRecordCreate | ConstructionCostRecordUpdate = {
      title: title.trim(),
      cost_category: costCategory,
      cost_source: costSource,
      cost_stage: costStage,
      amount: parsedAmount,
      currency: currency.trim() || "AED",
      effective_date: effectiveDate || null,
      reference_number: referenceNumber.trim() || null,
      notes: notes.trim() || null,
    };

    try {
      await onSubmit(payload);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to save cost record.",
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
        aria-labelledby="cost-record-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="cost-record-modal-title" className={styles.modalTitle}>
          {isEdit ? "Edit Cost Record" : "Add Cost Record"}
        </h2>

        <form className={styles.modalForm} onSubmit={handleSubmit}>
          {/* Title */}
          <div className={styles.formField}>
            <label htmlFor="cr-title" className={styles.formLabel}>
              Title <span aria-hidden>*</span>
            </label>
            <input
              id="cr-title"
              type="text"
              className={styles.formInput}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Foundation Works"
            />
          </div>

          <div className={styles.formRow}>
            {/* Category */}
            <div className={styles.formField}>
              <label htmlFor="cr-category" className={styles.formLabel}>
                Category
              </label>
              <select
                id="cr-category"
                className={styles.formSelect}
                value={costCategory}
                onChange={(e) => setCostCategory(e.target.value as CostCategory)}
              >
                {COST_CATEGORY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Source */}
            <div className={styles.formField}>
              <label htmlFor="cr-source" className={styles.formLabel}>
                Source
              </label>
              <select
                id="cr-source"
                className={styles.formSelect}
                value={costSource}
                onChange={(e) => setCostSource(e.target.value as CostSource)}
              >
                {COST_SOURCE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Stage */}
            <div className={styles.formField}>
              <label htmlFor="cr-stage" className={styles.formLabel}>
                Stage
              </label>
              <select
                id="cr-stage"
                className={styles.formSelect}
                value={costStage}
                onChange={(e) => setCostStage(e.target.value as CostStage)}
              >
                {COST_STAGE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className={styles.formRow}>
            {/* Amount */}
            <div className={styles.formField}>
              <label htmlFor="cr-amount" className={styles.formLabel}>
                Amount <span aria-hidden>*</span>
              </label>
              <input
                id="cr-amount"
                type="number"
                step="0.01"
                className={styles.formInput}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
              />
            </div>

            {/* Currency */}
            <div className={styles.formField}>
              <label htmlFor="cr-currency" className={styles.formLabel}>
                Currency
              </label>
              <input
                id="cr-currency"
                type="text"
                maxLength={10}
                className={styles.formInput}
                value={currency}
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                placeholder="AED"
              />
            </div>

            {/* Effective Date */}
            <div className={styles.formField}>
              <label htmlFor="cr-effective-date" className={styles.formLabel}>
                Effective Date
              </label>
              <input
                id="cr-effective-date"
                type="date"
                className={styles.formInput}
                value={effectiveDate}
                onChange={(e) => setEffectiveDate(e.target.value)}
              />
            </div>
          </div>

          {/* Reference Number */}
          <div className={styles.formField}>
            <label htmlFor="cr-reference" className={styles.formLabel}>
              Reference Number
            </label>
            <input
              id="cr-reference"
              type="text"
              maxLength={255}
              className={styles.formInput}
              value={referenceNumber}
              onChange={(e) => setReferenceNumber(e.target.value)}
              placeholder="e.g. PC-2026-001"
            />
          </div>

          {/* Notes */}
          <div className={styles.formField}>
            <label htmlFor="cr-notes" className={styles.formLabel}>
              Notes
            </label>
            <textarea
              id="cr-notes"
              className={styles.formTextarea}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional notes"
            />
          </div>

          {error && (
            <div className={styles.modalError} role="alert">
              {error}
            </div>
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
                ? isEdit
                  ? "Updating…"
                  : "Adding…"
                : isEdit
                  ? "Update Record"
                  : "Add Record"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
