/**
 * TenderComparisonFormModal tests
 */
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

import { TenderComparisonFormModal } from "@/components/tender-comparisons/TenderComparisonFormModal";
import type { ConstructionCostComparisonSetListItem } from "@/lib/tender-comparison-types";

const makeSet = (
  overrides: Partial<ConstructionCostComparisonSetListItem> = {},
): ConstructionCostComparisonSetListItem => ({
  id: "set-1",
  project_id: "proj-1",
  title: "Existing Set",
  comparison_stage: "tender_vs_award",
  baseline_label: "My Baseline",
  comparison_label: "My Tender",
  notes: "Some notes",
  is_active: true,
  created_at: "2026-03-01T00:00:00Z",
  updated_at: "2026-03-01T00:00:00Z",
  ...overrides,
});

describe("TenderComparisonFormModal", () => {
  it("renders in create mode when no set provided", () => {
    render(
      <TenderComparisonFormModal onSubmit={jest.fn()} onClose={jest.fn()} />,
    );
    expect(screen.getByText("New Comparison Set")).toBeInTheDocument();
  });

  it("renders in edit mode when set provided", () => {
    render(
      <TenderComparisonFormModal
        set={makeSet()}
        onSubmit={jest.fn()}
        onClose={jest.fn()}
      />,
    );
    expect(screen.getByText("Edit Comparison Set")).toBeInTheDocument();
  });

  it("pre-populates title in edit mode", () => {
    render(
      <TenderComparisonFormModal
        set={makeSet({ title: "Pre-filled Title" })}
        onSubmit={jest.fn()}
        onClose={jest.fn()}
      />,
    );
    expect(screen.getByDisplayValue("Pre-filled Title")).toBeInTheDocument();
  });

  it("shows error when title is empty and form submitted", async () => {
    render(
      <TenderComparisonFormModal onSubmit={jest.fn()} onClose={jest.fn()} />,
    );
    fireEvent.click(screen.getByText("Create Set"));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByText("Title is required.")).toBeInTheDocument();
    });
  });

  it("calls onClose when Cancel clicked", () => {
    const onClose = jest.fn();
    render(<TenderComparisonFormModal onSubmit={jest.fn()} onClose={onClose} />);
    fireEvent.click(screen.getByText("Cancel"));
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onSubmit with correct payload in create mode", async () => {
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    render(<TenderComparisonFormModal onSubmit={onSubmit} onClose={jest.fn()} />);

    fireEvent.change(screen.getByLabelText(/Title/i), {
      target: { value: "New Comparison" },
    });
    fireEvent.click(screen.getByText("Create Set"));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "New Comparison",
          comparison_stage: "baseline_vs_tender",
        }),
      );
    });
  });

  it("has accessible dialog role", () => {
    render(
      <TenderComparisonFormModal onSubmit={jest.fn()} onClose={jest.fn()} />,
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
