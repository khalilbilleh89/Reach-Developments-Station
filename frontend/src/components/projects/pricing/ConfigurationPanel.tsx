"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, pricing } from "@/lib/api";
import type {
  AreaType,
  Phase,
  PricingAreaRule,
  PricingConfiguration,
  PricingEscalationRule,
  PricingPremiumRule,
} from "@/lib/api";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, fractionFromPercent, money, percent, todayISO } from "@/lib/format";
import {
  Badge,
  Button,
  ButtonRow,
  Card,
  EmptyState,
  Field,
  FieldRow,
  FormActions,
  InlineMeta,
  InlineMetaItem,
  MoneyInput,
  Notice,
  RateInput,
  StatusDot,
  Steps,
  TableScroll,
} from "@/components/ui";
import type { Tone } from "@/components/ui";

/**
 * The pricing policy a project prices from, and the governed path it takes.
 *
 * Prepare, submit, approve, activate — four separate acts with different rights
 * attached, so four buttons rather than a status dropdown. The approve and
 * activate controls are shown only to the role that holds them, which mirrors
 * the server's rule rather than replacing it: the API refuses either way.
 */
const SOURCE_KINDS = [
  "phase",
  "building",
  "unit_type",
  "view_class",
  "floor_band",
  "orientation",
  "corner",
  "pool_access",
  "accessibility",
  "garden_class",
  "parking",
  "storage",
  "area_type",
];

const NEEDS_CODE = new Set([
  "phase",
  "building",
  "unit_type",
  "view_class",
  "floor_band",
  "orientation",
  "accessibility",
  "garden_class",
  "area_type",
]);

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  submitted: "Awaiting approval",
  approved: "Approved",
  active: "Active",
  superseded: "Superseded",
};

const STATUS_TONES: Record<string, Tone> = {
  draft: "muted",
  submitted: "warning",
  approved: "info",
  active: "success",
  superseded: "neutral",
};

const SEQUENCE = ["draft", "submitted", "approved", "active"];

const METHOD_LABELS: Record<string, string> = {
  internal_base: "At the internal base rate",
  fixed_rate_per_area: "At its own rate",
  factor_of_internal_rate: "A factor of the internal rate",
  excluded: "Measured but not sold",
};

const PREMIUM_METHOD_LABELS: Record<string, string> = {
  percentage: "Percentage of the base",
  fixed: "Fixed amount",
  per_area: "Per unit of area",
  fixed_per_asset: "Per parking or storage asset",
};

const humanise = (value: string) => value.replace(/_/g, " ");

