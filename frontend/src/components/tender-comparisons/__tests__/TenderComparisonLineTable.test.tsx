/**
 * TenderComparisonLineTable tests
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

import { TenderComparisonLineTable } from "@/components/tender-comparisons/TenderComparisonLineTable";
import type { ConstructionCostComparisonLine } from "@/lib/tender-comparison-types";

const makeLine = (
  overrides: Partial<ConstructionCostComparisonLine> = {},
): ConstructionCostComparisonLine => ({
  id: "line-1",
  comparison_set_id: "set-1",
  cost_category: "hard_cost",
  baseline_amount: "1000000.00",
  comparison_amount: "1100000.00",
  variance_amount: "100000.00",
  variance_pct: "10.0000",
  variance_reason: "unit_rate_change",
  notes: null,
  created_at: "2026-03-01T00:00:00Z",
  updated_at: "2026-03-01T00:00:00Z",
  ...overrides,
});

describe("TenderComparisonLineTable", () => {
  it("renders empty state when no lines", () => {
    render(
      <TenderComparisonLineTable
        lines={[]}
        baselineLabel="Baseline"
        comparisonLabel="Tender"
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        deletingId={null}
      />,
    );
    expect(screen.getByTestId("lines-empty-state")).toBeInTheDocument();
    expect(screen.getByText("No comparison lines yet.")).toBeInTheDocument();
  });

  it("renders accessible table with aria-label", () => {
    render(
      <TenderComparisonLineTable
        lines={[makeLine()]}
        baselineLabel="Baseline"
        comparisonLabel="Tender"
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        deletingId={null}
      />,
    );
    expect(
      screen.getByRole("table", { name: "Comparison cost lines" }),
    ).toBeInTheDocument();
  });

  it("renders baseline and comparison column headers from labels", () => {
    render(
      <TenderComparisonLineTable
        lines={[makeLine()]}
        baselineLabel="My Baseline"
        comparisonLabel="My Tender"
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        deletingId={null}
      />,
    );
    expect(screen.getByText("My Baseline")).toBeInTheDocument();
    expect(screen.getByText("My Tender")).toBeInTheDocument();
  });

  it("renders human-readable category label", () => {
    render(
      <TenderComparisonLineTable
        lines={[makeLine({ cost_category: "soft_cost" })]}
        baselineLabel="B"
        comparisonLabel="C"
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        deletingId={null}
      />,
    );
    expect(screen.getByText("Soft Cost")).toBeInTheDocument();
  });

  it("renders human-readable variance reason label", () => {
    render(
      <TenderComparisonLineTable
        lines={[makeLine({ variance_reason: "scope_change" })]}
        baselineLabel="B"
        comparisonLabel="C"
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        deletingId={null}
      />,
    );
    expect(screen.getByText("Scope Change")).toBeInTheDocument();
  });

  it("renders formatted baseline amount", () => {
    render(
      <TenderComparisonLineTable
        lines={[makeLine({ baseline_amount: "1234567.89" })]}
        baselineLabel="B"
        comparisonLabel="C"
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        deletingId={null}
      />,
    );
    expect(screen.getByText("1,234,567.89")).toBeInTheDocument();
  });

  it("renders positive variance with + sign", () => {
    render(
      <TenderComparisonLineTable
        lines={[makeLine({ variance_amount: "100000.00" })]}
        baselineLabel="B"
        comparisonLabel="C"
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        deletingId={null}
      />,
    );
    expect(screen.getByText("+100,000.00")).toBeInTheDocument();
  });

  it("renders negative variance with - sign", () => {
    render(
      <TenderComparisonLineTable
        lines={[makeLine({ variance_amount: "-50000.00" })]}
        baselineLabel="B"
        comparisonLabel="C"
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        deletingId={null}
      />,
    );
    expect(screen.getByText("-50,000.00")).toBeInTheDocument();
  });

  it("renders variance pct as percentage", () => {
    render(
      <TenderComparisonLineTable
        lines={[makeLine({ variance_pct: "10.0000" })]}
        baselineLabel="B"
        comparisonLabel="C"
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        deletingId={null}
      />,
    );
    expect(screen.getByText("+10.00%")).toBeInTheDocument();
  });

  it("renders dash when variance_pct is null", () => {
    render(
      <TenderComparisonLineTable
        lines={[makeLine({ variance_pct: null })]}
        baselineLabel="B"
        comparisonLabel="C"
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        deletingId={null}
      />,
    );
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("calls onEdit when Edit clicked", () => {
    const onEdit = jest.fn();
    const line = makeLine();
    render(
      <TenderComparisonLineTable
        lines={[line]}
        baselineLabel="B"
        comparisonLabel="C"
        onEdit={onEdit}
        onDelete={jest.fn()}
        deletingId={null}
      />,
    );
    fireEvent.click(screen.getByLabelText("Edit line line-1"));
    expect(onEdit).toHaveBeenCalledWith(line);
  });

  it("calls onDelete when Delete clicked", () => {
    const onDelete = jest.fn();
    const line = makeLine();
    render(
      <TenderComparisonLineTable
        lines={[line]}
        baselineLabel="B"
        comparisonLabel="C"
        onEdit={jest.fn()}
        onDelete={onDelete}
        deletingId={null}
      />,
    );
    fireEvent.click(screen.getByLabelText("Delete line line-1"));
    expect(onDelete).toHaveBeenCalledWith(line);
  });

  it("disables Delete button while deleting", () => {
    render(
      <TenderComparisonLineTable
        lines={[makeLine({ id: "line-1" })]}
        baselineLabel="B"
        comparisonLabel="C"
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        deletingId="line-1"
      />,
    );
    expect(screen.getByLabelText("Delete line line-1")).toBeDisabled();
  });

  it("renders multiple lines", () => {
    render(
      <TenderComparisonLineTable
        lines={[
          makeLine({ id: "l1", cost_category: "hard_cost" }),
          makeLine({ id: "l2", cost_category: "soft_cost" }),
        ]}
        baselineLabel="B"
        comparisonLabel="C"
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        deletingId={null}
      />,
    );
    expect(screen.getByText("Hard Cost")).toBeInTheDocument();
    expect(screen.getByText("Soft Cost")).toBeInTheDocument();
  });
});
