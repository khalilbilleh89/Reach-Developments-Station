/**
 * PaymentPlansPage tests
 */
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock Next.js navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => "/payment-plans",
}));

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
jest.mock("@/components/shell/PageContainer.module.css", () => ({}));

// Mock format-utils
jest.mock("@/lib/format-utils", () => ({
  formatCurrency: (v: number) => `AED ${v.toLocaleString()}`,
}));

// Mock payment-plans-api
jest.mock("@/lib/payment-plans-api", () => ({
  getProjects: jest.fn(),
  getPaymentPlans: jest.fn(),
  filterPaymentPlans: jest.fn((items: unknown[]) => items),
}));

import {
  getProjects,
  getPaymentPlans,
  filterPaymentPlans,
} from "@/lib/payment-plans-api";
import PaymentPlansPage from "@/app/(protected)/payment-plans/page";

const mockGetProjects = getProjects as jest.Mock;
const mockGetPaymentPlans = getPaymentPlans as jest.Mock;
const mockFilterPaymentPlans = filterPaymentPlans as jest.Mock;

const mockProjects = [
  { id: "proj-1", name: "Marina Tower", code: "MT-01", status: "active" },
  { id: "proj-2", name: "Palm Villa", code: "PV-01", status: "active" },
];

const mockPlans = [
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
];

describe("PaymentPlansPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetProjects.mockResolvedValue(mockProjects);
    mockGetPaymentPlans.mockResolvedValue(mockPlans);
    mockFilterPaymentPlans.mockImplementation((items: unknown[]) => items);
  });

  it("renders the page title", () => {
    render(<PaymentPlansPage />);
    expect(screen.getByText("Payment Plans")).toBeInTheDocument();
  });

  it("loads and displays projects in selector", async () => {
    render(<PaymentPlansPage />);
    await waitFor(() =>
      expect(
        screen.getByRole("combobox", { name: /select project/i }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText("Marina Tower")).toBeInTheDocument();
    expect(screen.getByText("Palm Villa")).toBeInTheDocument();
  });

  it("loads and displays payment plans after project selected", async () => {
    render(<PaymentPlansPage />);
    await waitFor(() =>
      expect(screen.getByText("CNT-001")).toBeInTheDocument(),
    );
  });

  it("shows plan count", async () => {
    render(<PaymentPlansPage />);
    await waitFor(() =>
      expect(screen.getByText(/1 plan shown/i)).toBeInTheDocument(),
    );
  });

  it("switches project when selector changes", async () => {
    render(<PaymentPlansPage />);
    await waitFor(() =>
      expect(
        screen.getByRole("combobox", { name: /select project/i }),
      ).toBeInTheDocument(),
    );
    fireEvent.change(
      screen.getByRole("combobox", { name: /select project/i }),
      { target: { value: "proj-2" } },
    );
    await waitFor(() => {
      expect(mockGetPaymentPlans).toHaveBeenCalledWith("proj-2", "Palm Villa");
    });
  });

  it("shows error state when plans fetch fails", async () => {
    mockGetPaymentPlans.mockRejectedValue(new Error("Network error"));
    render(<PaymentPlansPage />);
    await waitFor(() =>
      expect(screen.getByText("Network error")).toBeInTheDocument(),
    );
  });

  it("shows empty state when no project is available", async () => {
    mockGetProjects.mockResolvedValue([]);
    render(<PaymentPlansPage />);
    await waitFor(() =>
      expect(screen.getByText(/no project selected/i)).toBeInTheDocument(),
    );
  });

  it("shows project error when projects fail to load", async () => {
    mockGetProjects.mockRejectedValue(new Error("Server error"));
    render(<PaymentPlansPage />);
    await waitFor(() =>
      expect(screen.getByText("Server error")).toBeInTheDocument(),
    );
  });
});
