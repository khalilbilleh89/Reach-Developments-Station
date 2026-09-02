"use client";

import { useState } from "react";

import { ApiError, pricing } from "@/lib/api";
import type { QuotePreview } from "@/lib/api";
import {
  Button,
  Card,
  Field,
  FieldRow,
  FormActions,
  FormSection,
  InlineMeta,
  InlineMetaItem,
  MoneyInput,
  Notice,
  RateInput,
  Waterfall,
  WaterfallRow,
} from "@/components/ui";
import { fractionFromPercent, money, percent } from "@/lib/format";

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
 *
 * Rates are typed as percentages and sent as the server's fraction of one; the
 * conversion moves a decimal point in a string and never multiplies.
 */
const RATE_TERMS = new Set(["discount_fraction", "payment_plan_adjustment_fraction"]);

const PRICE_TERMS: { name: string; label: string; hint?: string }[] = [
  { name: "discount_fraction", label: "Discount rate", hint: "Of the reference price." },
  { name: "discount_amount", label: "Discount amount" },
  { name: "seller_credit", label: "Seller credit" },
  { name: "paid_upgrade_amount", label: "Paid upgrade" },
  {
    name: "payment_plan_adjustment_fraction",
    label: "Payment plan adjustment",
    hint: "Signed. A negative rate reduces the price.",
  },
];

const SELLER_COSTS: { name: string; label: string }[] = [
  { name: "package_cost", label: "Package cost" },
  { name: "upgrade_allowance_cost", label: "Upgrade allowance" },
  { name: "commission_support", label: "Commission support" },
  { name: "financing_subsidy", label: "Financing subsidy" },
  { name: "extended_terms_npv_cost", label: "Extended-term NPV cost" },
];

