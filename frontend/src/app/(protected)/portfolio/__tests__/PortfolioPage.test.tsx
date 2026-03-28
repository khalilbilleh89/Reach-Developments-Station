/**
 * PortfolioPage tests — validates dashboard state rendering, section display,
 * and null-safe handling across loading / error / empty / success states.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock Next.js navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => "/portfolio",
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
jest.mock("@/styles/portfolio.module.css", () => ({}));
jest.mock("@/components/shell/PageContainer.module.css", () => ({}));

// Mock portfolio dashboard API
jest.mock("@/lib/portfolio-api", () => ({
  getPortfolioDashboard: jest.fn(),
}));

// Mock portfolio variance API
jest.mock("@/lib/portfolio-variance-api", () => ({
  getPortfolioCostVariance: jest.fn(),
}));

import { getPortfolioDashboard } from "@/lib/portfolio-api";
import { getPortfolioCostVariance } from "@/lib/portfolio-variance-api";
import PortfolioPage from "@/app/(protected)/portfolio/page";

const mockGetPortfolioDashboard = getPortfolioDashboard as jest.Mock;
const mockGetPortfolioCostVariance = getPortfolioCostVariance as jest.Mock;

// ---------- Mock data ---------------------------------------------------

const mockSummary = {
  total_projects: 5,
  active_projects: 3,
  total_units: 200,
  available_units: 80,
  reserved_units: 20,
  under_contract_units: 60,
  registered_units: 40,
  contracted_revenue: 50_000_000,
  collected_cash: 30_000_000,
  outstanding_balance: 20_000_000,
};

const mockProjects = [
  {
    project_id: "proj-1",
    project_name: "Marina Tower",
    project_code: "MT-01",
    status: "active",
    total_units: 100,
    available_units: 40,
    reserved_units: 10,
    under_contract_units: 30,
    registered_units: 20,
    contracted_revenue: 25_000_000,
    collected_cash: 15_000_000,
    outstanding_balance: 10_000_000,
    sell_through_pct: 50.0,
    health_badge: "on_track",
  },
  {
    project_id: "proj-2",
    project_name: "Palm Villa",
    project_code: "PV-01",
    status: "active",
    total_units: 100,
    available_units: 40,
    reserved_units: 10,
    under_contract_units: 30,
    registered_units: 20,
    contracted_revenue: 25_000_000,
    collected_cash: 15_000_000,
    outstanding_balance: 10_000_000,
    sell_through_pct: null,
    health_badge: null,
  },
];

const mockPipeline = {
  total_scenarios: 12,
  approved_scenarios: 5,
  total_feasibility_runs: 20,
  calculated_feasibility_runs: 15,
  projects_with_no_feasibility: 1,
};

const mockCollections = {
  total_receivables: 300,
  overdue_receivables: 25,
  overdue_balance: 1_200_000,
  collection_rate_pct: 75.5,
};

const mockRiskFlags = [
  {
    flag_type: "overdue_receivables",
    severity: "warning",
    description: "25 overdue receivables detected.",
    affected_project_id: null,
    affected_project_name: null,
  },
  {
    flag_type: "low_sell_through",
    severity: "critical",
    description: "Sell-through below 20% for Palm Villa.",
    affected_project_id: "proj-2",
    affected_project_name: "Palm Villa",
  },
];

const mockDashboard = {
  summary: mockSummary,
  projects: mockProjects,
  pipeline: mockPipeline,
  collections: mockCollections,
  risk_flags: mockRiskFlags,
};

const mockVarianceEmpty = {
  summary: {
    projects_with_comparison_sets: 0,
    total_baseline_amount: 0,
    total_comparison_amount: 0,
    total_variance_amount: 0,
    total_variance_pct: null,
  },
  projects: [],
  top_overruns: [],
  top_savings: [],
  flags: [],
};

// ---------- Tests -------------------------------------------------------

describe("PortfolioPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Default variance mock returns empty state
    mockGetPortfolioCostVariance.mockResolvedValue(mockVarianceEmpty);
  });

  it("renders the page title", () => {
    mockGetPortfolioDashboard.mockReturnValue(new Promise(() => {}));
    mockGetPortfolioCostVariance.mockReturnValue(new Promise(() => {}));
    render(<PortfolioPage />);
    expect(screen.getByText("Portfolio")).toBeInTheDocument();
  });

  it("shows loading state while fetching dashboard", () => {
    mockGetPortfolioDashboard.mockReturnValue(new Promise(() => {}));
    mockGetPortfolioCostVariance.mockReturnValue(new Promise(() => {}));
    render(<PortfolioPage />);
    expect(screen.getByText(/Loading portfolio dashboard/i)).toBeInTheDocument();
  });

  it("shows error state on API failure", async () => {
    mockGetPortfolioDashboard.mockRejectedValue(new Error("Server unavailable"));
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByText("Server unavailable")).toBeInTheDocument(),
    );
  });

  it("error state has role=alert for accessibility", async () => {
    mockGetPortfolioDashboard.mockRejectedValue(new Error("Network error"));
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByRole("alert")).toBeInTheDocument(),
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Network error");
  });

  it("renders summary strip on success", async () => {
    mockGetPortfolioDashboard.mockResolvedValue(mockDashboard);
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByText("Total Projects")).toBeInTheDocument(),
    );
    expect(screen.getByText("Active Projects")).toBeInTheDocument();
    expect(screen.getAllByText("Total Units").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Contracted Revenue")).toBeInTheDocument();
    expect(screen.getByText("Collected Cash")).toBeInTheDocument();
    expect(screen.getByText("Outstanding Balance")).toBeInTheDocument();
  });

  it("renders correct summary KPI values", async () => {
    mockGetPortfolioDashboard.mockResolvedValue(mockDashboard);
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByText("Total Projects")).toBeInTheDocument(),
    );
    // total_projects = 5, active_projects = 3
    expect(screen.getAllByText("5").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("3").length).toBeGreaterThanOrEqual(1);
  });

  it("renders project cards section", async () => {
    mockGetPortfolioDashboard.mockResolvedValue(mockDashboard);
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByText("Marina Tower")).toBeInTheDocument(),
    );
    expect(screen.getAllByText("Palm Villa").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("MT-01")).toBeInTheDocument();
  });

  it("renders health badge from backend for project cards", async () => {
    mockGetPortfolioDashboard.mockResolvedValue(mockDashboard);
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByText("On Track")).toBeInTheDocument(),
    );
  });

  it("renders null health badge with accessible label Health: Unknown", async () => {
    mockGetPortfolioDashboard.mockResolvedValue(mockDashboard);
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByText("Marina Tower")).toBeInTheDocument(),
    );
    // Palm Villa has null health_badge — aria-label should be "Health: Unknown"
    const unknownBadge = screen.getByLabelText("Health: Unknown");
    expect(unknownBadge).toBeInTheDocument();
  });

  it("renders null sell_through_pct safely as dash", async () => {
    mockGetPortfolioDashboard.mockResolvedValue(mockDashboard);
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByText("Marina Tower")).toBeInTheDocument(),
    );
    // Palm Villa has null sell_through_pct — should render "—"
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it("renders collections panel", async () => {
    mockGetPortfolioDashboard.mockResolvedValue(mockDashboard);
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByText("Collections")).toBeInTheDocument(),
    );
    expect(screen.getByText("Total Receivables")).toBeInTheDocument();
    expect(screen.getByText("Overdue Receivables")).toBeInTheDocument();
    expect(screen.getByText("Collection Rate")).toBeInTheDocument();
  });

  it("renders pipeline panel", async () => {
    mockGetPortfolioDashboard.mockResolvedValue(mockDashboard);
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByText("Pipeline")).toBeInTheDocument(),
    );
    expect(screen.getByText("Total Scenarios")).toBeInTheDocument();
    expect(screen.getByText("Approved Scenarios")).toBeInTheDocument();
    expect(screen.getByText("Total Feasibility Runs")).toBeInTheDocument();
  });

  it("renders risk flags panel with flags", async () => {
    mockGetPortfolioDashboard.mockResolvedValue(mockDashboard);
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByText("Risk Flags")).toBeInTheDocument(),
    );
    expect(
      screen.getByText("25 overdue receivables detected."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Sell-through below 20% for Palm Villa."),
    ).toBeInTheDocument();
  });

  it("renders affected project name for project-scoped risk flags", async () => {
    mockGetPortfolioDashboard.mockResolvedValue(mockDashboard);
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByText("Risk Flags")).toBeInTheDocument(),
    );
    // "Palm Villa" appears in the risk flag as affected project name
    const palmVillaElements = screen.getAllByText("Palm Villa");
    expect(palmVillaElements.length).toBeGreaterThanOrEqual(1);
  });

  it("renders safe empty state when risk_flags is empty", async () => {
    mockGetPortfolioDashboard.mockResolvedValue({
      ...mockDashboard,
      risk_flags: [],
    });
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByText("Risk Flags")).toBeInTheDocument(),
    );
    expect(screen.getByText("No risk flags detected.")).toBeInTheDocument();
  });

  it("renders safe empty state when projects list is empty", async () => {
    mockGetPortfolioDashboard.mockResolvedValue({
      ...mockDashboard,
      projects: [],
    });
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByText("No projects found in portfolio.")).toBeInTheDocument(),
    );
  });

  it("renders collection_rate_pct as dash when null", async () => {
    mockGetPortfolioDashboard.mockResolvedValue({
      ...mockDashboard,
      collections: {
        ...mockCollections,
        collection_rate_pct: null,
      },
    });
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByText("Collections")).toBeInTheDocument(),
    );
    // collection_rate_pct null → at least one "—" is rendered
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(1);
  });

  it("renders page-level empty state when total_projects and projects are zero", async () => {
    mockGetPortfolioDashboard.mockResolvedValue({
      summary: {
        total_projects: 0,
        active_projects: 0,
        total_units: 0,
        available_units: 0,
        reserved_units: 0,
        under_contract_units: 0,
        registered_units: 0,
        contracted_revenue: 0,
        collected_cash: 0,
        outstanding_balance: 0,
      },
      projects: [],
      pipeline: {
        total_scenarios: 0,
        approved_scenarios: 0,
        total_feasibility_runs: 0,
        calculated_feasibility_runs: 0,
        projects_with_no_feasibility: 0,
      },
      collections: {
        total_receivables: 0,
        overdue_receivables: 0,
        overdue_balance: 0,
        collection_rate_pct: null,
      },
      risk_flags: [],
    });
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByText("No portfolio data available.")).toBeInTheDocument(),
    );
    expect(
      screen.getByText("Add projects and source data to populate the portfolio dashboard."),
    ).toBeInTheDocument();
  });

  it("renders dashboard sections when total_projects > 0", async () => {
    mockGetPortfolioDashboard.mockResolvedValue({
      ...mockDashboard,
      projects: [],
      summary: { ...mockSummary, total_projects: 2 },
    });
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByText("Total Projects")).toBeInTheDocument(),
    );
    // With total_projects > 0 the full dashboard renders, not the empty state
    expect(screen.queryByText("No portfolio data available.")).not.toBeInTheDocument();
  });

  // ---- Cost variance panel integration ----------------------------------

  it("renders cost variance panel when variance data loads", async () => {
    mockGetPortfolioDashboard.mockResolvedValue(mockDashboard);
    mockGetPortfolioCostVariance.mockResolvedValue({
      ...mockVarianceEmpty,
      summary: {
        projects_with_comparison_sets: 1,
        total_baseline_amount: 1_000_000,
        total_comparison_amount: 1_100_000,
        total_variance_amount: 100_000,
        total_variance_pct: 10.0,
      },
      top_overruns: [
        {
          project_id: "proj-1",
          project_name: "Marina Tower",
          comparison_set_count: 1,
          latest_comparison_stage: "baseline_vs_tender",
          baseline_total: 1_000_000,
          comparison_total: 1_100_000,
          variance_amount: 100_000,
          variance_pct: 10.0,
          variance_status: "overrun",
        },
      ],
    });
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByText("Cost Variance")).toBeInTheDocument(),
    );
    expect(screen.getByText("Projects with Sets")).toBeInTheDocument();
    expect(screen.getByText("Top Overruns")).toBeInTheDocument();
  });

  it("renders cost variance empty state when no comparison sets exist", async () => {
    mockGetPortfolioDashboard.mockResolvedValue(mockDashboard);
    mockGetPortfolioCostVariance.mockResolvedValue(mockVarianceEmpty);
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByText("Cost Variance")).toBeInTheDocument(),
    );
    expect(
      screen.getByText(/No active tender comparison sets found/i),
    ).toBeInTheDocument();
  });

  it("shows page-level error when either API call fails", async () => {
    mockGetPortfolioDashboard.mockResolvedValue(mockDashboard);
    mockGetPortfolioCostVariance.mockRejectedValue(new Error("Variance API error"));
    render(<PortfolioPage />);
    await waitFor(() =>
      expect(screen.getByRole("alert")).toBeInTheDocument(),
    );
    // The whole page shows an error (Promise.all fails together)
    expect(screen.queryByText("Total Projects")).not.toBeInTheDocument();
  });
});

