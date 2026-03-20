/**
 * NavConfig — central navigation configuration.
 *
 * All navigation items live here so that future role-based filtering,
 * module rollout, and icon assignment stay in one place instead of
 * being scattered across JSX.
 */

export interface NavItem {
  label: string;
  href: string;
  /** Lucide icon name or an icon component key — reserved for future use. */
  icon: string;
  section: "main" | "settings";
  requiresAuth: boolean;
  /** Role tags for future RBAC filtering — not enforced yet. */
  futureRoleTags?: string[];
}

export const NAV_ITEMS: NavItem[] = [
  // --- Main section --------------------------------------------------
  {
    label: "Dashboard",
    href: "/dashboard",
    icon: "LayoutDashboard",
    section: "main",
    requiresAuth: true,
  },
  {
    label: "Land",
    href: "/land",
    icon: "MapPin",
    section: "main",
    requiresAuth: true,
  },
  {
    label: "Projects",
    href: "/projects",
    icon: "FolderOpen",
    section: "main",
    requiresAuth: true,
  },
  {
    label: "Construction",
    href: "/construction",
    icon: "HardHat",
    section: "main",
    requiresAuth: true,
  },
  {
    label: "Units & Pricing",
    href: "/units-pricing",
    icon: "Tag",
    section: "main",
    requiresAuth: true,
  },
  {
    label: "Sales",
    href: "/sales",
    icon: "ShoppingCart",
    section: "main",
    requiresAuth: true,
  },
  {
    label: "Payment Plans",
    href: "/payment-plans",
    icon: "CreditCard",
    section: "main",
    requiresAuth: true,
  },
  {
    label: "Collections",
    href: "/collections",
    icon: "Wallet",
    section: "main",
    requiresAuth: true,
  },
  {
    label: "Finance",
    href: "/finance",
    icon: "BarChart2",
    section: "main",
    requiresAuth: true,
    futureRoleTags: ["finance_manager", "admin"],
  },
  {
    label: "Registry",
    href: "/registry",
    icon: "FileText",
    section: "main",
    requiresAuth: true,
  },
  {
    label: "Commission",
    href: "/commission",
    icon: "Percent",
    section: "main",
    requiresAuth: true,
    futureRoleTags: ["sales_manager", "admin"],
  },
  {
    label: "Cashflow",
    href: "/cashflow",
    icon: "TrendingUp",
    section: "main",
    requiresAuth: true,
    futureRoleTags: ["finance_manager", "admin"],
  },
  // --- Settings section ----------------------------------------------
  {
    label: "Settings",
    href: "/settings",
    icon: "Settings",
    section: "settings",
    requiresAuth: true,
  },
];

/** Returns nav items for a given section. */
export function getNavItemsBySection(section: NavItem["section"]): NavItem[] {
  return NAV_ITEMS.filter((item) => item.section === section);
}
