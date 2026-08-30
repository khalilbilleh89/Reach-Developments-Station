"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, projects, settings } from "@/lib/api";
import type { CountryPack, Currency, ProjectSummary, ReferenceValue } from "@/lib/api";
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
  PageHeader,
  SubPanel,
  TableScroll,
} from "@/components/ui";

const STATUSES = ["setup", "predevelopment", "active", "on_hold", "completed", "cancelled"];

/** Presentation only: the word beside it already carries the meaning. */
const STATUS_TONES: Record<string, "muted" | "info" | "success" | "warning" | "neutral" | "danger"> =
  {
    setup: "muted",
    predevelopment: "info",
    active: "success",
    on_hold: "warning",
    completed: "neutral",
    cancelled: "danger",
  };

/** Machine states read badly in a table; these are what a person calls them. */
const STATUS_LABELS: Record<string, string> = {
  setup: "Setup",
  predevelopment: "Pre-development",
  active: "Active",
  on_hold: "On hold",
  completed: "Completed",
  cancelled: "Cancelled",
};

function emptyForm() {
  return {
    code: "",
    name: "",
    developer_entity: "",
    country_pack_id: "",
    base_currency_id: "",
    reporting_currency_id: "",
    city: "",
    location: "",
    latitude: "",
    longitude: "",
    project_type_code: "",
    status: "setup",
    planned_start: "",
    planned_completion: "",
  };
}

/**
 * The project register: everything the current user is allowed to see.
 *
 * No portfolio analytics and no invented metrics — the counts shown are the
 * ones the API already derives, because they are what tells a manager which
 * project needs attention today.
 */
