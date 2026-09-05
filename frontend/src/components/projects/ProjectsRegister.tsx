"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, projects, settings } from "@/lib/api";
import type { CountryPack, Currency, ProjectSummary, ReferenceValue } from "@/lib/api";
import { PROJECT_WRITERS, hasAnyRole } from "@/lib/roles";
import { businessDate } from "@/lib/format";
import {
  Badge,
  Button,
  Card,
  DataToolbar,
  Drawer,
  EmptyState,
  Field,
  FieldRow,
  FormActions,
  FormSection,
  Icon,
  IdentityCell,
  Loading,
  Notice,
  PageHeader,
  PlaceCell,
  StatusDot,
  TableScroll,
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

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

/**
 * The portfolio: every development this person may open.
 *
 * A register rather than a wall of tiles, because a portfolio is read the way
 * every other register in the product is read — down the identity column,
 * with the facts that distinguish one development from the next beside it:
 * where it stands, where it is, when it runs, and what the server already
 * flags about its consents. No portfolio analytics and no invented metrics;
 * a row with nothing to flag says nothing.
 *
 * Creating a project opens a file over the register, the way every other
 * record in the product does, so the portfolio stays where it was.
 */
export function ProjectsRegister({ onOpen, roles }: { onOpen: (id: string) => void; roles: Set<string> }) {
  const canCreate = hasAnyRole(roles, PROJECT_WRITERS);
  const [rows, setRows] = useState<ProjectSummary[] | null>(null);
  const [packs, setPacks] = useState<CountryPack[]>([]);
  const [currencies, setCurrencies] = useState<Currency[]>([]);
  const [types, setTypes] = useState<ReferenceValue[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [form, setForm] = useState(emptyForm());
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
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
      // row's base currency; the register itself still works without it.
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
    setFormError(null);
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
      setFormError(caught instanceof ApiError ? caught.message : "Could not create the project.");
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
        subtitle="The developments you can open. Choose one to work inside it."
        actions={
          canCreate ? (
            <Button variant="primary" onClick={() => setCreating(true)}>
              New project
            </Button>
          ) : undefined
        }
      />

      <div className="stack">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}

        <DataToolbar
          framed
          search={{ value: search, onChange: setSearch, placeholder: "Code or name", label: "Search projects" }}
          count={rows ? { shown: rows.length, noun: "project" } : undefined}
          onReset={
            filtered
              ? () => {
                  setSearch("");
                  setStatus("");
                }
              : undefined
          }
        >
          <ToolbarFilter label="Status" active={status !== ""}>
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

        <Card flush>
          {rows === null ? (
            <Loading label="Loading projects…" shape="rows" rows={6} />
          ) : rows.length === 0 ? (
            <div className="card-body">
              <EmptyState
                icon="projects"
                title={filtered ? "No project matches" : "No projects yet"}
                hint={
                  filtered
                    ? "Widen the search, or clear the filters to see every project you can access."
                    : "Projects you are given access to appear here. An administrator grants access per project."
                }
                actions={
                  canCreate && !filtered ? (
                    <Button variant="primary" onClick={() => setCreating(true)}>
                      New project
                    </Button>
                  ) : undefined
                }
              />
            </div>
          ) : (
            <TableScroll label="Project register" fixedFirst>
              <thead>
                <tr>
                  <th scope="col">Project</th>
                  <th scope="col">Status</th>
                  <th scope="col">Where</th>
                  <th scope="col">Programme</th>
                  <th scope="col">Currency</th>
                  <th scope="col">Land and consents</th>
                  <th scope="col">Flags</th>
                  <th scope="col">
                    <span className="visually-hidden">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((project) => {
                  const base = currencyCode(project.base_currency_id);
                  const reporting = currencyCode(project.reporting_currency_id);
                  const flagged = project.overdue_permit_count > 0 || project.blocking_permit_count > 0;
                  return (
                    <tr key={project.id} className={flagged ? "row-flag" : undefined}>
                      <th scope="row">
                        <button
                          className="button-link"
                          type="button"
                          onClick={() => onOpen(project.id)}
                          aria-label={`Open ${project.name}`}
                        >
                          <IdentityCell
                            name={project.name}
                            meta={
                              <>
                                <span className="mono">{project.code}</span> · {project.developer_entity}
                              </>
                            }
                          />
                        </button>
                      </th>
                      <td>
                        <Badge tone={projectStatusTone(project.status)}>{projectStatusLabel(project.status)}</Badge>
                      </td>
                      <td>
                        <PlaceCell main={project.city} sub={typeLabel(project.project_type_code) ?? undefined} />
                      </td>
                      <td className="figure">
                        {project.planned_start || project.planned_completion
                          ? `${businessDate(project.planned_start)} → ${businessDate(project.planned_completion)}`
                          : "Not planned"}
                      </td>
                      <td className="figure">
                        {base ?? "—"}
                        {reporting && reporting !== base ? (
                          <span className="cell-secondary">Reports in {reporting}</span>
                        ) : null}
                      </td>
                      <td>
                        {plural(project.parcel_count, "parcel")} · {plural(project.permit_count, "permit")}
                      </td>
                      <td>
                        {project.overdue_permit_count > 0 ? (
                          <StatusDot tone="danger">
                            {plural(project.overdue_permit_count, "permit")} past statutory period
                          </StatusDot>
                        ) : null}
                        {project.blocking_permit_count > 0 ? (
                          <span className={project.overdue_permit_count > 0 ? "cell-secondary" : undefined}>
                            <StatusDot tone="warning">
                              {plural(project.blocking_permit_count, "blocking permit")}
                            </StatusDot>
                          </span>
                        ) : null}
                        {!flagged ? <span className="muted">—</span> : null}
                      </td>
                      <td className="row-go" aria-hidden="true">
                        <Icon name="chevron" />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </TableScroll>
          )}
        </Card>
      </div>

      {creating ? (
        <Drawer
          narrow
          eyebrow="New record"
          title="New project"
          subtitle="The code is issued once and never changes. Everything else can be edited later."
          onClose={() => setCreating(false)}
        >
          {configurationMissing ? (
            <EmptyState
              icon="settings"
              title="Configure the basis first"
              hint="A project needs an active country pack and an active currency before it can be created. Both are set under Settings."
            />
          ) : (
            <form onSubmit={submit}>
              {formError ? <Notice tone="error">{formError}</Notice> : null}
              <FormSection title="Identity">
                <FieldRow columns={2}>
                  <Field label="Project code" hint="Letters, digits, hyphen or underscore.">
                    <input
                      className="input input-medium"
                      required
                      value={form.code}
                      onChange={(event) => setForm({ ...form, code: event.target.value })}
                    />
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
                <Field label="Name">
                  <input
                    className="input"
                    required
                    value={form.name}
                    onChange={(event) => setForm({ ...form, name: event.target.value })}
                  />
                </Field>
                <FieldRow columns={2}>
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
                </FieldRow>
              </FormSection>

              <FormSection
                title="Financial basis"
                description="Every amount on this project is denominated in its base currency. There is no conversion anywhere."
              >
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
                <FieldRow columns={2}>
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
                <FieldRow columns={2}>
                  <Field label="City" optional>
                    <input
                      className="input"
                      value={form.city}
                      onChange={(event) => setForm({ ...form, city: event.target.value })}
                    />
                  </Field>
                  <Field label="Location" optional hint="A place name, or a map link.">
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
          )}
        </Drawer>
      ) : null}
    </>
  );
}
