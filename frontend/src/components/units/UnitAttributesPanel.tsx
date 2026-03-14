import React from "react";
import type { UnitDetail } from "@/lib/units-types";
import styles from "@/styles/units-pricing.module.css";

interface UnitAttributesPanelProps {
  unit: UnitDetail;
}

interface Attribute {
  label: string;
  value: string | null;
}

/**
 * UnitAttributesPanel — displays the physical and commercial attributes
 * of a unit to support real sales conversations.
 *
 * Shows unit number, type, floor reference, areas (internal + individual
 * outdoor components), and current commercial status.
 *
 * All values are sourced from the unit API response; no calculations are
 * performed beyond safe null checks for optional outdoor area fields.
 */
export function UnitAttributesPanel({ unit }: UnitAttributesPanelProps) {
  const attributes: Attribute[] = [
    { label: "Unit Number", value: unit.unit_number },
    {
      label: "Unit Type",
      value: unit.unit_type.replace(/_/g, " "),
    },
    {
      label: "Status",
      value: unit.status.replace(/_/g, " "),
    },
    {
      label: "Internal Area",
      value: `${unit.internal_area.toFixed(1)} sqm`,
    },
    {
      label: "Gross Area",
      value: unit.gross_area != null ? `${unit.gross_area.toFixed(1)} sqm` : null,
    },
    {
      label: "Balcony Area",
      value:
        unit.balcony_area != null
          ? `${unit.balcony_area.toFixed(1)} sqm`
          : null,
    },
    {
      label: "Terrace Area",
      value:
        unit.terrace_area != null
          ? `${unit.terrace_area.toFixed(1)} sqm`
          : null,
    },
    {
      label: "Roof Garden",
      value:
        unit.roof_garden_area != null
          ? `${unit.roof_garden_area.toFixed(1)} sqm`
          : null,
    },
    {
      label: "Front Garden",
      value:
        unit.front_garden_area != null
          ? `${unit.front_garden_area.toFixed(1)} sqm`
          : null,
    },
  ].filter((a): a is { label: string; value: string } => a.value !== null);

  return (
    <div className={styles.attributesCard} aria-label="Unit attributes">
      <h2 className={styles.attributesTitle}>Unit Attributes</h2>
      <div className={styles.attributesGrid}>
        {attributes.map((attr) => (
          <div key={attr.label} className={styles.attributeItem}>
            <span className={styles.attributeLabel}>{attr.label}</span>
            <span
              className={styles.attributeValue}
              style={{ textTransform: "capitalize" }}
            >
              {attr.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
