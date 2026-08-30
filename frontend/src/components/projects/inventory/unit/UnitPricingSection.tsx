"use client";

import type { UnitPricing } from "@/lib/api";
import {
  Badge,
  Button,
  ButtonRow,
  EmptyState,
  Notice,
  SectionHeader,
  Stat,
  StatRow,
  TableScroll,
} from "@/components/ui";
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
 */
export function UnitPricingSection({
  unitPricing,
  canPrice,
  canApprove,
  busy,
  onMove,
  onQuote,
}: {
  unitPricing: UnitPricing | null;
  canPrice: boolean;
  canApprove: boolean;
  busy: boolean;
  onMove: (action: "submit" | "approve" | "activate", versionId: string) => void;
  onQuote: () => void;
}) {
  if (unitPricing === null) {
    return (
      <EmptyState
        title="Not available to your role"
        hint="The live list price is shown on the unit summary. Price composition belongs to Finance."
      />
    );
  }

  // The newest version that is on its way somewhere. An active price has
  // arrived; a superseded one is history.
  const pending =
    unitPricing.history.find((version) =>
      ["draft", "submitted", "approved"].includes(version.status),
    ) ?? null;

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
          <SectionHeader title="Price in progress" />
          <ButtonRow>
            <span className="chip">
              <span className="chip-label">Version</span>
              <strong>{pending.version_number}</strong>
              <Badge tone={VERSION_TONES[pending.status] ?? "neutral"}>
                {VERSION_LABELS[pending.status] ?? pending.status}
              </Badge>
            </span>
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
              <Button
                small
                variant="primary"
                disabled={busy}
                onClick={() => onMove("activate", pending.id)}
              >
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
            unitPricing.active_price ? (
              <Button small onClick={onQuote}>
                Quote preview
              </Button>
            ) : undefined
          }
        />
        {unitPricing.active_price === null ? (
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
            <StatRow>
              <Stat
                label="Reference price (ex tax)"
                value={unitPricing.active_price.reference_price_ex_tax}
              />
              <Stat
                label="Per internal unit"
                value={unitPricing.active_price.price_per_internal_area ?? "—"}
                small
              />
              <Stat
                label="Version"
                value={`v${unitPricing.active_price.version_number}`}
                note={`Live from ${unitPricing.active_price.valid_from}`}
                small
              />
              <Stat
                label="Pricing gate"
                value={unitPricing.pricing_approved ? "Approved" : "Not approved"}
                small
              />
            </StatRow>
            <h4 className="section-heading">How it was built</h4>
            <PriceWaterfall version={unitPricing.active_price} />
          </>
        )}
      </section>

      {unitPricing.history.length > 1 ? (
        <section>
          <SectionHeader title="Price history" />
          <TableScroll label="Price history">
            <thead>
              <tr>
                <th scope="col">Version</th>
                <th scope="col">Status</th>
                <th scope="col">From</th>
                <th scope="col">To</th>
                <th scope="col" className="num">
                  Price
                </th>
                <th scope="col">Reason</th>
              </tr>
            </thead>
            <tbody>
              {unitPricing.history.map((version) => (
                <tr key={version.id}>
                  <th scope="row" className="mono">
                    {version.version_number}
                  </th>
                  <td>
                    <Badge tone={VERSION_TONES[version.status] ?? "neutral"}>
                      {VERSION_LABELS[version.status] ?? version.status}
                    </Badge>
                  </td>
                  <td className="mono nowrap">{version.valid_from}</td>
                  <td className="mono nowrap">{version.valid_to ?? "—"}</td>
                  <td className="num">{version.reference_price_ex_tax}</td>
                  <td>{version.change_reason ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        </section>
      ) : null}
    </>
  );
}
