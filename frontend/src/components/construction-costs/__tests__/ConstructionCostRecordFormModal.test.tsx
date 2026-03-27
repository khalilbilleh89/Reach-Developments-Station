/**
 * ConstructionCostRecordFormModal tests
 */
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

import { ConstructionCostRecordFormModal } from "@/components/construction-costs/ConstructionCostRecordFormModal";
import type { ConstructionCostRecord } from "@/lib/construction-cost-types";

const makeRecord = (
  overrides: Partial<ConstructionCostRecord> = {},
): ConstructionCostRecord => ({
  id: "rec-1",
  project_id: "proj-1",
  title: "Foundation Works",
  cost_category: "hard_cost",
  cost_source: "estimate",
  cost_stage: "construction",
  amount: 500000,
  currency: "AED",
  effective_date: "2026-06-01",
  reference_number: "REF-001",
  notes: "Test notes",
  is_active: true,
  created_at: "2026-03-01T00:00:00Z",
  updated_at: "2026-03-01T00:00:00Z",
  ...overrides,
});

describe("ConstructionCostRecordFormModal — create mode", () => {
  it("renders with Add Record title when no record provided", () => {
    render(
      <ConstructionCostRecordFormModal
        onSubmit={jest.fn()}
        onClose={jest.fn()}
      />,
    );
    expect(screen.getByText("Add Cost Record")).toBeInTheDocument();
  });

  it("has empty title field in create mode", () => {
    render(
      <ConstructionCostRecordFormModal
        onSubmit={jest.fn()}
        onClose={jest.fn()}
      />,
    );
    expect(screen.getByLabelText(/Title/)).toHaveValue("");
  });

  it("shows validation error when title is empty", async () => {
    render(
      <ConstructionCostRecordFormModal
        onSubmit={jest.fn()}
        onClose={jest.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText(/Amount/), {
      target: { value: "1000" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Add Record/ }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Title is required.");
    });
  });

  it("shows validation error when amount is empty", async () => {
    render(
      <ConstructionCostRecordFormModal
        onSubmit={jest.fn()}
        onClose={jest.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText(/Title/), {
      target: { value: "Test" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Add Record/ }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "A valid amount is required.",
      );
    });
  });

  it("calls onSubmit with correct payload", async () => {
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    render(
      <ConstructionCostRecordFormModal
        onSubmit={onSubmit}
        onClose={jest.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Title/), {
      target: { value: "New Record" },
    });
    fireEvent.change(screen.getByLabelText(/Amount/), {
      target: { value: "100000" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Add Record/ }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "New Record",
          amount: 100000,
          cost_category: "hard_cost",
          cost_source: "estimate",
          cost_stage: "construction",
          currency: "AED",
        }),
      );
    });
  });

  it("calls onClose when Cancel is clicked", () => {
    const onClose = jest.fn();
    render(
      <ConstructionCostRecordFormModal
        onSubmit={jest.fn()}
        onClose={onClose}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalled();
  });
});

describe("ConstructionCostRecordFormModal — edit mode", () => {
  it("renders with Edit Record title when record provided", () => {
    render(
      <ConstructionCostRecordFormModal
        record={makeRecord()}
        onSubmit={jest.fn()}
        onClose={jest.fn()}
      />,
    );
    expect(screen.getByText("Edit Cost Record")).toBeInTheDocument();
  });

  it("pre-populates title field with record title", () => {
    render(
      <ConstructionCostRecordFormModal
        record={makeRecord({ title: "Existing Title" })}
        onSubmit={jest.fn()}
        onClose={jest.fn()}
      />,
    );
    expect(screen.getByLabelText(/Title/)).toHaveValue("Existing Title");
  });

  it("pre-populates amount with record amount", () => {
    render(
      <ConstructionCostRecordFormModal
        record={makeRecord({ amount: 750000 })}
        onSubmit={jest.fn()}
        onClose={jest.fn()}
      />,
    );
    expect(screen.getByLabelText(/Amount/)).toHaveValue(750000);
  });

  it("pre-populates notes", () => {
    render(
      <ConstructionCostRecordFormModal
        record={makeRecord({ notes: "Existing notes" })}
        onSubmit={jest.fn()}
        onClose={jest.fn()}
      />,
    );
    expect(screen.getByLabelText(/Notes/)).toHaveValue("Existing notes");
  });

  it("calls onSubmit with updated payload", async () => {
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    render(
      <ConstructionCostRecordFormModal
        record={makeRecord({ title: "Old Title" })}
        onSubmit={onSubmit}
        onClose={jest.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Title/), {
      target: { value: "Updated Title" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Update Record/ }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Updated Title" }),
      );
    });
  });

  it("shows error returned from onSubmit", async () => {
    const onSubmit = jest
      .fn()
      .mockRejectedValue(new Error("Server error occurred"));
    render(
      <ConstructionCostRecordFormModal
        record={makeRecord()}
        onSubmit={onSubmit}
        onClose={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Update Record/ }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Server error occurred");
    });
  });
});

describe("ConstructionCostRecordFormModal — dialog accessibility", () => {
  it("has dialog role", () => {
    render(
      <ConstructionCostRecordFormModal
        onSubmit={jest.fn()}
        onClose={jest.fn()}
      />,
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("closes when overlay is clicked", () => {
    const onClose = jest.fn();
    const { container } = render(
      <ConstructionCostRecordFormModal
        onSubmit={jest.fn()}
        onClose={onClose}
      />,
    );
    // Click the overlay div (first child)
    const overlay = container.firstChild as HTMLElement;
    fireEvent.click(overlay);
    expect(onClose).toHaveBeenCalled();
  });
});
