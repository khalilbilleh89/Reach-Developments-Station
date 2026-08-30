"use client";

import { useState } from "react";

import { ApiError, pricing } from "@/lib/api";
import type { QuotePreview } from "@/lib/api";
import { Badge, Button, Field, Notice, Panel } from "@/components/ui";

/**
 * Model an offer against a unit's live price.
 *
 * Writes nothing: no client, no reservation, no sale. The inputs go to the
 * backend and the whole waterfall comes back, because implementing the same
 * arithmetic here in JavaScript would give the business two answers to one
 * question and no way to tell which is authoritative.
 *
 * The two groups of inputs are separated on screen because they are separate in
 * fact. A discount reduces what the buyer contracts to pay; a furniture package
 * the seller absorbs does not — the contract stays where it is and the seller's
 * net revenue falls.
 */
const PRICE_TERMS: { name: string; label: string; hint?: string }[] = [
  { name: "discount_fraction", label: "Discount (fraction)", hint: "0.050000 is 5%." },
  { name: "discount_amount", label: "Discount (amount)" },
  { name: "seller_credit", label: "Seller credit" },
  { name: "paid_upgrade_amount", label: "Paid upgrade" },
  {
    name: "payment_plan_adjustment_fraction",
    label: "Payment plan adjustment",
    hint: "A signed fraction of the reference price.",
  },
];

const SELLER_COSTS: { name: string; label: string }[] = [
  { name: "package_cost", label: "Package cost" },
  { name: "upgrade_allowance_cost", label: "Upgrade allowance" },
  { name: "commission_support", label: "Commission support" },
  { name: "financing_subsidy", label: "Financing subsidy" },
  { name: "extended_terms_npv_cost", label: "Extended-term NPV cost" },
];

function Line({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div>
      <dt className="reference-term">{strong ? <strong>{label}</strong> : label}</dt>
      <dd className="reference-value mono nowrap">{strong ? <strong>{value}</strong> : value}</dd>
    </div>
  );
}

export function QuotePreviewPanel({
  projectId,
  unitId,
  onClose,
}: {
  projectId: string;
  unitId: string;
  onClose: () => void;
}) {
  const [terms, setTerms] = useState<Record<string, string>>({});
  const [quote, setQuote] = useState<QuotePreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = Object.fromEntries(
        Object.entries(terms).filter(([, value]) => value.trim() !== ""),
      );
      setQuote(await pricing.quotePreview(projectId, unitId, body));
    } catch (caught) {
      setQuote(null);
      setError(caught instanceof ApiError ? caught.message : "Could not price that quote.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel
      title="Quote preview"
      description="A calculation, not a reservation. Nothing here is saved."
      actions={
        <Button small onClick={onClose}>
          Close
        </Button>
      }
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      <form onSubmit={run}>
        <h3 className="section-heading">Price terms</h3>
        <div className="form-inline">
          {PRICE_TERMS.map((term) => (
            <Field key={term.name} label={term.label} hint={term.hint}>
              <input
                className="input input-short"
                inputMode="decimal"
                value={terms[term.name] ?? ""}
                onChange={(event) =>
                  setTerms({ ...terms, [term.name]: event.target.value })
                }
              />
            </Field>
          ))}
        </div>
        <h3 className="section-heading">Seller-borne costs</h3>
        <p className="subtle">
          These reduce what the sale earns. They do not reduce the contract price.
        </p>
        <div className="form-inline">
          {SELLER_COSTS.map((term) => (
            <Field key={term.name} label={term.label}>
              <input
                className="input input-short"
                inputMode="decimal"
                value={terms[term.name] ?? ""}
                onChange={(event) =>
                  setTerms({ ...terms, [term.name]: event.target.value })
                }
              />
            </Field>
          ))}
          <Field label="Buyer-paid fees">
            <input
              className="input input-short"
              inputMode="decimal"
              value={terms.buyer_paid_fees ?? ""}
              onChange={(event) =>
                setTerms({ ...terms, buyer_paid_fees: event.target.value })
              }
            />
          </Field>
        </div>
        <Button variant="primary" type="submit" disabled={busy}>
          {busy ? "Pricing…" : "Preview"}
        </Button>
      </form>

      {quote ? (
        <>
          {quote.approval_required ? (
            <Notice tone="error">
              {quote.approval_reason}
              {quote.required_role ? ` Requires: ${quote.required_role}.` : ""}
            </Notice>
          ) : null}
          <h3 className="section-heading">Contract</h3>
          <dl className="reference-list">
            <Line
              label="Approved reference price (ex tax)"
              value={quote.approved_reference_price_ex_tax}
            />
            <Line label="Paid upgrade" value={quote.paid_upgrade_price} />
            <Line label="Payment plan adjustment" value={quote.payment_plan_price_adjustment} />
            <Line label="Gross quoted price (ex tax)" value={quote.gross_quoted_price_ex_tax} strong />
            <Line label="Cash discount" value={quote.cash_discount} />
            <Line label="Seller credit" value={quote.seller_credit} />
            <Line
              label="Net contract price (ex tax)"
              value={quote.net_contract_price_ex_tax}
              strong
            />
          </dl>
          <h3 className="section-heading">Seller costs</h3>
          <dl className="reference-list">
            <Line label="Package cost" value={quote.seller_package_cost} />
            <Line label="Upgrade allowance" value={quote.upgrade_allowance_cost} />
            <Line label="Commission support" value={quote.commission_support} />
            <Line label="Financing subsidy" value={quote.financing_subsidy} />
            <Line label="Extended-term NPV cost" value={quote.extended_terms_npv_cost} />
            <Line
              label="Effective net revenue"
              value={quote.effective_net_revenue_preview}
              strong
            />
          </dl>
          <h3 className="section-heading">Buyer payable</h3>
          {quote.tax_status === "not_configured" ? (
            <Notice tone="info">
              No sale tax is configured for this country pack, so no tax is shown. A guessed
              rate would be worse than none.
            </Notice>
          ) : null}
          <dl className="reference-list">
            {quote.taxes.map((tax) => (
              <Line key={tax.tax_code} label={`${tax.label} (${tax.rate_fraction})`} value={tax.amount} />
            ))}
            <Line label="Buyer-paid fees" value={quote.buyer_paid_fees} />
            <Line
              label="Total buyer payable"
              value={quote.total_buyer_payable_preview}
              strong
            />
          </dl>
          <div className="chip-list">
            <Badge tone="muted">{quote.tax_treatment_code}</Badge>
            {quote.offer_valid_days ? (
              <span className="chip">Offer valid {quote.offer_valid_days} days</span>
            ) : null}
            {quote.reservation_expiry_days ? (
              <span className="chip">Reservation expires in {quote.reservation_expiry_days} days</span>
            ) : null}
          </div>
        </>
      ) : null}
    </Panel>
  );
}
