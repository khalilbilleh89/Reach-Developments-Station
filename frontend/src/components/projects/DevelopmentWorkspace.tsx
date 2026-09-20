"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import { PROJECT_NAVIGATION, type ProjectSection } from "@/components/shell/navigation";
import { Icon } from "@/components/ui";

const DEVELOPMENT = new Set<ProjectSection>(["overview", "company", "land", "permits", "prelaunch", "consultant", "inventory"]);

/** Development has a property-focused treatment; other project modules share the platform theme. */
export function DevelopmentWorkspace({projectId, section, roles, children}: {
  projectId: string; section: ProjectSection; roles: Set<string>; children: ReactNode;
}) {
  const params = useSearchParams();
  if (!DEVELOPMENT.has(section)) return <div className="platform-workspace">{children}</div>;
  const items = PROJECT_NAVIGATION.flatMap(group => group.items)
    .filter(item => DEVELOPMENT.has(item.key) && (!item.visible || item.visible(roles)));
  return <div className="development-workspace">
    {!params.has("record") ? <nav className="development-nav" aria-label="Development workspaces">
      <span className="development-nav-label">Development</span>
      <div className="development-nav-links">{items.map(item => <Link key={item.key}
        href={`/projects/?${new URLSearchParams({project: projectId, section: item.key})}`}
        aria-current={section === item.key ? "page" : undefined} data-leaves-editor>
        <Icon name={item.icon} /><span>{item.label}</span>
      </Link>)}</div>
    </nav> : null}
    <div className="development-content">{children}</div>
  </div>;
}
