/**
 * FinanceDashboardPage tests
 */
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock Next.js navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => "/finance",
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
jest.mock("@/styles/finance-dashboard.module.css", () => ({}));
jest.mock("@/styles/dashboard.module.css", () => ({}));
jest.mock("@/components/shell/PageContainer.module.css", () => ({}));

// Mock finance dashboard API
jest.mock("@/lib/finance-dashboard-api", () => ({
  getProjects: jest.fn(),
  getProjectFinanceSummary: jest.fn(),
  getProjectCashflowSummary: jest.fn(),
  getProjectSalesExceptionsSummary: jest.fn(),
  getProjectRegistrationSummary: jest.fn(),
  getProjectCommissionSummary: jest.fn(),
}));

import {
  getProjects,
  getProjectFinanceSummary,
  getProjectCashflowSummary,
  getProjectSalesExceptionsSummary,
  getProjectRegistrationSummary,
  getProjectCommissionSummary,
} from "@/lib/finance-dashboard-api";

const mockGetProjects = getProjects as jest.Mock;
const mockGetProjectFinanceSummary = getProjectFinanceSummary as jest.Mock;
const mockGetProjectCashflowSummary = getProjectCashflowSummary as jest.Mock;
const mockGetProjectSalesExceptionsSummary =
  getProjectSalesExceptionsSummary as jest.Mock;
const mockGetProjectRegistrationSummary =
  getProjectRegistrationSummary as jest.Mock;
const mockGetProjectCommissionSummary = getProjectCommissionSummary as jest.Mock;

import FinanceDashboardPage from "@/app/(protected)/finance/page";

const mockProjects = [
  { id: "proj-1", name: "Marina Tower", code: "MT-01", status: "active" },
  { id: "proj-2", name: "Palm Villa", code: "PV-01", status: "active" },
];

const mockFinanceSummary = {
  kpis: {
    total_contract_value: 10_000_000,
    total_collected: 6_000_000,
    total_receivable: 4_000_000,
    collection_ratio: 0.6,
    units_sold: 40,
    total_units: 60,
    average_unit_price: 250_000,
  },
  collections: {
    total_collected: 6_000_000,
    total_receivable: 4_000_000,
    collection_ratio: 0.6,
  },
};

const mockCashflow = {
  expected_inflows: 2_000_000,
  expected_outflows: 1_000_000,
  net_cashflow: 1_000_000,
  closing_balance: 3_000_000,
};

const mockExceptions = {
  total_exceptions: 3,
  approved_exceptions: 2,
  pending_exceptions: 1,
  rejected_exceptions: 0,
  total_discount_amount: 50_000,
  total_incentive_value: 10_000,
};

const mockRegistration = {
  total_sold_units: 40,
  registration_cases_completed: 35,
  registration_cases_open: 5,
  sold_not_registered: 0,
  completion_ratio: 0.875,
};

const mockCommission = {
  total_payouts: 5,
  approved_payouts: 3,
  calculated_payouts: 2,
  total_gross_value: 5_000_000,
  total_commission_pool: 250_000,
};

