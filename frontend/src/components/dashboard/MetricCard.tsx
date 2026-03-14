import React from "react";
import styles from "@/styles/dashboard.module.css";

interface MetricCardProps {
  /** Card heading label. */
  title: string;
  /** Primary value displayed prominently. */
  value: string | number;
  /** Optional supporting text below the value. */
  subtitle?: string;
  /** Optional trend indicator: positive / negative / neutral direction. */
  trend?: { label: string; direction: "up" | "down" | "neutral" };
  /** Optional icon rendered in the top-right corner. */
  icon?: string;
}

/**
 * MetricCard — reusable stat card used across all dashboard sections.
 *
 * Renders a title, large primary value, optional subtitle, optional trend
 * indicator and optional icon. No data fetching — purely presentational.
 */
export function MetricCard({
  title,
  value,
  subtitle,
  trend,
  icon,
}: MetricCardProps) {
  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <span className={styles.cardTitle}>{title}</span>
        {icon && (
          <span className={styles.cardIcon} aria-hidden="true">
            {icon}
          </span>
        )}
      </div>

      <div className={styles.cardValue}>{value}</div>

      {subtitle && <div className={styles.cardSubtitle}>{subtitle}</div>}

      {trend && (
        <div
          className={`${styles.cardTrend} ${
            trend.direction === "up"
              ? styles.trendUp
              : trend.direction === "down"
                ? styles.trendDown
                : ""
          }`}
        >
          {trend.direction === "up" ? "↑" : trend.direction === "down" ? "↓" : "→"}{" "}
          {trend.label}
        </div>
      )}
    </div>
  );
}
