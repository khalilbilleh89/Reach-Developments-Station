"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, settings } from "@/lib/api";
import type { ApprovalThresholds, CountryPack, Currency, TaxRule } from "@/lib/api";
import { businessDate, fractionFromPercent, percent, percentInput } from "@/lib/format";
import {
  Button,
  Card,
  EmptyState,
  Field,
  FieldRow,
  FormActions,
  FormSection,
  Loading,
  MoneyInput,
  Notice,
  RateInput,
  StatusDot,
  TableScroll,
} from "@/components/ui";

const AREA_UNITS = ["sqm", "sqft"];
const APPLIES_TO = ["sale", "rental", "service_charge", "construction", "other"];
const BASIS = ["net_amount", "gross_amount"];

const label = (value: string) => value.replace(/_/g, " ");

/** The thresholds form as text, one field per control limit the API holds. */
function thresholdForm(row: ApprovalThresholds | null) {
  return {
    discount_review_rate: percentInput(row?.discount_review_rate_fraction),
    discount_review_amount: row?.discount_review_amount ?? "",
    minimum_margin_rate: percentInput(row?.minimum_margin_rate_fraction),
    custom_plan_min_down_payment_rate: percentInput(row?.custom_plan_min_down_payment_rate_fraction),
    custom_plan_max_duration_months: row?.custom_plan_max_duration_months?.toString() ?? "",
    custom_plan_max_post_handover_rate: percentInput(row?.custom_plan_max_post_handover_rate_fraction),
    custom_plan_max_npv_cost_rate: percentInput(row?.custom_plan_max_npv_cost_rate_fraction),
    construction_variation_review_amount: row?.construction_variation_review_amount ?? "",
    forecast_reset_variance_rate: percentInput(row?.forecast_reset_variance_rate_fraction),
    pricing_requires_finance_approval: row?.pricing_requires_finance_approval ?? false,
    pricing_requires_commercial_approval: row?.pricing_requires_commercial_approval ?? false,
    receipt_reversal_requires_dual_control: row?.receipt_reversal_requires_dual_control ?? true,
    refund_requires_dual_control: row?.refund_requires_dual_control ?? true,
  };
}

/**
 * One country workspace: the pack, its tax rules and its control limits.
 *
 * A pack is what a project inherits when it is created — locale, timezone,
 * default currency, area unit, fiscal year — and the tax rules and approval
 * thresholds beside it are the country's, not any one project's. Nothing here
 * calculates: a rate is stored as the fraction the server understands, and the
 * form shows it as the percentage a person reads.
 */
