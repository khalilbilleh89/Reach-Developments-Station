"use client";

import React from "react";
import type { UnitFiltersState, UnitStatus, UnitType } from "@/lib/units-types";
import { unitStatusLabel, unitTypeLabel } from "@/lib/units-types";
import styles from "@/styles/units-pricing.module.css";

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

interface UnitFiltersProps {
  filters: UnitFiltersState;
  onChange: (filters: UnitFiltersState) => void;
}

/**
 * UnitFilters — filter controls for the units listing page.
 *
 * Controlled component: the parent owns filter state and passes it down.
 * Filtering by status and type is applied client-side after the initial
 * API fetch. Min/max price filtering is applied against the backend-returned
 * final_unit_price when pricing data is available.
 */
export function UnitFilters({ filters, onChange }: UnitFiltersProps) {
  const handleStatus = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onChange({ ...filters, status: e.target.value as UnitStatus | "" });
  };

  const handleType = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onChange({ ...filters, unit_type: e.target.value as UnitType | "" });
  };

  const handleMinPrice = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...filters, min_price: e.target.value });
  };

  const handleMaxPrice = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...filters, max_price: e.target.value });
  };

  const handleReset = () => {
    onChange({ status: "", unit_type: "", min_price: "", max_price: "" });
  };

  const hasActiveFilters =
    filters.status !== "" ||
    filters.unit_type !== "" ||
    filters.min_price !== "" ||
    filters.max_price !== "";

  return (
    <div className={styles.filterBar} role="search" aria-label="Unit filters">
      <div className={styles.filterGroup}>
        <label htmlFor="filter-status" className={styles.filterLabel}>
          Status
        </label>
        <select
          id="filter-status"
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
        <label htmlFor="filter-type" className={styles.filterLabel}>
          Unit Type
        </label>
        <select
          id="filter-type"
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
        <label htmlFor="filter-min-price" className={styles.filterLabel}>
          Min Price (AED)
        </label>
        <input
          id="filter-min-price"
          type="number"
          className={styles.filterInput}
          placeholder="0"
          value={filters.min_price}
          onChange={handleMinPrice}
          min={0}
        />
      </div>

      <div className={styles.filterGroup}>
        <label htmlFor="filter-max-price" className={styles.filterLabel}>
          Max Price (AED)
        </label>
        <input
          id="filter-max-price"
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
