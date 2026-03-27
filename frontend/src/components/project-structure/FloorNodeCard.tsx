"use client";

import React, { useState } from "react";
import type { ProjectStructureFloorNode } from "@/lib/project-structure-types";
import { UnitNodeRow } from "@/components/project-structure/UnitNodeRow";
import styles from "@/styles/project-structure.module.css";

interface FloorNodeCardProps {
  floor: ProjectStructureFloorNode;
}

export function FloorNodeCard({ floor }: FloorNodeCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={styles.floorCard}>
      <div
        className={styles.floorHeader}
        onClick={() => setExpanded((prev) => !prev)}
        role="button"
        aria-expanded={expanded}
        aria-label={`Floor: ${floor.name}`}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") setExpanded((prev) => !prev);
        }}
      >
        <span className={styles.floorToggle}>{expanded ? "▾" : "▸"}</span>
        <span className={styles.floorTitle}>{floor.name}</span>
        <span className={styles.floorCode}>{floor.code}</span>
        <span className={styles.floorMeta}>
          {floor.unit_count} unit{floor.unit_count !== 1 ? "s" : ""}
        </span>
      </div>

      {expanded && (
        <div className={styles.floorBody}>
          {floor.units.length === 0 ? (
            <div className={styles.floorEmpty}>No units on this floor.</div>
          ) : (
            <table
              className={styles.unitsTable}
              aria-label={`Units on floor ${floor.name}`}
            >
              <thead>
                <tr>
                  <th scope="col">Unit</th>
                  <th scope="col">Type</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {floor.units.map((unit) => (
                  <UnitNodeRow key={unit.id} unit={unit} />
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
