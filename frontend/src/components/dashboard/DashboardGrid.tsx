import React from "react";
import styles from "@/styles/dashboard.module.css";

interface DashboardGridProps {
  children: React.ReactNode;
}

/**
 * DashboardGrid — responsive 2-column grid that wraps dashboard sections.
 *
 * Collapses to a single column on mobile (≤768 px). Grid cells that need
 * full-width treatment should use the `fullWidth` class from the CSS module.
 */
export function DashboardGrid({ children }: DashboardGridProps) {
  return <div className={styles.grid}>{children}</div>;
}
