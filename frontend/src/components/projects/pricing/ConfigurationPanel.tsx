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
import { Badge, EmptyState, Field, Notice, Panel } from "@/components/ui";

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

const STATUS_TONES: Record<string, "neutral" | "success" | "muted"> = {
  draft: "neutral",
  submitted: "neutral",
  approved: "neutral",
  active: "success",
  superseded: "muted",
};

const today = () => new Date().toISOString().slice(0, 10);

export function ConfigurationPanel({
  projectId,
  configurations,
  areaTypes,
  phases,
  defaultCurrencyId,
  canWrite,
  canApprove,
  onChanged,
}: {
  projectId: string;
  configurations: PricingConfiguration[];
  areaTypes: AreaType[];
  phases: Phase[];
  defaultCurrencyId: string;
  canWrite: boolean;
  canApprove: boolean;
  onChanged: () => Promise<void>;
}) {
  const [selected, setSelected] = useState<string>(configurations[0]?.id ?? "");
  const [areaRules, setAreaRules] = useState<PricingAreaRule[]>([]);
  const [premiums, setPremiums] = useState<PricingPremiumRule[]>([]);
  const [escalations, setEscalations] = useState<PricingEscalationRule[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const configuration = configurations.find((item) => item.id === selected) ?? null;
  const isDraft = configuration?.status === "draft";
  const canEditDraft = isDraft && canWrite;

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

  return (
    <Panel
      title="Pricing configuration"
      description="The policy that turns areas and features into money."
      actions={
        <select
          className="input"
          aria-label="Configuration version"
          value={selected}
          onChange={(event) => setSelected(event.target.value)}
        >
          <option value="">Select a version…</option>
          {configurations.map((item) => (
            <option key={item.id} value={item.id}>
              v{item.version_number} — {item.name} ({item.status})
            </option>
          ))}
        </select>
      }
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      {canWrite ? (
        <NewConfigurationForm
          projectId={projectId}
          currencyId={defaultCurrencyId}
          onCreated={onChanged}
        />
      ) : null}

      {configuration === null ? (
        <EmptyState
          title="No version selected"
          hint="Pick a version above, or create one to start pricing."
        />
      ) : (
        <>
          <div className="chip-list">
            <Badge tone={STATUS_TONES[configuration.status] ?? "neutral"}>
              {configuration.status}
            </Badge>
            <span className="chip mono">{configuration.base_internal_rate} internal rate</span>
            {configuration.maximum_premium_fraction ? (
              <span className="chip mono">
                cap {configuration.maximum_premium_fraction}
              </span>
            ) : (
              <span className="chip">no premium cap</span>
            )}
            <span className="chip">{configuration.premium_stacking_default} stacking</span>
            <span className="chip">from {configuration.valid_from}</span>
          </div>
          {configuration.change_reason ? (
            <Notice tone="info">{configuration.change_reason}</Notice>
          ) : null}

          <div className="chip-list">
            {canEditDraft ? (
              <button
                className="button button-small"
                type="button"
                disabled={busy}
                onClick={() =>
                  act(
                    () => pricing.submitConfiguration(projectId, configuration.id),
                    "Submitted for approval.",
                  )
                }
              >
                Submit for approval
              </button>
            ) : null}
            {canApprove && configuration.status === "submitted" ? (
              <>
                <button
                  className="button button-small"
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    act(
                      () =>
                        pricing.approveConfiguration(
                          projectId,
                          configuration.id,
                          "Reviewed against feasibility",
                        ),
                      "Approved. Activate it to price from it.",
                    )
                  }
                >
                  Approve
                </button>
                <button
                  className="button button-small"
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    act(
                      () =>
                        pricing.returnConfiguration(
                          projectId,
                          configuration.id,
                          "Returned for revision",
                        ),
                      "Returned to draft.",
                    )
                  }
                >
                  Return
                </button>
              </>
            ) : null}
            {canApprove && configuration.status === "approved" ? (
              <button
                className="button button-small"
                type="button"
                disabled={busy}
                onClick={() =>
                  act(
                    () => pricing.activateConfiguration(projectId, configuration.id),
                    "Live. New prices are calculated from this policy.",
                  )
                }
              >
                Activate
              </button>
            ) : null}
          </div>

          <h3 className="section-heading">Area pricing</h3>
          {canEditDraft ? (
            <AreaRuleForm
              projectId={projectId}
              configurationId={configuration.id}
              areaTypes={areaTypes}
              onCreated={loadRules}
            />
          ) : null}
          {areaRules.length === 0 ? (
            <EmptyState
              title="No area is priced"
              hint="A policy with no internal area rule prices every unit at nothing."
            />
          ) : (
            <div className="table-scroll">
              <table className="table">
                <caption className="visually-hidden">Area pricing rules</caption>
                <thead>
                  <tr>
                    <th scope="col">Area type</th>
                    <th scope="col">Method</th>
                    <th scope="col">Rate</th>
                    <th scope="col">Factor</th>
                    <th scope="col">Active</th>
                  </tr>
                </thead>
                <tbody>
                  {areaRules.map((rule) => (
                    <tr key={rule.id}>
                      <th scope="row">
                        {areaTypes.find((type) => type.id === rule.area_type_id)?.code ?? "—"}
                      </th>
                      <td>{rule.pricing_method}</td>
                      <td className="mono nowrap">{rule.rate_per_area ?? "—"}</td>
                      <td className="mono nowrap">{rule.internal_rate_factor ?? "—"}</td>
                      <td>{rule.is_active ? "Yes" : "No"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h3 className="section-heading">Premiums</h3>
          {canEditDraft ? (
            <PremiumRuleForm
              projectId={projectId}
              configurationId={configuration.id}
              onCreated={loadRules}
            />
          ) : null}
          {premiums.length === 0 ? (
            <EmptyState title="No premiums" hint="Every unit is priced on its areas alone." />
          ) : (
            <div className="table-scroll">
              <table className="table">
                <caption className="visually-hidden">Premium rules</caption>
                <thead>
                  <tr>
                    <th scope="col">Code</th>
                    <th scope="col">Reads</th>
                    <th scope="col">Matches</th>
                    <th scope="col">Method</th>
                    <th scope="col">Value</th>
                    <th scope="col">Stacking</th>
                    <th scope="col">Active</th>
                  </tr>
                </thead>
                <tbody>
                  {premiums.map((rule) => (
                    <tr key={rule.id}>
                      <th scope="row">{rule.code}</th>
                      <td>{rule.source_kind}</td>
                      <td>{rule.match_code ?? "—"}</td>
                      <td>{rule.method}</td>
                      <td className="mono nowrap">
                        {rule.percentage_fraction ?? rule.amount ?? "—"}
                      </td>
                      <td>{rule.stacking_method ?? "default"}</td>
                      <td>{rule.is_active ? "Yes" : "No"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h3 className="section-heading">Escalation</h3>
          {canEditDraft ? (
            <EscalationRuleForm
              projectId={projectId}
              configurationId={configuration.id}
              phases={phases}
              onCreated={loadRules}
            />
          ) : null}
          {escalations.length === 0 ? (
            <EmptyState
              title="No escalation rules"
              hint="Prices move only when somebody generates and activates new versions."
            />
          ) : (
            <div className="table-scroll">
              <table className="table">
                <caption className="visually-hidden">Escalation rules</caption>
                <thead>
                  <tr>
                    <th scope="col">Code</th>
                    <th scope="col">Trigger</th>
                    <th scope="col">Scope</th>
                    <th scope="col">Adjustment</th>
                    <th scope="col">Cumulative</th>
                    <th scope="col">Activate</th>
                  </tr>
                </thead>
                <tbody>
                  {escalations.map((rule) => (
                    <tr key={rule.id}>
                      <th scope="row">{rule.code}</th>
                      <td>{rule.trigger_type}</td>
                      <td>{rule.scope_type}</td>
                      <td className="mono nowrap">
                        {rule.adjustment_percentage_fraction ?? rule.adjustment_amount ?? "—"}
                      </td>
                      <td>{rule.cumulative ? "Yes" : "No"}</td>
                      <td>
                        {canApprove && configuration.status === "active" ? (
                          <button
                            className="button button-small"
                            type="button"
                            disabled={busy}
                            onClick={() =>
                              act(
                                () =>
                                  pricing.activateEscalation(projectId, rule.id, {
                                    effective_date: today(),
                                    evidence_reference: `${rule.label} evidence`,
                                    reason: `Activating ${rule.code}`,
                                  }),
                                "Escalation active. Generate new prices to apply it.",
                              )
                            }
                          >
                            Activate
                          </button>
                        ) : (
                          <span className="subtle">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </Panel>
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
  onCreated,
}: {
  projectId: string;
  currencyId: string;
  onCreated: () => Promise<void>;
}) {
  const [form, setForm] = useState({ name: "", base_internal_rate: "", valid_from: today() });
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
      setForm({ name: "", base_internal_rate: "", valid_from: today() });
      await onCreated();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not create the version.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="form-inline" onSubmit={submit}>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <Field label="New version name">
        <input
          className="input"
          required
          value={form.name}
          onChange={(event) => setForm({ ...form, name: event.target.value })}
        />
      </Field>
      <Field label="Internal rate">
        <input
          className="input input-short"
          inputMode="decimal"
          required
          value={form.base_internal_rate}
          onChange={(event) => setForm({ ...form, base_internal_rate: event.target.value })}
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
      <button className="button" type="submit" disabled={busy}>
        {busy ? "Creating…" : "New version"}
      </button>
    </form>
  );
}

function AreaRuleForm({
  projectId,
  configurationId,
  areaTypes,
  onCreated,
}: {
  projectId: string;
  configurationId: string;
  areaTypes: AreaType[];
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
        ...(form.pricing_method === "fixed_rate_per_area"
          ? { rate_per_area: form.rate_per_area }
          : {}),
        ...(form.pricing_method === "factor_of_internal_rate"
          ? { internal_rate_factor: form.internal_rate_factor }
          : {}),
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
          <option value="internal_base">At the internal base rate</option>
          <option value="fixed_rate_per_area">At its own rate</option>
          <option value="factor_of_internal_rate">A factor of the internal rate</option>
          <option value="excluded">Measured but not sold</option>
        </select>
      </Field>
      {form.pricing_method === "fixed_rate_per_area" ? (
        <Field label="Rate per area">
          <input
            className="input input-short"
            inputMode="decimal"
            required
            value={form.rate_per_area}
            onChange={(event) => setForm({ ...form, rate_per_area: event.target.value })}
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
      <button className="button" type="submit" disabled={busy}>
        {busy ? "Adding…" : "Add area rule"}
      </button>
    </form>
  );
}

function PremiumRuleForm({
  projectId,
  configurationId,
  onCreated,
}: {
  projectId: string;
  configurationId: string;
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
          ? { percentage_fraction: form.value }
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
              {kind.replace(/_/g, " ")}
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
        <select
          className="input"
          value={form.method}
          onChange={(event) => setForm({ ...form, method: event.target.value })}
        >
          <option value="percentage">Percentage of the base</option>
          <option value="fixed">Fixed amount</option>
          <option value="per_area">Per unit of area</option>
          <option value="fixed_per_asset">Per parking or storage asset</option>
        </select>
      </Field>
      <Field label="Value" hint={form.method === "percentage" ? "0.050000 is 5%." : undefined}>
        <input
          className="input input-short"
          inputMode="decimal"
          required
          value={form.value}
          onChange={(event) => setForm({ ...form, value: event.target.value })}
        />
      </Field>
      <button className="button" type="submit" disabled={busy}>
        {busy ? "Adding…" : "Add premium"}
      </button>
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
    threshold_date: today(),
    adjustment_percentage_fraction: "",
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
        adjustment_percentage_fraction: form.adjustment_percentage_fraction,
        cumulative: form.cumulative,
      });
      setForm({ ...form, code: "", label: "", adjustment_percentage_fraction: "" });
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
        <input
          className="input"
          required
          value={form.label}
          onChange={(event) => setForm({ ...form, label: event.target.value })}
        />
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
        <select
          className="input"
          value={form.scope_type}
          onChange={(event) => setForm({ ...form, scope_type: event.target.value })}
        >
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
      <Field label="Uplift" hint="0.030000 is 3%.">
        <input
          className="input input-short"
          inputMode="decimal"
          required
          value={form.adjustment_percentage_fraction}
          onChange={(event) =>
            setForm({ ...form, adjustment_percentage_fraction: event.target.value })
          }
        />
      </Field>
      <button className="button" type="submit" disabled={busy}>
        {busy ? "Adding…" : "Add escalation"}
      </button>
    </form>
  );
}
