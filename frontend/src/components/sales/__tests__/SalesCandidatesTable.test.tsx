/**
 * SalesCandidatesTable tests
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

jest.mock("@/styles/sales-workflow.module.css", () => ({}));
jest.mock("@/lib/format-utils", () => ({
  formatCurrency: (v: number) => `AED ${v.toLocaleString()}`,
  formatAmount: (v: number, currency: string) => `${currency} ${v.toLocaleString()}`,
}));

import { SalesCandidatesTable } from "@/components/sales/SalesCandidatesTable";
import type { SalesCandidate } from "@/lib/sales-types";

const makeCandidate = (
  overrides: Partial<SalesCandidate> = {},
): SalesCandidate => ({
  unit: {
    id: "unit-1",
    floor_id: "floor-1",
    unit_number: "A101",
    unit_type: "one_bedroom",
    status: "available",
    internal_area: 85,
    balcony_area: null,
    terrace_area: null,
    roof_garden_area: null,
    front_garden_area: null,
    gross_area: null,
  },
  pricing: {
    unit_id: "unit-1",
    unit_area: 85,
    base_unit_price: 900_000,
    premium_total: 50_000,
    final_unit_price: 950_000,
    currency: "AED",
  },
  hasApprovedException: false,
  contractStatus: null,
  readiness: "ready",
  ...overrides,
});

describe("SalesCandidatesTable", () => {
  it("renders unit number", () => {
    render(
      <SalesCandidatesTable
        candidates={[makeCandidate()]}
        onSelectUnit={jest.fn()}
      />,
    );
    expect(screen.getByText("A101")).toBeInTheDocument();
  });

  it("renders pricing when available", () => {
    render(
      <SalesCandidatesTable
        candidates={[makeCandidate()]}
        onSelectUnit={jest.fn()}
      />,
    );
    expect(screen.getByText(/950,000/)).toBeInTheDocument();
  });

  it("shows dash when pricing unavailable", () => {
    render(
      <SalesCandidatesTable
        candidates={[makeCandidate({ pricing: null })]}
        onSelectUnit={jest.fn()}
      />,
    );
    expect(screen.getByLabelText("Not priced")).toBeInTheDocument();
  });

  it("shows 'Yes' for approved exception", () => {
    render(
      <SalesCandidatesTable
        candidates={[makeCandidate({ hasApprovedException: true })]}
        onSelectUnit={jest.fn()}
      />,
    );
    expect(screen.getByText("Yes")).toBeInTheDocument();
  });

  it("shows 'No' when no approved exception", () => {
    render(
      <SalesCandidatesTable
        candidates={[makeCandidate({ hasApprovedException: false })]}
        onSelectUnit={jest.fn()}
      />,
    );
    expect(screen.getByText("No")).toBeInTheDocument();
  });

  it("renders readiness badge", () => {
    render(
      <SalesCandidatesTable
        candidates={[makeCandidate({ readiness: "ready" })]}
        onSelectUnit={jest.fn()}
      />,
    );
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });

  it("calls onSelectUnit when Open is clicked", () => {
    const onSelect = jest.fn();
    render(
      <SalesCandidatesTable
        candidates={[makeCandidate()]}
        onSelectUnit={onSelect}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /open sales workflow/i }));
    expect(onSelect).toHaveBeenCalledWith("unit-1");
  });

  it("renders empty state when no candidates", () => {
    render(
      <SalesCandidatesTable candidates={[]} onSelectUnit={jest.fn()} />,
    );
    expect(screen.getByText("No units found")).toBeInTheDocument();
  });

  it("renders candidates in default ascending order by unit number", () => {
    const candidates = [
      makeCandidate({ unit: { ...makeCandidate().unit, id: "u2", unit_number: "B201" } }),
      makeCandidate({ unit: { ...makeCandidate().unit, id: "u1", unit_number: "A101" } }),
    ];
    render(
      <SalesCandidatesTable candidates={candidates} onSelectUnit={jest.fn()} />,
    );
    // Default sort is ascending by unit_number: A101 before B201
    const rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("A101");
    expect(rows[2]).toHaveTextContent("B201");
  });

  it("reverses sort order when unit number header is clicked again", () => {
    const candidates = [
      makeCandidate({ unit: { ...makeCandidate().unit, id: "u1", unit_number: "A101" } }),
      makeCandidate({ unit: { ...makeCandidate().unit, id: "u2", unit_number: "B201" } }),
    ];
    render(
      <SalesCandidatesTable candidates={candidates} onSelectUnit={jest.fn()} />,
    );
    // Click the Unit column header sort button to reverse the default ascending sort
    const unitHeader = screen.getByRole("columnheader", { name: "Unit" });
    fireEvent.click(unitHeader.querySelector("button")!);
    const rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("B201");
    expect(rows[2]).toHaveTextContent("A101");
  });

  it("renders contract status when present", () => {
    render(
      <SalesCandidatesTable
        candidates={[makeCandidate({ contractStatus: "active" })]}
        onSelectUnit={jest.fn()}
      />,
    );
    expect(screen.getByText("Active")).toBeInTheDocument();
  });
});
