/**
 * TenderComparisonSummaryStrip tests
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

import { TenderComparisonSummaryStrip } from "@/components/tender-comparisons/TenderComparisonSummaryStrip";
import type { ConstructionCostComparisonSummary } from "@/lib/tender-comparison-types";

const makeSummary = (
  overrides: Partial<ConstructionCostComparisonSummary> = {},
): ConstructionCostComparisonSummary => ({
  comparison_set_id: "set-1",
  project_id: "proj-1",
  line_count: 2,
  total_baseline: "1200000.00",
  total_comparison: "1280000.00",
  total_variance: "80000.00",
  total_variance_pct: "6.6667",
  ...overrides,
});

describe("TenderComparisonSummaryStrip", () => {
  it("renders the summary strip", () => {
    render(<TenderComparisonSummaryStrip summary={makeSummary()} />);
    expect(
      screen.getByTestId("tender-comparison-summary-strip"),
    ).toBeInTheDocument();
  });

  it("renders line count", () => {
    render(<TenderComparisonSummaryStrip summary={makeSummary({ line_count: 5 })} />);
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("renders formatted total baseline", () => {
    render(
      <TenderComparisonSummaryStrip
        summary={makeSummary({ total_baseline: "1200000.00" })}
      />,
    );
    expect(screen.getByText("1,200,000.00")).toBeInTheDocument();
  });

  it("renders formatted total comparison", () => {
    render(
      <TenderComparisonSummaryStrip
        summary={makeSummary({ total_comparison: "1280000.00" })}
      />,
    );
    expect(screen.getByText("1,280,000.00")).toBeInTheDocument();
  });

  it("renders formatted total variance", () => {
    render(
      <TenderComparisonSummaryStrip
        summary={makeSummary({ total_variance: "80000.00" })}
      />,
    );
    expect(screen.getByText("80,000.00")).toBeInTheDocument();
  });

  it("renders variance percentage with sign", () => {
    render(
      <TenderComparisonSummaryStrip
        summary={makeSummary({ total_variance_pct: "6.6667" })}
      />,
    );
    expect(screen.getByText("+6.67%")).toBeInTheDocument();
  });

  it("renders dash when total_variance_pct is null", () => {
    render(
      <TenderComparisonSummaryStrip
        summary={makeSummary({ total_variance_pct: null })}
      />,
    );
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders negative variance percentage with negative sign", () => {
    render(
      <TenderComparisonSummaryStrip
        summary={makeSummary({ total_variance_pct: "-5.0000" })}
      />,
    );
    expect(screen.getByText("-5.00%")).toBeInTheDocument();
  });
});
