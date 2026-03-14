/**
 * UnitsTable tests
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

jest.mock("@/styles/units-pricing.module.css", () => ({}));
jest.mock("@/lib/format-utils", () => ({
  formatCurrency: (v: number) => `AED ${v.toLocaleString()}`,
}));

import { UnitsTable } from "@/components/units/UnitsTable";
import type { UnitListItem, UnitPrice } from "@/lib/units-types";

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

const mockPricing: Record<string, UnitPrice> = {
  "unit-1": {
    unit_id: "unit-1",
    unit_area: 85.5,
    base_unit_price: 900_000,
    premium_total: 50_000,
    final_unit_price: 950_000,
  },
};

describe("UnitsTable", () => {
  it("renders unit rows", () => {
    render(
      <UnitsTable units={mockUnits} pricing={mockPricing} onViewUnit={jest.fn()} />,
    );
    expect(screen.getByText("A101")).toBeInTheDocument();
    expect(screen.getByText("B202")).toBeInTheDocument();
  });

  it("renders pricing data for priced units", () => {
    render(
      <UnitsTable units={mockUnits} pricing={mockPricing} onViewUnit={jest.fn()} />,
    );
    // unit-1 has pricing
    expect(screen.getByText(/950,000/)).toBeInTheDocument();
  });

  it("renders dash for unpriced units", () => {
    render(
      <UnitsTable units={mockUnits} pricing={mockPricing} onViewUnit={jest.fn()} />,
    );
    // unit-2 has no pricing — expect an aria-label of Not priced
    expect(screen.getAllByLabelText("Not priced").length).toBeGreaterThanOrEqual(1);
  });

  it("renders outdoor area when present", () => {
    render(
      <UnitsTable units={mockUnits} pricing={mockPricing} onViewUnit={jest.fn()} />,
    );
    // unit-1 has 10 sqm balcony
    expect(screen.getByText("10.0 sqm")).toBeInTheDocument();
    // unit-2 has terrace + roof garden = 80 sqm
    expect(screen.getByText("80.0 sqm")).toBeInTheDocument();
  });

  it("renders empty state when no units provided", () => {
    render(
      <UnitsTable units={[]} pricing={{}} onViewUnit={jest.fn()} />,
    );
    expect(screen.getByText(/no units found/i)).toBeInTheDocument();
  });

  it("calls onViewUnit when View button is clicked", () => {
    const onViewUnit = jest.fn();
    render(
      <UnitsTable units={mockUnits} pricing={mockPricing} onViewUnit={onViewUnit} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /view pricing for unit a101/i }));
    expect(onViewUnit).toHaveBeenCalledWith("unit-1");
  });

  it("renders unit type label correctly", () => {
    render(
      <UnitsTable units={mockUnits} pricing={mockPricing} onViewUnit={jest.fn()} />,
    );
    // one_bedroom → "1 Bedroom"
    expect(screen.getByText("1 Bedroom")).toBeInTheDocument();
    // penthouse → "Penthouse"
    expect(screen.getByText("Penthouse")).toBeInTheDocument();
  });

  it("renders status badge with correct label for backend enum values", () => {
    render(
      <UnitsTable units={mockUnits} pricing={mockPricing} onViewUnit={jest.fn()} />,
    );
    // available → "Available"
    expect(screen.getByText("Available")).toBeInTheDocument();
    // under_contract → "Under Contract"
    expect(screen.getByText("Under Contract")).toBeInTheDocument();
  });

  it("sorts by internal_area when area column sort button is clicked", () => {
    render(
      <UnitsTable units={mockUnits} pricing={mockPricing} onViewUnit={jest.fn()} />,
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
