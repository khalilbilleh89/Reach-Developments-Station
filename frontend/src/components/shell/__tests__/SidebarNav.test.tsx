/**
 * SidebarNav tests — validates navigation item rendering and active
 * route highlighting.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { SidebarNav } from "../SidebarNav";
import { NAV_ITEMS } from "../NavConfig";

// Mock Next.js navigation
jest.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}));

// Mock Next.js Link
jest.mock("next/link", () => {
  const MockLink = ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
  MockLink.displayName = "MockLink";
  return MockLink;
});

jest.mock("../SidebarNav.module.css", () => ({
  nav: "nav",
  list: "list",
  item: "item",
  active: "active",
  icon: "icon",
  label: "label",
  divider: "divider",
}));

describe("SidebarNav", () => {
  it("renders without crashing", () => {
    render(<SidebarNav />);
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });

  it("renders all expected nav items", () => {
    render(<SidebarNav />);
    const expectedLabels = [
      "Dashboard",
      "Land",
      "Feasibility",
      "Scenarios",
      "Concept Design",
      "Projects",
      "Construction",
      "Units & Pricing",
      "Sales",
      "Payment Plans",
      "Collections",
      "Finance",
      "Registry",
      "Commission",
      "Cashflow",
      "Portfolio",
      "Settings",
    ];
    for (const label of expectedLabels) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("marks the active route with aria-current=page", () => {
    // pathname mocked to /dashboard
    render(<SidebarNav />);
    const dashboardLink = screen.getByRole("link", { name: /dashboard/i });
    expect(dashboardLink).toHaveAttribute("aria-current", "page");
  });

  it("does not mark inactive routes as current", () => {
    render(<SidebarNav />);
    const projectsLink = screen.getByRole("link", { name: /^projects$/i });
    expect(projectsLink).not.toHaveAttribute("aria-current");
  });

  it("hides labels when collapsed", () => {
    render(<SidebarNav collapsed={true} />);
    // Labels should not be visible
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
  });

  it("shows labels when not collapsed", () => {
    render(<SidebarNav collapsed={false} />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("renders links pointing to correct hrefs", () => {
    render(<SidebarNav />);
    expect(screen.getByRole("link", { name: /^projects$/i })).toHaveAttribute(
      "href",
      "/projects",
    );
    expect(screen.getByRole("link", { name: /finance/i })).toHaveAttribute(
      "href",
      "/finance",
    );
  });

  it("exports the correct number of nav items from NavConfig", () => {
    expect(NAV_ITEMS.length).toBeGreaterThanOrEqual(11);
  });

  it("includes both main and settings sections in NavConfig", () => {
    const mainItems = NAV_ITEMS.filter((i) => i.section === "main");
    const settingsItems = NAV_ITEMS.filter((i) => i.section === "settings");
    expect(mainItems.length).toBeGreaterThan(0);
    expect(settingsItems.length).toBeGreaterThan(0);
  });
});