describe("FinanceDashboardPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetProjects.mockResolvedValue(mockProjects);
    mockGetProjectFinanceSummary.mockResolvedValue(mockFinanceSummary);
    mockGetProjectCashflowSummary.mockResolvedValue(mockCashflow);
    mockGetProjectSalesExceptionsSummary.mockResolvedValue(mockExceptions);
    mockGetProjectRegistrationSummary.mockResolvedValue(mockRegistration);
    mockGetProjectCommissionSummary.mockResolvedValue(mockCommission);
  });

  it("renders the page title", () => {
    render(<FinanceDashboardPage />);
    expect(screen.getByText("Finance")).toBeInTheDocument();
  });

  it("shows loading state while projects are loading", () => {
    mockGetProjects.mockReturnValue(new Promise(() => {}));
    render(<FinanceDashboardPage />);
    expect(screen.getByText(/Loading projects/i)).toBeInTheDocument();
  });

  it("shows empty state before project is selected", async () => {
    mockGetProjects.mockReturnValue(new Promise(() => {}));
    render(<FinanceDashboardPage />);
    expect(screen.getByText(/No project selected/i)).toBeInTheDocument();
  });

  it("auto-selects the first project and renders finance sections", async () => {
    render(<FinanceDashboardPage />);

    await waitFor(() =>
      expect(screen.getByText("Finance KPIs")).toBeInTheDocument(),
    );

    expect(screen.getByText("Collections Health")).toBeInTheDocument();
    expect(screen.getByText("Cashflow Health")).toBeInTheDocument();
    expect(screen.getByText("Commission Exposure")).toBeInTheDocument();
    expect(screen.getByText("Sales Exception Impact")).toBeInTheDocument();
    expect(screen.getByText("Registration Signal")).toBeInTheDocument();
    expect(screen.getByText("Finance Health Summary")).toBeInTheDocument();
  });

  it("renders correct KPI values for selected project", async () => {
    render(<FinanceDashboardPage />);

    await waitFor(() =>
      expect(screen.getByText("AED 10.0M")).toBeInTheDocument(),
    );
  });

  it("renders cashflow section correctly", async () => {
    render(<FinanceDashboardPage />);

    await waitFor(() =>
      expect(screen.getByText("Cashflow Health")).toBeInTheDocument(),
    );
    // closing_balance = 3_000_000 → "AED 3.0M" (unique in cashflow section)
    expect(screen.getByText("AED 3.0M")).toBeInTheDocument();
  });

  it("renders registration completion progress bar", async () => {
    render(<FinanceDashboardPage />);

    await waitFor(() =>
      expect(
        screen.getByRole("progressbar", { name: /registration completion/i }),
      ).toBeInTheDocument(),
    );
  });

  it("renders finance health summary badges", async () => {
    render(<FinanceDashboardPage />);

    await waitFor(() =>
      expect(screen.getByText("Finance Health Summary")).toBeInTheDocument(),
    );
    // Collections ratio 0.6 → healthy
    expect(screen.getByText(/Collections healthy/)).toBeInTheDocument();
    // Cashflow net = +1M → positive
    expect(screen.getByText(/Cashflow positive/)).toBeInTheDocument();
  });

  it("updates dashboard sections when project is switched", async () => {
    render(<FinanceDashboardPage />);

    await waitFor(() =>
      expect(screen.getByRole("combobox")).toBeInTheDocument(),
    );

    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "proj-2" },
    });

    await waitFor(() => {
      expect(mockGetProjectFinanceSummary).toHaveBeenCalledWith("proj-2");
      expect(mockGetProjectCashflowSummary).toHaveBeenCalledWith("proj-2");
    });
  });

  it("handles project list error gracefully", async () => {
    mockGetProjects.mockRejectedValue(new Error("Server unavailable"));
    render(<FinanceDashboardPage />);

    await waitFor(() =>
      expect(screen.getByText("Server unavailable")).toBeInTheDocument(),
    );
  });

  it("renders sales exception impact section correctly", async () => {
    render(<FinanceDashboardPage />);

    await waitFor(() =>
      expect(screen.getByText("Sales Exception Impact")).toBeInTheDocument(),
    );
    // total_exceptions = 3
    expect(screen.getAllByText("3").length).toBeGreaterThanOrEqual(1);
  });

  it("renders commission section correctly", async () => {
    render(<FinanceDashboardPage />);

    await waitFor(() =>
      expect(screen.getByText("Commission Exposure")).toBeInTheDocument(),
    );
    // approved_payouts = 3
    expect(screen.getAllByText("3").length).toBeGreaterThanOrEqual(1);
  });

  it("handles individual section errors without crashing the page", async () => {
    mockGetProjectCashflowSummary.mockRejectedValue(new Error("Cashflow unavailable"));
    render(<FinanceDashboardPage />);

    await waitFor(() =>
      expect(screen.getByText("Finance KPIs")).toBeInTheDocument(),
    );
    // Cashflow section shows its own error; other sections render normally
    expect(screen.getByText("Cashflow unavailable")).toBeInTheDocument();
    expect(screen.getByText("Collections Health")).toBeInTheDocument();
  });

  it("handles zero values in all sections without crashing", async () => {
    mockGetProjectFinanceSummary.mockResolvedValue({
      kpis: {
        total_contract_value: 0,
        total_collected: 0,
        total_receivable: 0,
        collection_ratio: 0,
        units_sold: 0,
        total_units: 0,
        average_unit_price: 0,
      },
      collections: {
        total_collected: 0,
        total_receivable: 0,
        collection_ratio: 0,
      },
    });
    mockGetProjectCashflowSummary.mockResolvedValue({
      expected_inflows: 0,
      expected_outflows: 0,
      net_cashflow: 0,
      closing_balance: 0,
    });
    mockGetProjectSalesExceptionsSummary.mockResolvedValue({
      total_exceptions: 0,
      approved_exceptions: 0,
      pending_exceptions: 0,
      rejected_exceptions: 0,
      total_discount_amount: 0,
      total_incentive_value: 0,
    });
    mockGetProjectRegistrationSummary.mockResolvedValue({
      total_sold_units: 0,
      registration_cases_completed: 0,
      registration_cases_open: 0,
      sold_not_registered: 0,
      completion_ratio: 0,
    });
    mockGetProjectCommissionSummary.mockResolvedValue({
      total_payouts: 0,
      approved_payouts: 0,
      calculated_payouts: 0,
      total_gross_value: 0,
      total_commission_pool: 0,
    });

    render(<FinanceDashboardPage />);

    await waitFor(() =>
      expect(screen.getByText("Finance KPIs")).toBeInTheDocument(),
    );
    // Should not crash — just render zero values
    expect(screen.getByText("Finance Health Summary")).toBeInTheDocument();
  });
});
