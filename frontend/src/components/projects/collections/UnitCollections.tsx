"use client";

import { useEffect, useState } from "react";

import { Badge, Button, Notice, SectionHeader, Stat, StatRow } from "@/components/ui";
import { ApiError, collections } from "@/lib/api";
import type { CollectionSaleSummary } from "@/lib/api";
import { useCurrencyCode } from "@/lib/currency";
import { isPositive, money } from "@/lib/format";

import { unitCollectionLabel, unitCollectionTone } from "./labels";

/**
 * The collection dimension on Unit 360, and the figures behind the badge.
 *
 * Unit 360 has shown a `collection_status` since PR-MVP-03 with nothing to
 * substantiate it. This is what it now means: the cash confirmed against this
 * unit's contract, how much of it has been applied, what is still outstanding
 * and how much of that is overdue.
 *
 * Deliberately five figures and a link, not a second collections workspace.
 * Every one of them comes from the sale's own summary endpoint — the same
 * function the register and the account screen call — so a reader who checks
 * this against the Collections tab finds the same numbers rather than a second
 * opinion.
 */
export function UnitCollections({
  projectId,
  saleId,
  onOpenCollections,
}: {
  projectId: string;
  saleId: string | null;
  onOpenCollections?: () => void;
}) {
  const [summary, setSummary] = useState<CollectionSaleSummary | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const currencyCodeOf = useCurrencyCode();

  useEffect(() => {
    let live = true;
    void (async () => {
      if (saleId === null) return;
      try {
        const value = await collections.account(projectId, saleId);
        if (live) {
          setSummary(value);
          setProblem(null);
        }
      } catch (caught) {
        // A 403 is a fact about this reader; anything else is a fault, and
        // telling somebody their role is wrong when the server returned a 500
        // sends them to an administrator instead of to the logs.
        if (live) {
          setSummary(null);
          setProblem(
            caught instanceof ApiError && caught.isForbidden
              ? "Collections is not available to your role."
              : caught instanceof ApiError
                ? caught.message
                : "Could not load the collections position.",
          );
        }
      }
    })();
    return () => {
      live = false;
    };
  }, [projectId, saleId]);

  if (saleId === null) {
    return null;
  }

  const code = currencyCodeOf(summary?.currency_id);

  return (
    <section>
      <SectionHeader
        title="Collection"
        actions={
          onOpenCollections ? (
            <Button small onClick={onOpenCollections}>
              Collections account
            </Button>
          ) : undefined
        }
      />
      {problem !== null ? (
        <p className="subtle">{problem}</p>
      ) : summary === null ? (
        <p className="subtle">Loading the collections position.</p>
      ) : (
        <>
          <StatRow>
            <Stat
              label="Position"
              value={
                <Badge tone={unitCollectionTone(summary.derived_collection_status)}>
                  {unitCollectionLabel(summary.derived_collection_status)}
                </Badge>
              }
              small
            />
            <Stat
              label="Collected"
              value={money(summary.allocated_total, code)}
              note="Confirmed and applied"
              small
            />
            <Stat
              label="Outstanding"
              value={money(summary.outstanding_total, code)}
              small
            />
            <Stat
              label="Overdue"
              value={money(summary.overdue_total, code)}
              note={
                summary.oldest_overdue_days > 0
                  ? `Oldest ${summary.oldest_overdue_days} days`
                  : "Nothing past grace"
              }
              small
            />
            <Stat
              label="Unapplied cash"
              value={money(summary.unapplied_cash, code)}
              note="Received, not yet applied"
              small
            />
          </StatRow>
          {isPositive(summary.unapplied_cash) ? (
            <p className="footnote">
              Confirmed cash on this account has not been applied to an instalment, so it is not
              reducing the outstanding balance.
            </p>
          ) : null}
          {summary.open_disputes > 0 ? (
            <Notice tone="warning">
              {summary.open_disputes} instalment
              {summary.open_disputes === 1 ? " is" : "s are"} disputed. The balance is unchanged
              and still ageing.
            </Notice>
          ) : null}
        </>
      )}
    </section>
  );
}
