"use client";

import Link from "next/link";

import { Icon } from "@/components/ui";
import type { IconName } from "@/components/ui";
import type { CurrentUser } from "@/lib/api";
import { hasAnyRole, PORTFOLIO_READERS, roleSet } from "@/lib/roles";

import { PROJECT_NAVIGATION, projectHref, settingsHref, visibleNavigation } from "./navigation";
import type { ProjectSection } from "./navigation";
import type { ShellArea } from "./AppShell";

/** The project sections a thumb reaches first; the rest live under More. */
const PROJECT_TABS: ProjectSection[] = ["overview", "inventory", "sales", "collections"];

/**
 * On a phone the most used areas sit in a bar at the bottom, where a thumb is
 * (design system L3). Inside a project: Overview, Inventory, Sales and
 * Collections, each only when this person may open it; elsewhere Portfolio,
 * Projects and Settings. More opens the full navigation page.
 */
export function PhoneTabs({ user, area, projectId, section, onMore }: {
  user: CurrentUser;
  area: ShellArea;
  projectId?: string;
  section?: string;
  onMore: () => void;
}) {
  const roles = roleSet(user.roles);
  const tabs: { key: string; label: string; icon: IconName; href: string; current: boolean }[] = [];
  if (area === "projects" && projectId) {
    const visible = new Map(visibleNavigation(PROJECT_NAVIGATION, roles).flatMap((group) => group.items.map((item) => [item.key, item] as const)));
    for (const key of PROJECT_TABS) {
      const item = visible.get(key);
      if (item) tabs.push({ key, label: item.label, icon: item.icon, href: projectHref(projectId, key), current: section === key });
    }
  } else {
    if (hasAnyRole(roles, PORTFOLIO_READERS)) tabs.push({ key: "portfolio", label: "Portfolio", icon: "overview", href: "/portfolio/", current: area === "portfolio" });
    tabs.push({ key: "projects", label: "Projects", icon: "projects", href: "/projects/", current: area === "projects" });
    tabs.push({ key: "settings", label: "Settings", icon: "settings", href: settingsHref(), current: area === "settings" });
  }
  return (
    <nav className="phone-tabs" aria-label="Quick navigation">
      {tabs.map((tab) => (
        <Link key={tab.key} href={tab.href} className="phone-tab" aria-current={tab.current ? "page" : undefined}>
          <Icon name={tab.icon} />
          <span>{tab.label}</span>
        </Link>
      ))}
      <button type="button" className="phone-tab" aria-controls="mobile-navigation" onClick={onMore}>
        <Icon name="menu" />
        <span>More</span>
      </button>
    </nav>
  );
}
