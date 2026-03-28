/**
 * TenderComparisonSetList tests
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

import { TenderComparisonSetList } from "@/components/tender-comparisons/TenderComparisonSetList";
import type { ConstructionCostComparisonSetListItem } from "@/lib/tender-comparison-types";

const makeSet = (
  overrides: Partial<ConstructionCostComparisonSetListItem> = {},
): ConstructionCostComparisonSetListItem => ({
  id: "set-1",
  project_id: "proj-1",
  title: "Baseline vs Tender Q1",
  comparison_stage: "baseline_vs_tender",
  baseline_label: "Baseline",
  comparison_label: "Tender",
  notes: null,
  is_active: true,
  created_at: "2026-03-01T00:00:00Z",
  updated_at: "2026-03-01T00:00:00Z",
  ...overrides,
});

describe("TenderComparisonSetList", () => {
  it("renders empty state when no sets", () => {
    render(
      <TenderComparisonSetList
        sets={[]}
        selectedId={null}
        onSelect={jest.fn()}
      />,
    );
    expect(screen.getByTestId("sets-empty-state")).toBeInTheDocument();
    expect(screen.getByText("No comparison sets yet.")).toBeInTheDocument();
  });

  it("renders set title", () => {
    render(
      <TenderComparisonSetList
        sets={[makeSet()]}
        selectedId={null}
        onSelect={jest.fn()}
      />,
    );
    expect(screen.getByText("Baseline vs Tender Q1")).toBeInTheDocument();
  });

  it("renders human-readable stage label", () => {
    render(
      <TenderComparisonSetList
        sets={[makeSet({ comparison_stage: "tender_vs_award" })]}
        selectedId={null}
        onSelect={jest.fn()}
      />,
    );
    expect(screen.getByText("Tender vs Award")).toBeInTheDocument();
  });

  it("renders baseline and comparison labels", () => {
    render(
      <TenderComparisonSetList
        sets={[
          makeSet({ baseline_label: "Initial Budget", comparison_label: "Contract Award" }),
        ]}
        selectedId={null}
        onSelect={jest.fn()}
      />,
    );
    expect(screen.getByText("Initial Budget")).toBeInTheDocument();
    expect(screen.getByText("Contract Award")).toBeInTheDocument();
  });

  it("shows Active badge for active set", () => {
    render(
      <TenderComparisonSetList
        sets={[makeSet({ is_active: true })]}
        selectedId={null}
        onSelect={jest.fn()}
      />,
    );
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows Archived badge for inactive set", () => {
    render(
      <TenderComparisonSetList
        sets={[makeSet({ is_active: false })]}
        selectedId={null}
        onSelect={jest.fn()}
      />,
    );
    expect(screen.getByText("Archived")).toBeInTheDocument();
  });

  it("calls onSelect when card clicked", () => {
    const onSelect = jest.fn();
    const set = makeSet();
    render(
      <TenderComparisonSetList
        sets={[set]}
        selectedId={null}
        onSelect={onSelect}
      />,
    );
    fireEvent.click(
      screen.getByLabelText("Open comparison set: Baseline vs Tender Q1"),
    );
    expect(onSelect).toHaveBeenCalledWith(set);
  });

  it("marks selected card as pressed", () => {
    render(
      <TenderComparisonSetList
        sets={[makeSet({ id: "set-1" })]}
        selectedId="set-1"
        onSelect={jest.fn()}
      />,
    );
    expect(
      screen.getByLabelText("Open comparison set: Baseline vs Tender Q1"),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("renders multiple sets", () => {
    render(
      <TenderComparisonSetList
        sets={[
          makeSet({ id: "s1", title: "Set One" }),
          makeSet({ id: "s2", title: "Set Two" }),
        ]}
        selectedId={null}
        onSelect={jest.fn()}
      />,
    );
    expect(screen.getByText("Set One")).toBeInTheDocument();
    expect(screen.getByText("Set Two")).toBeInTheDocument();
  });
});
