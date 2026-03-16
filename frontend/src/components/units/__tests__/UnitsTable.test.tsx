/**
 * UnitsTable tests
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

jest.mock("@/styles/units-pricing.module.css", () => ({}));
jest.mock("@/lib/format-utils", () => ({
  formatCurrency: (v: number) => `AED ${v.toLocaleString()}`,
  formatAmount: (v: number, _currency: string) => `AED ${v.toLocaleString()}`,
  formatAdjustment: (v: number, _currency: string) =>
    `${v >= 0 ? "+" : "-"}AED ${Math.abs(v).toLocaleString()}`,
}));

import { UnitsTable } from "@/components/units/UnitsTable";
import type { UnitListItem, UnitPricingRecord } from "@/lib/units-types";

const mockUnits: UnitListItem[] = [
  {
    id: "unit-1",
    floor_id: "floor-1",
    unit_number: "A101",
    unit_type: "one_bedroom",
    status: "available",
    internal_area: 85.5,
    balcony_area: 10,
    terrace_area: null,
    roof_garden_area: null,
    front_garden_area: null,
    gross_area: null,
  },
  {
    id: "unit-2",
    floor_id: "floor-2",
    unit_number: "B202",
    unit_type: "penthouse",
    status: "under_contract",
    internal_area: 200.0,
    balcony_area: null,
    terrace_area: 50,
    roof_garden_area: 30,
    front_garden_area: null,
    gross_area: null,
  },
];

const mockPricing: Record<string, UnitPricingRecord> = {
  "unit-1": {
    id: "pr-1",
    unit_id: "unit-1",
    base_price: 900_000,
    manual_adjustment: 50_000,
    final_price: 950_000,
    currency: "AED",
    pricing_status: "draft",
    notes: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
};

describe("UnitsTable", () => {
  it("renders unit rows", () => {
    render(
      <UnitsTable units={mockUnits} pricingRecords={mockPricing} onViewUnit={jest.fn()} />,
    );
    expect(screen.getByText("A101")).toBeInTheDocument();
    expect(screen.getByText("B202")).toBeInTheDocument();
  });

  it("renders pricing data for priced units", () => {
    render(
      <UnitsTable units={mockUnits} pricingRecords={mockPricing} onViewUnit={jest.fn()} />,
    );
    // unit-1 has pricing — final_price=950,000 formatted via mocked formatAmount
    expect(screen.getByText(/950,000/)).toBeInTheDocument();
  });

  it("renders dash for unpriced units", () => {
    render(
      <UnitsTable units={mockUnits} pricingRecords={mockPricing} onViewUnit={jest.fn()} />,
    );
    // unit-2 has no pricing — expect an aria-label of Not priced
    expect(screen.getAllByLabelText("Not priced").length).toBeGreaterThanOrEqual(1);
  });

  it("renders internal area for each unit", () => {
    render(
      <UnitsTable units={mockUnits} pricingRecords={mockPricing} onViewUnit={jest.fn()} />,
    );
    // unit-1 internal_area = 85.5
    expect(screen.getByText("85.5")).toBeInTheDocument();
    // unit-2 internal_area = 200.0
    expect(screen.getByText("200.0")).toBeInTheDocument();
  });

  it("renders empty state when no units provided", () => {
    render(
      <UnitsTable units={[]} pricingRecords={{}} onViewUnit={jest.fn()} />,
    );
    expect(screen.getByText(/no units found/i)).toBeInTheDocument();
  });

  it("calls onViewUnit when View button is clicked", () => {
    const onViewUnit = jest.fn();
    render(
      <UnitsTable units={mockUnits} pricingRecords={mockPricing} onViewUnit={onViewUnit} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /view detail for unit a101/i }));
    expect(onViewUnit).toHaveBeenCalledWith("unit-1");
  });

  it("renders unit type label correctly", () => {
    render(
      <UnitsTable units={mockUnits} pricingRecords={mockPricing} onViewUnit={jest.fn()} />,
    );
    // one_bedroom → "1 Bedroom"
    expect(screen.getByText("1 Bedroom")).toBeInTheDocument();
    // penthouse → "Penthouse"
    expect(screen.getByText("Penthouse")).toBeInTheDocument();
  });

  it("renders status badge with correct label for backend enum values", () => {
    render(
      <UnitsTable units={mockUnits} pricingRecords={mockPricing} onViewUnit={jest.fn()} />,
    );
    // available → "Available" (may appear in both unit-status badge and reservation badge)
    expect(screen.getAllByText("Available").length).toBeGreaterThanOrEqual(1);
    // under_contract → "Under Contract"
    expect(screen.getByText("Under Contract")).toBeInTheDocument();
  });

  it("sorts by internal_area when area column sort button is clicked", () => {
    render(
      <UnitsTable units={mockUnits} pricingRecords={mockPricing} onViewUnit={jest.fn()} />,
    );
    // Sort buttons are inside <th> elements — click the button for Area
    fireEvent.click(screen.getByRole("button", { name: /area \(sqm\)/i }));
    const rows = screen.getAllByRole("row");
    // First data row should be A101 (85.5 sqm — smaller)
    expect(rows[1]).toHaveTextContent("A101");

    // Click again for descending
    fireEvent.click(screen.getByRole("button", { name: /area \(sqm\)/i }));
    const rowsDesc = screen.getAllByRole("row");
    expect(rowsDesc[1]).toHaveTextContent("B202");
  });
});
