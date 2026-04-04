"use client";

import React, { useEffect, useState } from "react";
import type { ReservationCreate, UnitListItem } from "@/lib/units-types";
import { DEFAULT_CURRENCY } from "@/lib/currency-constants";
import styles from "@/styles/projects.module.css";

interface ReserveUnitModalProps {
  /** The unit being reserved. */
  unit: UnitListItem;
  onSubmit: (data: ReservationCreate) => Promise<void>;
  onClose: () => void;
}

/**
 * ReserveUnitModal — modal form for placing a reservation hold on a unit.
 *
 * Collects customer contact information, pricing, and an optional expiry date.
 * Triggered from the Units table "Reserve Unit" action.
 *
 * Modal stays open on API failure and shows an inline error.
 */
export function ReserveUnitModal({ unit, onSubmit, onClose }: ReserveUnitModalProps) {
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");
  const [reservationPrice, setReservationPrice] = useState("");
  const [reservationFee, setReservationFee] = useState("");
  const [currency, setCurrency] = useState(DEFAULT_CURRENCY);
  const [expiresAt, setExpiresAt] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset fields when the unit changes
  useEffect(() => {
    setCustomerName("");
    setCustomerPhone("");
    setCustomerEmail("");
    setReservationPrice("");
    setReservationFee("");
    setCurrency(DEFAULT_CURRENCY);
    setExpiresAt("");
    setNotes("");
    setError(null);
  }, [unit.id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!customerName.trim()) {
      setError("Customer name is required.");
      return;
    }
    if (!customerPhone.trim()) {
      setError("Customer phone is required.");
      return;
    }
    const priceVal = parseFloat(reservationPrice);
    if (!reservationPrice.trim() || isNaN(priceVal) || priceVal <= 0) {
      setError("Reservation price must be a positive number.");
      return;
    }

    const feeVal = reservationFee.trim()
      ? parseFloat(reservationFee)
      : null;
    if (feeVal !== null && (isNaN(feeVal) || feeVal < 0)) {
      setError("Reservation fee must be a non-negative number.");
      return;
    }

    const data: ReservationCreate = {
      unit_id: unit.id,
      customer_name: customerName.trim(),
      customer_phone: customerPhone.trim(),
      customer_email: customerEmail.trim() || null,
      reservation_price: priceVal,
      reservation_fee: feeVal,
      currency: currency.trim() || DEFAULT_CURRENCY,
      expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
      notes: notes.trim() || null,
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
    <div
      className={styles.modalOverlay}
      role="dialog"
      aria-modal="true"
      aria-labelledby="reserve-unit-modal-title"
    >
      <div className={styles.modal}>
        <h2 id="reserve-unit-modal-title" className={styles.modalTitle}>
          Reserve Unit {unit.unit_number}
        </h2>

        <form className={styles.modalForm} onSubmit={handleSubmit} noValidate>
          {error && (
            <div className={styles.modalError} role="alert">
              {error}
            </div>
          )}

          {/* Customer information */}
          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="reserve-customer-name" className={styles.formLabel}>
                Customer Name <span aria-hidden="true">*</span>
              </label>
              <input
                id="reserve-customer-name"
                type="text"
                className={styles.formInput}
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                maxLength={200}
                placeholder="e.g. John Doe"
                required
                autoFocus
              />
            </div>

            <div className={styles.formField}>
              <label htmlFor="reserve-customer-phone" className={styles.formLabel}>
                Customer Phone <span aria-hidden="true">*</span>
              </label>
              <input
                id="reserve-customer-phone"
                type="tel"
                className={styles.formInput}
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
                maxLength={50}
                placeholder="e.g. +971501234567"
                required
              />
            </div>
          </div>

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="reserve-customer-email" className={styles.formLabel}>
                Customer Email
              </label>
              <input
                id="reserve-customer-email"
                type="email"
                className={styles.formInput}
                value={customerEmail}
                onChange={(e) => setCustomerEmail(e.target.value)}
                maxLength={254}
                placeholder="Optional"
              />
            </div>
          </div>

          {/* Pricing */}
          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="reserve-price" className={styles.formLabel}>
                Reservation Price <span aria-hidden="true">*</span>
              </label>
              <input
                id="reserve-price"
                type="number"
                className={styles.formInput}
                value={reservationPrice}
                onChange={(e) => setReservationPrice(e.target.value)}
                min={0.01}
                step={0.01}
                placeholder="e.g. 750000"
                required
              />
            </div>

            <div className={styles.formField}>
              <label htmlFor="reserve-fee" className={styles.formLabel}>
                Reservation Fee
              </label>
              <input
                id="reserve-fee"
                type="number"
                className={styles.formInput}
                value={reservationFee}
                onChange={(e) => setReservationFee(e.target.value)}
                min={0}
                step={0.01}
                placeholder="Optional"
              />
            </div>
          </div>

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="reserve-currency" className={styles.formLabel}>
                Currency
              </label>
              <input
                id="reserve-currency"
                type="text"
                className={styles.formInput}
                value={currency}
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                maxLength={10}
                placeholder="e.g. AED, USD, JOD"
              />
            </div>

            <div className={styles.formField}>
              <label htmlFor="reserve-expires-at" className={styles.formLabel}>
                Expiration Date
              </label>
              <input
                id="reserve-expires-at"
                type="datetime-local"
                className={styles.formInput}
                value={expiresAt}
                onChange={(e) => setExpiresAt(e.target.value)}
              />
            </div>
          </div>

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="reserve-notes" className={styles.formLabel}>
                Notes
              </label>
              <textarea
                id="reserve-notes"
                className={styles.formInput}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                maxLength={2000}
                placeholder="Optional internal notes"
                rows={3}
              />
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
              {submitting ? "Saving\u2026" : "Reserve Unit"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
