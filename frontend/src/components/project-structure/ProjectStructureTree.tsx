"use client";

import React from "react";
import type { ProjectStructureResponse } from "@/lib/project-structure-types";
import { PhaseNodeCard } from "@/components/project-structure/PhaseNodeCard";
import styles from "@/styles/project-structure.module.css";

interface ProjectStructureTreeProps {
  structure: ProjectStructureResponse;
}

/**
 * ProjectStructureTree
 *
 * Renders the full canonical hierarchy as an expandable/collapsible tree:
 *   Project → Phases → Buildings → Floors → Units
 *
 * Summary counts are shown at each level. All read-only.
 */
export function ProjectStructureTree({ structure }: ProjectStructureTreeProps) {
  return (
    <div>
      {/* Summary strip */}
      <div className={styles.summaryStrip}>
        <div className={styles.summaryCard}>
          <div className={styles.summaryLabel}>Phases</div>
          <div className={styles.summaryValue}>{structure.phase_count}</div>
        </div>
        <div className={styles.summaryCard}>
          <div className={styles.summaryLabel}>Buildings</div>
          <div className={styles.summaryValue}>{structure.building_count}</div>
        </div>
        <div className={styles.summaryCard}>
          <div className={styles.summaryLabel}>Floors</div>
          <div className={styles.summaryValue}>{structure.floor_count}</div>
        </div>
        <div className={styles.summaryCard}>
          <div className={styles.summaryLabel}>Units</div>
          <div className={styles.summaryValue}>{structure.unit_count}</div>
        </div>
      </div>

      {/* Hierarchy tree */}
      {structure.phases.length === 0 ? (
        <div className={styles.emptyState}>
          <p className={styles.emptyStateTitle}>No phases yet.</p>
          <p className={styles.emptyStateBody}>
            Add phases to this project to see the structure hierarchy here.
          </p>
        </div>
      ) : (
        <div className={styles.tree}>
          {structure.phases.map((phase) => (
            <PhaseNodeCard key={phase.id} phase={phase} />
          ))}
        </div>
      )}
    </div>
  );
}
