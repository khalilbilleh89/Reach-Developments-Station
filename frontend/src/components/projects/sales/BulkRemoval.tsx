"use client";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import type { BulkRemoval } from "@/lib/api";
import { BulkBar, Button, Notice, PromptDialog } from "@/components/ui";

/**
 * The bulk bar's destructive action for a register. The server runs each
 * ticked record through its own single-record removal, so a record that must be
 * kept is listed with the reason that kept it and never blocks the rest.
 */
export function BulkRemovalBar({ count, noun, verb, description, names, run, onClear, onDone }: {
  count: number;
  noun: string;
  verb: "Delete" | "Remove";
  /** What happens to the ticked records, and what is kept. */
  description: string;
  /** Display names by id, so a kept record is named rather than numbered. */
  names: Record<string, string>;
  run: (reason: string) => Promise<BulkRemoval>;
  onClear: () => void;
  onDone: () => void;
}) {
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BulkRemoval | null>(null);
  // Names as they were when the action ran: the register reloads underneath.
  const [named, setNamed] = useState<Record<string, string>>({});
  const many = (n: number) => `${n} ${n === 1 ? noun : `${noun}s`}`;
  const done = verb === "Delete" ? "Deleted" : "Removed";
  const submit = async (reason: string) => {
    setBusy(true);
    setError(null);
    try {
      const outcome = await run(reason);
      setNamed(names);
      setResult(outcome);
      setAsking(false);
      onClear();
      onDone();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : `Could not finish. Refresh the list to see which ${noun}s changed.`);
    } finally {
      setBusy(false);
    }
  };
  return <>
    {result ? <Notice tone={result.skipped.length ? "warning" : "success"}>
      <p className="bulk-result-head">
        <strong>{`${done} ${many(result.removed.length)}.`}</strong>
        {result.skipped.length ? `${many(result.skipped.length)} kept:` : null}
        <Button small variant="quiet" onClick={() => setResult(null)}>Dismiss</Button>
      </p>
      {result.skipped.length ? <ul className="bulk-result-list">{groups(result, named).map(([message, who]) => <li key={message}><strong>{message}</strong> {who.join(", ")}</li>)}</ul> : null}
    </Notice> : null}
    <BulkBar count={count} noun={noun} onClear={onClear}>
      <Button small variant="danger" disabled={busy} onClick={() => { setError(null); setAsking(true); }}>{verb} selected</Button>
    </BulkBar>
    {asking ? <PromptDialog
      title={`${verb} ${many(count)}?`}
      description={description}
      label={`Reason for ${verb === "Delete" ? "deletion" : "removal"}`}
      hint="Recorded on every record, with your name and the time."
      confirmLabel={`${verb} ${many(count)}`}
      destructive
      busy={busy}
      error={error}
      onCancel={() => { if (!busy) { setAsking(false); setError(null); } }}
      onSubmit={reason => void submit(reason)}
    /> : null}
  </>;
}

/** Kept records grouped by the rule that kept them, so twelve identical reasons read once. */
function groups(result: BulkRemoval, names: Record<string, string>): [string, string[]][] {
  const byMessage = new Map<string, string[]>();
  for (const row of result.skipped) {
    const who = byMessage.get(row.message) ?? [];
    who.push(names[row.id] ?? "a record no longer listed");
    byMessage.set(row.message, who);
  }
  return [...byMessage];
}
