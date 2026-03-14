/**
 * UnitFilters tests
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

jest.mock("@/styles/units-pricing.module.css", () => ({}));

import { UnitFilters } from "@/components/units/UnitFilters";
import type { UnitFiltersState } from "@/lib/units-types";

const defaultFilters: UnitFiltersState = {
  status: "",
  unit_type: "",
  min_price: "",
  max_price: "",
};

describe("UnitFilters", () => {
  it("renders all filter controls", () => {
    render(<UnitFilters filters={defaultFilters} onChange={jest.fn()} />);
    expect(screen.getByLabelText(/status/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/unit type/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/min price/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/max price/i)).toBeInTheDocument();
  });

  it("does not show reset button when no filters are active", () => {
    render(<UnitFilters filters={defaultFilters} onChange={jest.fn()} />);
    expect(screen.queryByRole("button", { name: /reset/i })).not.toBeInTheDocument();
  });

  it("shows reset button when a filter is active", () => {
    const filters: UnitFiltersState = { ...defaultFilters, status: "sold" };
    render(<UnitFilters filters={filters} onChange={jest.fn()} />);
    expect(screen.getByRole("button", { name: /reset/i })).toBeInTheDocument();
  });

  it("calls onChange with updated status when status is changed", () => {
    const onChange = jest.fn();
    render(<UnitFilters filters={defaultFilters} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText(/status/i), {
      target: { value: "available" },
    });

    expect(onChange).toHaveBeenCalledWith({
      ...defaultFilters,
      status: "available",
    });
  });

  it("calls onChange with updated unit_type when type is changed", () => {
    const onChange = jest.fn();
    render(<UnitFilters filters={defaultFilters} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText(/unit type/i), {
      target: { value: "apartment" },
    });

    expect(onChange).toHaveBeenCalledWith({
      ...defaultFilters,
      unit_type: "apartment",
    });
  });

  it("calls onChange with reset state when reset button is clicked", () => {
    const onChange = jest.fn();
    const filters: UnitFiltersState = {
      status: "sold",
      unit_type: "apartment",
      min_price: "100000",
      max_price: "500000",
    };
    render(<UnitFilters filters={filters} onChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: /reset/i }));

    expect(onChange).toHaveBeenCalledWith({
      status: "",
      unit_type: "",
      min_price: "",
      max_price: "",
    });
  });

  it("calls onChange with updated min_price", () => {
    const onChange = jest.fn();
    render(<UnitFilters filters={defaultFilters} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText(/min price/i), {
      target: { value: "200000" },
    });

    expect(onChange).toHaveBeenCalledWith({
      ...defaultFilters,
      min_price: "200000",
    });
  });
});
