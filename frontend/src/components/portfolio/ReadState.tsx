import { Button, Loading, Notice } from "@/components/ui";
import type { Answer } from "@/lib/answer";

export function ReadState({ answer, label }: { answer: Answer<unknown> & { retry?: () => void }; label: string }) {
  if (answer.status === "denied" || answer.status === "off") return <Notice tone="info">This section is not available to your current access.</Notice>;
  if (answer.status === "failed") return <Notice tone="error">{answer.message} {answer.retry ? <Button onClick={answer.retry}>Retry</Button> : null}</Notice>;
  return <Loading label={label} />;
}
