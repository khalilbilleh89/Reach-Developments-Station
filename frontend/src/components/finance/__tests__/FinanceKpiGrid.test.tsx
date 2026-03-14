/**
 * FinanceKpiGrid tests
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock CSS modules
jest.mock("@/styles/finance-dashboard.module.css", () => ({}));
jest.mock("@/styles/dashboard.module.css", () => ({}));

import { FinanceKpiGrid } from "@/components/finance/FinanceKpiGrid";
import type { FinanceKpis } from "@/lib/finance-dashboard-types";

const mockKpis: FinanceKpis = {
  total_contract_value: 10_000_000,
  total_collected: 6_000_000,
  total_receivable: 4_000_000,
  collection_ratio: 0.6,
  units_sold: 40,
  total_units: 60,
  average_unit_price: 250_000,
};

describe("FinanceKpiGrid", () => {
  it("renders loading state", () => {
    render(<FinanceKpiGrid kpis={null} loading={true} error={null} />);
    expect(screen.getByText(/Loading financial summary/i)).toBeInTheDocument();
  });

  it("renders error state", () => {
    render(<FinanceKpiGrid kpis={null} loading={false} error="Network error" />);
    expect(screen.getByText("Network error")).toBeInTheDocument();
  });

  it("renders unavailable state when data is null with no error", () => {
    render(<FinanceKpiGrid kpis={null} loading={false} error={null} />);
    expect(screen.getByText(/Financial data unavailable/i)).toBeInTheDocument();
  });

  it("renders section title when data is available", () => {
    render(<FinanceKpiGrid kpis={mockKpis} loading={false} error={null} />);
    expect(screen.getByText("Finance KPIs")).toBeInTheDocument();
  });

  it("renders total contract value", () => {
    render(<FinanceKpiGrid kpis={mockKpis} loading={false} error={null} />);
    expect(screen.getByText("AED 10.0M")).toBeInTheDocument();
  });

  it("renders collection ratio as percentage", () => {
    render(<FinanceKpiGrid kpis={mockKpis} loading={false} error={null} />);
    expect(screen.getByText("60.0%")).toBeInTheDocument();
  });

  it("renders units sold metric", () => {
    render(<FinanceKpiGrid kpis={mockKpis} loading={false} error={null} />);
    expect(screen.getByText("40 / 60")).toBeInTheDocument();
  });

  it("renders zero values without crashing", () => {
    const zeroKpis: FinanceKpis = {
      total_contract_value: 0,
      total_collected: 0,
      total_receivable: 0,
      collection_ratio: 0,
      units_sold: 0,
      total_units: 0,
      average_unit_price: 0,
    };
    render(<FinanceKpiGrid kpis={zeroKpis} loading={false} error={null} />);
    expect(screen.getByText("Finance KPIs")).toBeInTheDocument();
    expect(screen.getByText("0 / 0")).toBeInTheDocument();
  });

  it("shows loading over data when loading=true", () => {
    render(<FinanceKpiGrid kpis={mockKpis} loading={true} error={null} />);
    expect(screen.getByText(/Loading financial summary/i)).toBeInTheDocument();
    expect(screen.queryByText("Finance KPIs")).not.toBeInTheDocument();
  });
});
