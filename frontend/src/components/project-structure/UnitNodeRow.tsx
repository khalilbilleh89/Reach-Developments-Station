"use client";

import React from "react";
import type { ProjectStructureUnitNode } from "@/lib/project-structure-types";
import styles from "@/styles/project-structure.module.css";

interface UnitNodeRowProps {
  unit: ProjectStructureUnitNode;
}

function unitStatusClass(status: string): string {
  switch (status) {
    case "available":
      return styles.statusAvailable;
    case "reserved":
      return styles.statusReserved;
    case "under_contract":
      return styles.statusUnderContract;
    case "registered":
      return styles.statusRegistered;
    default:
      return styles.statusDefault;
  }
}

function unitStatusLabel(status: string): string {
  return status.replace(/_/g, " ");
}

export function UnitNodeRow({ unit }: UnitNodeRowProps) {
  return (
    <tr>
      <td>{unit.unit_number}</td>
      <td>{unit.unit_type.replace(/_/g, " ")}</td>
      <td>
        <span className={`${styles.statusBadge} ${unitStatusClass(unit.status)}`}>
          {unitStatusLabel(unit.status)}
        </span>
      </td>
    </tr>
  );
}
