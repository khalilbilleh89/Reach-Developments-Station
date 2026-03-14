/**
 * InstallmentScheduleTable tests
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock CSS modules
jest.mock("@/styles/payment-plans.module.css", () => ({}));

// Mock format-utils
jest.mock("@/lib/format-utils", () => ({
  formatCurrency: (v: number) => `AED ${v.toLocaleString()}`,
}));

import { InstallmentScheduleTable } from "@/components/payment-plans/InstallmentScheduleTable";
import type { InstallmentRow } from "@/lib/payment-plans-types";

const mockRows: InstallmentRow[] = [
  {
    installmentNumber: 1,
    dueDate: "2025-01-01",
    scheduledAmount: 100_000,
    collectedAmount: 100_000,
    remainingAmount: 0,
    status: "paid",
  },
  {
    installmentNumber: 2,
    dueDate: "2025-04-01",
    scheduledAmount: 100_000,
    collectedAmount: 50_000,
    remainingAmount: 50_000,
    status: "partially_paid",
  },
  {
    installmentNumber: 3,
    dueDate: "2025-07-01",
    scheduledAmount: 100_000,
    collectedAmount: 0,
    remainingAmount: 100_000,
    status: "overdue",
  },
  {
    installmentNumber: 4,
    dueDate: "2025-10-01",
    scheduledAmount: 100_000,
    collectedAmount: 0,
    remainingAmount: 100_000,
    status: "pending",
  },
  {
    installmentNumber: 5,
    dueDate: "2025-11-01",
    scheduledAmount: 100_000,
    collectedAmount: 0,
    remainingAmount: 100_000,
    status: "due",
  },
  {
    installmentNumber: 6,
    dueDate: "2025-12-01",
    scheduledAmount: 100_000,
    collectedAmount: 0,
    remainingAmount: 100_000,
    status: "cancelled",
  },
];

describe("InstallmentScheduleTable", () => {
  it("renders the schedule table with correct headers", () => {
    render(<InstallmentScheduleTable rows={mockRows} />);
    expect(
      screen.getByRole("table", { name: /installment schedule/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/due date/i)).toBeInTheDocument();
    expect(screen.getByText(/scheduled amount/i)).toBeInTheDocument();
    expect(screen.getByText(/collected/i)).toBeInTheDocument();
    expect(screen.getByText(/remaining/i)).toBeInTheDocument();
    expect(screen.getByText(/status/i)).toBeInTheDocument();
  });

  it("renders all rows", () => {
    render(<InstallmentScheduleTable rows={mockRows} />);
    expect(screen.getAllByRole("row")).toHaveLength(mockRows.length + 1); // +1 for header
  });

  it("shows Paid status for paid installment", () => {
    render(<InstallmentScheduleTable rows={[mockRows[0]]} />);
    expect(screen.getByText("Paid")).toBeInTheDocument();
  });

  it("shows Partially Paid status for partially paid installment", () => {
    render(<InstallmentScheduleTable rows={[mockRows[1]]} />);
    expect(screen.getByText("Partially Paid")).toBeInTheDocument();
  });

  it("shows Overdue status for overdue installment", () => {
    render(<InstallmentScheduleTable rows={[mockRows[2]]} />);
    expect(screen.getByText("Overdue")).toBeInTheDocument();
  });

  it("shows Upcoming status for pending installment", () => {
    render(<InstallmentScheduleTable rows={[mockRows[3]]} />);
    expect(screen.getByText("Upcoming")).toBeInTheDocument();
  });

  it("shows Due status for due installment (schedule-only status)", () => {
    render(<InstallmentScheduleTable rows={[mockRows[4]]} />);
    expect(screen.getByText("Due")).toBeInTheDocument();
  });

  it("shows Cancelled status for cancelled installment (schedule-only status)", () => {
    render(<InstallmentScheduleTable rows={[mockRows[5]]} />);
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
  });

  it("shows dash for remaining when fully paid", () => {
    render(<InstallmentScheduleTable rows={[mockRows[0]]} />);
    expect(screen.getByLabelText(/fully paid/i)).toBeInTheDocument();
  });

  it("shows empty state when no rows", () => {
    render(<InstallmentScheduleTable rows={[]} />);
    expect(screen.getByText(/no installment schedule/i)).toBeInTheDocument();
  });
});
