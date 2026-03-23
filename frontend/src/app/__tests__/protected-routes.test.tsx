/**
 * Protected routes tests — validates that the protected layout:
 *   1. renders nothing and redirects to /login when no token is present
 *   2. renders the AppShell only after the auth check confirms a valid token
 */
import React from "react";
import { render, screen, act } from "@testing-library/react";
import ProtectedLayout from "@/app/(protected)/layout";
import "@testing-library/jest-dom";

// ---------- Mocks --------------------------------------------------------

const mockPush = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/dashboard",
}));

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

jest.mock("@/lib/auth", () => ({
  logout: jest.fn(),
  getToken: jest.fn(),
  setToken: jest.fn(),
  clearToken: jest.fn(),
  isAuthenticated: jest.fn(),
  requireAuth: jest.fn(),
}));

jest.mock("@/components/shell/AppShell.module.css", () => ({}));
jest.mock("@/components/shell/AppHeader.module.css", () => ({}));
jest.mock("@/components/shell/SidebarNav.module.css", () => ({}));

import * as authLib from "@/lib/auth";

// ---------- Helpers ------------------------------------------------------

const mockGetToken = authLib.getToken as jest.Mock;

/** Make the auth lib return a valid token. */
function withToken() {
  mockGetToken.mockReturnValue("fake-token-123");
}

/** Make the auth lib return no token. */
function withoutToken() {
  mockGetToken.mockReturnValue(null);
}

// ---------- Tests --------------------------------------------------------

describe("Protected Layout", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("redirects to /login when no token is present", async () => {
    withoutToken();
    await act(async () => {
      render(
        <ProtectedLayout>
          <div data-testid="protected-child">Protected Content</div>
        </ProtectedLayout>,
      );
    });
    expect(mockPush).toHaveBeenCalledWith("/login");
  });

  it("does not render shell content when no token is present", async () => {
    withoutToken();
    await act(async () => {
      render(
        <ProtectedLayout>
          <div data-testid="protected-child">Protected Content</div>
        </ProtectedLayout>,
      );
    });
    expect(screen.queryByTestId("protected-child")).not.toBeInTheDocument();
    expect(screen.queryByRole("banner")).not.toBeInTheDocument();
  });

  it("renders children inside the AppShell when authenticated", async () => {
    withToken();
    await act(async () => {
      render(
        <ProtectedLayout>
          <div data-testid="protected-child">Protected Content</div>
        </ProtectedLayout>,
      );
    });
    expect(screen.getByTestId("protected-child")).toBeInTheDocument();
  });

  it("renders the navigation sidebar when authenticated", async () => {
    withToken();
    await act(async () => {
      render(
        <ProtectedLayout>
          <div>Child</div>
        </ProtectedLayout>,
      );
    });
    expect(
      screen.getByRole("navigation", { name: /main navigation/i }),
    ).toBeInTheDocument();
  });

  it("renders the header when authenticated", async () => {
    withToken();
    await act(async () => {
      render(
        <ProtectedLayout>
          <div>Child</div>
        </ProtectedLayout>,
      );
    });
    expect(screen.getByRole("banner")).toBeInTheDocument();
  });
});

