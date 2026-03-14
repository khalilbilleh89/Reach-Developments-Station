/**
 * FinanceKpiGrid tests
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock CSS modules
jest.mock("@/styles/finance-dashboard.module.css", () => ({}));
jest.mock("@/styles/dashboard.module.css", () => ({}));
jest.mock("@/components/shell/PageContainer.module.css", () => ({}));

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

// Mock finance dashboard API
jest.mock("@/lib/finance-dashboard-api", () => ({
  getProjectFinanceSummary: jest.fn(),
}));

import { getProjectFinanceSummary } from "@/lib/finance-dashboard-api";
import { FinanceKpiGrid } from "@/components/finance/FinanceKpiGrid";

const mockGetProjectFinanceSummary = getProjectFinanceSummary as jest.Mock;

const mockKpis = {
  total_contract_value: 10_000_000,
  total_collected: 6_000_000,
  total_receivable: 4_000_000,
  collection_ratio: 0.6,
  units_sold: 40,
  total_units: 60,
  average_unit_price: 250_000,
};

const mockCollections = {
  total_collected: 6_000_000,
  total_receivable: 4_000_000,
  collection_ratio: 0.6,
};

describe("FinanceKpiGrid", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetProjectFinanceSummary.mockResolvedValue({
      kpis: mockKpis,
      collections: mockCollections,
    });
  });

  it("renders loading state initially", () => {
    mockGetProjectFinanceSummary.mockReturnValue(new Promise(() => {}));
    render(<FinanceKpiGrid projectId="proj-1" />);
    expect(screen.getByText(/Loading financial summary/i)).toBeInTheDocument();
  });

  it("renders KPI section title after load", async () => {
    render(<FinanceKpiGrid projectId="proj-1" />);
    await waitFor(() =>
      expect(screen.getByText("Finance KPIs")).toBeInTheDocument(),
    );
  });

  it("renders total contract value", async () => {
    render(<FinanceKpiGrid projectId="proj-1" />);
    await waitFor(() =>
      expect(screen.getByText("AED 10.0M")).toBeInTheDocument(),
    );
  });

  it("renders collection ratio as percentage", async () => {
    render(<FinanceKpiGrid projectId="proj-1" />);
    await waitFor(() => {
      // Collection Ratio card value
      expect(screen.getByText("60.0%")).toBeInTheDocument();
    });
  });

  it("renders units sold metric", async () => {
    render(<FinanceKpiGrid projectId="proj-1" />);
    await waitFor(() =>
      expect(screen.getByText("40 / 60")).toBeInTheDocument(),
    );
  });

  it("renders error state when fetch fails", async () => {
    mockGetProjectFinanceSummary.mockRejectedValue(
      new Error("Network error"),
    );
    render(<FinanceKpiGrid projectId="proj-1" />);
    await waitFor(() =>
      expect(screen.getByText("Network error")).toBeInTheDocument(),
    );
  });

  it("re-fetches when projectId changes", async () => {
    const { rerender } = render(<FinanceKpiGrid projectId="proj-1" />);
    await waitFor(() =>
      expect(screen.getByText("Finance KPIs")).toBeInTheDocument(),
    );

    rerender(<FinanceKpiGrid projectId="proj-2" />);
    await waitFor(() =>
      expect(mockGetProjectFinanceSummary).toHaveBeenCalledWith("proj-2"),
    );
  });

  it("renders zero values without crashing", async () => {
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
      collections: { total_collected: 0, total_receivable: 0, collection_ratio: 0 },
    });
    render(<FinanceKpiGrid projectId="proj-1" />);
    await waitFor(() =>
      expect(screen.getByText("Finance KPIs")).toBeInTheDocument(),
    );
    expect(screen.getByText("0 / 0")).toBeInTheDocument();
  });
});