export function CountryPacksSection() {
  const [packs, setPacks] = useState<CountryPack[] | null>(null);
  const [currencies, setCurrencies] = useState<Currency[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [taxRules, setTaxRules] = useState<TaxRule[]>([]);
  const [thresholds, setThresholds] = useState<ApprovalThresholds | null>(null);
  const [limits, setLimits] = useState(thresholdForm(null));
  const [addingPack, setAddingPack] = useState(false);
  const [addingTax, setAddingTax] = useState(false);
  const [packForm, setPackForm] = useState({
    country_code: "",
    name: "",
    locale: "en",
    timezone: "UTC",
    default_currency_id: "",
    area_unit: "sqm",
    fiscal_year_start_month: "1",
  });
  const [taxForm, setTaxForm] = useState({
    tax_code: "",
    label: "",
    applies_to: "sale",
    calculation_basis: "net_amount",
    rate_percent: "",
    valid_from: "",
    valid_to: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [packList, currencyList] = await Promise.all([settings.countryPacks(), settings.currencies()]);
      setPacks(packList);
      setCurrencies(currencyList);
      setSelected((current) => current ?? packList[0]?.id ?? null);
      setError(null);
    } catch (caught) {
      setPacks([]);
      setError(caught instanceof ApiError ? caught.message : "Could not load country packs.");
    }
  }, []);

  const loadDetail = useCallback(async (packId: string) => {
    setTaxRules(await settings.taxRules(packId));
    try {
      const row = await settings.approvalThresholds(packId);
      setThresholds(row);
      setLimits(thresholdForm(row));
    } catch (caught) {
      // Thresholds are optional until someone configures them.
      if (caught instanceof ApiError && caught.status === 404) {
        setThresholds(null);
        setLimits(thresholdForm(null));
      } else throw caught;
    }
  }, []);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  useEffect(() => {
    if (!selected) return;
    void (async () => {
      try {
        await loadDetail(selected);
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : "Could not load the country pack.");
      }
    })();
  }, [selected, loadDetail]);

  async function act<T>(operation: () => Promise<T>, success: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await operation();
      setNotice(success);
      await load();
      if (selected) await loadDetail(selected);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The change could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  const currencyCode = (id: string) => currencies.find((currency) => currency.id === id)?.code ?? null;
  const activeCurrencies = currencies.filter((currency) => currency.is_active);
  const pack = packs?.find((candidate) => candidate.id === selected) ?? null;
  const packCode = pack ? currencyCode(pack.default_currency_id) : null;
  const optional = (text: string) => (text.trim() === "" ? null : text.trim());

  return (
    <div className="stack">
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      {addingPack ? (
        <Card title="Add a country pack" description="What every project in this country inherits when it is created.">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void act(async () => {
                await settings.createCountryPack({
                  country_code: packForm.country_code.trim().toUpperCase(),
                  name: packForm.name.trim(),
                  locale: packForm.locale.trim(),
                  timezone: packForm.timezone.trim(),
                  default_currency_id: packForm.default_currency_id,
                  area_unit: packForm.area_unit,
                  fiscal_year_start_month: Number(packForm.fiscal_year_start_month || "1"),
                });
                setAddingPack(false);
              }, "Country pack created.");
            }}
          >
            <FieldRow columns={4}>
              <Field label="Country code" hint="ISO 3166, two letters.">
                <input
                  className="input input-xs"
                  required
                  minLength={2}
                  maxLength={2}
                  value={packForm.country_code}
                  onChange={(event) => setPackForm({ ...packForm, country_code: event.target.value })}
                />
              </Field>
              <Field label="Name">
                <input
                  className="input"
                  required
                  value={packForm.name}
                  onChange={(event) => setPackForm({ ...packForm, name: event.target.value })}
                />
              </Field>
              <Field label="Locale">
                <input
                  className="input input-short"
                  required
                  value={packForm.locale}
                  onChange={(event) => setPackForm({ ...packForm, locale: event.target.value })}
                />
              </Field>
              <Field label="Timezone">
                <input
                  className="input"
                  required
                  value={packForm.timezone}
                  onChange={(event) => setPackForm({ ...packForm, timezone: event.target.value })}
                />
              </Field>
              <Field label="Default currency">
                <select
                  className="input"
                  required
                  value={packForm.default_currency_id}
                  onChange={(event) => setPackForm({ ...packForm, default_currency_id: event.target.value })}
                >
                  <option value="">Choose…</option>
                  {activeCurrencies.map((currency) => (
                    <option key={currency.id} value={currency.id}>
                      {currency.code} — {currency.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Area unit">
                <select
                  className="input input-short"
                  value={packForm.area_unit}
                  onChange={(event) => setPackForm({ ...packForm, area_unit: event.target.value })}
                >
                  {AREA_UNITS.map((unit) => (
                    <option key={unit} value={unit}>
                      {unit}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Fiscal year starts" hint="Month number, 1 to 12.">
                <input
                  className="input input-xs"
                  type="number"
                  min={1}
                  max={12}
                  value={packForm.fiscal_year_start_month}
                  onChange={(event) => setPackForm({ ...packForm, fiscal_year_start_month: event.target.value })}
                />
              </Field>
            </FieldRow>
            <FormActions>
              <Button variant="primary" type="submit" disabled={busy || activeCurrencies.length === 0}>
                {busy ? "Saving…" : "Create country pack"}
              </Button>
              <Button onClick={() => setAddingPack(false)} disabled={busy}>
                Cancel
              </Button>
            </FormActions>
          </form>
        </Card>
      ) : null}

      <Card
        title="Country packs"
        description="Select a pack to maintain its tax rules and approval thresholds."
        actions={
          addingPack ? undefined : (
            <Button variant="primary" onClick={() => setAddingPack(true)}>
              Add country pack
            </Button>
          )
        }
        flush
      >
        {packs === null ? (
          <Loading label="Loading country configuration…" shape="rows" rows={2} />
        ) : packs.length === 0 ? (
          <div className="card-body">
            <EmptyState
              title="No country packs yet"
              hint="A country pack holds the configuration every project in that country inherits. Add a currency first if there is none."
            />
          </div>
        ) : (
          <TableScroll label="Country packs">
            <thead>
              <tr>
                <th scope="col">Country</th>
                <th scope="col">Locale</th>
                <th scope="col">Timezone</th>
                <th scope="col">Currency</th>
                <th scope="col">Area unit</th>
                <th scope="col" className="num">
                  Fiscal year starts
                </th>
                <th scope="col">State</th>
              </tr>
            </thead>
            <tbody>
              {packs.map((candidate) => (
                <tr key={candidate.id}>
                  <th scope="row">
                    <button
                      type="button"
                      className="button-link"
                      aria-current={candidate.id === selected ? "true" : undefined}
                      onClick={() => setSelected(candidate.id)}
                    >
                      {candidate.country_code} · {candidate.name}
                    </button>
                    {candidate.id === selected ? <span className="cell-secondary">Selected</span> : null}
                  </th>
                  <td>{candidate.locale}</td>
                  <td>{candidate.timezone}</td>
                  <td className="mono">{currencyCode(candidate.default_currency_id) ?? "—"}</td>
                  <td>{candidate.area_unit}</td>
                  <td className="num">Month {candidate.fiscal_year_start_month}</td>
                  <td>
                    {candidate.is_active ? (
                      <StatusDot tone="success">Active</StatusDot>
                    ) : (
                      <StatusDot tone="muted">Inactive</StatusDot>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        )}
      </Card>

      {pack ? (
        <div className="grid-12">
          <div className="span-7">
            <Card
              title={`Tax rules — ${pack.name}`}
              description="Effective-dated. Nothing is calculated here, and history is never overwritten."
              actions={
                <Button onClick={() => setAddingTax((open) => !open)} aria-expanded={addingTax}>
                  {addingTax ? "Cancel" : "Add tax rule"}
                </Button>
              }
            >
              {addingTax ? (
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    void act(async () => {
                      await settings.createTaxRule(pack.id, {
                        tax_code: taxForm.tax_code.trim(),
                        label: taxForm.label.trim(),
                        applies_to: taxForm.applies_to,
                        calculation_basis: taxForm.calculation_basis,
                        rate_fraction: fractionFromPercent(taxForm.rate_percent),
                        valid_from: taxForm.valid_from,
                        valid_to: taxForm.valid_to || null,
                      });
                      setAddingTax(false);
                      setTaxForm({ ...taxForm, tax_code: "", label: "", rate_percent: "", valid_from: "", valid_to: "" });
                    }, "Tax rule added.");
                  }}
                >
                  <FieldRow columns={3}>
                    <Field label="Code">
                      <input
                        className="input input-short"
                        required
                        value={taxForm.tax_code}
                        onChange={(event) => setTaxForm({ ...taxForm, tax_code: event.target.value })}
                      />
                    </Field>
                    <Field label="Label" className="field-span-2">
                      <input
                        className="input"
                        required
                        value={taxForm.label}
                        onChange={(event) => setTaxForm({ ...taxForm, label: event.target.value })}
                      />
                    </Field>
                    <Field label="Applies to">
                      <select
                        className="input"
                        value={taxForm.applies_to}
                        onChange={(event) => setTaxForm({ ...taxForm, applies_to: event.target.value })}
                      >
                        {APPLIES_TO.map((value) => (
                          <option key={value} value={value}>
                            {label(value)}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Basis">
                      <select
                        className="input"
                        value={taxForm.calculation_basis}
                        onChange={(event) => setTaxForm({ ...taxForm, calculation_basis: event.target.value })}
                      >
                        {BASIS.map((value) => (
                          <option key={value} value={value}>
                            {label(value)}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Rate">
                      <RateInput
                        required
                        value={taxForm.rate_percent}
                        onChange={(value) => setTaxForm({ ...taxForm, rate_percent: value })}
                      />
                    </Field>
                    <Field label="Valid from">
                      <input
                        className="input input-short"
                        type="date"
                        required
                        value={taxForm.valid_from}
                        onChange={(event) => setTaxForm({ ...taxForm, valid_from: event.target.value })}
                      />
                    </Field>
                    <Field label="Valid to" optional>
                      <input
                        className="input input-short"
                        type="date"
                        value={taxForm.valid_to}
                        onChange={(event) => setTaxForm({ ...taxForm, valid_to: event.target.value })}
                      />
                    </Field>
                  </FieldRow>
                  <FormActions>
                    <Button variant="primary" type="submit" disabled={busy}>
                      {busy ? "Saving…" : "Add tax rule"}
                    </Button>
                  </FormActions>
                </form>
              ) : null}

              {taxRules.length === 0 ? (
                <EmptyState compact title="No tax rules configured" hint="A sale quoted under this pack carries no tax until one applies." />
              ) : (
                <TableScroll label="Tax rules" compact>
                  <thead>
                    <tr>
                      <th scope="col">Tax</th>
                      <th scope="col">Applies to</th>
                      <th scope="col">Basis</th>
                      <th scope="col" className="num">
                        Rate
                      </th>
                      <th scope="col">Valid</th>
                      <th scope="col">State</th>
                    </tr>
                  </thead>
                  <tbody>
                    {taxRules.map((rule) => (
                      <tr key={rule.id}>
                        <th scope="row">
                          {rule.label}
                          <span className="cell-secondary mono">{rule.tax_code}</span>
                        </th>
                        <td>{label(rule.applies_to)}</td>
                        <td>{label(rule.calculation_basis)}</td>
                        <td className="num">{percent(rule.rate_fraction)}</td>
                        <td className="figure">
                          {businessDate(rule.valid_from)} → {rule.valid_to ? businessDate(rule.valid_to) : "open"}
                        </td>
                        <td>
                          {rule.is_active ? (
                            <StatusDot tone="success">Active</StatusDot>
                          ) : (
                            <StatusDot tone="muted">Retired</StatusDot>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </TableScroll>
              )}
            </Card>
          </div>

          <div className="span-5">
            <Card
              title={`Approval thresholds — ${pack.name}`}
              description="Control limits the modules consume. Storing policy here executes no workflow."
            >
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  void act(
                    () =>
                      settings.writeApprovalThresholds(pack.id, {
                        discount_review_rate_fraction: optional(fractionFromPercent(limits.discount_review_rate)),
                        discount_review_amount: optional(limits.discount_review_amount),
                        minimum_margin_rate_fraction: optional(fractionFromPercent(limits.minimum_margin_rate)),
                        custom_plan_min_down_payment_rate_fraction: optional(
                          fractionFromPercent(limits.custom_plan_min_down_payment_rate),
                        ),
                        custom_plan_max_duration_months: limits.custom_plan_max_duration_months
                          ? Number(limits.custom_plan_max_duration_months)
                          : null,
                        custom_plan_max_post_handover_rate_fraction: optional(
                          fractionFromPercent(limits.custom_plan_max_post_handover_rate),
                        ),
                        custom_plan_max_npv_cost_rate_fraction: optional(
                          fractionFromPercent(limits.custom_plan_max_npv_cost_rate),
                        ),
                        construction_variation_review_amount: optional(limits.construction_variation_review_amount),
                        forecast_reset_variance_rate_fraction: optional(
                          fractionFromPercent(limits.forecast_reset_variance_rate),
                        ),
                        pricing_requires_finance_approval: limits.pricing_requires_finance_approval,
                        pricing_requires_commercial_approval: limits.pricing_requires_commercial_approval,
                        receipt_reversal_requires_dual_control: limits.receipt_reversal_requires_dual_control,
                        refund_requires_dual_control: limits.refund_requires_dual_control,
                      }),
                    "Approval thresholds saved.",
                  );
                }}
              >
                <FormSection title="Commercial">
                  <FieldRow columns={2}>
                    <Field label="Discount review rate" hint="A discount at or above this needs sanction.">
                      <RateInput
                        value={limits.discount_review_rate}
                        onChange={(value) => setLimits({ ...limits, discount_review_rate: value })}
                      />
                    </Field>
                    <Field label="Discount review amount">
                      <MoneyInput
                        code={packCode}
                        value={limits.discount_review_amount}
                        onChange={(value) => setLimits({ ...limits, discount_review_amount: value })}
                      />
                    </Field>
                    <Field label="Minimum margin" hint="Units below this are flagged in unit economics.">
                      <RateInput
                        value={limits.minimum_margin_rate}
                        onChange={(value) => setLimits({ ...limits, minimum_margin_rate: value })}
                      />
                    </Field>
                  </FieldRow>
                </FormSection>
                <FormSection title="Payment plans">
                  <FieldRow columns={2}>
                    <Field label="Minimum down payment">
                      <RateInput
                        value={limits.custom_plan_min_down_payment_rate}
                        onChange={(value) => setLimits({ ...limits, custom_plan_min_down_payment_rate: value })}
                      />
                    </Field>
                    <Field label="Maximum duration">
                      <span className="input-shell input-shell-rate">
                        <input
                          className="input"
                          type="number"
                          min={1}
                          max={600}
                          value={limits.custom_plan_max_duration_months}
                          onChange={(event) =>
                            setLimits({ ...limits, custom_plan_max_duration_months: event.target.value })
                          }
                        />
                        <span className="input-affix" aria-hidden="true">
                          months
                        </span>
                      </span>
                    </Field>
                    <Field label="Maximum post-handover share">
                      <RateInput
                        value={limits.custom_plan_max_post_handover_rate}
                        onChange={(value) => setLimits({ ...limits, custom_plan_max_post_handover_rate: value })}
                      />
                    </Field>
                    <Field label="Maximum NPV cost">
                      <RateInput
                        value={limits.custom_plan_max_npv_cost_rate}
                        onChange={(value) => setLimits({ ...limits, custom_plan_max_npv_cost_rate: value })}
                      />
                    </Field>
                  </FieldRow>
                </FormSection>
                <FormSection title="Construction and forecasting" description="Consumed once those modules exist. Stored now so a project inherits them.">
                  <FieldRow columns={2}>
                    <Field label="Variation review amount">
                      <MoneyInput
                        code={packCode}
                        value={limits.construction_variation_review_amount}
                        onChange={(value) => setLimits({ ...limits, construction_variation_review_amount: value })}
                      />
                    </Field>
                    <Field label="Forecast reset variance">
                      <RateInput
                        value={limits.forecast_reset_variance_rate}
                        onChange={(value) => setLimits({ ...limits, forecast_reset_variance_rate: value })}
                      />
                    </Field>
                  </FieldRow>
                </FormSection>
                <FormSection title="Controls">
                  <div className="checkbox-grid">
                    {(
                      [
                        ["pricing_requires_finance_approval", "Pricing requires finance approval"],
                        ["pricing_requires_commercial_approval", "Pricing requires commercial approval"],
                        ["receipt_reversal_requires_dual_control", "Receipt reversal requires dual control"],
                        ["refund_requires_dual_control", "Refund requires dual control"],
                      ] as const
                    ).map(([key, text]) => (
                      <label className="checkbox" key={key}>
                        <input
                          type="checkbox"
                          checked={limits[key]}
                          onChange={(event) => setLimits({ ...limits, [key]: event.target.checked })}
                        />
                        <span>{text}</span>
                      </label>
                    ))}
                  </div>
                </FormSection>
                <FormActions>
                  <Button variant="primary" type="submit" disabled={busy}>
                    {busy ? "Saving…" : thresholds ? "Save thresholds" : "Set thresholds"}
                  </Button>
                </FormActions>
              </form>
            </Card>
          </div>
        </div>
      ) : null}
    </div>
  );
}
