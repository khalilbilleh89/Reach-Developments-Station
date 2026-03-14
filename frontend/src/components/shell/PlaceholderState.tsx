import React from "react";

interface PlaceholderStateProps {
  module: string;
}

/**
 * PlaceholderState — temporary page body shown for modules not yet built.
 *
 * Replaced by real content in subsequent PRs (PR-018 through PR-022).
 */
export function PlaceholderState({ module }: PlaceholderStateProps) {
  return (
    <div
      style={{
        padding: "48px 0",
        textAlign: "center",
        color: "var(--color-text-muted)",
      }}
    >
      <p style={{ fontSize: "var(--font-size-lg)", marginBottom: "8px" }}>
        {module} coming soon
      </p>
      <p style={{ fontSize: "var(--font-size-sm)" }}>
        This module will be built in a future PR.
      </p>
    </div>
  );
}
