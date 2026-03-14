/**
 * Protected routes tests — validates that the protected layout redirects
 * unauthenticated users to /login and renders the AppShell for
 * authenticated users.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
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

jest.mock("@/components/shell/AppShell.module.css", () => ({}));
jest.mock("@/components/shell/AppHeader.module.css", () => ({}));
jest.mock("@/components/shell/SidebarNav.module.css", () => ({}));

// ---------- Helpers ------------------------------------------------------

/** Set a fake token in localStorage. */
function setFakeToken() {
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

/** Clear the token from localStorage. */
function clearFakeToken() {
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

// Import after mocks are registered
// eslint-disable-next-line @typescript-eslint/no-require-imports
const ProtectedLayout = require("@/app/(protected)/layout").default as React.FC<{
  children: React.ReactNode;
}>;

// ---------- Tests --------------------------------------------------------

describe("Protected Layout", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("redirects to /login when no token is present", () => {
    clearFakeToken();
    render(
      <ProtectedLayout>
        <div data-testid="protected-child">Protected Content</div>
      </ProtectedLayout>,
    );
    expect(mockPush).toHaveBeenCalledWith("/login");
  });

  it("renders children inside the AppShell when authenticated", () => {
    setFakeToken();
    render(
      <ProtectedLayout>
        <div data-testid="protected-child">Protected Content</div>
      </ProtectedLayout>,
    );
    expect(screen.getByTestId("protected-child")).toBeInTheDocument();
  });

  it("renders the navigation sidebar when authenticated", () => {
    setFakeToken();
    render(
      <ProtectedLayout>
        <div>Child</div>
      </ProtectedLayout>,
    );
    expect(
      screen.getByRole("navigation", { name: /main navigation/i }),
    ).toBeInTheDocument();
  });

  it("renders the header when authenticated", () => {
    setFakeToken();
    render(
      <ProtectedLayout>
        <div>Child</div>
      </ProtectedLayout>,
    );
    expect(screen.getByRole("banner")).toBeInTheDocument();
  });
});
