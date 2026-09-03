"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, inventory, pricing } from "@/lib/api";
import type {
  AreaType,
  MarketBenchmark,
  Phase,
  PriceRegister,
  PricingConfiguration,
  PricingOverview,
} from "@/lib/api";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, fractionFromPercent, money, percent, todayISO } from "@/lib/format";
import { sectionDescription } from "@/components/shell/navigation";
import {
  Badge,
  Button,
  Card,
  DataToolbar,
  IdentityCell,
  EmptyState,
  Field,
  FieldRow,
  FormActions,
  Loading,
  Position,
  PositionFigure,
  PositionSupport,
  PositionSupportItem,
  MoneyInput,
  Notice,
  PageHeader,
  RateInput,
  StatusDot,
  TableScroll,
  ToolbarFilter,
} from "@/components/ui";
import type { Tone } from "@/components/ui";
import { ConfigurationPanel } from "@/components/projects/pricing/ConfigurationPanel";

const MARKET_LABELS: Record<string, string> = {
  within_tolerance: "In line",
  above_tolerance: "Above market",
  below_tolerance: "Below market",
  no_benchmark: "No benchmark",
};

/** Presentation only: the word beside it already carries the meaning. */
const MARKET_TONES: Record<string, Tone> = {
  within_tolerance: "success",
  above_tolerance: "warning",
  below_tolerance: "info",
  no_benchmark: "muted",
};

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  submitted: "Submitted",
  approved: "Approved",
  active: "Active",
  superseded: "Superseded",
};

/**
 * The pricing workspace.
 *
 * Three questions, in the order somebody actually asks them: what policy is
 * this development priced from, which units carry a live price, and which of
 * them are no longer priced against their own facts. Everything below is a
 * number the backend computed; nothing on this screen does pricing arithmetic.
 */
