/**
 * ConstructionCostRecordTable tests
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

import { ConstructionCostRecordTable } from "@/components/construction-costs/ConstructionCostRecordTable";
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
  amount: "500000.00",
  currency: "AED",
  effective_date: null,
  reference_number: null,
  notes: null,
  is_active: true,
  created_at: "2026-03-01T00:00:00Z",
  updated_at: "2026-03-01T00:00:00Z",
  ...overrides,
});

describe("ConstructionCostRecordTable", () => {
  it("renders empty state when no records", () => {
    render(
      <ConstructionCostRecordTable
        records={[]}
        onEdit={jest.fn()}
        onArchive={jest.fn()}
        archivingId={null}
      />,
    );
    expect(screen.getByTestId("records-empty-state")).toBeInTheDocument();
    expect(screen.getByText("No cost records yet.")).toBeInTheDocument();
  });

  it("renders record title", () => {
    render(
      <ConstructionCostRecordTable
        records={[makeRecord()]}
        onEdit={jest.fn()}
        onArchive={jest.fn()}
        archivingId={null}
      />,
    );
    expect(screen.getByText("Foundation Works")).toBeInTheDocument();
  });

  it("renders human-readable category label", () => {
    render(
      <ConstructionCostRecordTable
        records={[makeRecord({ cost_category: "soft_cost" })]}
        onEdit={jest.fn()}
        onArchive={jest.fn()}
        archivingId={null}
      />,
    );
    expect(screen.getByText("Soft Cost")).toBeInTheDocument();
  });

  it("renders human-readable source label", () => {
    render(
      <ConstructionCostRecordTable
        records={[makeRecord({ cost_source: "contract" })]}
        onEdit={jest.fn()}
        onArchive={jest.fn()}
        archivingId={null}
      />,
    );
    expect(screen.getByText("Contract")).toBeInTheDocument();
  });

  it("renders human-readable stage label", () => {
    render(
      <ConstructionCostRecordTable
        records={[makeRecord({ cost_stage: "tender" })]}
        onEdit={jest.fn()}
        onArchive={jest.fn()}
        archivingId={null}
      />,
    );
    expect(screen.getByText("Tender")).toBeInTheDocument();
  });

  it("renders formatted amount", () => {
    render(
      <ConstructionCostRecordTable
        records={[makeRecord({ amount: "1234567.89" })]}
        onEdit={jest.fn()}
        onArchive={jest.fn()}
        archivingId={null}
      />,
    );
    expect(screen.getByText("1,234,567.89")).toBeInTheDocument();
  });

  it("renders currency", () => {
    render(
      <ConstructionCostRecordTable
        records={[makeRecord({ currency: "USD" })]}
        onEdit={jest.fn()}
        onArchive={jest.fn()}
        archivingId={null}
      />,
    );
    expect(screen.getByText("USD")).toBeInTheDocument();
  });

  it("renders effective date when present", () => {
    render(
      <ConstructionCostRecordTable
        records={[makeRecord({ effective_date: "2026-06-01" })]}
        onEdit={jest.fn()}
        onArchive={jest.fn()}
        archivingId={null}
      />,
    );
    expect(screen.getByText("2026-06-01")).toBeInTheDocument();
  });

  it("renders dash when effective date absent", () => {
    render(
      <ConstructionCostRecordTable
        records={[makeRecord({ effective_date: null })]}
        onEdit={jest.fn()}
        onArchive={jest.fn()}
        archivingId={null}
      />,
    );
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("shows Active badge for active record", () => {
    render(
      <ConstructionCostRecordTable
        records={[makeRecord({ is_active: true })]}
        onEdit={jest.fn()}
        onArchive={jest.fn()}
        archivingId={null}
      />,
    );
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows Archived badge for inactive record", () => {
    render(
      <ConstructionCostRecordTable
        records={[makeRecord({ is_active: false })]}
        onEdit={jest.fn()}
        onArchive={jest.fn()}
        archivingId={null}
      />,
    );
    expect(screen.getByText("Archived")).toBeInTheDocument();
  });

  it("calls onEdit when Edit button clicked", () => {
    const onEdit = jest.fn();
    const record = makeRecord();
    render(
      <ConstructionCostRecordTable
        records={[record]}
        onEdit={onEdit}
        onArchive={jest.fn()}
        archivingId={null}
      />,
    );
    fireEvent.click(screen.getByLabelText("Edit Foundation Works"));
    expect(onEdit).toHaveBeenCalledWith(record);
  });

  it("calls onArchive when Archive button clicked", () => {
    const onArchive = jest.fn();
    const record = makeRecord({ is_active: true });
    render(
      <ConstructionCostRecordTable
        records={[record]}
        onEdit={jest.fn()}
        onArchive={onArchive}
        archivingId={null}
      />,
    );
    fireEvent.click(screen.getByLabelText("Archive Foundation Works"));
    expect(onArchive).toHaveBeenCalledWith(record);
  });

  it("disables Archive button while archiving", () => {
    render(
      <ConstructionCostRecordTable
        records={[makeRecord({ id: "rec-1", is_active: true })]}
        onEdit={jest.fn()}
        onArchive={jest.fn()}
        archivingId="rec-1"
      />,
    );
    expect(screen.getByLabelText("Archive Foundation Works")).toBeDisabled();
  });

  it("hides Archive button for archived record", () => {
    render(
      <ConstructionCostRecordTable
        records={[makeRecord({ is_active: false })]}
        onEdit={jest.fn()}
        onArchive={jest.fn()}
        archivingId={null}
      />,
    );
    expect(screen.queryByText("Archive")).not.toBeInTheDocument();
  });

  it("renders accessible table with aria-label", () => {
    render(
      <ConstructionCostRecordTable
        records={[makeRecord()]}
        onEdit={jest.fn()}
        onArchive={jest.fn()}
        archivingId={null}
      />,
    );
    expect(
      screen.getByRole("table", { name: "Construction cost records" }),
    ).toBeInTheDocument();
  });

  it("renders multiple records", () => {
    render(
      <ConstructionCostRecordTable
        records={[
          makeRecord({ id: "r1", title: "Record One" }),
          makeRecord({ id: "r2", title: "Record Two" }),
        ]}
        onEdit={jest.fn()}
        onArchive={jest.fn()}
        archivingId={null}
      />,
    );
    expect(screen.getByText("Record One")).toBeInTheDocument();
    expect(screen.getByText("Record Two")).toBeInTheDocument();
  });
});
