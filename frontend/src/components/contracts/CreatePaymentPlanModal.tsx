"use client";

import React, { useState } from "react";
import type { PaymentPlanCreatePayload } from "@/lib/payment-plans-api";
import type { PaymentPlan } from "@/lib/payment-plans-types";
import styles from "@/styles/projects.module.css";

interface CreatePaymentPlanModalProps {
  contractId: string;
  onSubmit: (payload: PaymentPlanCreatePayload) => Promise<PaymentPlan>;
  onClose: () => void;
}

type Frequency = "monthly" | "quarterly" | "custom";

const FREQUENCY_OPTIONS: { value: Frequency; label: string }[] = [
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
  { value: "custom", label: "Custom" },
];

/**
 * CreatePaymentPlanModal — modal form for creating a payment plan for a
 * contract.
 *
 * Fields:
 *   - Plan name
 *   - Number of installments
 *   - Start date
 *   - Frequency
 *   - Down payment percent (optional, defaults to 0%)
 *
 * Calls onSubmit with the assembled payload and closes on success.
 * Stays open and shows an inline error on failure.
 */
export function CreatePaymentPlanModal({
  contractId,
  onSubmit,
  onClose,
}: CreatePaymentPlanModalProps) {
  const [planName, setPlanName] = useState("");
  const [numberOfInstallments, setNumberOfInstallments] = useState(12);
  const [startDate, setStartDate] = useState(
    () => new Date().toISOString().slice(0, 10),
  );
  const [frequency, setFrequency] = useState<Frequency>("monthly");
  const [downPaymentPercent, setDownPaymentPercent] = useState(0);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!planName.trim()) {
      setError("Plan name is required.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        contract_id: contractId,
        plan_name: planName.trim(),
        number_of_installments: numberOfInstallments,
        start_date: startDate,
        installment_frequency: frequency,
        down_payment_percent: downPaymentPercent,
      });
      onClose();
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to create payment plan.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.modalOverlay} role="dialog" aria-modal="true" aria-label="Create Payment Plan">
      <div className={styles.modal}>
        <h2 className={styles.modalTitle}>Create Payment Plan</h2>

        <form onSubmit={handleSubmit} className={styles.modalForm} noValidate>
          <label className={styles.formLabel} htmlFor="plan-name">
            Plan Name
          </label>
          <input
            id="plan-name"
            type="text"
            className={styles.formInput}
            value={planName}
            onChange={(e) => setPlanName(e.target.value)}
            placeholder="e.g. Standard 12-Month Plan"
            required
          />

          <label className={styles.formLabel} htmlFor="num-installments">
            Number of Installments
          </label>
          <input
            id="num-installments"
            type="number"
            className={styles.formInput}
            value={numberOfInstallments}
            min={1}
            step={1}
            onChange={(e) =>
              setNumberOfInstallments(Math.max(1, parseInt(e.target.value, 10) || 1))
            }
            required
          />

          <label className={styles.formLabel} htmlFor="start-date">
            Start Date
          </label>
          <input
            id="start-date"
            type="date"
            className={styles.formInput}
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            required
          />

          <label className={styles.formLabel} htmlFor="frequency">
            Frequency
          </label>
          <select
            id="frequency"
            className={styles.formSelect}
            value={frequency}
            onChange={(e) => setFrequency(e.target.value as Frequency)}
          >
            {FREQUENCY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          <label className={styles.formLabel} htmlFor="down-payment-pct">
            Down Payment Percent (%)
          </label>
          <input
            id="down-payment-pct"
            type="number"
            className={styles.formInput}
            value={downPaymentPercent}
            min={0}
            max={100}
            step={0.01}
            onChange={(e) =>
              setDownPaymentPercent(
                Math.min(100, Math.max(0, parseFloat(e.target.value) || 0)),
              )
            }
          />

          {error && <p className={styles.modalError}>{error}</p>}

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
              {submitting ? "Creating…" : "Create Payment Plan"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
