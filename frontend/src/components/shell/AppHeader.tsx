"use client";

import React from "react";
import styles from "./AppHeader.module.css";
import { logout } from "@/lib/auth";

interface AppHeaderProps {
  /** Current page title, shown in the header. */
  pageTitle?: string;
  /** Called when the sidebar toggle button is clicked. */
  onToggleSidebar?: () => void;
}

/**
 * AppHeader — top application bar.
 *
 * Contains: app name, page title, search placeholder,
 * notifications placeholder, and user menu placeholder.
 * Keep this clean — it is a product shell, not a billboard.
 */
export function AppHeader({ pageTitle, onToggleSidebar }: AppHeaderProps) {
  const handleLogout = () => {
    logout();
  };

  return (
    <header className={styles.header} role="banner">
      <div className={styles.left}>
        <button
          className={styles.toggleBtn}
          onClick={onToggleSidebar}
          aria-label="Toggle sidebar"
          type="button"
        >
          <span className={styles.hamburger} aria-hidden="true">☰</span>
        </button>

        <div className={styles.brand}>
          <span className={styles.brandName}>Reach Developments</span>
          {pageTitle && (
            <>
              <span className={styles.brandSep} aria-hidden="true">/</span>
              <span className={styles.pageTitle}>{pageTitle}</span>
            </>
          )}
        </div>
      </div>

      <div className={styles.center}>
        <div className={styles.searchPlaceholder} role="search">
          <span className={styles.searchIcon} aria-hidden="true">🔍</span>
          <span className={styles.searchHint}>Search…</span>
        </div>
      </div>

      <div className={styles.right}>
        <button
          className={styles.iconBtn}
          aria-label="Notifications"
          type="button"
          title="Notifications"
        >
          <span aria-hidden="true">🔔</span>
        </button>

        <button
          className={`${styles.iconBtn} ${styles.userMenu}`}
          aria-label="User menu"
          type="button"
          title="User menu"
        >
          <span className={styles.avatar} aria-hidden="true">👤</span>
        </button>

        <button
          className={styles.logoutBtn}
          onClick={handleLogout}
          type="button"
          aria-label="Log out"
        >
          Sign out
        </button>
      </div>
    </header>
  );
}