export function ProjectsRegister({ onOpen }: { onOpen: (id: string) => void }) {
  const [rows, setRows] = useState<ProjectSummary[] | null>(null);
  const [packs, setPacks] = useState<CountryPack[]>([]);
  const [currencies, setCurrencies] = useState<Currency[]>([]);
  const [types, setTypes] = useState<ReferenceValue[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [form, setForm] = useState(emptyForm());
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setRows(await projects.list({ search: search || undefined, status: status || undefined }));
      setError(null);
    } catch (caught) {
      setRows([]);
      setError(caught instanceof ApiError ? caught.message : "Could not load projects.");
    }
  }, [search, status]);

  const loadConfiguration = useCallback(async () => {
    try {
      const [packList, currencyList, referenceList] = await Promise.all([
        settings.countryPacks(),
        settings.currencies(),
        settings.referenceValues(),
      ]);
      setPacks(packList.filter((pack) => pack.is_active));
      setCurrencies(currencyList.filter((currency) => currency.is_active));
      setTypes(
        referenceList.filter(
          (value) => value.is_active && value.category === "project_type",
        ),
      );
    } catch {
      // Configuration is only needed to open the create form; the register
      // itself still works without it.
    }
  }, []);

  useEffect(() => {
    // Wrapped rather than awaited directly: an effect body must not be async.
    void (async () => {
      await load();
    })();
  }, [load]);

  useEffect(() => {
    void (async () => {
      await loadConfiguration();
    })();
  }, [loadConfiguration]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const payload: Record<string, unknown> = {
        code: form.code,
        name: form.name,
        developer_entity: form.developer_entity,
        country_pack_id: form.country_pack_id,
        base_currency_id: form.base_currency_id,
        reporting_currency_id: form.reporting_currency_id || form.base_currency_id,
        status: form.status,
      };
      for (const key of [
        "city",
        "location",
        "latitude",
        "longitude",
        "project_type_code",
        "planned_start",
        "planned_completion",
      ] as const) {
        if (form[key]) payload[key] = form[key];
      }
      const created = await projects.create(payload);
      setNotice(`Project ${created.code} created.`);
      setForm(emptyForm());
      setCreating(false);
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not create the project.");
    } finally {
      setBusy(false);
    }
  };

  const configurationMissing = packs.length === 0 || currencies.length === 0;

  return (
    <>
      <PageHeader
        eyebrow="Portfolio"
        title="Projects"
        subtitle="Every development you have been given access to. Open one to work inside it."
        actions={
          <Button variant="primary" onClick={() => setCreating((open) => !open)}>
            {creating ? "Cancel" : "New project"}
          </Button>
        }
      />
      <Card>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      <FilterBar>
        <Field label="Search" grow>
          <input
            className="input"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Code or name"
          />
        </Field>
        <Field label="Status">
          <select
            className="input input-short"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">All</option>
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {STATUS_LABELS[value]}
              </option>
            ))}
          </select>
        </Field>
      </FilterBar>

      {creating ? (
        configurationMissing ? (
          <Notice tone="info">
            A project needs an active country pack and currency first. Configure them under
            Settings → Country packs, then come back.
          </Notice>
        ) : (
          <SubPanel title="New project">
          <form onSubmit={submit}>
            <div className="form-grid form-grid-3">
              <Field label="Project code" hint="Letters, digits, hyphen or underscore.">
                <input
                  className="input"
                  required
                  value={form.code}
                  onChange={(event) => setForm({ ...form, code: event.target.value })}
                />
              </Field>
              <Field label="Name">
                <input
                  className="input"
                  required
                  value={form.name}
                  onChange={(event) => setForm({ ...form, name: event.target.value })}
                />
              </Field>
              <Field label="Developer entity">
                <input
                  className="input"
                  required
                  value={form.developer_entity}
                  onChange={(event) =>
                    setForm({ ...form, developer_entity: event.target.value })
                  }
                />
              </Field>
              <Field label="Country pack">
                <select
                  className="input"
                  required
                  value={form.country_pack_id}
                  onChange={(event) =>
                    setForm({ ...form, country_pack_id: event.target.value })
                  }
                >
                  <option value="">Choose…</option>
                  {packs.map((pack) => (
                    <option key={pack.id} value={pack.id}>
                      {pack.name} ({pack.country_code})
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Base currency" hint="Every amount on this project is in this currency.">
                <select
                  className="input"
                  required
                  value={form.base_currency_id}
                  onChange={(event) =>
                    setForm({ ...form, base_currency_id: event.target.value })
                  }
                >
                  <option value="">Choose…</option>
                  {currencies.map((currency) => (
                    <option key={currency.id} value={currency.id}>
                      {currency.code} — {currency.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Reporting currency" hint="Defaults to the base currency.">
                <select
                  className="input"
                  value={form.reporting_currency_id}
                  onChange={(event) =>
                    setForm({ ...form, reporting_currency_id: event.target.value })
                  }
                >
                  <option value="">Same as base</option>
                  {currencies.map((currency) => (
                    <option key={currency.id} value={currency.id}>
                      {currency.code}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Project type">
                <select
                  className="input"
                  value={form.project_type_code}
                  onChange={(event) =>
                    setForm({ ...form, project_type_code: event.target.value })
                  }
                >
                  <option value="">Not set</option>
                  {types.map((value) => (
                    <option key={value.id} value={value.code}>
                      {value.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="City">
                <input
                  className="input"
                  value={form.city}
                  onChange={(event) => setForm({ ...form, city: event.target.value })}
                />
              </Field>
              <Field label="Location">
                <input
                  className="input"
                  value={form.location}
                  onChange={(event) => setForm({ ...form, location: event.target.value })}
                />
              </Field>
              <Field label="Latitude" hint="Optional. Decimal degrees.">
                <input
                  className="input input-short"
                  value={form.latitude}
                  onChange={(event) => setForm({ ...form, latitude: event.target.value })}
                />
              </Field>
              <Field label="Longitude" hint="Optional. Decimal degrees.">
                <input
                  className="input input-short"
                  value={form.longitude}
                  onChange={(event) => setForm({ ...form, longitude: event.target.value })}
                />
              </Field>
              <Field label="Planned start">
                <input
                  className="input input-short"
                  type="date"
                  value={form.planned_start}
                  onChange={(event) => setForm({ ...form, planned_start: event.target.value })}
                />
              </Field>
              <Field label="Planned completion">
                <input
                  className="input input-short"
                  type="date"
                  value={form.planned_completion}
                  onChange={(event) =>
                    setForm({ ...form, planned_completion: event.target.value })
                  }
                />
              </Field>
              <FormActions>
                <Button variant="primary" type="submit" disabled={busy}>
                  {busy ? "Creating…" : "Create project"}
                </Button>
              </FormActions>
            </div>
          </form>
          </SubPanel>
        )
      ) : null}

      {rows === null ? (
        <Loading label="Loading projects…" lines={4} />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No projects yet"
          hint="Projects you are given access to appear here."
        />
      ) : (
        <TableScroll label="Projects you can access">
            <thead>
              <tr>
                <th scope="col">Code</th>
                <th scope="col">Name</th>
                <th scope="col">City</th>
                <th scope="col">Status</th>
                <th scope="col">Planned completion</th>
                <th scope="col" className="num">
                  Blocking
                </th>
                <th scope="col" className="num">
                  Critical path
                </th>
                <th scope="col" className="num">
                  Overdue
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((project) => (
                <tr key={project.id}>
                  <th scope="row">
                    <button
                      className="button-link mono"
                      type="button"
                      onClick={() => onOpen(project.id)}
                    >
                      {project.code}
                    </button>
                  </th>
                  <td>
                    <button
                      className="button-link"
                      type="button"
                      onClick={() => onOpen(project.id)}
                    >
                      {project.name}
                    </button>
                  </td>
                  <td>{project.city ?? "—"}</td>
                  <td>
                    <Badge tone={STATUS_TONES[project.status] ?? "neutral"}>
                      {STATUS_LABELS[project.status] ?? project.status}
                    </Badge>
                  </td>
                  <td className="mono nowrap">{project.planned_completion ?? "—"}</td>
                  <td className="num">{project.blocking_permit_count}</td>
                  <td className="num">{project.critical_path_permit_count}</td>
                  <td className="num">{project.overdue_permit_count}</td>
                </tr>
              ))}
            </tbody>
        </TableScroll>
      )}
      </Card>
    </>
  );
}
