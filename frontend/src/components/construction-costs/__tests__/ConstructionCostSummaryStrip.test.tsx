/**
 * ConstructionCostSummaryStrip tests
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

import { ConstructionCostSummaryStrip } from "@/components/construction-costs/ConstructionCostSummaryStrip";
import type { ConstructionCostSummary } from "@/lib/construction-cost-types";

const makeSummary = (
  overrides: Partial<ConstructionCostSummary> = {},
): ConstructionCostSummary => ({
  project_id: "proj-1",
  active_record_count: 3,
  grand_total: "350000.00",
  by_category: { hard_cost: "300000.00", soft_cost: "50000.00" },
  by_stage: { construction: "350000.00" },
  ...overrides,
});

describe("ConstructionCostSummaryStrip", () => {
  it("renders active record count", () => {
    render(<ConstructionCostSummaryStrip summary={makeSummary()} />);
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("renders formatted grand total", () => {
    render(<ConstructionCostSummaryStrip summary={makeSummary()} />);
    expect(screen.getByText("350,000.00")).toBeInTheDocument();
  });

  it("renders category label for hard_cost", () => {
    render(<ConstructionCostSummaryStrip summary={makeSummary()} />);
    expect(screen.getByText("Hard Cost")).toBeInTheDocument();
  });

  it("renders category label for soft_cost", () => {
    render(<ConstructionCostSummaryStrip summary={makeSummary()} />);
    expect(screen.getByText("Soft Cost")).toBeInTheDocument();
  });

  it("renders category total", () => {
    render(<ConstructionCostSummaryStrip summary={makeSummary()} />);
    expect(screen.getByText("300,000.00")).toBeInTheDocument();
    expect(screen.getByText("50,000.00")).toBeInTheDocument();
  });

  it("renders empty summary gracefully", () => {
    render(
      <ConstructionCostSummaryStrip
        summary={makeSummary({
          active_record_count: 0,
          grand_total: "0.00",
          by_category: {},
          by_stage: {},
        })}
      />,
    );
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.getByText("0.00")).toBeInTheDocument();
  });

  it("has testid on the strip container", () => {
    render(<ConstructionCostSummaryStrip summary={makeSummary()} />);
    expect(screen.getByTestId("cost-summary-strip")).toBeInTheDocument();
  });
});
