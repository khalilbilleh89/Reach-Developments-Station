import type { IconName } from "@/components/ui/Icon";
import {
  AUDIT_READERS,
  COLLECTION_READERS,
  ECONOMICS_READERS,
  INTERNAL_PRICE_READERS,
  PLAN_READERS,
  ROLE_SYSTEM_ADMIN,
  SALES_READERS,
  hasAnyRole,
} from "@/lib/roles";
import type { Roles } from "@/lib/roles";

/**
 * The map of the product.
 *
 * A project is navigated top to bottom in the order a development happens:
 * the land it sits on and the consents it needs, the units it becomes, what
 * they are priced at, who buys them, how the money is scheduled and collected,
 * and what each one earned. The groups are that lifecycle; the sidebar draws
 * them and nothing else does.
 *
 * This is UI composition, not a plugin system. When PR-MVP-09 lands,
 * Construction is one entry under a new Delivery group; when PR-MVP-10 lands,
 * Cashflow & Reporting is a second entry under Finance. A group with no
 * visible entries is not drawn, so nothing is ever advertised before it exists.
 *
 * `visible` mirrors the backend's reader sets for the module. A person whose
 * every request to a module would be refused is not shown the door — that is
 * courtesy, not security, and the server decides again on each call.
 */

export type ProjectSection =
  | "overview"
  | "land"
  | "permits"
  | "inventory"
  | "pricing"
  | "sales"
  | "payments"
  | "collections"
  | "economics"
  | "documents"
  | "access";

export interface NavItem<Key extends string = string> {
  key: Key;
  label: string;
  icon: IconName;
  /** One sentence under the page title: what this place is for. */
  description: string;
  visible?: (roles: Roles) => boolean;
}

export interface NavGroup<Key extends string = string> {
  key: string;
  /** Null for a group drawn without a heading (the project's front page). */
  label: string | null;
  items: NavItem<Key>[];
}

const everyone = () => true;

export const PROJECT_NAVIGATION: NavGroup<ProjectSection>[] = [
  {
    key: "home",
    label: null,
    items: [
      {
        key: "overview",
        label: "Overview",
        icon: "overview",
        description: "Where this development stands, and what needs attention.",
        visible: everyone,
      },
    ],
  },
  {
    key: "development",
    label: "Development",
    items: [
      {
        key: "land",
        label: "Land",
        icon: "land",
        description: "The parcels this development sits on, and what may be built on them.",
        visible: everyone,
      },
      {
        key: "permits",
        label: "Permits",
        icon: "permits",
        description: "The consents this development needs, and which of them are late.",
        visible: everyone,
      },
      {
        key: "inventory",
        label: "Inventory",
        icon: "inventory",
        description: "Every unit in this development, and what stops each one being released.",
        visible: everyone,
      },
    ],
  },
  {
    key: "commercial",
    label: "Commercial",
    items: [
      {
        key: "pricing",
        label: "Pricing",
        icon: "pricing",
        description: "What this development is priced at, and what that price is made of.",
        visible: (roles) => hasAnyRole(roles, INTERNAL_PRICE_READERS),
      },
      {
        key: "sales",
        label: "Sales & Legal",
        icon: "sales",
        description: "Where every unit stands commercially, legally and on delivery.",
        visible: (roles) => hasAnyRole(roles, SALES_READERS),
      },
      {
        key: "payments",
        label: "Payment Plans",
        icon: "payments",
        description: "How each contracted amount is scheduled to be paid, and what makes it due.",
        visible: (roles) => hasAnyRole(roles, PLAN_READERS),
      },
      {
        key: "collections",
        label: "Collections",
        icon: "collections",
        description: "What the buyers have actually paid, what is still owed, and how old it is.",
        visible: (roles) => hasAnyRole(roles, COLLECTION_READERS),
      },
    ],
  },
  {
    key: "finance",
    label: "Finance",
    items: [
      {
        key: "economics",
        label: "Unit Economics",
        icon: "economics",
        description: "What each unit costs, what it earns, and the governed basis that says so.",
        visible: (roles) => hasAnyRole(roles, ECONOMICS_READERS),
      },
    ],
  },
  {
    key: "governance",
    label: "Governance",
    items: [
      {
        key: "documents",
        label: "Documents",
        icon: "documents",
        description: "Links to documents held elsewhere. Nothing is uploaded or stored here.",
        visible: everyone,
      },
      {
        key: "access",
        label: "Access",
        icon: "access",
        description: "Who may open this project. Roles decide what they can do once inside.",
        visible: (roles) => roles.has(ROLE_SYSTEM_ADMIN),
      },
    ],
  },
];