export function PricingTab({
  projectId,
  projectStatus,
  reportingCurrencyId,
  canPrice,
  canApprove,
  canSeeInternal,
  onOpenUnit,
}: {
  projectId: string;
  projectStatus: string;
  reportingCurrencyId: string;
  canPrice: boolean;
  canApprove: boolean;
  canSeeInternal: boolean;
  onOpenUnit: (unitId: string) => void;
}) {
  const [overview, setOverview] = useState<PricingOverview | null>(null);
  const [register, setRegister] = useState<PriceRegister | null>(null);
  const [configurations, setConfigurations] = useState<PricingConfiguration[]>([]);
  const [benchmarks, setBenchmarks] = useState<MarketBenchmark[]>([]);
  const [phases, setPhases] = useState<Phase[]>([]);
  const [areaTypes, setAreaTypes] = useState<AreaType[]>([]);
  const [filters, setFilters] = useState({ phase_id: "", market_flag: "" });
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState<"none" | "configuration" | "benchmarks">("none");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const currencyCodeOf = useCurrencyCode();

  const load = useCallback(async () => {
    try {
      const query: Record<string, string> = { limit: "200" };
      for (const [key, value] of Object.entries(filters)) {
        if (value) query[key] = value;
      }
      const [head, rows, configs, marks, phaseList, typeList] = await Promise.all([
        pricing.overview(projectId),
        pricing.register(projectId, query),
        pricing.configurations(projectId),
        pricing.benchmarks(projectId),
        inventory.phases(projectId),
        inventory.areaTypes(projectId),
      ]);
      setOverview(head);
      setRegister(rows);
      setConfigurations(configs);
      setBenchmarks(marks);
      setPhases(phaseList);
      setAreaTypes(typeList);
      setError(null);
    } catch (caught) {
      setOverview(null);
      setError(caught instanceof ApiError ? caught.message : "Could not load pricing.");
    }
  }, [projectId, filters]);

  useEffect(() => {
    void (async () => {
      if (canSeeInternal && projectStatus !== "setup") await load();
    })();
  }, [load, canSeeInternal, projectStatus]);

  const generateAll = async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await pricing.generatePrices(projectId, {
        ...(filters.phase_id ? { phase_id: filters.phase_id } : {}),
        ...(filters.phase_id ? {} : { commercial_status: "unreleased" }),
      });
      setNotice(
        `${created.length} draft ${created.length === 1 ? "price" : "prices"} generated. ` +
          "Nothing is live until each is approved and activated.",
      );
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not generate prices.");
    } finally {
      setBusy(false);
    }
  };

  const header = (actions?: React.ReactNode) => (
    <PageHeader title="Pricing" subtitle={sectionDescription("pricing")} compact actions={actions} />
  );

  // Pricing is refused while the project is in setup, because that is the
  // window in which its currency can still change under whatever was priced in
  // it. Saying so beats a row of identical 409s.
  if (projectStatus === "setup") {
    return (
      <>
        {header()}
        <Card>
          <EmptyState
            title="Finalize project setup first"
            hint="Confirm country and currency settings, then move the project to Pre-development before configuring pricing."
          />
        </Card>
      </>
    );
  }

  if (!canSeeInternal) {
    return (
      <>
        {header()}
        <Card>
          <EmptyState
            title="Not available to your role"
            hint="Live unit prices are on each unit. Pricing configuration belongs to Finance."
          />
        </Card>
      </>
    );
  }

  const needle = search.trim().toLowerCase();
  const rows = (register?.rows ?? []).filter(
    (row) => !needle || `${row.unit_reference} ${row.unit_number} ${row.unit_type_code ?? ""}`.toLowerCase().includes(needle),
  );
  const filtered = search !== "" || filters.phase_id !== "" || filters.market_flag !== "";

  return (
    <>
      {header(
        <>
          {canPrice || canApprove ? (
            <Button
              onClick={() => setOpen(open === "configuration" ? "none" : "configuration")}
              aria-expanded={open === "configuration"}
            >
              Configuration
            </Button>
          ) : null}
          {canPrice ? (
            <Button
              onClick={() => setOpen(open === "benchmarks" ? "none" : "benchmarks")}
              aria-expanded={open === "benchmarks"}
            >
              Market benchmarks
            </Button>
          ) : null}
          {canPrice && overview?.configuration ? (
            <Button variant="primary" disabled={busy} onClick={generateAll}>
              {busy ? "Generating…" : "Generate draft prices"}
            </Button>
          ) : null}
        </>,
      )}

      <div className="stack">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}

        {/* What this development is currently offered at, before any of the
            machinery that decides it. The rate is the headline because it is
            the number a commercial team quotes; the policy that produced it
            is named underneath, where a reader who doubts the rate can find
            which version to open. */}
        <Card
          tone={overview?.configuration ? "command" : undefined}
          title="Commercial position"
          description={overview?.configuration ? "The policy in force and what it has priced." : undefined}
        >
          {overview === null ? (
            <Loading label="Loading pricing…" shape="metrics" />
          ) : overview.configuration === null ? (
            <EmptyState
              title="No active pricing configuration"
              hint="Create one, add the area rules and premiums it prices by, then have it approved and activated. Until then no unit can be priced."
              actions={
                canPrice ? (
                  <Button variant="primary" onClick={() => setOpen("configuration")}>
                    Open configuration
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <>
              <Position>
                <PositionFigure
                  lead
                  label="Base rate"
                  value={money(overview.base_internal_rate, currencyCodeOf(overview.currency_id))}
                  note="Per internal unit of area"
                />
                <PositionFigure
                  label="Priced"
                  value={`${overview.units_priced} of ${overview.units_total}`}
                  note="Units with a live price"
                />
                <PositionFigure
                  label="Not priced"
                  value={overview.units_not_priced}
                  tone={overview.units_not_priced > 0 ? "warning" : "neutral"}
                />
                <PositionFigure
                  label="Need repricing"
                  value={overview.units_repricing_required}
                  tone={overview.units_repricing_required > 0 ? "danger" : "neutral"}
                  note="Changed since pricing"
                />
              </Position>
              <PositionSupport>
                <PositionSupportItem
                  label="Policy"
                  value={`v${overview.configuration.version_number} · ${overview.configuration.name}`}
                />
                <PositionSupportItem
                  label="Active from"
                  value={businessDate(overview.configuration.valid_from)}
                />
                <PositionSupportItem label="Active escalations" value={overview.active_escalations} />
              </PositionSupport>
            </>
          )}
        </Card>

        {open === "configuration" ? (
          <ConfigurationPanel
            projectId={projectId}
            configurations={configurations}
            areaTypes={areaTypes}
            phases={phases}
            defaultCurrencyId={overview?.currency_id ?? reportingCurrencyId}
            canWrite={canPrice}
            canApprove={canApprove}
            onChanged={load}
            onClose={() => setOpen("none")}
          />
        ) : null}

        {open === "benchmarks" ? (
          <BenchmarksPanel
            projectId={projectId}
            benchmarks={benchmarks}
            phases={phases}
            currencyId={overview?.currency_id ?? null}
            onChanged={load}
            onClose={() => setOpen("none")}
          />
        ) : null}

        <DataToolbar
          framed
          search={{ value: search, onChange: setSearch, placeholder: "Unit reference", label: "Search the price register" }}
          count={register ? { shown: rows.length, total: register.total, noun: "unit" } : undefined}
          onReset={
            filtered
              ? () => {
                  setSearch("");
                  setFilters({ phase_id: "", market_flag: "" });
                }
              : undefined
          }
        >
          <ToolbarFilter label="Phase" active={filters.phase_id !== ""}>
            <select
              className="input"
              value={filters.phase_id}
              onChange={(event) => setFilters({ ...filters, phase_id: event.target.value })}
            >
              <option value="">All phases</option>
              {phases.map((phase) => (
                <option key={phase.id} value={phase.id}>
                  {phase.code} — {phase.name}
                </option>
              ))}
            </select>
          </ToolbarFilter>
          <ToolbarFilter label="Market position" active={filters.market_flag !== ""}>
            <select
              className="input"
              value={filters.market_flag}
              onChange={(event) => setFilters({ ...filters, market_flag: event.target.value })}
            >
              <option value="">Any market position</option>
              {Object.entries(MARKET_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </ToolbarFilter>
        </DataToolbar>

        <Card flush>
          {register === null ? (
            <Loading label="Loading the register…" shape="rows" rows={8} />
          ) : rows.length === 0 ? (
            <div className="card-body">
              <EmptyState
                title={filtered ? "No unit matches" : "No units to price"}
                hint={filtered ? "Widen the filter to see the rest." : "Load inventory first; every unit then appears here with its price."}
              />
            </div>
          ) : (
            <>
              <TableScroll label="Price register" fixedFirst>
                <thead>
                  <tr>
                    <th scope="col">Unit</th>
                    <th scope="col" className="num">
                      Internal
                    </th>
                    <th scope="col" className="num">
                      Weighted
                    </th>
                    <th scope="col" className="num">
                      List price (ex tax)
                    </th>
                    <th scope="col" className="num">
                      Per internal
                    </th>
                    <th scope="col">Version</th>
                    <th scope="col">Market</th>
                    <th scope="col">Pricing gate</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.unit_id}>
                      <th scope="row">
                        <button className="button-link" type="button" onClick={() => onOpenUnit(row.unit_id)}>
                          <IdentityCell name={row.unit_reference} meta={row.unit_type_code ?? row.unit_number} />
                        </button>
                      </th>
                      <td className="num">{row.internal_area_snapshot ?? "—"}</td>
                      <td className="num">{row.weighted_area_snapshot ?? "—"}</td>
                      {/*
                        * Denominated by the ROW's own price version, never by
                        * the active configuration: a frozen price keeps the
                        * currency it was approved in, whatever the project
                        * prices in today.
                        */}
                      <td className="num">
                        {money(row.reference_price_ex_tax, currencyCodeOf(row.currency_id))}
                      </td>
                      <td className="num">
                        {money(row.price_per_internal_area, currencyCodeOf(row.currency_id))}
                      </td>
                      <td>
                        {row.version_number === null ? (
                          <span className="muted">Not priced</span>
                        ) : (
                          <>
                            <span className="figure">v{row.version_number}</span>
                            <span className="cell-secondary">
                              {row.status ? (STATUS_LABELS[row.status] ?? row.status) : ""}
                            </span>
                          </>
                        )}
                      </td>
                      <td>
                        {row.market_flag ? (
                          <StatusDot tone={MARKET_TONES[row.market_flag] ?? "neutral"}>
                            {MARKET_LABELS[row.market_flag] ?? row.market_flag}
                            {row.market_deviation_fraction ? ` · ${percent(row.market_deviation_fraction)}` : ""}
                          </StatusDot>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td>
                        {row.repricing_required ? (
                          <Badge tone="danger">Repricing required</Badge>
                        ) : row.pricing_approved ? (
                          <StatusDot tone="success">Approved</StatusDot>
                        ) : (
                          <StatusDot tone="muted">Not approved</StatusDot>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </TableScroll>
              {register.total > register.rows.length ? (
                <p className="footnote" style={{ padding: "0.75rem 1.5rem" }}>
                  Showing the first {register.rows.length} of {register.total} units. Narrow the filter to
                  reach the rest.
                </p>
              ) : null}
            </>
          )}
        </Card>
      </div>
    </>
  );
}

/**
 * Manually governed market observations.
 *
 * There is no feed and no scraper. A benchmark is somebody's recorded reading
 * of the market, with a date, a source and a tolerance, and a unit price is
 * compared against exactly one of them.
 */
function BenchmarksPanel({
  projectId,
  benchmarks,
  phases,
  currencyId,
  onChanged,
  onClose,
}: {
  projectId: string;
  benchmarks: MarketBenchmark[];
  phases: Phase[];
  currencyId: string | null;
  onChanged: () => Promise<void>;
  onClose: () => void;
}) {
  const currencyCodeOf = useCurrencyCode();
  const code = currencyCodeOf(currencyId);
  const [form, setForm] = useState({
    phase_id: "",
    unit_type_code: "",
    area_basis: "internal",
    benchmark_price_per_area: "",
    comparison_date: todayISO(),
    source_name: "",
    tolerance_percent: "10",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (currencyId === null) {
      setError("Activate a pricing configuration first: a benchmark needs a currency to match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await pricing.createBenchmark(projectId, {
        ...(form.phase_id ? { phase_id: form.phase_id } : {}),
        ...(form.unit_type_code ? { unit_type_code: form.unit_type_code } : {}),
        area_basis: form.area_basis,
        benchmark_price_per_area: form.benchmark_price_per_area,
        currency_id: currencyId,
        comparison_date: form.comparison_date,
        source_name: form.source_name,
        tolerance_fraction: fractionFromPercent(form.tolerance_percent),
      });
      setForm({ ...form, benchmark_price_per_area: "", source_name: "" });
      await onChanged();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not record the benchmark.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      title="Market benchmarks"
      description="Recorded observations, attributed to a source. A unit price is compared only when one exists for its scope."
      actions={<Button variant="quiet" onClick={onClose}>Close</Button>}
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      <form onSubmit={submit}>
        <FieldRow columns={4}>
          <Field label="Scope">
            <select
              className="input"
              value={form.phase_id}
              onChange={(event) => setForm({ ...form, phase_id: event.target.value })}
            >
              <option value="">Whole project</option>
              {phases.map((phase) => (
                <option key={phase.id} value={phase.id}>
                  {phase.code} — {phase.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Unit type" optional>
            <input
              className="input input-short"
              value={form.unit_type_code}
              onChange={(event) => setForm({ ...form, unit_type_code: event.target.value })}
            />
          </Field>
          <Field label="Area basis">
            <select
              className="input input-short"
              value={form.area_basis}
              onChange={(event) => setForm({ ...form, area_basis: event.target.value })}
            >
              <option value="internal">Internal</option>
              <option value="weighted">Weighted</option>
            </select>
          </Field>
          <Field label="Price per unit of area">
            <MoneyInput
              code={code}
              required
              value={form.benchmark_price_per_area}
              onChange={(value) => setForm({ ...form, benchmark_price_per_area: value })}
            />
          </Field>
          <Field label="Tolerance" hint="How far a price may sit from the benchmark and still be in line.">
            <RateInput
              required
              value={form.tolerance_percent}
              onChange={(value) => setForm({ ...form, tolerance_percent: value })}
            />
          </Field>
          <Field label="Observed on">
            <input
              className="input input-short"
              type="date"
              required
              value={form.comparison_date}
              onChange={(event) => setForm({ ...form, comparison_date: event.target.value })}
            />
          </Field>
          <Field label="Source" className="field-span-2">
            <input
              className="input"
              required
              value={form.source_name}
              onChange={(event) => setForm({ ...form, source_name: event.target.value })}
            />
          </Field>
        </FieldRow>
        <FormActions>
          <Button variant="primary" type="submit" disabled={busy}>
            {busy ? "Saving…" : "Record observation"}
          </Button>
        </FormActions>
      </form>

      {benchmarks.length === 0 ? (
        <EmptyState compact title="No benchmarks yet" hint="Record one to compare every priced unit in its scope against the market." />
      ) : (
        <TableScroll label="Market benchmarks" compact>
          <thead>
            <tr>
              <th scope="col">Scope</th>
              <th scope="col">Basis</th>
              <th scope="col" className="num">
                Price per area
              </th>
              <th scope="col" className="num">
                Tolerance
              </th>
              <th scope="col">Observed</th>
              <th scope="col">Source</th>
              <th scope="col">State</th>
            </tr>
          </thead>
          <tbody>
            {benchmarks.map((benchmark) => (
              <tr key={benchmark.id}>
                <th scope="row">
                  {benchmark.unit_type_code ?? "Any type"} ·{" "}
                  {phases.find((phase) => phase.id === benchmark.phase_id)?.code ?? "Whole project"}
                </th>
                <td>{benchmark.area_basis}</td>
                <td className="num">
                  {money(benchmark.benchmark_price_per_area, currencyCodeOf(benchmark.currency_id))}
                </td>
                <td className="num">{percent(benchmark.tolerance_fraction)}</td>
                <td className="figure">{businessDate(benchmark.comparison_date)}</td>
                <td>
                  {benchmark.source_name}
                  {benchmark.source_reference ? <span className="cell-secondary">{benchmark.source_reference}</span> : null}
                </td>
                <td>
                  {benchmark.is_active ? (
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
  );
}
