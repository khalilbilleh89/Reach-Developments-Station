"use client";

import React, { useState } from "react";
import { AppHeader } from "./AppHeader";
import { SidebarNav } from "./SidebarNav";
import styles from "./AppShell.module.css";

interface Breadcrumb {
  label: string;
  href?: string;
}

interface AppShellProps {
  /** Current page title shown in the header. */
  title?: string;
  /** Breadcrumb trail for the current page (reserved for future use). */
  breadcrumbs?: Breadcrumb[];
  children: React.ReactNode;
}

/**
 * AppShell — primary reusable application shell component.
 *
 * Responsibilities:
 *   - frame layout (header + sidebar + content)
 *   - sidebar collapse / expand toggle
 *   - mobile sidebar overlay behaviour
 *   - breadcrumb / page title slot
 *
 * This component is layout-only. No data fetching happens here.
 */
export function AppShell({ title, breadcrumbs, children }: AppShellProps) {
  // breadcrumbs reserved for future nav breadcrumb component
  void breadcrumbs;
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);

  const toggleSidebar = () => {
    if (typeof window !== "undefined" && window.innerWidth < 768) {
      setMobileOpen((prev) => !prev);
    } else {
      setSidebarOpen((prev) => !prev);
    }
  };

  const closeMobile = () => setMobileOpen(false);

  return (
    <div className={styles.shell}>
      {/* Mobile overlay backdrop */}
      {mobileOpen && (
        <div
          className={styles.backdrop}
          onClick={closeMobile}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={[
          styles.sidebar,
          sidebarOpen ? styles.sidebarOpen : styles.sidebarCollapsed,
          mobileOpen ? styles.mobileVisible : "",
        ]
          .filter(Boolean)
          .join(" ")}
        aria-label="Application sidebar"
      >
        <div className={styles.sidebarLogo}>
          {sidebarOpen ? (
            <span className={styles.logoFull}>Reach</span>
          ) : (
            <span className={styles.logoMark}>R</span>
          )}
        </div>

        <SidebarNav collapsed={!sidebarOpen} />
      </aside>

      {/* Main content area */}
      <div className={styles.main}>
        <AppHeader pageTitle={title} onToggleSidebar={toggleSidebar} />

        <div className={styles.content}>{children}</div>
      </div>
    </div>
  );
}