export function QuotePreviewPanel({
  projectId,
  unitId,
  currencyCode,
  onClose,
}: {
  projectId: string;
  unitId: string;
  /** The active price version's currency — the quote is computed from it. */
  currencyCode: string | null;
  onClose: () => void;
}) {
  const [terms, setTerms] = useState<Record<string, string>>({});
  const [quote, setQuote] = useState<QuotePreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (name: string) => (value: string) => setTerms((current) => ({ ...current, [name]: value }));

  const run = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = Object.fromEntries(
        Object.entries(terms)
          .filter(([, value]) => value.trim() !== "")
          .map(([name, value]) => [name, RATE_TERMS.has(name) ? fractionFromPercent(value) : value]),
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
    <Card
      title="Quote preview"
      description="A calculation, not a reservation. Nothing here is saved."
      headingLevel={3}
      actions={
        <Button small variant="quiet" onClick={onClose}>
          Close
        </Button>
      }
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      <form onSubmit={run}>
        <FormSection title="Price terms" description="These change what the buyer contracts to pay.">
          <FieldRow columns={3}>
            {PRICE_TERMS.map((term) => (
              <Field key={term.name} label={term.label} hint={term.hint} optional>
                {RATE_TERMS.has(term.name) ? (
                  <RateInput value={terms[term.name] ?? ""} onChange={set(term.name)} />
                ) : (
                  <MoneyInput code={currencyCode} value={terms[term.name] ?? ""} onChange={set(term.name)} />
                )}
              </Field>
            ))}
          </FieldRow>
        </FormSection>
        <FormSection
          title="Seller-borne costs"
          description="These reduce what the sale earns. They do not reduce the contract price."
        >
          <FieldRow columns={3}>
            {SELLER_COSTS.map((term) => (
              <Field key={term.name} label={term.label} optional>
                <MoneyInput code={currencyCode} value={terms[term.name] ?? ""} onChange={set(term.name)} />
              </Field>
            ))}
            <Field label="Buyer-paid fees" optional>
              <MoneyInput code={currencyCode} value={terms.buyer_paid_fees ?? ""} onChange={set("buyer_paid_fees")} />
            </Field>
          </FieldRow>
        </FormSection>
        <FormActions>
          <Button variant="primary" type="submit" disabled={busy}>
            {busy ? "Pricing…" : "Preview the quote"}
          </Button>
        </FormActions>
      </form>

      {quote ? (
        <>
          {quote.approval_required ? (
            <Notice tone="error">
              {quote.approval_reason}
              {quote.required_role ? ` Requires: ${quote.required_role}.` : ""}
            </Notice>
          ) : null}
          <h4 className="section-heading">Contract</h4>
          <Waterfall>
            <WaterfallRow
              label="Approved reference price"
              note="Ex tax"
              amount={money(quote.approved_reference_price_ex_tax, currencyCode)}
            />
            <WaterfallRow label="Paid upgrade" amount={money(quote.paid_upgrade_price, currencyCode)} />
            <WaterfallRow
              label="Payment plan adjustment"
              amount={money(quote.payment_plan_price_adjustment, currencyCode)}
            />
            <WaterfallRow
              label="Gross quoted price"
              note="Ex tax"
              amount={money(quote.gross_quoted_price_ex_tax, currencyCode)}
              kind="subtotal"
            />
            <WaterfallRow label="Cash discount" amount={money(quote.cash_discount, currencyCode)} />
            <WaterfallRow label="Seller credit" amount={money(quote.seller_credit, currencyCode)} />
            <WaterfallRow
              label="Net contract price"
              note="Ex tax"
              amount={money(quote.net_contract_price_ex_tax, currencyCode)}
              kind="total"
            />
          </Waterfall>
          <h4 className="section-heading">Seller costs</h4>
          <Waterfall>
            <WaterfallRow label="Package cost" amount={money(quote.seller_package_cost, currencyCode)} />
            <WaterfallRow label="Upgrade allowance" amount={money(quote.upgrade_allowance_cost, currencyCode)} />
            <WaterfallRow label="Commission support" amount={money(quote.commission_support, currencyCode)} />
            <WaterfallRow label="Financing subsidy" amount={money(quote.financing_subsidy, currencyCode)} />
            <WaterfallRow label="Extended-term NPV cost" amount={money(quote.extended_terms_npv_cost, currencyCode)} />
            <WaterfallRow
              label="Effective net revenue"
              note="What the sale earns after seller costs"
              amount={money(quote.effective_net_revenue_preview, currencyCode)}
              kind="total"
            />
          </Waterfall>
          <h4 className="section-heading">Buyer payable</h4>
          {quote.tax_status === "not_configured" ? (
            <Notice tone="info">
              No sale tax is configured for this country pack, so no tax is shown. A guessed rate
              would be worse than none.
            </Notice>
          ) : null}
          <Waterfall>
            <WaterfallRow
              label="Net contract price"
              note="Ex tax"
              amount={money(quote.net_contract_price_ex_tax, currencyCode)}
            />
            {quote.taxes.map((tax) => (
              <WaterfallRow
                key={tax.tax_code}
                label={tax.label}
                note={percent(tax.rate_fraction)}
                amount={money(tax.amount, currencyCode)}
              />
            ))}
            <WaterfallRow label="Buyer-paid fees" amount={money(quote.buyer_paid_fees, currencyCode)} />
            <WaterfallRow
              label="Total buyer payable"
              amount={money(quote.total_buyer_payable_preview, currencyCode)}
              kind="total"
            />
          </Waterfall>
          <InlineMeta>
            <InlineMetaItem label="Tax treatment">{quote.tax_treatment_code}</InlineMetaItem>
            {quote.offer_valid_days ? (
              <InlineMetaItem label="Offer valid">{quote.offer_valid_days} days</InlineMetaItem>
            ) : null}
            {quote.reservation_expiry_days ? (
              <InlineMetaItem label="Reservation expires in">{quote.reservation_expiry_days} days</InlineMetaItem>
            ) : null}
          </InlineMeta>
        </>
      ) : null}
    </Card>
  );
}
