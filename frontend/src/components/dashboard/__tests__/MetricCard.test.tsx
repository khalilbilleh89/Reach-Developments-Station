/**
 * MetricCard tests
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { MetricCard } from "../MetricCard";

jest.mock("@/styles/dashboard.module.css", () => ({}));

describe("MetricCard", () => {
  it("renders title and value", () => {
    render(<MetricCard title="Total Revenue" value="AED 5.0M" />);
    expect(screen.getByText("Total Revenue")).toBeInTheDocument();
    expect(screen.getByText("AED 5.0M")).toBeInTheDocument();
  });

  it("renders subtitle when provided", () => {
    render(
      <MetricCard title="Units Sold" value="42" subtitle="out of 100 total" />,
    );
    expect(screen.getByText("out of 100 total")).toBeInTheDocument();
  });

  it("does not render subtitle when omitted", () => {
    render(<MetricCard title="Units Sold" value="42" />);
    expect(screen.queryByText(/out of/)).not.toBeInTheDocument();
  });

  it("renders icon when provided", () => {
    render(<MetricCard title="Revenue" value="100" icon="💰" />);
    expect(screen.getByText("💰")).toBeInTheDocument();
  });

  it("renders up trend indicator", () => {
    render(
      <MetricCard
        title="Net Position"
        value="AED 1.0M"
        trend={{ direction: "up", label: "Positive" }}
      />,
    );
    expect(screen.getByText(/Positive/)).toBeInTheDocument();
    expect(screen.getByText(/↑/)).toBeInTheDocument();
  });

  it("renders down trend indicator", () => {
    render(
      <MetricCard
        title="Net Position"
        value="AED -0.5M"
        trend={{ direction: "down", label: "Negative" }}
      />,
    );
    expect(screen.getByText(/Negative/)).toBeInTheDocument();
    expect(screen.getByText(/↓/)).toBeInTheDocument();
  });

  it("renders neutral trend indicator", () => {
    render(
      <MetricCard
        title="Net Position"
        value="AED 0"
        trend={{ direction: "neutral", label: "Neutral" }}
      />,
    );
    expect(screen.getByText(/Neutral/)).toBeInTheDocument();
    expect(screen.getByText(/→/)).toBeInTheDocument();
  });

  it("renders numeric value", () => {
    render(<MetricCard title="Count" value={99} />);
    expect(screen.getByText("99")).toBeInTheDocument();
  });
});
