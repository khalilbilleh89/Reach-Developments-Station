/**
 * PortfolioProjectCards — per-project snapshot card grid.
 *
 * Renders one card per project from the portfolio dashboard API response.
 * Health badges are rendered as received from the backend — no badge logic
 * lives here. All null/sparse fields are handled safely.
 */

import React from "react";
import type { PortfolioProjectCard } from "@/lib/portfolio-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/portfolio.module.css";

interface PortfolioProjectCardsProps {
  projects: PortfolioProjectCard[];
}

function healthBadgeClass(badge: string | null): string {
  switch (badge) {
    case "on_track":
      return styles.badgeOnTrack;
    case "needs_attention":
      return styles.badgeNeedsAttention;
    case "at_risk":
      return styles.badgeAtRisk;
    default:
      return styles.badgeUnknown;
  }
}

function healthBadgeLabel(badge: string | null): string {
  switch (badge) {
    case "on_track":
      return "On Track";
    case "needs_attention":
      return "Needs Attention";
    case "at_risk":
      return "At Risk";
    default:
      return "—";
  }
}

export function PortfolioProjectCards({ projects }: PortfolioProjectCardsProps) {
  if (projects.length === 0) {
    return (
      <div className={styles.panelCard}>
        <h2 className={styles.panelTitle}>Projects</h2>
        <p className={styles.panelEmpty}>No projects found in portfolio.</p>
      </div>
    );
  }

  return (
    <div>
      <h2 className={styles.panelTitle}>Projects</h2>
      <div className={styles.projectGrid}>
        {projects.map((project) => (
          <div key={project.project_id} className={styles.projectCard}>
            <div className={styles.projectCardHeader}>
              <div>
                <div className={styles.projectName}>{project.project_name}</div>
                <div className={styles.projectCode}>{project.project_code}</div>
              </div>
              <span
                className={`${styles.healthBadge} ${healthBadgeClass(project.health_badge)}`}
                aria-label={`Health: ${healthBadgeLabel(project.health_badge)}`}
              >
                {healthBadgeLabel(project.health_badge)}
              </span>
            </div>

            <div className={styles.projectStats}>
              <div className={styles.statItem}>
                <span className={styles.statLabel}>Status</span>
                <span className={styles.statValue}>{project.status}</span>
              </div>
              <div className={styles.statItem}>
                <span className={styles.statLabel}>Total Units</span>
                <span className={styles.statValue}>{project.total_units}</span>
              </div>
              <div className={styles.statItem}>
                <span className={styles.statLabel}>Available</span>
                <span className={styles.statValue}>{project.available_units}</span>
              </div>
              <div className={styles.statItem}>
                <span className={styles.statLabel}>Sell-Through</span>
                <span className={styles.statValue}>
                  {project.sell_through_pct !== null
                    ? `${project.sell_through_pct.toFixed(1)}%`
                    : "—"}
                </span>
              </div>
              <div className={styles.statItem}>
                <span className={styles.statLabel}>Contracted</span>
                <span className={styles.statValue}>
                  {formatCurrency(project.contracted_revenue)}
                </span>
              </div>
              <div className={styles.statItem}>
                <span className={styles.statLabel}>Collected</span>
                <span className={styles.statValue}>
                  {formatCurrency(project.collected_cash)}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
