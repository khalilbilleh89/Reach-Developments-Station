import React from "react";
import styles from "./PageContainer.module.css";

interface PageContainerProps {
  /** Page title displayed at the top of the content area. */
  title: string;
  /** Optional subtitle / description below the title. */
  subtitle?: string;
  /** Optional slot for top-right action buttons. */
  actions?: React.ReactNode;
  children: React.ReactNode;
}

/**
 * PageContainer — reusable content wrapper for all protected pages.
 *
 * Responsibilities:
 *   - consistent spacing and max-width
 *   - page title / subtitle pattern
 *   - optional top-right actions slot
 *
 * This becomes the backbone for PR-018 through PR-022.
 */
export function PageContainer({
  title,
  subtitle,
  actions,
  children,
}: PageContainerProps) {
  return (
    <main className={styles.container} id="main-content">
      <div className={styles.header}>
        <div className={styles.titleBlock}>
          <h1 className={styles.title}>{title}</h1>
          {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
        </div>
        {actions && <div className={styles.actions}>{actions}</div>}
      </div>

      <div className={styles.body}>{children}</div>
    </main>
  );
}
