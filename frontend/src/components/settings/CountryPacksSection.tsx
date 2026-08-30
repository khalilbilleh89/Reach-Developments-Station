"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, settings } from "@/lib/api";
import type { ApprovalThresholds, CountryPack, Currency, TaxRule } from "@/lib/api";
import {
  Badge,
  Button,
  EmptyState,
  Field,
  Loading,
  Notice,
  Panel,
  TableScroll,
  Tabs,
} from "@/components/ui";
import { percent } from "@/lib/format";

const AREA_UNITS = ["sqm", "sqft"];
const APPLIES_TO = ["sale", "rental", "service_charge", "construction", "other"];
const BASIS = ["net_amount", "gross_amount"];

/**
 * One cohesive country workspace: the pack, its currencies, its tax rules and
 * its control limits — rather than four separate screens for four small things.
 */
export function CountryPacksSection() {
  const [packs, setPacks] = useState<CountryPack[] | null>(null);
  const [currencies, setCurrencies] = useState<Currency[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [taxRules, setTaxRules] = useState<TaxRule[]>([]);
  const [thresholds, setThresholds] = useState<ApprovalThresholds | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [packList, currencyList] = await Promise.all([
        settings.countryPacks(),
        settings.currencies(),
      ]);
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
      setThresholds(await settings.approvalThresholds(packId));
    } catch (caught) {
      // Thresholds are optional until someone configures them.
      if (caught instanceof ApiError && caught.status === 404) setThresholds(null);
      else throw caught;
    }
  }, []);

  useEffect(() => {
    // Wrapped rather than called directly: the effect body must not invoke a
    // state-setting function synchronously (react-hooks/set-state-in-effect).
    void (async () => {
      await load();
    })();
  }, [load]);

  useEffect(() => {
    if (!selected) return;
    void (async () => {
      await loadDetail(selected);
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

  if (packs === null) return <Loading label="Loading country configuration…" />;

  const pack = packs.find((candidate) => candidate.id === selected) ?? null;

  return (
    <>
      <Panel
        title="Currencies"
        description="The currencies this business actually transacts in. No exchange rates are stored."
      >
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}

        <form
          className="form-inline"
          onSubmit={(event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const data = new FormData(form);
            void act(async () => {
              await settings.createCurrency({
                code: String(data.get("code") ?? ""),
                name: String(data.get("name") ?? ""),
                symbol: String(data.get("symbol") ?? "") || null,
                minor_units: Number(data.get("minor_units") ?? 2),
              });
              form.reset();
            }, "Currency added.");
          }}
        >
          <Field label="Code">
            <input className="input input-short" name="code" required maxLength={3} minLength={3} />
          </Field>
          <Field label="Name">
            <input className="input" name="name" required />
          </Field>
          <Field label="Symbol">
            <input className="input input-short" name="symbol" maxLength={8} />
          </Field>
          <Field label="Minor units">
            <input
              className="input input-short"
              name="minor_units"
              type="number"
              min={0}
              max={6}
              defaultValue={2}
            />
          </Field>
          <Button variant="primary" type="submit" disabled={busy}>
            Add
          </Button>
        </form>

        {currencies.length === 0 ? (
          <EmptyState title="No currencies yet" hint="Add one before creating a country pack." />
        ) : (
          <ul className="chip-list">
            {currencies.map((currency) => (
              <li key={currency.id} className="chip">
                <span className="mono">{currency.code}</span> {currency.name}
                {currency.is_active ? null : <Badge tone="muted">Inactive</Badge>}
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel
        title="Country packs"
        description="Per-country configuration: locale, timezone, default currency and area unit."
      >
        <form
          className="form-inline"
          onSubmit={(event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const data = new FormData(form);
            void act(async () => {
              await settings.createCountryPack({
                country_code: String(data.get("country_code") ?? ""),
                name: String(data.get("name") ?? ""),
                locale: String(data.get("locale") ?? ""),
                timezone: String(data.get("timezone") ?? ""),
                default_currency_id: String(data.get("default_currency_id") ?? ""),
                area_unit: String(data.get("area_unit") ?? "sqm"),
                fiscal_year_start_month: Number(data.get("fiscal_year_start_month") ?? 1),
              });
              form.reset();
            }, "Country pack created.");
          }}
        >
          <Field label="Country code">
            <input
              className="input input-short"
              name="country_code"
              required
              maxLength={2}
              minLength={2}
            />
          </Field>
          <Field label="Name">
            <input className="input" name="name" required />
          </Field>
          <Field label="Locale">
            <input className="input input-short" name="locale" required defaultValue="en" />
          </Field>
          <Field label="Timezone">
            <input className="input" name="timezone" required defaultValue="UTC" />
          </Field>
          <Field label="Default currency">
            <select className="input" name="default_currency_id" required>
              {currencies
                .filter((currency) => currency.is_active)
                .map((currency) => (
                  <option key={currency.id} value={currency.id}>
                    {currency.code}
                  </option>
                ))}
            </select>
          </Field>
          <Field label="Area unit">
            <select className="input input-short" name="area_unit" defaultValue="sqm">
              {AREA_UNITS.map((unit) => (
                <option key={unit} value={unit}>
                  {unit}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Fiscal start month">
            <input
              className="input input-short"
              name="fiscal_year_start_month"
              type="number"
              min={1}
              max={12}
              defaultValue={1}
            />
          </Field>
          <Button variant="primary" type="submit" disabled={busy || currencies.length === 0}>
            Add
          </Button>
        </form>

        {packs.length === 0 ? (
          <EmptyState
            title="No country packs yet"
            hint="A country pack holds the configuration every project in that country inherits."
          />
        ) : (
          <Tabs
            label="Country packs"
            tabs={packs.map((candidate) => ({
              key: candidate.id,
              label: `${candidate.country_code} · ${candidate.name}`,
            }))}
            active={selected ?? ""}
            onSelect={setSelected}
          />
        )}
      </Panel>

      {pack ? (
        <>
          <Panel
            title={`Tax rules — ${pack.name}`}
            description="Effective-dated configuration. Nothing is calculated here, and history is never overwritten."
          >
            <form
              className="form-inline"
              onSubmit={(event) => {
                event.preventDefault();
                const form = event.currentTarget;
                const data = new FormData(form);
                void act(async () => {
                  await settings.createTaxRule(pack.id, {
                    tax_code: String(data.get("tax_code") ?? ""),
                    label: String(data.get("label") ?? ""),
                    applies_to: String(data.get("applies_to") ?? "sale"),
                    calculation_basis: String(data.get("calculation_basis") ?? "net_amount"),
                    rate_fraction: String(data.get("rate_fraction") ?? "0"),
                    valid_from: String(data.get("valid_from") ?? ""),
                    valid_to: String(data.get("valid_to") ?? "") || null,
                  });
                  form.reset();
                }, "Tax rule added.");
              }}
            >
              <Field label="Code">
                <input className="input input-short" name="tax_code" required />
              </Field>
              <Field label="Label">
                <input className="input" name="label" required />
              </Field>
              <Field label="Applies to">
                <select className="input" name="applies_to" defaultValue="sale">
                  {APPLIES_TO.map((value) => (
                    <option key={value} value={value}>
                      {value.replace("_", " ")}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Basis">
                <select className="input" name="calculation_basis" defaultValue="net_amount">
                  {BASIS.map((value) => (
                    <option key={value} value={value}>
                      {value.replace("_", " ")}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Rate" hint="A fraction of one: 0.16 is 16%.">
                <input
                  className="input input-short"
                  name="rate_fraction"
                  required
                  inputMode="decimal"
                  placeholder="0.160000"
                />
              </Field>
              <Field label="Valid from">
                <input className="input" name="valid_from" type="date" required />
              </Field>
              <Field label="Valid to">
                <input className="input" name="valid_to" type="date" />
              </Field>
              <Button variant="primary" type="submit" disabled={busy}>
                Add
              </Button>
            </form>

            {taxRules.length === 0 ? (
              <EmptyState title="No tax rules configured" />
            ) : (
              <TableScroll label="Tax rules">
                  <thead>
                    <tr>
                      <th scope="col">Code</th>
                      <th scope="col">Applies to</th>
                      <th scope="col">Rate</th>
                      <th scope="col">Valid</th>
                      <th scope="col">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {taxRules.map((rule) => (
                      <tr key={rule.id}>
                        <td className="mono">{rule.tax_code}</td>
                        <td>{rule.applies_to.replace("_", " ")}</td>
                        <td className="mono">
                          {percent(rule.rate_fraction)}
                          <span className="subtle"> ({rule.rate_fraction})</span>
                        </td>
                        <td className="mono">
                          {rule.valid_from} → {rule.valid_to ?? "open"}
                        </td>
                        <td>
                          {rule.is_active ? (
                            <Badge tone="success">Active</Badge>
                          ) : (
                            <Badge tone="muted">Retired</Badge>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
</TableScroll>
            )}
          </Panel>

          <Panel
            title={`Approval thresholds — ${pack.name}`}
            description="Baseline control limits future modules consume. Storing policy here does not execute any workflow."
          >
            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                const data = new FormData(event.currentTarget);
                const text = (key: string) => String(data.get(key) ?? "").trim() || null;
                void act(
                  () =>
                    settings.writeApprovalThresholds(pack.id, {
                      discount_review_rate_fraction: text("discount_review_rate_fraction"),
                      discount_review_amount: text("discount_review_amount"),
                      minimum_margin_rate_fraction: text("minimum_margin_rate_fraction"),
                      custom_plan_max_duration_months: data.get("custom_plan_max_duration_months")
                        ? Number(data.get("custom_plan_max_duration_months"))
                        : null,
                      pricing_requires_finance_approval:
                        data.get("pricing_requires_finance_approval") === "on",
                      pricing_requires_commercial_approval:
                        data.get("pricing_requires_commercial_approval") === "on",
                      receipt_reversal_requires_dual_control:
                        data.get("receipt_reversal_requires_dual_control") === "on",
                      refund_requires_dual_control: data.get("refund_requires_dual_control") === "on",
                    }),
                  "Approval thresholds saved.",
                );
              }}
            >
              <Field label="Discount review rate" hint="Fraction of one: 0.05 is 5%.">
                <input
                  className="input"
                  name="discount_review_rate_fraction"
                  inputMode="decimal"
                  defaultValue={thresholds?.discount_review_rate_fraction ?? ""}
                />
              </Field>
              <Field label="Discount review amount" hint={`In the pack's default currency.`}>
                <input
                  className="input"
                  name="discount_review_amount"
                  inputMode="decimal"
                  defaultValue={thresholds?.discount_review_amount ?? ""}
                />
              </Field>
              <Field label="Minimum margin rate" hint="Fraction of one.">
                <input
                  className="input"
                  name="minimum_margin_rate_fraction"
                  inputMode="decimal"
                  defaultValue={thresholds?.minimum_margin_rate_fraction ?? ""}
                />
              </Field>
              <Field label="Max custom plan duration" hint="Months.">
                <input
                  className="input"
                  name="custom_plan_max_duration_months"
                  type="number"
                  min={1}
                  max={600}
                  defaultValue={thresholds?.custom_plan_max_duration_months ?? ""}
                />
              </Field>
              <fieldset className="fieldset">
                <legend className="field-label">Controls</legend>
                <div className="checkbox-grid">
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      name="pricing_requires_finance_approval"
                      defaultChecked={thresholds?.pricing_requires_finance_approval ?? false}
                    />
                    <span>Pricing requires finance approval</span>
                  </label>
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      name="pricing_requires_commercial_approval"
                      defaultChecked={thresholds?.pricing_requires_commercial_approval ?? false}
                    />
                    <span>Pricing requires commercial approval</span>
                  </label>
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      name="receipt_reversal_requires_dual_control"
                      defaultChecked={thresholds?.receipt_reversal_requires_dual_control ?? true}
                    />
                    <span>Receipt reversal requires dual control</span>
                  </label>
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      name="refund_requires_dual_control"
                      defaultChecked={thresholds?.refund_requires_dual_control ?? true}
                    />
                    <span>Refund requires dual control</span>
                  </label>
                </div>
              </fieldset>
              <div className="form-actions">
                <Button variant="primary" type="submit" disabled={busy}>
                  Save thresholds
                </Button>
              </div>
            </form>
          </Panel>
        </>
      ) : null}
    </>
  );
}
