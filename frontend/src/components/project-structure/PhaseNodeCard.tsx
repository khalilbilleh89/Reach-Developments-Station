"use client";

import React, { useState } from "react";
import type { ProjectStructurePhaseNode } from "@/lib/project-structure-types";
import { BuildingNodeCard } from "@/components/project-structure/BuildingNodeCard";
import styles from "@/styles/project-structure.module.css";

interface PhaseNodeCardProps {
  phase: ProjectStructurePhaseNode;
}

export function PhaseNodeCard({ phase }: PhaseNodeCardProps) {
  const [expanded, setExpanded] = useState(true);

  const toggleExpanded = () => setExpanded((prev) => !prev);

  return (
    <div className={styles.phaseCard}>
      <div
        className={styles.phaseHeader}
        onClick={toggleExpanded}
        role="button"
        aria-expanded={expanded}
        aria-label={`Phase: ${phase.name}`}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggleExpanded();
          }
        }}
      >
        <span className={styles.phaseToggle}>{expanded ? "▾" : "▸"}</span>
        <span className={styles.phaseTitle}>
          Phase {phase.sequence}: {phase.name}
        </span>
        <div className={styles.phaseMeta}>
          {phase.phase_type && (
            <span className={styles.phaseBadge}>{phase.phase_type}</span>
          )}
          <span className={styles.phaseBadge}>{phase.status}</span>
          <span>
            {phase.building_count} building{phase.building_count !== 1 ? "s" : ""}
          </span>
          <span>{phase.unit_count} units</span>
        </div>
      </div>

      {expanded && (
        <div className={styles.phaseBody}>
          {phase.buildings.length === 0 ? (
            <div className={styles.phaseEmpty}>No buildings in this phase.</div>
          ) : (
            phase.buildings.map((building) => (
              <BuildingNodeCard key={building.id} building={building} />
            ))
          )}
        </div>
      )}
    </div>
  );
}
