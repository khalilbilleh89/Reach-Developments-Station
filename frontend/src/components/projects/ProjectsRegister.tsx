"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, projects, settings } from "@/lib/api";
import type { CountryPack, Currency, ProjectSummary, ReferenceValue } from "@/lib/api";
import { businessDate } from "@/lib/format";
import {
  Badge,
  Button,
  Card,
  DataToolbar,
  EmptyState,
  Field,
  FieldRow,
  FormActions,
  FormSection,
  Loading,
  Notice,
  PageHeader,
  ToolbarFilter,
} from "@/components/ui";
import { PROJECT_STATUSES, projectStatusLabel, projectStatusTone } from "./projectStatus";

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
 * The portfolio: every development this person may open.
 *
 * One tile per project, carrying the identity the API returns — code, name,
 * developer, city, status, programme, base currency — and the permit counts
 * the server already derives, because those are what tell a manager which
 * project needs attention today. No portfolio analytics and no invented
 * metrics; a tile with nothing to flag says nothing.
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
      setCurrencies(currencyList);
      setTypes(referenceList.filter((value) => value.is_active && value.category === "project_type"));
    } catch {
      // Configuration is only needed to open the create form and to name a
      // tile's base currency; the register itself still works without it.
    }
  }, []);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  useEffect(() => {
    void (async () => {
      await loadConfiguration();
    })();
  }, [loadConfiguration]);

  const currencyCode = (id: string) => currencies.find((currency) => currency.id === id)?.code ?? null;
  const typeLabel = (code: string | null) =>
    code ? (types.find((value) => value.code === code)?.label ?? code) : null;
  const activeCurrencies = currencies.filter((currency) => currency.is_active);

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

  const configurationMissing = packs.length === 0 || activeCurrencies.length === 0;
  const filtered = search !== "" || status !== "";

  return (
    <>
      <PageHeader
        title="Projects"
        subtitle="Manage the developments you can access."
        actions={
          <Button variant="primary" onClick={() => setCreating((open) => !open)}>
            {creating ? "Cancel" : "New project"}
          </Button>
        }
      />

      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      {creating ? (
        configurationMissing ? (
          <Notice tone="info">
            A project needs an active country pack and currency first. Configure them under
            Settings, then come back.
          </Notice>
        ) : (
          <Card title="New project" description="The code is issued once and never changes. Everything else can be edited later.">
            <form onSubmit={submit}>
              <FormSection title="Identity">
                <FieldRow columns={3}>
                  <Field label="Project code" hint="Letters, digits, hyphen or underscore.">
                    <input
                      className="input input-medium"
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
                      onChange={(event) => setForm({ ...form, developer_entity: event.target.value })}
                    />
                  </Field>
                  <Field label="Project type" optional>
                    <select
                      className="input"
                      value={form.project_type_code}
                      onChange={(event) => setForm({ ...form, project_type_code: event.target.value })}
                    >
                      <option value="">Not set</option>
                      {types.map((value) => (
                        <option key={value.id} value={value.code}>
                          {value.label}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Status">
                    <select
                      className="input"
                      value={form.status}
                      onChange={(event) => setForm({ ...form, status: event.target.value })}
                    >
                      {PROJECT_STATUSES.map((value) => (
                        <option key={value} value={value}>
                          {projectStatusLabel(value)}
                        </option>
                      ))}
                    </select>
                  </Field>
                </FieldRow>
              </FormSection>

              <FormSection
                title="Financial basis"
                description="Every amount on this project is denominated in its base currency. There is no conversion anywhere."
              >
                <FieldRow columns={3}>
                  <Field label="Country pack">
                    <select
                      className="input"
                      required
                      value={form.country_pack_id}
                      onChange={(event) => setForm({ ...form, country_pack_id: event.target.value })}
                    >
                      <option value="">Choose…</option>
                      {packs.map((pack) => (
                        <option key={pack.id} value={pack.id}>
                          {pack.name} ({pack.country_code})
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Base currency">
                    <select
                      className="input"
                      required
                      value={form.base_currency_id}
                      onChange={(event) => setForm({ ...form, base_currency_id: event.target.value })}
                    >
                      <option value="">Choose…</option>
                      {activeCurrencies.map((currency) => (
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
                      onChange={(event) => setForm({ ...form, reporting_currency_id: event.target.value })}
                    >
                      <option value="">Same as base</option>
                      {activeCurrencies.map((currency) => (
                        <option key={currency.id} value={currency.id}>
                          {currency.code}
                        </option>
                      ))}
                    </select>
                  </Field>
                </FieldRow>
              </FormSection>

              <FormSection title="Location and programme">
                <FieldRow columns={4}>
                  <Field label="City" optional>
                    <input
                      className="input"
                      value={form.city}
                      onChange={(event) => setForm({ ...form, city: event.target.value })}
                    />
                  </Field>
                  <Field label="Location" optional>
                    <input
                      className="input"
                      value={form.location}
                      onChange={(event) => setForm({ ...form, location: event.target.value })}
                    />
                  </Field>
                  <Field label="Latitude" optional hint="Decimal degrees.">
                    <input
                      className="input input-short"
                      inputMode="decimal"
                      value={form.latitude}
                      onChange={(event) => setForm({ ...form, latitude: event.target.value })}
                    />
                  </Field>
                  <Field label="Longitude" optional>
                    <input
                      className="input input-short"
                      inputMode="decimal"
                      value={form.longitude}
                      onChange={(event) => setForm({ ...form, longitude: event.target.value })}
                    />
                  </Field>
                  <Field label="Planned start" optional>
                    <input
                      className="input input-short"
                      type="date"
                      value={form.planned_start}
                      onChange={(event) => setForm({ ...form, planned_start: event.target.value })}
                    />
                  </Field>
                  <Field label="Planned completion" optional>
                    <input
                      className="input input-short"
                      type="date"
                      value={form.planned_completion}
                      onChange={(event) => setForm({ ...form, planned_completion: event.target.value })}
                    />
                  </Field>
                </FieldRow>
              </FormSection>
              <FormActions>
                <Button variant="primary" type="submit" disabled={busy}>
                  {busy ? "Creating…" : "Create project"}
                </Button>
                <Button onClick={() => setCreating(false)} disabled={busy}>
                  Cancel
                </Button>
              </FormActions>
            </form>
          </Card>
        )
      ) : null}

      <DataToolbar
        search={{ value: search, onChange: setSearch, placeholder: "Code or name", label: "Search projects" }}
        count={rows ? { shown: rows.length, noun: "project" } : undefined}
        onReset={filtered ? () => {
          setSearch("");
          setStatus("");
        } : undefined}
      >
        <ToolbarFilter label="Status">
          <select className="input" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">Any status</option>
            {PROJECT_STATUSES.map((value) => (
              <option key={value} value={value}>
                {projectStatusLabel(value)}
              </option>
            ))}
          </select>
        </ToolbarFilter>
      </DataToolbar>

      {rows === null ? (
        <Loading label="Loading projects…" shape="metrics" />
      ) : rows.length === 0 ? (
        <EmptyState
          title={filtered ? "No project matches" : "No projects yet"}
          hint={
            filtered
              ? "Widen the search, or clear the filters to see every project you can access."
              : "Projects you are given access to appear here. An administrator grants access per project."
          }
        />
      ) : (
        <div className="project-tiles">
          {rows.map((project) => {
            const base = currencyCode(project.base_currency_id);
            const reporting = currencyCode(project.reporting_currency_id);
            return (
              <button
                key={project.id}
                type="button"
                className="project-tile"
                onClick={() => onOpen(project.id)}
                aria-label={`Open ${project.name}`}
              >
                <div className="project-tile-head">
                  <div style={{ minWidth: 0 }}>
                    <p className="project-tile-code">{project.code}</p>
                    <h2 className="project-tile-name">{project.name}</h2>
                    <p className="project-tile-sub">
                      {project.developer_entity}
                      {project.city ? ` · ${project.city}` : ""}
                    </p>
                  </div>
                  <Badge tone={projectStatusTone(project.status)}>{projectStatusLabel(project.status)}</Badge>
                </div>
                <dl className="project-tile-facts">
                  <div>
                    <dt>Type</dt>
                    <dd>{typeLabel(project.project_type_code) ?? "—"}</dd>
                  </div>
                  <div>
                    <dt>Currency</dt>
                    <dd>
                      {base ?? "—"}
                      {reporting && reporting !== base ? ` · reports ${reporting}` : ""}
                    </dd>
                  </div>
                  <div>
                    <dt>Programme</dt>
                    <dd>
                      {project.planned_start || project.planned_completion
                        ? `${businessDate(project.planned_start)} → ${businessDate(project.planned_completion)}`
                        : "Not planned"}
                    </dd>
                  </div>
                  <div>
                    <dt>Land and consents</dt>
                    <dd>
                      {project.parcel_count} parcel{project.parcel_count === 1 ? "" : "s"} ·{" "}
                      {project.permit_count} permit{project.permit_count === 1 ? "" : "s"}
                    </dd>
                  </div>
                </dl>
                {project.blocking_permit_count > 0 || project.overdue_permit_count > 0 ? (
                  <div className="project-tile-flags">
                    {project.overdue_permit_count > 0 ? (
                      <Badge tone="danger">
                        {project.overdue_permit_count} permit{project.overdue_permit_count === 1 ? "" : "s"} past
                        statutory period
                      </Badge>
                    ) : null}
                    {project.blocking_permit_count > 0 ? (
                      <Badge tone="warning">
                        {project.blocking_permit_count} blocking permit
                        {project.blocking_permit_count === 1 ? "" : "s"}
                      </Badge>
                    ) : null}
                  </div>
                ) : null}
              </button>
            );
          })}
        </div>
      )}
    </>
  );
}
