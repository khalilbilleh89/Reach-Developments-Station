"use client";

import React, { useState } from "react";
import type { ProjectStructureBuildingNode } from "@/lib/project-structure-types";
import { FloorNodeCard } from "@/components/project-structure/FloorNodeCard";
import styles from "@/styles/project-structure.module.css";

interface BuildingNodeCardProps {
  building: ProjectStructureBuildingNode;
}

export function BuildingNodeCard({ building }: BuildingNodeCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={styles.buildingCard}>
      <div
        className={styles.buildingHeader}
        onClick={() => setExpanded((prev) => !prev)}
        role="button"
        aria-expanded={expanded}
        aria-label={`Building: ${building.name}`}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") setExpanded((prev) => !prev);
        }}
      >
        <span className={styles.buildingToggle}>{expanded ? "▾" : "▸"}</span>
        <span className={styles.buildingTitle}>{building.name}</span>
        <span className={styles.buildingCode}>{building.code}</span>
        <div className={styles.buildingMeta}>
          <span>
            {building.floor_count} floor{building.floor_count !== 1 ? "s" : ""}
          </span>
          <span>
            {building.unit_count} unit{building.unit_count !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      {expanded && (
        <div className={styles.buildingBody}>
          {building.floors.length === 0 ? (
            <div className={styles.buildingEmpty}>No floors in this building.</div>
          ) : (
            building.floors.map((floor) => (
              <FloorNodeCard key={floor.id} floor={floor} />
            ))
          )}
        </div>
      )}
    </div>
  );
}
