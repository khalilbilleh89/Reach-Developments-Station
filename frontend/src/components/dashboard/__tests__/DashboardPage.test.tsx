/**
 * DashboardPage tests
 */
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock Next.js navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
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

// Mock CSS modules
jest.mock("@/styles/dashboard.module.css", () => ({}));
jest.mock("@/components/shell/PageContainer.module.css", () => ({}));

// Mock all dashboard API calls
jest.mock("@/lib/dashboard-api", () => ({
  getProjects: jest.fn(),
  getFinancialSummary: jest.fn(),
  getRegistrationSummary: jest.fn(),
  getCashflowSummary: jest.fn(),
  getSalesExceptionsSummary: jest.fn(),
}));

import {
  getProjects,
  getFinancialSummary,
  getRegistrationSummary,
  getCashflowSummary,
  getSalesExceptionsSummary,
} from "@/lib/dashboard-api";

const mockGetProjects = getProjects as jest.Mock;
const mockGetFinancialSummary = getFinancialSummary as jest.Mock;
const mockGetRegistrationSummary = getRegistrationSummary as jest.Mock;
const mockGetCashflowSummary = getCashflowSummary as jest.Mock;
const mockGetSalesExceptionsSummary = getSalesExceptionsSummary as jest.Mock;

import DashboardPage from "@/app/(protected)/dashboard/page";

const mockProjects = [
  { id: "proj-1", name: "Marina Tower" },
  { id: "proj-2", name: "Palm Villa" },
];

const mockFinancial = {
  total_contract_value: 10_000_000,
  total_collected: 6_000_000,
  total_receivable: 4_000_000,
  collection_ratio: 0.6,
  units_sold: 40,
  total_units: 60,
  average_unit_price: 250_000,
};

const mockRegistration = {
  total_cases: 40,
  registered: 25,
  in_progress: 10,
  pending: 5,
  registration_progress_pct: 62.5,
};

const mockCashflow = {
  current_cash_position: 2_000_000,
  expected_inflows: 1_500_000,
  expected_outflows: 800_000,
  net_position: 700_000,
};

const mockExceptions = {
  total_exceptions: 5,
  total_discount_amount: 150_000,
  average_discount_pct: 3.2,
};

describe("DashboardPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetProjects.mockResolvedValue(mockProjects);
    mockGetFinancialSummary.mockResolvedValue(mockFinancial);
    mockGetRegistrationSummary.mockResolvedValue(mockRegistration);
    mockGetCashflowSummary.mockResolvedValue(mockCashflow);
    mockGetSalesExceptionsSummary.mockResolvedValue(mockExceptions);
  });

  it("renders the page title", () => {
    render(<DashboardPage />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("shows empty state before project is selected", async () => {
    // Projects load and auto-select first — delay to test empty state briefly
    mockGetProjects.mockReturnValue(new Promise(() => {}));
    render(<DashboardPage />);
    expect(screen.getByText(/No project selected/i)).toBeInTheDocument();
  });

  it("auto-selects the first project and loads dashboard sections", async () => {
    render(<DashboardPage />);

    // Wait for project selector to resolve and sections to render
    await waitFor(() =>
      expect(screen.getByText("Financial Summary")).toBeInTheDocument(),
    );

    expect(screen.getByText("Registration Progress")).toBeInTheDocument();
    expect(screen.getByText("Cashflow Snapshot")).toBeInTheDocument();
    expect(screen.getByText("Sales Exception Impact")).toBeInTheDocument();
  });

  it("renders financial metric values", async () => {
    render(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByText("AED 10.0M")).toBeInTheDocument(),
    );
    expect(screen.getByText("40 / 60")).toBeInTheDocument();
  });

  it("renders registration progress bar", async () => {
    render(<DashboardPage />);
    await waitFor(() =>
      expect(
        screen.getByRole("progressbar", { name: /registration progress/i }),
      ).toBeInTheDocument(),
    );
  });

  it("renders cashflow net position", async () => {
    render(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByText("Cashflow Snapshot")).toBeInTheDocument(),
    );
    // net_position is 700_000 → AED 700K
    expect(screen.getByText("AED 700K")).toBeInTheDocument();
  });

  it("renders sales exception count", async () => {
    render(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByText("Sales Exception Impact")).toBeInTheDocument(),
    );
    // "5" appears for both total_exceptions and registration pending count
    expect(screen.getAllByText("5").length).toBeGreaterThanOrEqual(1);
  });

  it("updates dashboard when project is switched", async () => {
    render(<DashboardPage />);

    await waitFor(() =>
      expect(screen.getByRole("combobox")).toBeInTheDocument(),
    );

    // Switch to project 2
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "proj-2" },
    });

    await waitFor(() => {
      expect(mockGetFinancialSummary).toHaveBeenCalledWith("proj-2");
    });
  });
});
