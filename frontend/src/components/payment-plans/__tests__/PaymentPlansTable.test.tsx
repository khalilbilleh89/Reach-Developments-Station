/**
 * PaymentPlansTable tests
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock Next.js Link
jest.mock("next/link", () => {
  const MockLink = ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
  MockLink.displayName = "MockLink";
  return MockLink;
});

// Mock CSS modules
jest.mock("@/styles/payment-plans.module.css", () => ({}));

// Mock format-utils
jest.mock("@/lib/format-utils", () => ({
  formatCurrency: (v: number) => `AED ${v.toLocaleString()}`,
}));

import { PaymentPlansTable } from "@/components/payment-plans/PaymentPlansTable";
import type { PaymentPlanListItem } from "@/lib/payment-plans-types";

const mockItems: PaymentPlanListItem[] = [
  {
    contractId: "contract-1",
    contractNumber: "CNT-001",
    contractPrice: 1_000_000,
    contractStatus: "active",
    unitId: "unit-1",
    unitNumber: "A101",
    project: "Marina Tower",
    totalCollected: 250_000,
    totalOutstanding: 750_000,
    totalDue: 1_000_000,
    nextDueDate: "2025-06-01",
    overdueAmount: 0,
    overdueCount: 0,
    collectionPercent: 25,
  },
  {
    contractId: "contract-2",
    contractNumber: "CNT-002",
    contractPrice: 2_000_000,
    contractStatus: "active",
    unitId: "unit-2",
    unitNumber: "B202",
    project: "Marina Tower",
    totalCollected: 500_000,
    totalOutstanding: 1_500_000,
    totalDue: 2_000_000,
    nextDueDate: "2025-05-01",
    overdueAmount: 200_000,
    overdueCount: 1,
    collectionPercent: 25,
  },
];

describe("PaymentPlansTable", () => {
  it("renders the table with correct headers", () => {
    render(<PaymentPlansTable items={mockItems} />);
    expect(screen.getByRole("table", { name: /payment plans/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^contract$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /outstanding/i })).toBeInTheDocument();
  });

  it("renders contract numbers as links to detail page", () => {
    render(<PaymentPlansTable items={mockItems} />);
    const link = screen.getByRole("link", { name: /view payment plan for contract CNT-001/i });
    expect(link).toHaveAttribute("href", "/payment-plans/contract-1");
  });

  it("renders all items", () => {
    render(<PaymentPlansTable items={mockItems} />);
    expect(screen.getByText("CNT-001")).toBeInTheDocument();
    expect(screen.getByText("CNT-002")).toBeInTheDocument();
    expect(screen.getByText("A101")).toBeInTheDocument();
    expect(screen.getByText("B202")).toBeInTheDocument();
  });

  it("shows overdue amount when overdue", () => {
    render(<PaymentPlansTable items={mockItems} />);
    expect(screen.getByText(/AED 200,000/i)).toBeInTheDocument();
  });

  it("shows dash for next due date when null", () => {
    const itemsWithNull = [{ ...mockItems[0], nextDueDate: null }];
    render(<PaymentPlansTable items={itemsWithNull} />);
    expect(screen.getByLabelText(/no upcoming due date/i)).toBeInTheDocument();
  });

  it("shows empty state when no items", () => {
    render(<PaymentPlansTable items={[]} />);
    expect(screen.getByText(/no payment plans found/i)).toBeInTheDocument();
  });

  it("sorts items when header is clicked", () => {
    render(<PaymentPlansTable items={mockItems} />);
    const contractHeader = screen.getAllByRole("button", { name: /^contract$/i })[0];
    fireEvent.click(contractHeader);
    // After click, descending sort
    fireEvent.click(contractHeader);
    expect(screen.getByText("CNT-001")).toBeInTheDocument();
    expect(screen.getByText("CNT-002")).toBeInTheDocument();
  });

  it("renders progress bar for collection percent", () => {
    render(<PaymentPlansTable items={[mockItems[0]]} />);
    const progressbar = screen.getByRole("progressbar");
    expect(progressbar).toHaveAttribute("aria-valuenow", "25");
  });
});
