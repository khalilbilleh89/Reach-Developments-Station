"use client";

import type { UnitPricing } from "@/lib/api";
import type { Answer } from "@/lib/answer";
import {
  Badge,
  Button,
  ButtonRow,
  EmptyState,
  Loading,
  Metric,
  MetricGroup,
  Notice,
  SectionHeader,
  TableScroll,
} from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, money } from "@/lib/format";
import { PriceWaterfall } from "@/components/projects/pricing/PriceWaterfall";

const VERSION_LABELS: Record<string, string> = {
  draft: "Draft",
  submitted: "Submitted",
  approved: "Approved",
  active: "Active",
  superseded: "Superseded",
};

const VERSION_TONES: Record<string, "muted" | "warning" | "info" | "success" | "neutral"> = {
  draft: "muted",
  submitted: "warning",
  approved: "info",
  active: "success",
  superseded: "neutral",
};

/**
 * What this unit is offered at, and what that figure is made of.
 *
 * The buttons a caller is offered mirror the server's rule rather than replacing
 * it: the API refuses a submitter approving their own price, and an
 * administrator approving anything, whichever button was on screen.
 *
 * `canSeeInternal` mirrors the server's own narrowing: for a role that may see
 * only the live list price the history it returned holds nothing that is not
 * live, and the section says so rather than leaving an unexplained gap.
 *
 * The answer is the unit file's, made once for the header and this section
 * alike. A refusal, a failure and "not priced" are three different facts and
 * are drawn as three: a failed request is never reported as a role problem,
 * and never as a unit without a price.
 */
export function UnitPricingSection({
  answer,
  canPrice,
  canApprove,
  canSeeInternal,
  busy,
  onMove,
  onQuote,
}: {
  answer: Answer<UnitPricing>;
  canPrice: boolean;
  canApprove: boolean;
  canSeeInternal: boolean;
  busy: boolean;
  onMove: (action: "submit" | "approve" | "activate", versionId: string) => void;
  onQuote: () => void;
}) {
  const currencyCodeOf = useCurrencyCode();

  if (answer.status === "off" || answer.status === "denied") {
    return (
      <EmptyState
        title="Not available to your role"
        hint="The list price and its composition are shown to the roles that read pricing."
      />
    );
  }
  if (answer.status === "loading") {
    return <Loading label="Loading the unit's pricing" shape="metrics" />;
  }
  if (answer.status === "failed") {
    return (
      <Notice tone="error">
        Pricing could not be loaded. {answer.message} Nothing about this unit&rsquo;s price is
        known until it can be.
      </Notice>
    );
  }
  const unitPricing = answer.data;

  // The newest version that is on its way somewhere. An active price has
  // arrived; a superseded one is history.
  const pending = canSeeInternal
    ? (unitPricing.history.find((version) => ["draft", "submitted", "approved"].includes(version.status)) ?? null)
    : null;
  const active = unitPricing.active_price;
  const activeCode = currencyCodeOf(active?.currency_id);

  return (
    <>
      {unitPricing.repricing_required ? (
        <Notice tone="error">
          Repricing required. This unit has changed since its list price was set, so the price
          below is what it was offered at and no longer describes it. The unit cannot be released
          until a new price is approved and activated.
        </Notice>
      ) : null}

      {pending ? (
        <section>
          <SectionHeader
            title="Price in progress"
            actions={
              <Badge tone={VERSION_TONES[pending.status] ?? "neutral"}>
                {VERSION_LABELS[pending.status] ?? pending.status}
              </Badge>
            }
          />
          <MetricGroup compact>
            <Metric label="Version" value={`v${pending.version_number}`} size="sm" />
            <Metric
              label="Reference price (ex tax)"
              value={money(pending.reference_price_ex_tax, currencyCodeOf(pending.currency_id))}
              size="sm"
            />
            <Metric label="Prepared" value={businessDate(pending.valid_from)} size="sm" />
          </MetricGroup>
          <ButtonRow>
            {canPrice && pending.status === "draft" ? (
              <Button small disabled={busy} onClick={() => onMove("submit", pending.id)}>
                Submit for approval
              </Button>
            ) : null}
            {canApprove && pending.status === "submitted" ? (
              <Button small disabled={busy} onClick={() => onMove("approve", pending.id)}>
                Approve
              </Button>
            ) : null}
            {canApprove && pending.status === "approved" ? (
              <Button small variant="primary" disabled={busy} onClick={() => onMove("activate", pending.id)}>
                Activate
              </Button>
            ) : null}
          </ButtonRow>
          <p className="footnote">
            Nothing is live until it is approved and activated. Approval and preparation are
            deliberately different people.
          </p>
        </section>
      ) : null}

      <section>
        <SectionHeader
          title="Live list price"
          actions={
            active ? (
              <Button small onClick={onQuote}>
                Quote preview
              </Button>
            ) : undefined
          }
        />
        {active === null ? (
          <EmptyState
            title="Not priced"
            hint={
              unitPricing.has_active_configuration
                ? "Generate a price from the project's Pricing section."
                : "This project has no active pricing configuration yet."
            }
          />
        ) : (
          <>
            <MetricGroup>
              <Metric
                label="Reference price (ex tax)"
                value={money(active.reference_price_ex_tax, activeCode)}
                size="lg"
              />
              <Metric
                label="Per internal unit"
                value={money(active.price_per_internal_area, activeCode)}
                size="sm"
              />
              <Metric
                label="Version"
                value={`v${active.version_number}`}
                note={`Live from ${businessDate(active.valid_from)}`}
                size="sm"
              />
              <Metric
                label="Pricing gate"
                value={unitPricing.pricing_approved ? "Approved" : "Not approved"}
                size="sm"
              />
            </MetricGroup>
            <h4 className="section-heading">How it was built</h4>
            <PriceWaterfall version={active} />
          </>
        )}
      </section>

      {unitPricing.history.length > 1 ? (
        <section>
          <SectionHeader title="Price history" />
          <TableScroll label="Price history" compact>
            <thead>
              <tr>
                <th scope="col">Version</th>
                <th scope="col">Status</th>
                <th scope="col">From</th>
                <th scope="col">To</th>
                <th scope="col" className="num">
                  Price
                </th>
                <th scope="col" className="cell-prose">
                  Reason
                </th>
              </tr>
            </thead>
            <tbody>
              {unitPricing.history.map((version) => (
                <tr key={version.id}>
                  <th scope="row" className="mono">
                    v{version.version_number}
                  </th>
                  <td>
                    <Badge tone={VERSION_TONES[version.status] ?? "neutral"}>
                      {VERSION_LABELS[version.status] ?? version.status}
                    </Badge>
                  </td>
                  <td className="figure">{businessDate(version.valid_from)}</td>
                  <td className="figure">{businessDate(version.valid_to)}</td>
                  <td className="num">
                    {money(version.reference_price_ex_tax, currencyCodeOf(version.currency_id))}
                  </td>
                  <td className="cell-prose">{version.change_reason ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        </section>
      ) : null}

      {canSeeInternal ? null : (
        <p className="footnote">
          Prices that are not yet live — drafts, submissions and approvals awaiting activation — are
          not shown to your role.
        </p>
      )}
    </>
  );
}
