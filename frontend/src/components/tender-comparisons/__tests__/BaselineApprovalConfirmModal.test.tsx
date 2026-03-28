/**
 * BaselineApprovalConfirmModal tests (PR-V6-13)
 *
 * Covers:
 *  - modal renders with title and description
 *  - cancel button calls onClose
 *  - confirm button calls onConfirm
 *  - replacement warning shown when hasExistingBaseline is true
 *  - replacement warning absent when hasExistingBaseline is false
 *  - submit button shows "Approving…" and is disabled when isSubmitting
 *  - error message rendered when error prop is set
 *  - cancel button disabled while submitting
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

jest.mock("@/styles/construction.module.css", () => ({}));

import { BaselineApprovalConfirmModal } from "@/components/tender-comparisons/BaselineApprovalConfirmModal";

const defaultProps = {
  comparisonTitle: "Baseline vs Tender Q1",
  hasExistingBaseline: false,
  isSubmitting: false,
  error: null,
  onConfirm: jest.fn(),
  onClose: jest.fn(),
};

beforeEach(() => jest.clearAllMocks());

describe("BaselineApprovalConfirmModal", () => {
  it("renders with modal title", () => {
    render(<BaselineApprovalConfirmModal {...defaultProps} />);
    expect(screen.getByText("Approve as Baseline")).toBeInTheDocument();
  });

  it("renders comparison title in description", () => {
    render(
      <BaselineApprovalConfirmModal
        {...defaultProps}
        comparisonTitle="My Q2 Tender"
      />,
    );
    expect(screen.getByText(/My Q2 Tender/)).toBeInTheDocument();
  });

  it("calls onClose when cancel is clicked", () => {
    const onClose = jest.fn();
    render(<BaselineApprovalConfirmModal {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByText("Cancel"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onConfirm when confirm button is clicked", () => {
    const onConfirm = jest.fn();
    render(
      <BaselineApprovalConfirmModal {...defaultProps} onConfirm={onConfirm} />,
    );
    fireEvent.click(screen.getByTestId("confirm-approve-baseline"));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("shows replacement warning when hasExistingBaseline is true", () => {
    render(
      <BaselineApprovalConfirmModal
        {...defaultProps}
        hasExistingBaseline={true}
      />,
    );
    expect(
      screen.getByTestId("replace-baseline-warning"),
    ).toBeInTheDocument();
    expect(screen.getByText(/existing approved baseline will be replaced/i)).toBeInTheDocument();
  });

  it("does not show replacement warning when hasExistingBaseline is false", () => {
    render(
      <BaselineApprovalConfirmModal
        {...defaultProps}
        hasExistingBaseline={false}
      />,
    );
    expect(
      screen.queryByTestId("replace-baseline-warning"),
    ).not.toBeInTheDocument();
  });

  it("shows Approving… and disables buttons while submitting", () => {
    render(
      <BaselineApprovalConfirmModal {...defaultProps} isSubmitting={true} />,
    );
    expect(screen.getByTestId("confirm-approve-baseline")).toHaveTextContent(
      "Approving…",
    );
    expect(screen.getByTestId("confirm-approve-baseline")).toBeDisabled();
    expect(screen.getByText("Cancel")).toBeDisabled();
  });

  it("renders error message when error prop is set", () => {
    render(
      <BaselineApprovalConfirmModal
        {...defaultProps}
        error="Network failure"
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Network failure");
  });

  it("does not render error banner when error is null", () => {
    render(<BaselineApprovalConfirmModal {...defaultProps} error={null} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("is accessible with dialog role and label", () => {
    render(<BaselineApprovalConfirmModal {...defaultProps} />);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-labelledby", "baseline-confirm-title");
  });
});
