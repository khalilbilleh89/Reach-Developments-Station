"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS, getNavItemsBySection } from "./NavConfig";
import styles from "./SidebarNav.module.css";

interface SidebarNavProps {
  collapsed?: boolean;
}

/**
 * SidebarNav — main application navigation component.
 *
 * Renders config-driven nav items grouped by section. Highlights
 * the active route and supports future role-based item hiding.
 * Icons are rendered as Unicode emoji placeholders until a proper
 * icon library is wired up in a later PR.
 */
export function SidebarNav({ collapsed = false }: SidebarNavProps) {
  const pathname = usePathname();

  const mainItems = getNavItemsBySection("main");
  const settingsItems = getNavItemsBySection("settings");

  const isActive = (href: string) => {
    if (href === "/dashboard") return pathname === href;
    return pathname.startsWith(href);
  };

  return (
    <nav className={styles.nav} aria-label="Main navigation">
      <ul className={styles.list} role="list">
        {mainItems.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className={`${styles.item} ${isActive(item.href) ? styles.active : ""}`}
              aria-current={isActive(item.href) ? "page" : undefined}
              title={collapsed ? item.label : undefined}
            >
              <span className={styles.icon} aria-hidden="true">
                {ICON_MAP[item.icon] ?? "•"}
              </span>
              {!collapsed && (
                <span className={styles.label}>{item.label}</span>
              )}
            </Link>
          </li>
        ))}
      </ul>

      <div className={styles.divider} />

      <ul className={styles.list} role="list">
        {settingsItems.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className={`${styles.item} ${isActive(item.href) ? styles.active : ""}`}
              aria-current={isActive(item.href) ? "page" : undefined}
              title={collapsed ? item.label : undefined}
            >
              <span className={styles.icon} aria-hidden="true">
                {ICON_MAP[item.icon] ?? "•"}
              </span>
              {!collapsed && (
                <span className={styles.label}>{item.label}</span>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** Minimal inline icon map — replace with a proper icon library later. */
const ICON_MAP: Record<string, string> = {
  LayoutDashboard: "⊞",
  MapPin: "📍",
  Calculator: "📐",
  Layers: "⧉",
  PenTool: "✏️",
  FolderOpen: "📁",
  HardHat: "🪖",
  Tag: "🏷",
  ShoppingCart: "🛒",
  CreditCard: "💳",
  Wallet: "💰",
  BarChart2: "📊",
  FileText: "📄",
  Percent: "%",
  TrendingUp: "📈",
  Settings: "⚙",
};

export { NAV_ITEMS };
