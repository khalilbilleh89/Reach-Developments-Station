/**
 * TenderComparisonSetList — list of comparison sets for a project.
 *
 * Renders a list of comparison set cards showing stage, labels, and active
 * status.  Calls onSelect when a card is clicked.
 */

"use client";

import React from "react";
import type { ConstructionCostComparisonSetListItem } from "@/lib/tender-comparison-types";
import { COMPARISON_STAGE_LABELS } from "@/lib/tender-comparison-types";
import styles from "@/styles/construction.module.css";

interface TenderComparisonSetListProps {
  sets: ConstructionCostComparisonSetListItem[];
  selectedId: string | null;
  onSelect: (set: ConstructionCostComparisonSetListItem) => void;
}

export function TenderComparisonSetList({
  sets,
  selectedId,
  onSelect,
}: TenderComparisonSetListProps) {
  if (sets.length === 0) {
    return (
      <div className={styles.emptyState} data-testid="sets-empty-state">
        <p className={styles.emptyStateTitle}>No comparison sets yet.</p>
        <p className={styles.emptyStateBody}>
          Create a comparison set to get started.
        </p>
      </div>
    );
  }

  return (
    <ul className={styles.setList} data-testid="tender-comparison-set-list">
      {sets.map((set) => (
        <li key={set.id}>
          <button
            className={`${styles.setListItem} ${selectedId === set.id ? styles.setListItemSelected : ""}`}
            onClick={() => onSelect(set)}
            aria-pressed={selectedId === set.id}
            aria-label={`Open comparison set: ${set.title}`}
          >
            <div className={styles.setListItemHeader}>
              <span className={styles.setListItemTitle}>{set.title}</span>
              <span
                className={
                  set.is_active ? styles.badgeActive : styles.badgeArchived
                }
              >
                {set.is_active ? "Active" : "Archived"}
              </span>
            </div>
            <div className={styles.setListItemMeta}>
              {COMPARISON_STAGE_LABELS[set.comparison_stage] ??
                set.comparison_stage}
            </div>
            <div className={styles.setListItemLabels}>
              <span>{set.baseline_label}</span>
              <span className={styles.setListItemArrow}>→</span>
              <span>{set.comparison_label}</span>
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}