export function ConfigurationPanel({
  projectId,
  configurations,
  areaTypes,
  phases,
  defaultCurrencyId,
  canWrite,
  canApprove,
  onChanged,
  onClose,
}: {
  projectId: string;
  configurations: PricingConfiguration[];
  areaTypes: AreaType[];
  phases: Phase[];
  defaultCurrencyId: string;
  canWrite: boolean;
  canApprove: boolean;
  onChanged: () => Promise<void>;
  onClose?: () => void;
}) {
  const currencyCodeOf = useCurrencyCode();
  const [selected, setSelected] = useState<string>(configurations[0]?.id ?? "");
  const [areaRules, setAreaRules] = useState<PricingAreaRule[]>([]);
  const [premiums, setPremiums] = useState<PricingPremiumRule[]>([]);
  const [escalations, setEscalations] = useState<PricingEscalationRule[]>([]);
  const [creating, setCreating] = useState(configurations.length === 0);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const configuration = configurations.find((item) => item.id === selected) ?? null;
  const isDraft = configuration?.status === "draft";
  const canEditDraft = isDraft && canWrite;
  const code = currencyCodeOf(configuration?.pricing_currency_id ?? defaultCurrencyId);

  const loadRules = useCallback(async () => {
    if (!selected) {
      setAreaRules([]);
      setPremiums([]);
      setEscalations([]);
      return;
    }
    try {
      const [areas, premiumList, escalationList] = await Promise.all([
        pricing.areaRules(projectId, selected),
        pricing.premiumRules(projectId, selected),
        pricing.escalationRules(projectId),
      ]);
      setAreaRules(areas);
      setPremiums(premiumList);
      setEscalations(escalationList.filter((rule) => rule.pricing_configuration_id === selected));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not load the rules.");
    }
  }, [projectId, selected]);

  useEffect(() => {
    void (async () => {
      await loadRules();
    })();
  }, [loadRules]);

  const act = async (run: () => Promise<unknown>, message: string) => {
    setBusy(true);
    setError(null);
    try {
      await run();
      setNotice(message);
      await onChanged();
      await loadRules();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "That did not work.");
    } finally {
      setBusy(false);
    }
  };

  const areaTypeCode = (id: string) => areaTypes.find((type) => type.id === id)?.code ?? "—";

  return (
    <Card
      title="Pricing configuration"
      description="The policy that turns areas and features into money. One version is active at a time; a change is a new version."
      actions={
        <>
          {configurations.length > 0 ? (
            <select
              className="input input-medium"
              aria-label="Configuration version"
              value={selected}
              onChange={(event) => setSelected(event.target.value)}
            >
              {configurations.map((item) => (
                <option key={item.id} value={item.id}>
                  v{item.version_number} — {item.name} · {STATUS_LABELS[item.status] ?? item.status}
                </option>
              ))}
            </select>
          ) : null}
          {canWrite ? (
            <Button onClick={() => setCreating((open) => !open)} aria-expanded={creating}>
              New version
            </Button>
          ) : null}
          {onClose ? (
            <Button variant="quiet" onClick={onClose}>
              Close
            </Button>
          ) : null}
        </>
      }
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      {creating && canWrite ? (
        <NewConfigurationForm
          projectId={projectId}
          currencyId={defaultCurrencyId}
          currencyCode={currencyCodeOf(defaultCurrencyId)}
          onCreated={async () => {
            setCreating(false);
            await onChanged();
          }}
          onCancel={configurations.length > 0 ? () => setCreating(false) : undefined}
        />
      ) : null}

      {configuration === null ? (
        configurations.length === 0 ? null : (
          <EmptyState compact title="No version selected" hint="Pick a version above to read or edit it." />
        )
      ) : (
        <>
          <div className="stack stack-tight">
            <Steps
              label="Configuration lifecycle"
              steps={SEQUENCE.map((key) => ({
                key,
                label: STATUS_LABELS[key],
                state:
                  key === configuration.status
                    ? "current"
                    : configuration.status === "superseded" || SEQUENCE.indexOf(key) < SEQUENCE.indexOf(configuration.status)
                      ? "done"
                      : "pending",
              }))}
            />
            <InlineMeta>
              <InlineMetaItem label="Version">v{configuration.version_number}</InlineMetaItem>
              <InlineMetaItem label="Status">
                <Badge tone={STATUS_TONES[configuration.status] ?? "neutral"}>
                  {STATUS_LABELS[configuration.status] ?? configuration.status}
                </Badge>
              </InlineMetaItem>
              <InlineMetaItem label="Internal rate">{money(configuration.base_internal_rate, code)}</InlineMetaItem>
              <InlineMetaItem label="Premium cap">
                {configuration.maximum_premium_fraction ? percent(configuration.maximum_premium_fraction) : "None"}
              </InlineMetaItem>
              <InlineMetaItem label="Stacking">{humanise(configuration.premium_stacking_default)}</InlineMetaItem>
              <InlineMetaItem label="Valid from">{businessDate(configuration.valid_from)}</InlineMetaItem>
              {configuration.price_lock_days ? (
                <InlineMetaItem label="Price lock">{configuration.price_lock_days} days</InlineMetaItem>
              ) : null}
            </InlineMeta>
            {configuration.change_reason ? <p className="footnote">{configuration.change_reason}</p> : null}

            {canEditDraft || (canApprove && ["submitted", "approved"].includes(configuration.status)) ? (
              <ButtonRow>
                {canEditDraft ? (
                  <Button
                    variant="primary"
                    disabled={busy}
                    onClick={() =>
                      act(() => pricing.submitConfiguration(projectId, configuration.id), "Submitted for approval.")
                    }
                  >
                    Submit for approval
                  </Button>
                ) : null}
                {canApprove && configuration.status === "submitted" ? (
                  <>
                    <Button
                      variant="primary"
                      disabled={busy}
                      onClick={() =>
                        act(
                          () =>
                            pricing.approveConfiguration(projectId, configuration.id, "Reviewed against feasibility"),
                          "Approved. Activate it to price from it.",
                        )
                      }
                    >
                      Approve
                    </Button>
                    <Button
                      disabled={busy}
                      onClick={() =>
                        act(
                          () => pricing.returnConfiguration(projectId, configuration.id, "Returned for revision"),
                          "Returned to draft.",
                        )
                      }
                    >
                      Return to draft
                    </Button>
                  </>
                ) : null}
                {canApprove && configuration.status === "approved" ? (
                  <Button
                    variant="primary"
                    disabled={busy}
                    onClick={() =>
                      act(
                        () => pricing.activateConfiguration(projectId, configuration.id),
                        "Live. New prices are calculated from this policy.",
                      )
                    }
                  >
                    Activate
                  </Button>
                ) : null}
              </ButtonRow>
            ) : null}
          </div>

          <section>
            <h3 className="section-heading">Area pricing</h3>
            {canEditDraft ? (
              <AreaRuleForm
                projectId={projectId}
                configurationId={configuration.id}
                areaTypes={areaTypes}
                currencyCode={code}
                onCreated={loadRules}
              />
            ) : null}
            {areaRules.length === 0 ? (
              <EmptyState compact title="No area is priced" hint="A policy with no internal area rule prices every unit at nothing." />
            ) : (
              <TableScroll label="Area pricing rules" compact>
                <thead>
                  <tr>
                    <th scope="col">Area type</th>
                    <th scope="col">Method</th>
                    <th scope="col" className="num">
                      Rate
                    </th>
                    <th scope="col" className="num">
                      Factor
                    </th>
                    <th scope="col">State</th>
                  </tr>
                </thead>
                <tbody>
                  {areaRules.map((rule) => (
                    <tr key={rule.id}>
                      <th scope="row" className="mono">
                        {areaTypeCode(rule.area_type_id)}
                      </th>
                      <td>{METHOD_LABELS[rule.pricing_method] ?? humanise(rule.pricing_method)}</td>
                      <td className="num">{rule.rate_per_area ? money(rule.rate_per_area, code) : "—"}</td>
                      <td className="num">{rule.internal_rate_factor ?? "—"}</td>
                      <td>
                        {rule.is_active ? <StatusDot tone="success">Active</StatusDot> : <StatusDot tone="muted">Retired</StatusDot>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </TableScroll>
            )}
          </section>

          <section>
            <h3 className="section-heading">Premiums</h3>
            {canEditDraft ? (
              <PremiumRuleForm projectId={projectId} configurationId={configuration.id} currencyCode={code} onCreated={loadRules} />
            ) : null}
            {premiums.length === 0 ? (
              <EmptyState compact title="No premiums" hint="Every unit is priced on its areas alone." />
            ) : (
              <TableScroll label="Premium rules" compact>
                <thead>
                  <tr>
                    <th scope="col">Premium</th>
                    <th scope="col">Reads</th>
                    <th scope="col">Method</th>
                    <th scope="col" className="num">
                      Value
                    </th>
                    <th scope="col">Stacking</th>
                    <th scope="col">State</th>
                  </tr>
                </thead>
                <tbody>
                  {premiums.map((rule) => (
                    <tr key={rule.id}>
                      <th scope="row">
                        {rule.label}
                        <span className="cell-secondary mono">{rule.code}</span>
                      </th>
                      <td>
                        {humanise(rule.source_kind)}
                        {rule.match_code ? <span className="cell-secondary mono">= {rule.match_code}</span> : null}
                      </td>
                      <td>{PREMIUM_METHOD_LABELS[rule.method] ?? humanise(rule.method)}</td>
                      <td className="num">
                        {rule.percentage_fraction ? percent(rule.percentage_fraction) : rule.amount ? money(rule.amount, code) : "—"}
                      </td>
                      <td>{rule.stacking_method ? humanise(rule.stacking_method) : "Default"}</td>
                      <td>
                        {rule.is_active ? <StatusDot tone="success">Active</StatusDot> : <StatusDot tone="muted">Retired</StatusDot>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </TableScroll>
            )}
          </section>

          <section>
            <h3 className="section-heading">Escalation</h3>
            {canEditDraft ? (
              <EscalationRuleForm projectId={projectId} configurationId={configuration.id} phases={phases} onCreated={loadRules} />
            ) : null}
            {escalations.length === 0 ? (
              <EmptyState compact title="No escalation rules" hint="Prices move only when somebody generates and activates new versions." />
            ) : (
              <TableScroll label="Escalation rules" compact>
                <thead>
                  <tr>
                    <th scope="col">Rule</th>
                    <th scope="col">Trigger</th>
                    <th scope="col">Scope</th>
                    <th scope="col" className="num">
                      Uplift
                    </th>
                    <th scope="col">Cumulative</th>
                    <th scope="col">
                      <span className="visually-hidden">Activate</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {escalations.map((rule) => (
                    <tr key={rule.id}>
                      <th scope="row">
                        {rule.label}
                        <span className="cell-secondary mono">{rule.code}</span>
                      </th>
                      <td>
                        {humanise(rule.trigger_type)}
                        {rule.threshold_date ? <span className="cell-secondary">from {businessDate(rule.threshold_date)}</span> : null}
                      </td>
                      <td>{rule.scope_type === "phase" ? phases.find((phase) => phase.id === rule.phase_id)?.code ?? "One phase" : "Whole project"}</td>
                      <td className="num">
                        {rule.adjustment_percentage_fraction
                          ? percent(rule.adjustment_percentage_fraction)
                          : rule.adjustment_amount
                            ? money(rule.adjustment_amount, code)
                            : "—"}
                      </td>
                      <td>{rule.cumulative ? "Yes" : "No"}</td>
                      <td>
                        {canApprove && configuration.status === "active" ? (
                          <Button
                            small
                            variant="quiet"
                            disabled={busy}
                            onClick={() =>
                              act(
                                () =>
                                  pricing.activateEscalation(projectId, rule.id, {
                                    effective_date: todayISO(),
                                    evidence_reference: `${rule.label} evidence`,
                                    reason: `Activating ${rule.code}`,
                                  }),
                                "Escalation active. Generate new prices to apply it.",
                              )
                            }
                          >
                            Activate
                          </Button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </TableScroll>
            )}
          </section>
        </>
      )}
    </Card>
  );
}

/**
 * A new draft version.
 *
 * The currency defaults to the project's reporting currency and is not offered
 * as a choice here: every amount in one configuration and every price generated
 * from it is denominated in it, and there is no conversion anywhere in this MVP.
 */
function NewConfigurationForm({
  projectId,
  currencyId,
  currencyCode,
  onCreated,
  onCancel,
}: {
  projectId: string;
  currencyId: string;
  currencyCode: string | null;
  onCreated: () => Promise<void>;
  onCancel?: () => void;
}) {
  const [form, setForm] = useState({ name: "", base_internal_rate: "", valid_from: todayISO() });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await pricing.createConfiguration(projectId, {
        name: form.name,
        pricing_currency_id: currencyId,
        base_internal_rate: form.base_internal_rate,
        valid_from: form.valid_from,
      });
      setForm({ name: "", base_internal_rate: "", valid_from: todayISO() });
      await onCreated();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not create the version.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="subpanel">
      <h3 className="subpanel-title">New configuration version</h3>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <FieldRow columns={3}>
        <Field label="Name">
          <input
            className="input"
            required
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </Field>
        <Field label="Internal base rate" hint="Per unit of internal area.">
          <MoneyInput
            code={currencyCode}
            required
            value={form.base_internal_rate}
            onChange={(value) => setForm({ ...form, base_internal_rate: value })}
          />
        </Field>
        <Field label="Valid from">
          <input
            className="input input-short"
            type="date"
            required
            value={form.valid_from}
            onChange={(event) => setForm({ ...form, valid_from: event.target.value })}
          />
        </Field>
      </FieldRow>
      <FormActions>
        <Button variant="primary" type="submit" disabled={busy}>
          {busy ? "Creating…" : "Create draft version"}
        </Button>
        {onCancel ? (
          <Button onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
        ) : null}
      </FormActions>
    </form>
  );
}

function AreaRuleForm({
  projectId,
  configurationId,
  areaTypes,
  currencyCode,
  onCreated,
}: {
  projectId: string;
  configurationId: string;
  areaTypes: AreaType[];
  currencyCode: string | null;
  onCreated: () => Promise<void>;
}) {
  const [form, setForm] = useState({
    area_type_id: "",
    pricing_method: "internal_base",
    rate_per_area: "",
    internal_rate_factor: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await pricing.createAreaRule(projectId, configurationId, {
        area_type_id: form.area_type_id,
        pricing_method: form.pricing_method,
        ...(form.pricing_method === "fixed_rate_per_area" ? { rate_per_area: form.rate_per_area } : {}),
        ...(form.pricing_method === "factor_of_internal_rate" ? { internal_rate_factor: form.internal_rate_factor } : {}),
      });
      setForm({ ...form, rate_per_area: "", internal_rate_factor: "" });
      await onCreated();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not add the rule.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="form-inline" onSubmit={submit}>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <Field label="Area type">
        <select
          className="input"
          required
          value={form.area_type_id}
          onChange={(event) => setForm({ ...form, area_type_id: event.target.value })}
        >
          <option value="">Select…</option>
          {areaTypes.map((type) => (
            <option key={type.id} value={type.id}>
              {type.code} — {type.label}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Method">
        <select
          className="input"
          value={form.pricing_method}
          onChange={(event) => setForm({ ...form, pricing_method: event.target.value })}
        >
          {Object.entries(METHOD_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </Field>
      {form.pricing_method === "fixed_rate_per_area" ? (
        <Field label="Rate per unit of area">
          <MoneyInput
            code={currencyCode}
            required
            value={form.rate_per_area}
            onChange={(value) => setForm({ ...form, rate_per_area: value })}
          />
        </Field>
      ) : null}
      {form.pricing_method === "factor_of_internal_rate" ? (
        <Field label="Factor" hint="0.500000 is half the internal rate.">
          <input
            className="input input-short"
            inputMode="decimal"
            required
            value={form.internal_rate_factor}
            onChange={(event) => setForm({ ...form, internal_rate_factor: event.target.value })}
          />
        </Field>
      ) : null}
      <Button variant="primary" type="submit" disabled={busy}>
        {busy ? "Adding…" : "Add area rule"}
      </Button>
    </form>
  );
}

function PremiumRuleForm({
  projectId,
  configurationId,
  currencyCode,
  onCreated,
}: {
  projectId: string;
  configurationId: string;
  currencyCode: string | null;
  onCreated: () => Promise<void>;
}) {
  const [form, setForm] = useState({
    code: "",
    label: "",
    source_kind: "view_class",
    match_code: "",
    method: "percentage",
    value: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await pricing.createPremiumRule(projectId, configurationId, {
        code: form.code,
        label: form.label,
        source_kind: form.source_kind,
        ...(NEEDS_CODE.has(form.source_kind) ? { match_code: form.match_code } : {}),
        method: form.method,
        ...(form.method === "percentage"
          ? { percentage_fraction: fractionFromPercent(form.value) }
          : { amount: form.value }),
      });
      setForm({ ...form, code: "", label: "", match_code: "", value: "" });
      await onCreated();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not add the premium.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="form-inline" onSubmit={submit}>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <Field label="Code">
        <input
          className="input input-short"
          required
          value={form.code}
          onChange={(event) => setForm({ ...form, code: event.target.value.toUpperCase() })}
        />
      </Field>
      <Field label="Label">
        <input
          className="input"
          required
          value={form.label}
          onChange={(event) => setForm({ ...form, label: event.target.value })}
        />
      </Field>
      <Field label="Reads">
        <select
          className="input"
          value={form.source_kind}
          onChange={(event) => setForm({ ...form, source_kind: event.target.value })}
        >
          {SOURCE_KINDS.map((kind) => (
            <option key={kind} value={kind}>
              {humanise(kind)}
            </option>
          ))}
        </select>
      </Field>
      {NEEDS_CODE.has(form.source_kind) ? (
        <Field label="Matches code">
          <input
            className="input input-short"
            required
            value={form.match_code}
            onChange={(event) => setForm({ ...form, match_code: event.target.value })}
          />
        </Field>
      ) : null}
      <Field label="Method">
        <select className="input" value={form.method} onChange={(event) => setForm({ ...form, method: event.target.value })}>
          {Object.entries(PREMIUM_METHOD_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </Field>
      <Field label={form.method === "percentage" ? "Premium" : "Amount"}>
        {form.method === "percentage" ? (
          <RateInput required value={form.value} onChange={(value) => setForm({ ...form, value })} />
        ) : (
          <MoneyInput code={currencyCode} required value={form.value} onChange={(value) => setForm({ ...form, value })} />
        )}
      </Field>
      <Button variant="primary" type="submit" disabled={busy}>
        {busy ? "Adding…" : "Add premium"}
      </Button>
    </form>
  );
}

function EscalationRuleForm({
  projectId,
  configurationId,
  phases,
  onCreated,
}: {
  projectId: string;
  configurationId: string;
  phases: Phase[];
  onCreated: () => Promise<void>;
}) {
  const [form, setForm] = useState({
    code: "",
    label: "",
    trigger_type: "date",
    scope_type: "project",
    phase_id: "",
    threshold_date: todayISO(),
    uplift_percent: "",
    cumulative: false,
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await pricing.createEscalationRule(projectId, configurationId, {
        code: form.code,
        label: form.label,
        trigger_type: form.trigger_type,
        scope_type: form.scope_type,
        ...(form.scope_type === "phase" ? { phase_id: form.phase_id } : {}),
        ...(form.trigger_type === "date" ? { threshold_date: form.threshold_date } : {}),
        adjustment_method: "percentage",
        adjustment_percentage_fraction: fractionFromPercent(form.uplift_percent),
        cumulative: form.cumulative,
      });
      setForm({ ...form, code: "", label: "", uplift_percent: "" });
      await onCreated();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not add the rule.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="form-inline" onSubmit={submit}>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <Field label="Code">
        <input
          className="input input-short"
          required
          value={form.code}
          onChange={(event) => setForm({ ...form, code: event.target.value.toUpperCase() })}
        />
      </Field>
      <Field label="Label">
        <input className="input" required value={form.label} onChange={(event) => setForm({ ...form, label: event.target.value })} />
      </Field>
      <Field label="Trigger">
        <select
          className="input"
          value={form.trigger_type}
          onChange={(event) => setForm({ ...form, trigger_type: event.target.value })}
        >
          <option value="date">Date</option>
          <option value="sales_percentage">Sales percentage</option>
          <option value="construction_milestone">Construction milestone</option>
          <option value="market_index">Market index</option>
        </select>
      </Field>
      {form.trigger_type === "date" ? (
        <Field label="Eligible from">
          <input
            className="input input-short"
            type="date"
            required
            value={form.threshold_date}
            onChange={(event) => setForm({ ...form, threshold_date: event.target.value })}
          />
        </Field>
      ) : null}
      <Field label="Scope">
        <select className="input" value={form.scope_type} onChange={(event) => setForm({ ...form, scope_type: event.target.value })}>
          <option value="project">Whole project</option>
          <option value="phase">One phase</option>
        </select>
      </Field>
      {form.scope_type === "phase" ? (
        <Field label="Phase">
          <select
            className="input"
            required
            value={form.phase_id}
            onChange={(event) => setForm({ ...form, phase_id: event.target.value })}
          >
            <option value="">Select…</option>
            {phases.map((phase) => (
              <option key={phase.id} value={phase.id}>
                {phase.code}
              </option>
            ))}
          </select>
        </Field>
      ) : null}
      <Field label="Uplift">
        <RateInput required value={form.uplift_percent} onChange={(value) => setForm({ ...form, uplift_percent: value })} />
      </Field>
      <label className="checkbox" style={{ alignSelf: "center" }}>
        <input
          type="checkbox"
          checked={form.cumulative}
          onChange={(event) => setForm({ ...form, cumulative: event.target.checked })}
        />
        <span>Cumulative</span>
      </label>
      <Button variant="primary" type="submit" disabled={busy}>
        {busy ? "Adding…" : "Add escalation"}
      </Button>
    </form>
  );
}
