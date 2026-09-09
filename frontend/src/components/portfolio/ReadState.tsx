import { Loading, Notice } from "@/components/ui";
import type { Answer } from "@/lib/answer";

export function ReadState({ answer, label }: { answer: Answer<unknown>; label: string }) {
  if (answer.status === "denied" || answer.status === "off") return <Notice tone="info">This management view is not available to your current access.</Notice>;
  if (answer.status === "failed") return <Notice tone="error">{answer.message}</Notice>;
  return <Loading label={label} />;
}
