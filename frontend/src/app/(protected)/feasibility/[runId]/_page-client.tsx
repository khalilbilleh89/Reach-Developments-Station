"use client";

import FeasibilityRunDetailView from "@/components/feasibility/FeasibilityRunDetailView";

interface Props {
  runId: string;
}

export default function FeasibilityRunDeepLinkClient({ runId }: Props) {
  return <FeasibilityRunDetailView runId={runId} />;
}
