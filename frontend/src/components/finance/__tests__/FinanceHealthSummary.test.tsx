/**
 * FinanceHealthSummary tests
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock CSS modules
jest.mock("@/styles/finance-dashboard.module.css", () => ({}));

import { FinanceHealthSummary } from "@/components/finance/FinanceHealthSummary";
import type {
  CollectionsHealth,
  CashflowHealth,
  SalesExceptionImpact,
  RegistrationFinanceSignal,
} from "@/lib/finance-dashboard-types";

const healthyCollections: CollectionsHealth = {
  total_collected: 6_000_000,
  total_receivable: 4_000_000,
  collection_ratio: 0.6,
};

const watchCollections: CollectionsHealth = {
  total_collected: 2_000_000,
  total_receivable: 8_000_000,
  collection_ratio: 0.3,
};

const criticalCollections: CollectionsHealth = {
  total_collected: 500_000,
  total_receivable: 9_500_000,
  collection_ratio: 0.05,
};

const positiveCashflow: CashflowHealth = {
  expected_inflows: 2_000_000,
  expected_outflows: 1_000_000,
  net_cashflow: 1_000_000,
  closing_balance: 3_000_000,
};

const negativeCashflow: CashflowHealth = {
  expected_inflows: 500_000,
  expected_outflows: 1_500_000,
  net_cashflow: -1_000_000,
  closing_balance: 500_000,
};

const noExceptions: SalesExceptionImpact = {
  total_exceptions: 0,
  approved_exceptions: 0,
  pending_exceptions: 0,
  rejected_exceptions: 0,
  total_discount_amount: 0,
  total_incentive_value: 0,
};

const pendingExceptions: SalesExceptionImpact = {
  total_exceptions: 3,
  approved_exceptions: 2,
  pending_exceptions: 1,
  rejected_exceptions: 0,
  total_discount_amount: 50_000,
  total_incentive_value: 10_000,
};

const cleanRegistration: RegistrationFinanceSignal = {
  total_sold_units: 40,
  registration_cases_completed: 40,
  registration_cases_open: 0,
  sold_not_registered: 0,
  completion_ratio: 1.0,
};

const lagRegistration: RegistrationFinanceSignal = {
  total_sold_units: 40,
  registration_cases_completed: 30,
  registration_cases_open: 5,
  sold_not_registered: 5,
  completion_ratio: 0.75,
};

describe("FinanceHealthSummary", () => {
  it("renders the section title", () => {
    render(
      <FinanceHealthSummary
        collections={healthyCollections}
        cashflow={positiveCashflow}
        exceptions={noExceptions}
        registration={cleanRegistration}
      />,
    );
    expect(screen.getByText("Finance Health Summary")).toBeInTheDocument();
  });

  it("shows healthy badges when all metrics are positive", () => {
    render(
      <FinanceHealthSummary
        collections={healthyCollections}
        cashflow={positiveCashflow}
        exceptions={noExceptions}
        registration={cleanRegistration}
      />,
    );
    expect(screen.getByText(/Collections healthy/)).toBeInTheDocument();
    expect(screen.getByText(/Cashflow positive/)).toBeInTheDocument();
    expect(screen.getByText(/Exceptions clear/)).toBeInTheDocument();
    expect(screen.getByText(/Registration on track/)).toBeInTheDocument();
  });

  it("shows watch badge when collection ratio is below 0.5", () => {
    render(
      <FinanceHealthSummary
        collections={watchCollections}
        cashflow={positiveCashflow}
        exceptions={noExceptions}
        registration={cleanRegistration}
      />,
    );
    expect(screen.getByText(/Collections — watch/)).toBeInTheDocument();
  });

  it("shows critical badge when collection ratio is below 0.25", () => {
    render(
      <FinanceHealthSummary
        collections={criticalCollections}
        cashflow={positiveCashflow}
        exceptions={noExceptions}
        registration={cleanRegistration}
      />,
    );
    expect(screen.getByText(/Collections critical/)).toBeInTheDocument();
  });

  it("shows cashflow negative badge when net cashflow is negative", () => {
    render(
      <FinanceHealthSummary
        collections={healthyCollections}
        cashflow={negativeCashflow}
        exceptions={noExceptions}
        registration={cleanRegistration}
      />,
    );
    expect(screen.getByText(/Cashflow negative/)).toBeInTheDocument();
  });

  it("shows exceptions pending badge when there are pending exceptions", () => {
    render(
      <FinanceHealthSummary
        collections={healthyCollections}
        cashflow={positiveCashflow}
        exceptions={pendingExceptions}
        registration={cleanRegistration}
      />,
    );
    expect(screen.getByText(/Exceptions pending/)).toBeInTheDocument();
  });

  it("shows registration lag badge when sold_not_registered > 0", () => {
    render(
      <FinanceHealthSummary
        collections={healthyCollections}
        cashflow={positiveCashflow}
        exceptions={noExceptions}
        registration={lagRegistration}
      />,
    );
    expect(screen.getByText(/Registration lag/)).toBeInTheDocument();
  });

  it("renders without crashing when all props are null", () => {
    render(
      <FinanceHealthSummary
        collections={null}
        cashflow={null}
        exceptions={null}
        registration={null}
      />,
    );
    // All sections default to healthy when data is null
    expect(screen.getByText(/Collections healthy/)).toBeInTheDocument();
    expect(screen.getByText(/Cashflow positive/)).toBeInTheDocument();
  });
});
