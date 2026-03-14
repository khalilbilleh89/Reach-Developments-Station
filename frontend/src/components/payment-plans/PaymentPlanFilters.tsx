"use client";

import React from "react";
import type { PaymentPlanFiltersState } from "@/lib/payment-plans-types";
import styles from "@/styles/payment-plans.module.css";

const DEFAULT_FILTERS: PaymentPlanFiltersState = {
  collectionStatus: "",
  contractStatus: "",
  minOutstanding: "",
  maxOutstanding: "",
};

interface PaymentPlanFiltersProps {
  filters: PaymentPlanFiltersState;
  onChange: (filters: PaymentPlanFiltersState) => void;
}

/**
 * PaymentPlanFilters — filter controls for the payment plans queue.
 *
 * Suggested filters: collection status, contract status, outstanding range.
 * All filter values are aligned with backend fields — no imaginary finance.
 */
export function PaymentPlanFilters({
  filters,
  onChange,
}: PaymentPlanFiltersProps) {
  const handleChange = (field: keyof PaymentPlanFiltersState, value: string) => {
    onChange({ ...filters, [field]: value });
  };

  const isModified =
    filters.collectionStatus !== "" ||
    filters.contractStatus !== "" ||
    filters.minOutstanding !== "" ||
    filters.maxOutstanding !== "";

  return (
    <div className={styles.filterBar} role="search" aria-label="Payment plan filters">
      <div className={styles.filterGroup}>
        <label htmlFor="pp-filter-collection" className={styles.filterLabel}>
          Collection Status
        </label>
        <select
          id="pp-filter-collection"
          className={styles.filterSelect}
          value={filters.collectionStatus}
          onChange={(e) => handleChange("collectionStatus", e.target.value)}
          aria-label="Filter by collection status"
        >
          <option value="">All</option>
          <option value="has_overdue">Has Overdue</option>
          <option value="in_progress">In Progress</option>
          <option value="fully_paid">Fully Paid</option>
        </select>
      </div>

      <div className={styles.filterGroup}>
        <label htmlFor="pp-filter-contract-status" className={styles.filterLabel}>
          Contract Status
        </label>
        <select
          id="pp-filter-contract-status"
          className={styles.filterSelect}
          value={filters.contractStatus}
          onChange={(e) => handleChange("contractStatus", e.target.value)}
          aria-label="Filter by contract status"
        >
          <option value="">All</option>
          <option value="active">Active</option>
          <option value="draft">Draft</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      <div className={styles.filterGroup}>
        <label htmlFor="pp-filter-min-outstanding" className={styles.filterLabel}>
          Min Outstanding
        </label>
        <input
          id="pp-filter-min-outstanding"
          type="number"
          className={styles.filterInput}
          value={filters.minOutstanding}
          onChange={(e) => handleChange("minOutstanding", e.target.value)}
          placeholder="AED"
          min="0"
          aria-label="Minimum outstanding amount"
        />
      </div>

      <div className={styles.filterGroup}>
        <label htmlFor="pp-filter-max-outstanding" className={styles.filterLabel}>
          Max Outstanding
        </label>
        <input
          id="pp-filter-max-outstanding"
          type="number"
          className={styles.filterInput}
          value={filters.maxOutstanding}
          onChange={(e) => handleChange("maxOutstanding", e.target.value)}
          placeholder="AED"
          min="0"
          aria-label="Maximum outstanding amount"
        />
      </div>

      {isModified && (
        <button
          type="button"
          className={styles.filterReset}
          onClick={() => onChange(DEFAULT_FILTERS)}
          aria-label="Reset filters"
        >
          Reset
        </button>
      )}
    </div>
  );
}