export type SettingsSection =
  | "users"
  | "currencies"
  | "country"
  | "reference"
  | "audit"
  | "account";

export const SETTINGS_NAVIGATION: NavGroup<SettingsSection>[] = [
  {
    key: "configuration",
    label: "Configuration",
    items: [
      {
        key: "country",
        label: "Country packs",
        icon: "land",
        description: "The tax, currency and legal defaults a project inherits when it is created.",
        visible: everyone,
      },
      {
        key: "currencies",
        label: "Currencies",
        icon: "collections",
        description: "The currencies this business transacts in. No exchange rates are stored.",
        visible: everyone,
      },
      {
        key: "reference",
        label: "Reference data",
        icon: "documents",
        description: "The controlled vocabularies every project chooses its codes from.",
        visible: everyone,
      },
    ],
  },
  {
    key: "people",
    label: "People",
    items: [
      {
        key: "users",
        label: "Users & roles",
        icon: "user",
        description: "Who has an account, and what each of them may do across the portfolio.",
        visible: (roles) => roles.has(ROLE_SYSTEM_ADMIN),
      },
      {
        key: "audit",
        label: "Audit",
        icon: "permits",
        description: "What was changed, by whom, and when.",
        visible: (roles) => hasAnyRole(roles, AUDIT_READERS),
      },
    ],
  },
  {
    key: "me",
    label: "Your account",
    items: [
      {
        key: "account",
        label: "Password",
        icon: "access",
        description: "Change the password you sign in with.",
        visible: everyone,
      },
    ],
  },
];

/** The groups a person may see, with empty groups dropped rather than drawn. */
export function visibleNavigation<Key extends string>(
  groups: NavGroup<Key>[],
  roles: Roles,
): NavGroup<Key>[] {
  return groups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => (item.visible ?? everyone)(roles)),
    }))
    .filter((group) => group.items.length > 0);
}

/** The entry for one section, wherever it sits in the groups. */
export function findNavItem<Key extends string>(
  groups: NavGroup<Key>[],
  key: Key,
): NavItem<Key> | undefined {
  for (const group of groups) {
    const item = group.items.find((entry) => entry.key === key);
    if (item) return item;
  }
  return undefined;
}

const PROJECT_SECTIONS = new Set<string>(
  PROJECT_NAVIGATION.flatMap((group) => group.items.map((item) => item.key)),
);

const SETTINGS_SECTIONS = new Set<string>(
  SETTINGS_NAVIGATION.flatMap((group) => group.items.map((item) => item.key)),
);

export function isProjectSection(value: string | null | undefined): value is ProjectSection {
  return value !== null && value !== undefined && PROJECT_SECTIONS.has(value);
}

export function isSettingsSection(value: string | null | undefined): value is SettingsSection {
  return value !== null && value !== undefined && SETTINGS_SECTIONS.has(value);
}

/** The one sentence under a project section's title. Written once, here. */
export function sectionDescription(key: ProjectSection): string {
  return findNavItem(PROJECT_NAVIGATION, key)?.description ?? "";
}

/** The address of a project section. The frontend is a static export, so the
 * open project and its section travel in the query string. */
export function projectHref(projectId: string, section: ProjectSection = "overview"): string {
  const params = new URLSearchParams({ project: projectId });
  if (section !== "overview") params.set("section", section);
  return `/projects/?${params.toString()}`;
}

export function settingsHref(section: SettingsSection = "country"): string {
  return section === "country" ? "/settings/" : `/settings/?section=${section}`;
}
