"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, pricing } from "@/lib/api";
import type {
  AreaType,
  MarketBenchmark,
  Phase,
  PriceRegister,
  PricingConfiguration,
  PricingOverview,
} from "@/lib/api";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  FilterBar,
  FormActions,
  Loading,
  Notice,
  Stat,
  StatRow,
  SubPanel,
  TableScroll,
} from "@/components/ui";
import { inventory } from "@/lib/api";
import { ConfigurationPanel } from "@/components/projects/pricing/ConfigurationPanel";

/**
 * The Pricing Studio, inside the project workspace.
 *
 * Three questions, in the order somebody actually asks them: what is this
 * development priced at, which units are priced, and which of them are no longer
 * priced against their own facts. Everything below is a number the backend
 * computed; nothing on this screen does pricing arithmetic.
 */
const MARKET_LABELS: Record<string, string> = {
  within_tolerance: "In line",
  above_tolerance: "Above market",
  below_tolerance: "Below market",
  no_benchmark: "No benchmark",
};

/** Presentation only: the word beside it already carries the meaning. */
const MARKET_TONES: Record<string, "success" | "warning" | "info" | "muted"> = {
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
  const [open, setOpen] = useState<"none" | "configuration" | "benchmarks">("none");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const query: Record<string, string> = { limit: "100" };
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
      await load();
    })();
  }, [load]);

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

  // Pricing is refused while the project is in setup, because that is the
  // window in which its currency can still change under whatever was priced in
  // it. Saying so beats a row of identical 409s.
  if (projectStatus === "setup") {
    return (
      <Card title="Pricing" description="Not yet — the project basis is still open.">
        <EmptyState
          title="Finalize project setup"
          hint="Confirm country and currency settings, then move the project to Pre-development before configuring pricing."
        />
      </Card>
    );
  }

  if (!canSeeInternal) {
    return (
      <Card title="Pricing">
        <EmptyState
          title="Not available to you"
          hint="Live unit prices are on each unit. Pricing configuration belongs to Finance."
        />
      </Card>
    );
  }

  return (
    <>
      <Card
        title="Pricing"
        description="What this development is priced at, and what that price is made of."
        actions={
          <>
            {canPrice || canApprove ? (
              <Button onClick={() => setOpen(open === "configuration" ? "none" : "configuration")}>
                {open === "configuration" ? "Cancel" : "Configuration"}
              </Button>
            ) : null}
            {canPrice ? (
              <Button onClick={() => setOpen(open === "benchmarks" ? "none" : "benchmarks")}>
                {open === "benchmarks" ? "Cancel" : "Market benchmarks"}
              </Button>
            ) : null}
            {canPrice && overview?.configuration ? (
              <Button variant="primary" disabled={busy} onClick={generateAll}>
                {busy ? "Generating…" : "Generate draft prices"}
              </Button>
            ) : null}
          </>
        }
      >
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}

        {overview === null ? (
          <Loading label="Loading pricing…" lines={3} />
        ) : overview.configuration === null ? (
          <EmptyState
            title="No active pricing configuration"
            hint="Create one, add the area rules and premiums it prices by, then have it approved and activated. Until then no unit can be priced."
          />
        ) : (
          <>
            <ul className="chip-list">
              <li className="chip">
                <span className="chip-label">Configuration</span>
                <strong>{overview.configuration.name}</strong>
                <Badge tone="success">v{overview.configuration.version_number}</Badge>
              </li>
            </ul>
            <StatRow>
              <Stat label="Base rate" value={overview.base_internal_rate} note="Per internal unit" />
              <Stat label="Units" value={overview.units_total} small />
              <Stat label="Priced" value={overview.units_priced} small />
              <Stat label="Not priced" value={overview.units_not_priced} small />
              <Stat label="Need repricing" value={overview.units_repricing_required} small />
              <Stat label="Active escalations" value={overview.active_escalations} small />
            </StatRow>
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
        />
      ) : null}

      {open === "benchmarks" ? (
        <BenchmarksPanel
          projectId={projectId}
          benchmarks={benchmarks}
          phases={phases}
          currencyId={overview?.currency_id ?? null}
          onChanged={load}
        />
      ) : null}

      <Card title="Price register" description="Every unit, and the price it is offered at.">
        <FilterBar>
          <Field label="Phase">
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
          </Field>
          <Field label="Market">
            <select
              className="input"
              value={filters.market_flag}
              onChange={(event) => setFilters({ ...filters, market_flag: event.target.value })}
            >
              <option value="">Any</option>
              {Object.entries(MARKET_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
        </FilterBar>

        {register === null ? (
          <Loading label="Loading the register…" lines={4} />
        ) : register.rows.length === 0 ? (
          <EmptyState title="No units match" hint="Adjust the filters, or load inventory first." />
        ) : (
          <>
            <StatRow>
              <Stat label="Units" value={register.total} small />
              <Stat label="Priced" value={register.priced} small />
              <Stat label="Not priced" value={register.not_priced} small />
              <Stat label="Need repricing" value={register.repricing_required} small />
            </StatRow>
            <TableScroll label="Price register" fixedFirst>
                <thead>
                  <tr>
                    <th scope="col">Unit</th>
                    <th scope="col">Type</th>
                    <th scope="col" className="num">
                      Internal
                    </th>
                    <th scope="col" className="num">
                      Weighted
                    </th>
                    <th scope="col" className="num">
                      Price
                    </th>
                    <th scope="col" className="num">
                      Per internal
                    </th>
                    <th scope="col" className="num">
                      Version
                    </th>
                    <th scope="col">Status</th>
                    <th scope="col">Market</th>
                    <th scope="col">Pricing</th>
                  </tr>
                </thead>
                <tbody>
                  {register.rows.map((row) => (
                    <tr key={row.unit_id}>
                      <th scope="row">
                        <button
                          className="button-link mono"
                          type="button"
                          onClick={() => onOpenUnit(row.unit_id)}
                        >
                          {row.unit_reference}
                        </button>
                      </th>
                      <td>{row.unit_type_code ?? "—"}</td>
                      <td className="num">{row.internal_area_snapshot ?? "—"}</td>
                      <td className="num">{row.weighted_area_snapshot ?? "—"}</td>
                      <td className="num">{row.reference_price_ex_tax ?? "—"}</td>
                      <td className="num">{row.price_per_internal_area ?? "—"}</td>
                      <td className="num">{row.version_number ?? "—"}</td>
                      <td>{row.status ? (STATUS_LABELS[row.status] ?? row.status) : "Not priced"}</td>
                      <td>
                        {row.market_flag ? (
                          <Badge tone={MARKET_TONES[row.market_flag] ?? "neutral"}>
                            {MARKET_LABELS[row.market_flag] ?? row.market_flag}
                          </Badge>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td>
                        {row.repricing_required ? (
                          <Badge tone="danger">Repricing required</Badge>
                        ) : row.pricing_approved ? (
                          <Badge tone="success">Approved</Badge>
                        ) : (
                          <span className="subtle">Not approved</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
            </TableScroll>
          </>
        )}
      </Card>
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
}: {
  projectId: string;
  benchmarks: MarketBenchmark[];
  phases: Phase[];
  currencyId: string | null;
  onChanged: () => Promise<void>;
}) {
  const [form, setForm] = useState({
    phase_id: "",
    unit_type_code: "",
    area_basis: "internal",
    benchmark_price_per_area: "",
    comparison_date: new Date().toISOString().slice(0, 10),
    source_name: "",
    tolerance_fraction: "0.100000",
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
        tolerance_fraction: form.tolerance_fraction,
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
    <Card title="Market benchmarks" description="Recorded observations, attributed to a source.">
      {error ? <Notice tone="error">{error}</Notice> : null}
      <SubPanel title="Record an observation">
      <form onSubmit={submit}>
        <div className="form-grid form-grid-3">
        <Field label="Phase">
          <select
            className="input"
            value={form.phase_id}
            onChange={(event) => setForm({ ...form, phase_id: event.target.value })}
          >
            <option value="">Whole project</option>
            {phases.map((phase) => (
              <option key={phase.id} value={phase.id}>
                {phase.code}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Unit type">
          <input
            className="input input-short"
            value={form.unit_type_code}
            onChange={(event) => setForm({ ...form, unit_type_code: event.target.value })}
          />
        </Field>
        <Field label="Basis">
          <select
            className="input input-short"
            value={form.area_basis}
            onChange={(event) => setForm({ ...form, area_basis: event.target.value })}
          >
            <option value="internal">Internal</option>
            <option value="weighted">Weighted</option>
          </select>
        </Field>
        <Field label="Price per area">
          <input
            className="input input-short"
            inputMode="decimal"
            required
            value={form.benchmark_price_per_area}
            onChange={(event) =>
              setForm({ ...form, benchmark_price_per_area: event.target.value })
            }
          />
        </Field>
        <Field label="Tolerance" hint="0.100000 is 10%.">
          <input
            className="input input-short"
            inputMode="decimal"
            required
            value={form.tolerance_fraction}
            onChange={(event) => setForm({ ...form, tolerance_fraction: event.target.value })}
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
        <Field label="Source">
          <input
            className="input"
            required
            value={form.source_name}
            onChange={(event) => setForm({ ...form, source_name: event.target.value })}
          />
        </Field>
        <FormActions>
          <Button variant="primary" type="submit" disabled={busy}>
            {busy ? "Saving…" : "Record"}
          </Button>
        </FormActions>
        </div>
      </form>
      </SubPanel>

      {benchmarks.length === 0 ? (
        <EmptyState title="No benchmarks" hint="A unit price is compared only when one exists." />
      ) : (
        <TableScroll label="Market benchmarks">
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
                <th scope="col">Active</th>
              </tr>
            </thead>
            <tbody>
              {benchmarks.map((benchmark) => (
                <tr key={benchmark.id}>
                  <th scope="row">
                    {benchmark.unit_type_code ?? "Any type"} ·{" "}
                    {phases.find((phase) => phase.id === benchmark.phase_id)?.code ??
                      "Whole project"}
                  </th>
                  <td>{benchmark.area_basis}</td>
                  <td className="num">{benchmark.benchmark_price_per_area}</td>
                  <td className="num">{benchmark.tolerance_fraction}</td>
                  <td className="mono nowrap">{benchmark.comparison_date}</td>
                  <td>{benchmark.source_name}</td>
                  <td>
                    {benchmark.is_active ? (
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
    </Card>
  );
}
