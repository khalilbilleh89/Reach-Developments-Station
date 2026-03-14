"use client";

import React from "react";
import type { SalesFiltersState } from "@/lib/sales-types";
import { unitStatusLabel, unitTypeLabel } from "@/lib/units-types";
import type { UnitStatus, UnitType } from "@/lib/units-types";
import styles from "@/styles/sales-workflow.module.css";

const STATUS_OPTIONS: { value: UnitStatus | ""; label: string }[] = [
  { value: "", label: "All Statuses" },
  { value: "available", label: unitStatusLabel("available") },
  { value: "reserved", label: unitStatusLabel("reserved") },
  { value: "under_contract", label: unitStatusLabel("under_contract") },
  { value: "registered", label: unitStatusLabel("registered") },
];

const TYPE_OPTIONS: { value: UnitType | ""; label: string }[] = [
  { value: "", label: "All Types" },
  { value: "studio", label: unitTypeLabel("studio") },
  { value: "one_bedroom", label: unitTypeLabel("one_bedroom") },
  { value: "two_bedroom", label: unitTypeLabel("two_bedroom") },
  { value: "three_bedroom", label: unitTypeLabel("three_bedroom") },
  { value: "four_bedroom", label: unitTypeLabel("four_bedroom") },
  { value: "penthouse", label: unitTypeLabel("penthouse") },
  { value: "villa", label: unitTypeLabel("villa") },
  { value: "townhouse", label: unitTypeLabel("townhouse") },
  { value: "retail", label: unitTypeLabel("retail") },
  { value: "office", label: unitTypeLabel("office") },
];

const EXCEPTION_OPTIONS: { value: "" | "yes" | "no"; label: string }[] = [
  { value: "", label: "Any" },
  { value: "yes", label: "Has Approved Exception" },
  { value: "no", label: "No Approved Exception" },
];

const READINESS_OPTIONS: { value: "" | "ready" | "needs_exception_approval" | "under_contract" | "missing_pricing" | "blocked"; label: string }[] = [
  { value: "", label: "All Readiness" },
  { value: "ready", label: "Ready" },
  { value: "needs_exception_approval", label: "Needs Exception Approval" },
  { value: "under_contract", label: "Under Contract" },
  { value: "missing_pricing", label: "Missing Pricing" },
  { value: "blocked", label: "Blocked" },
];

interface SalesFiltersProps {
  filters: SalesFiltersState;
  onChange: (filters: SalesFiltersState) => void;
}

/**
 * SalesFilters — filter controls for the sales candidates queue.
 *
 * Controlled component: the parent owns filter state and passes it down.
 * All filtering is applied client-side against the fetched candidate list.
 */
export function SalesFilters({ filters, onChange }: SalesFiltersProps) {
  const handleStatus = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onChange({ ...filters, status: e.target.value });
  };

  const handleType = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onChange({ ...filters, unit_type: e.target.value });
  };

  const handleException = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onChange({
      ...filters,
      has_approved_exception: e.target.value as "" | "yes" | "no",
    });
  };

  const handleReadiness = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onChange({
      ...filters,
      readiness: e.target.value as SalesFiltersState["readiness"],
    });
  };

  const handleMinPrice = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...filters, min_price: e.target.value });
  };

  const handleMaxPrice = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...filters, max_price: e.target.value });
  };

  const handleReset = () => {
    onChange({
      status: "",
      unit_type: "",
      has_approved_exception: "",
      contract_status: "",
      readiness: "",
      min_price: "",
      max_price: "",
    });
  };

  const hasActiveFilters =
    filters.status !== "" ||
    filters.unit_type !== "" ||
    filters.has_approved_exception !== "" ||
    filters.contract_status !== "" ||
    filters.readiness !== "" ||
    filters.min_price !== "" ||
    filters.max_price !== "";

  return (
    <div className={styles.filterBar} role="search" aria-label="Sales filters">
      <div className={styles.filterGroup}>
        <label htmlFor="sf-status" className={styles.filterLabel}>
          Status
        </label>
        <select
          id="sf-status"
          className={styles.filterSelect}
          value={filters.status}
          onChange={handleStatus}
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.filterGroup}>
        <label htmlFor="sf-type" className={styles.filterLabel}>
          Unit Type
        </label>
        <select
          id="sf-type"
          className={styles.filterSelect}
          value={filters.unit_type}
          onChange={handleType}
        >
          {TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.filterGroup}>
        <label htmlFor="sf-exception" className={styles.filterLabel}>
          Exception
        </label>
        <select
          id="sf-exception"
          className={styles.filterSelect}
          value={filters.has_approved_exception}
          onChange={handleException}
        >
          {EXCEPTION_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.filterGroup}>
        <label htmlFor="sf-readiness" className={styles.filterLabel}>
          Readiness
        </label>
        <select
          id="sf-readiness"
          className={styles.filterSelect}
          value={filters.readiness}
          onChange={handleReadiness}
        >
          {READINESS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.filterGroup}>
        <label htmlFor="sf-min-price" className={styles.filterLabel}>
          Min Price (AED)
        </label>
        <input
          id="sf-min-price"
          type="number"
          className={styles.filterInput}
          placeholder="0"
          value={filters.min_price}
          onChange={handleMinPrice}
          min={0}
        />
      </div>

      <div className={styles.filterGroup}>
        <label htmlFor="sf-max-price" className={styles.filterLabel}>
          Max Price (AED)
        </label>
        <input
          id="sf-max-price"
          type="number"
          className={styles.filterInput}
          placeholder="Any"
          value={filters.max_price}
          onChange={handleMaxPrice}
          min={0}
        />
      </div>

      {hasActiveFilters && (
        <button
          type="button"
          className={styles.filterReset}
          onClick={handleReset}
          aria-label="Reset filters"
        >
          Reset
        </button>
      )}
    </div>
  );
}
