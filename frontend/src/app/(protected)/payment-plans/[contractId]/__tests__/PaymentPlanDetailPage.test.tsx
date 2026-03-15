/**
 * PaymentPlanDetailView tests
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock Next.js navigation — useSearchParams provides ?contractId=contract-1
let mockSearchParams = new URLSearchParams("contractId=contract-1");
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => "/payment-plans",
  useSearchParams: () => mockSearchParams,
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
  getContractPaymentPlan: jest.fn(),
}));

import { getContractPaymentPlan } from "@/lib/payment-plans-api";
import PaymentPlanDetailView from "@/components/payment-plans/PaymentPlanDetailView";
import type { PaymentPlanDetail } from "@/lib/payment-plans-types";

const mockGetContractPaymentPlan = getContractPaymentPlan as jest.Mock;

const mockDetail: PaymentPlanDetail = {
  contractId: "contract-1",
  contractNumber: "CNT-001",
  contractPrice: 1_000_000,
  contractStatus: "active",
  contractDate: "2024-01-15",
  unitId: "unit-1",
  unitNumber: "A101",
  project: "Marina Tower",
  buyerId: "buyer-1",
  schedule: [
    {
      installmentNumber: 1,
      dueDate: "2024-03-01",
      scheduledAmount: 250_000,
      collectedAmount: 250_000,
      remainingAmount: 0,
      status: "paid",
    },
    {
      installmentNumber: 2,
      dueDate: "2024-06-01",
      scheduledAmount: 250_000,
      collectedAmount: 0,
      remainingAmount: 250_000,
      status: "pending",
    },
  ],
  collectionSummary: {
    contractId: "contract-1",
    totalDue: 1_000_000,
    totalReceived: 250_000,
    totalOutstanding: 750_000,
    paidInstallments: 1,
    overdueInstallments: 0,
    totalInstallments: 4,
  },
  overdueInstallments: [],
};

describe("PaymentPlanDetailView", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSearchParams = new URLSearchParams("contractId=contract-1");
    mockGetContractPaymentPlan.mockResolvedValue(mockDetail);
  });

  it("shows loading state initially", () => {
    render(<PaymentPlanDetailView />);
    expect(screen.getByText(/loading payment plan/i)).toBeInTheDocument();
  });

  it("renders contract number in page title after loading", async () => {
    render(<PaymentPlanDetailView />);
    await waitFor(() =>
      expect(screen.getAllByText(/CNT-001/i).length).toBeGreaterThan(0),
    );
  });

  it("renders contract header details", async () => {
    render(<PaymentPlanDetailView />);
    await waitFor(() =>
      expect(screen.getByText("A101")).toBeInTheDocument(),
    );
    expect(screen.getByText("buyer-1")).toBeInTheDocument();
  });

  it("renders installment schedule", async () => {
    render(<PaymentPlanDetailView />);
    await waitFor(() =>
      expect(
        screen.getByRole("table", { name: /installment schedule/i }),
      ).toBeInTheDocument(),
    );
  });

  it("renders collections progress card", async () => {
    render(<PaymentPlanDetailView />);
    await waitFor(() =>
      expect(screen.getByText(/collections progress/i)).toBeInTheDocument(),
    );
  });

  it("does NOT render overdue panel when no overdue installments", async () => {
    render(<PaymentPlanDetailView />);
    // Wait for loading to complete
    await waitFor(() =>
      expect(screen.queryByText(/loading payment plan/i)).not.toBeInTheDocument(),
    );
    expect(screen.queryByText(/overdue installments/i)).not.toBeInTheDocument();
  });

  it("renders overdue panel when overdue installments exist", async () => {
    mockGetContractPaymentPlan.mockResolvedValue({
      ...mockDetail,
      overdueInstallments: [
        {
          installmentNumber: 2,
          dueDate: "2024-06-01",
          overdueAmount: 250_000,
          daysOverdue: 45,
        },
      ],
      collectionSummary: {
        ...mockDetail.collectionSummary,
        overdueInstallments: 1,
      },
    });
    render(<PaymentPlanDetailView />);
    await waitFor(() =>
      expect(
        screen.getByRole("region", { name: /overdue installments/i }),
      ).toBeInTheDocument(),
    );
  });

  it("shows error state when API fails", async () => {
    mockGetContractPaymentPlan.mockRejectedValue(new Error("Not found"));
    render(<PaymentPlanDetailView />);
    await waitFor(() =>
      expect(screen.getByText("Not found")).toBeInTheDocument(),
    );
  });

  it("renders back link to payment plans", async () => {
    render(<PaymentPlanDetailView />);
    const backLink = screen.getByRole("link", { name: /back to payment plans/i });
    expect(backLink).toHaveAttribute("href", "/payment-plans");
  });

  it("handles missing optional fields gracefully (empty project)", async () => {
    mockGetContractPaymentPlan.mockResolvedValue({
      ...mockDetail,
      project: "",
    });
    render(<PaymentPlanDetailView />);
    await waitFor(() =>
      expect(screen.getByText("CNT-001")).toBeInTheDocument(),
    );
  });

  it("handles empty schedule gracefully", async () => {
    mockGetContractPaymentPlan.mockResolvedValue({
      ...mockDetail,
      schedule: [],
    });
    render(<PaymentPlanDetailView />);
    await waitFor(() =>
      expect(screen.getByText(/no installment schedule/i)).toBeInTheDocument(),
    );
  });
});
