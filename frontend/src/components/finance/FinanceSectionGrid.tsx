import React from "react";
import styles from "@/styles/finance-dashboard.module.css";

interface FinanceSectionGridProps {
  children: React.ReactNode;
}

/**
 * FinanceSectionGrid — responsive 2-column grid that wraps finance dashboard
 * sections. Collapses to a single column on mobile (≤768 px). Grid cells that
 * need full-width treatment should wrap their content in a div with the
 * `fullWidth` helper class from the finance-dashboard CSS module.
 */
export function FinanceSectionGrid({ children }: FinanceSectionGridProps) {
  return <div className={styles.sectionGrid}>{children}</div>;
}
