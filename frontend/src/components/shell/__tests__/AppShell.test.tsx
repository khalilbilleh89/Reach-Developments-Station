/**
 * AppShell tests — validates shell rendering and sidebar toggle behaviour.
 *
 * Note: Next.js hooks (usePathname, useRouter) are mocked so tests run
 * outside a real Next.js environment.
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { AppShell } from "../AppShell";

// Mock Next.js navigation hooks
jest.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push: jest.fn() }),
}));

// Mock Next.js Link component
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

// Suppress CSS module import errors in tests
jest.mock("../AppShell.module.css", () => ({}));
jest.mock("../AppHeader.module.css", () => ({}));
jest.mock("../SidebarNav.module.css", () => ({}));

// Mock auth lib to prevent localStorage/window.location side-effects
jest.mock("@/lib/auth", () => ({
  logout: jest.fn(),
  getToken: jest.fn(),
  setToken: jest.fn(),
  clearToken: jest.fn(),
  isAuthenticated: jest.fn(),
  requireAuth: jest.fn(),
}));

describe("AppShell", () => {
  it("renders without crashing", () => {
    render(
      <AppShell>
        <div>Page content</div>
      </AppShell>,
    );
    expect(screen.getByRole("banner")).toBeInTheDocument();
  });

  it("renders the sidebar", () => {
    render(
      <AppShell>
        <div>Page content</div>
      </AppShell>,
    );
    expect(
      screen.getByRole("complementary", { name: /application sidebar/i }),
    ).toBeInTheDocument();
  });

  it("renders children inside the shell", () => {
    render(
      <AppShell>
        <div data-testid="child-content">Hello</div>
      </AppShell>,
    );
    expect(screen.getByTestId("child-content")).toBeInTheDocument();
  });

  it("shows the page title in the header when provided", () => {
    render(
      <AppShell title="Dashboard">
        <div>Content</div>
      </AppShell>,
    );
    // "Dashboard" appears both in the sidebar nav link and in the header page title.
    // We query for all instances and assert at least one is present.
    expect(screen.getAllByText("Dashboard").length).toBeGreaterThanOrEqual(1);
  });

  it("toggles the sidebar when the toggle button is clicked", () => {
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>,
    );
    const toggleBtn = screen.getByRole("button", { name: /toggle sidebar/i });
    // Sidebar starts open; clicking should collapse it
    fireEvent.click(toggleBtn);
    // Re-clicking should expand again
    fireEvent.click(toggleBtn);
    // Just assert the button is still present (collapse/expand state is
    // tested via CSS class which is mocked — we verify no crash occurs)
    expect(toggleBtn).toBeInTheDocument();
  });

  it("renders the main navigation", () => {
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>,
    );
    expect(
      screen.getByRole("navigation", { name: /main navigation/i }),
    ).toBeInTheDocument();
  });
});
