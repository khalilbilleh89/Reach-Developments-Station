/**
 * Protected routes tests — validates that the protected layout:
 *   1. renders nothing and redirects to /login when no token is present
 *   2. renders the AppShell only after the auth check confirms a valid token
 */
import React from "react";
import { render, screen, act } from "@testing-library/react";
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

// ---------- Helpers ------------------------------------------------------

/** Make localStorage return a valid token. */
function withToken() {
  Object.defineProperty(window, "localStorage", {
    value: {
      getItem: (key: string) =>
        key === "reach_access_token" ? "fake-token-123" : null,
      setItem: jest.fn(),
      removeItem: jest.fn(),
      clear: jest.fn(),
    },
    writable: true,
  });
}

/** Make localStorage return no token. */
function withoutToken() {
  Object.defineProperty(window, "localStorage", {
    value: {
      getItem: () => null,
      setItem: jest.fn(),
      removeItem: jest.fn(),
      clear: jest.fn(),
    },
    writable: true,
  });
}

// ---------- Test target --------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-require-imports
const ProtectedLayout = require("@/app/(protected)/layout").default as React.FC<{
  children: React.ReactNode;
}>;

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

