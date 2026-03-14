/**
 * FinancialSummaryGrid tests
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { FinancialSummaryGrid } from "../FinancialSummaryGrid";

jest.mock("@/styles/dashboard.module.css", () => ({}));

jest.mock("@/lib/dashboard-api", () => ({
  getFinancialSummary: jest.fn(),
}));

import { getFinancialSummary } from "@/lib/dashboard-api";
const mockGetFinancialSummary = getFinancialSummary as jest.Mock;

const mockSummary = {
  project_id: "proj-1",
  total_contract_value: 5_000_000,
  total_collected: 3_000_000,
  total_receivable: 2_000_000,
  collection_ratio: 0.6,
  units_sold: 30,
  total_units: 50,
  units_available: 20,
  average_unit_price: 166_667,
};

describe("FinancialSummaryGrid", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows loading state", () => {
    mockGetFinancialSummary.mockReturnValue(new Promise(() => {}));
    render(<FinancialSummaryGrid projectId="proj-1" />);
    expect(screen.getByText(/Loading financial summary/i)).toBeInTheDocument();
  });

  it("renders financial metrics after load", async () => {
    mockGetFinancialSummary.mockResolvedValue(mockSummary);
    render(<FinancialSummaryGrid projectId="proj-1" />);

    await waitFor(() =>
      expect(screen.getByText("Financial Summary")).toBeInTheDocument(),
    );

    // Check a formatted currency value (5M)
    expect(screen.getByText("AED 5.0M")).toBeInTheDocument();
    // Check units sold metric
    expect(screen.getByText("30 / 50")).toBeInTheDocument();
    // Check collection ratio in subtitle
    expect(screen.getByText(/60\.0%/)).toBeInTheDocument();
  });

  it("shows error when API fails", async () => {
    mockGetFinancialSummary.mockRejectedValue(new Error("Server error"));
    render(<FinancialSummaryGrid projectId="proj-1" />);
    await waitFor(() =>
      expect(screen.getByText("Server error")).toBeInTheDocument(),
    );
  });

  it("re-fetches when projectId changes", async () => {
    mockGetFinancialSummary.mockResolvedValue(mockSummary);
    const { rerender } = render(<FinancialSummaryGrid projectId="proj-1" />);
    await waitFor(() =>
      expect(screen.getByText("Financial Summary")).toBeInTheDocument(),
    );

    rerender(<FinancialSummaryGrid projectId="proj-2" />);
    expect(mockGetFinancialSummary).toHaveBeenCalledWith("proj-2");
  });
});
