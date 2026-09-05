"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, projects, settings } from "@/lib/api";
import type { DocumentReference, LandParcel, PlanningControl, ReferenceValue } from "@/lib/api";
import { businessDate, fractionFromPercent, money, percent, percentInput } from "@/lib/format";
import { sectionDescription } from "@/components/shell/navigation";
import {
  Badge,
  Button,
  Card,
  DataToolbar,
  Drawer,
  EmptyState,
  ExternalLink,
  Field,
  FieldRow,
  FormActions,
  FormSection,
  Icon,
  IdentityCell,
  KeyValue,
  KeyValueGrid,
  Loading,
  Notice,
  PageHeader,
  PlaceCell,
  SectionHeader,
  StatusDot,
  TableScroll,
} from "@/components/ui";
import type { DrawerFact } from "@/components/ui";
import { EditForm, asValue } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";

/** Tri-state: null means nobody has established it yet, which is not "no". */
function utility(value: boolean | null): string {
  if (value === null) return "Not established";
  return value ? "Available" : "Not available";
}

/**
 * The three classifications, the Settings category that suggests each, and the
 * wording that explains what the box is for.
 *
 * Since PR-V2-01 these are text: the register records what the title office
 * and the planning authority wrote, not the nearest entry in a dictionary
 * somebody configured in advance. The categories survive so the interface can
 * offer the usual phrasings — a suggestion the operator may ignore, and never
 * a value the form can refuse. If Settings cannot be reached the datalist is
 * simply empty and the parcel still saves.
 */
const CLASSIFICATIONS = [
  {
    name: "ownership_type",
    label: "Ownership",
    category: "ownership_type",
    hint: "How the parcel is held, in the words the title uses.",
  },
  {
    name: "title_status",
    label: "Title status",
    category: "title_status",
    hint: "Where registration stands today.",
  },
  {
    name: "zoning",
    label: "Zoning",
    category: "zoning_class",
    hint: "The authority's classification as issued. The envelope it permits is recorded under Planning.",
  },
] as const;

function emptyParcel() {
  return {
    plot_number: "",
    land_area: "",
    area_unit: "",
    title_deed_number: "",
    cadastral_reference: "",
    ownership_type: "",
    ownership_share_fraction: "",
    title_status: "",
    zoning: "",
    acquisition_date: "",
    seller: "",
    purchase_price: "",
    acquisition_fees: "",
  };
}

function planningFrom(control: PlanningControl | null) {
  return {
    permitted_uses: control?.permitted_uses ?? "",
    site_coverage_percent: percentInput(control?.site_coverage_rate_fraction ?? null),
    far_ratio: control?.far_ratio ?? "",
    maximum_gfa: control?.maximum_gfa ?? "",
    maximum_floors: control?.maximum_floors?.toString() ?? "",
    maximum_height: control?.maximum_height ?? "",
    front_setback: control?.front_setback ?? "",
    side_setback: control?.side_setback ?? "",
    rear_setback: control?.rear_setback ?? "",
    parking_requirement: control?.parking_requirement ?? "",
    minimum_plot_area: control?.minimum_plot_area ?? "",
    minimum_frontage: control?.minimum_frontage ?? "",
    density: control?.density ?? "",
    exclusions: control?.exclusions ?? "",
    variance_required: control?.variance_required ?? false,
    variance_notes: control?.variance_notes ?? "",
  };
}

/**
 * The parcel fields an ordinary edit may carry.
 *
 * Cost is described only when the caller's own response said they may see it:
 * a caller who receives `financials_visible: false` never had the values, so
 * there is nothing to render and nothing to send back.
 */
function parcelFields(parcel: LandParcel, canSeeCost: boolean): EditField[] {
  const code = parcel.base_currency_code ?? undefined;
  return [
    { name: "plot_number", label: "Plot number", group: "Identity", width: "medium" },
    { name: "title_deed_number", label: "Title deed number", group: "Identity", width: "medium" },
    {
      name: "cadastral_reference",
      label: "Cadastral reference",
      group: "Identity",
      width: "medium",
    },
    {
      name: "land_area",
      label: "Land area",
      kind: "number",
      group: "Identity",
      affix: parcel.area_unit,
    },
    {
      name: "area_unit",
      label: "Area unit",
      kind: "select",
      group: "Identity",
      options: [
        { value: "sqm", label: "sqm" },
        { value: "sqft", label: "sqft" },
      ],
    },
    { name: "ownership_type", label: "Ownership", group: "Tenure", width: "full" },
    {
      name: "ownership_share_fraction",
      label: "Ownership share",
      kind: "number",
      hint: "A fraction of one: 0.500000 is a half share.",
      group: "Tenure",
    },
    { name: "title_status", label: "Title status", group: "Tenure", width: "full" },
    { name: "zoning", label: "Zoning", group: "Tenure", width: "full" },
    { name: "acquisition_date", label: "Acquisition date", kind: "date", group: "Acquisition" },
    { name: "seller", label: "Seller", group: "Acquisition" },
    {
      name: "purchase_price",
      label: "Purchase price",
      kind: "number",
      visible: canSeeCost,
      group: "Acquisition",
      affix: code,
    },
    {
      name: "acquisition_fees",
      label: "Acquisition fees",
      kind: "number",
      visible: canSeeCost,
      group: "Acquisition",
      affix: code,
    },
    { name: "frontage", label: "Frontage", kind: "number", group: "Site" },
    { name: "road_access", label: "Road access", group: "Site" },
    { name: "topography", label: "Topography", group: "Site" },
    { name: "geotechnical_status", label: "Geotechnical status", group: "Site" },
    { name: "contamination_status", label: "Contamination status", group: "Site" },
    { name: "flood_drainage_status", label: "Flood and drainage", group: "Site" },
    { name: "archaeology_heritage_status", label: "Archaeology and heritage", group: "Site" },
    { name: "utility_notes", label: "Utility notes", kind: "textarea", group: "Constraints" },
    { name: "easements", label: "Easements", kind: "textarea", group: "Constraints" },
    { name: "encroachments", label: "Encroachments", kind: "textarea", group: "Constraints" },
    { name: "constraints_notes", label: "Constraints", kind: "textarea", group: "Constraints" },
    { name: "is_active", label: "Parcel is active", kind: "checkbox", group: "Constraints" },
  ];
}

/**
 * The land register, and a parcel opened as the development record it is.
 *
 * The register answers what a director asks walking in: which parcels there
 * are, how each is held, where its title stands and how it is zoned. Everything
 * a surveyor, a lawyer or an engineer needs afterwards lives inside the parcel,
 * because a page that shows forty due-diligence fields for every row answers
 * nobody's question.
 *
 * Planning is read first and edited on intent. The envelope is a standing fact
 * issued by an authority — permitted use, coverage, FAR, height, setbacks — and
 * showing it as a permanently open form said, wrongly, that it is something the
 * project decides. Nothing here computes: no yield, no buildable area, no
 * residual value. The envelope is recorded; feasibility belongs elsewhere.
 */
export function LandTab({
  projectId,
  canWriteLand,
  canWritePlanning,
  canSeeCost,
}: {
  projectId: string;
  canWriteLand: boolean;
  canWritePlanning: boolean;
  /** Mirrors the server's own redaction, so cost is never asked for and hidden. */
  canSeeCost: boolean;
}) {
  const [parcels, setParcels] = useState<LandParcel[] | null>(null);
  const [suggestions, setSuggestions] = useState<ReferenceValue[]>([]);
  const [selected, setSelected] = useState<LandParcel | null>(null);
  const [section, setSection] = useState("overview");
  const [planning, setPlanning] = useState<PlanningControl | null>(null);
  const [planningForm, setPlanningForm] = useState(planningFrom(null));
  const [editingPlanning, setEditingPlanning] = useState(false);
  const [editingParcel, setEditingParcel] = useState(false);
  const [documents, setDocuments] = useState<DocumentReference[] | null>(null);
  const [form, setForm] = useState(emptyParcel());
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setParcels(await projects.parcels(projectId));
      setError(null);
    } catch (caught) {
      setParcels([]);
      setError(caught instanceof ApiError ? caught.message : "Could not load parcels.");
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  useEffect(() => {
    void (async () => {
      try {
        setSuggestions((await settings.referenceValues()).filter((value) => value.is_active));
      } catch {
        // Suggestions only. A parcel records what the title says whether or not
        // Settings can be reached, which is the whole point of the change.
      }
    })();
  }, []);

  const suggestionsFor = (category: string) =>
    suggestions.filter((value) => value.category === category);

  const openParcel = async (parcel: LandParcel) => {
    setSelected(parcel);
    setSection("overview");
    setEditingParcel(false);
    setEditingPlanning(false);
    setNotice(null);
    setPlanning(null);
    setDocuments(null);
    try {
      const control = await projects.planning(projectId, parcel.id);
      setPlanning(control);
      setPlanningForm(planningFrom(control));
    } catch (caught) {
      // No planning recorded yet is an ordinary state, not an error.
      if (caught instanceof ApiError && caught.status === 404) {
        setPlanning(null);
        setPlanningForm(planningFrom(null));
      } else {
        setError("Could not load planning controls.");
      }
    }
    try {
      setDocuments(await projects.documents(projectId, { parcel_id: parcel.id }));
    } catch {
      setDocuments([]);
    }
  };

  const refreshSelected = async (parcelId: string) => {
    const rows = await projects.parcels(projectId);
    setParcels(rows);
    setSelected(rows.find((row) => row.id === parcelId) ?? null);
  };

  const createParcel = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      const payload: Record<string, unknown> = {
        plot_number: form.plot_number,
        land_area: form.land_area,
      };
      for (const key of [
        "area_unit",
        "title_deed_number",
        "cadastral_reference",
        "ownership_type",
        "ownership_share_fraction",
        "title_status",
        "zoning",
        "acquisition_date",
        "seller",
        "purchase_price",
        "acquisition_fees",
      ] as const) {
        if (form[key]) payload[key] = form[key];
      }
      await projects.createParcel(projectId, payload);
      setNotice(`Parcel ${form.plot_number} registered.`);
      setForm(emptyParcel());
      setCreating(false);
      await load();
    } catch (caught) {
      setFormError(caught instanceof ApiError ? caught.message : "Could not register the parcel.");
    } finally {
      setBusy(false);
    }
  };

  const savePlanning = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        variance_required: planningForm.variance_required,
      };
      for (const key of [
        "permitted_uses",
        "far_ratio",
        "maximum_gfa",
        "maximum_height",
        "front_setback",
        "side_setback",
        "rear_setback",
        "parking_requirement",
        "minimum_plot_area",
        "minimum_frontage",
        "density",
        "exclusions",
        "variance_notes",
      ] as const) {
        if (planningForm[key]) payload[key] = planningForm[key];
      }
      if (planningForm.site_coverage_percent) {
        payload.site_coverage_rate_fraction = fractionFromPercent(
          planningForm.site_coverage_percent,
        );
      }
      if (planningForm.maximum_floors) {
        payload.maximum_floors = Number(planningForm.maximum_floors);
      }
      const saved = await projects.writePlanning(projectId, selected.id, payload);
      setPlanning(saved);
      setPlanningForm(planningFrom(saved));
      setEditingPlanning(false);
      setNotice("Planning envelope recorded.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save planning controls.");
    } finally {
      setBusy(false);
    }
  };

  const needle = search.trim().toLowerCase();
  const rows = (parcels ?? []).filter(
    (parcel) =>
      !needle ||
      `${parcel.plot_number} ${parcel.title_deed_number ?? ""} ${parcel.zoning ?? ""} ${
        parcel.title_status ?? ""
      } ${parcel.ownership_type ?? ""}`
        .toLowerCase()
        .includes(needle),
  );

  const facts: DrawerFact[] = selected
    ? [
        {
          label: "Ownership share",
          value: selected.ownership_share_fraction
            ? percent(selected.ownership_share_fraction)
            : "Whole parcel",
        },
        { label: "Acquired", value: businessDate(selected.acquisition_date) ?? "Not recorded" },
        ...(selected.financials_visible
          ? [
              {
                label: "Purchase price",
                value: selected.purchase_price
                  ? money(selected.purchase_price, selected.base_currency_code)
                  : "Not recorded",
                note: "Acquisition consideration, not market value",
              },
              {
                label: "Acquisition fees",
                value: selected.acquisition_fees
                  ? money(selected.acquisition_fees, selected.base_currency_code)
                  : "Not recorded",
              },
            ]
          : []),
      ]
    : [];

  return (
    <>
      <PageHeader
        title="Land"
        subtitle={sectionDescription("land")}
        compact
        actions={
          canWriteLand ? (
            <Button variant="primary" onClick={() => setCreating(true)}>
              New parcel
            </Button>
          ) : undefined
        }
      />

      <div className="stack">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}

        <DataToolbar
          framed
          search={{
            value: search,
            onChange: setSearch,
            placeholder: "Plot, deed, zoning or title status",
            label: "Search parcels",
          }}
          count={parcels ? { shown: rows.length, total: parcels.length, noun: "parcel" } : undefined}
          onReset={search ? () => setSearch("") : undefined}
        />

        <Card flush>
          {parcels === null ? (
            <Loading label="Loading the land register…" shape="rows" rows={5} />
          ) : rows.length === 0 ? (
            <div className="card-body">
              <EmptyState
                icon="land"
                title={search ? "No parcel matches" : "No land registered yet"}
                hint={
                  search
                    ? "Widen the search to see the rest of the register."
                    : "Register the parcels this development sits on. Title, ownership and zoning are recorded in the words the documents use — there is no list to pick from."
                }
                actions={
                  canWriteLand && !search ? (
                    <Button variant="primary" onClick={() => setCreating(true)}>
                      New parcel
                    </Button>
                  ) : undefined
                }
              />
            </div>
          ) : (
            <TableScroll label="Land register" fixedFirst>
              <thead>
                <tr>
                  <th scope="col">Parcel</th>
                  <th scope="col">Ownership</th>
                  <th scope="col">Title status</th>
                  <th scope="col">Zoning</th>
                  <th scope="col" className="num">
                    Area
                  </th>
                  <th scope="col">Acquired</th>
                  {canSeeCost ? (
                    <th scope="col" className="num">
                      Purchase price
                    </th>
                  ) : null}
                  <th scope="col">State</th>
                  <th scope="col">
                    <span className="visually-hidden">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((parcel) => (
                  <tr key={parcel.id} aria-selected={selected?.id === parcel.id}>
                    <th scope="row">
                      <button
                        className="button-link"
                        type="button"
                        onClick={() => void openParcel(parcel)}
                      >
                        <IdentityCell
                          name={parcel.plot_number}
                          meta={
                            parcel.title_deed_number
                              ? `Deed ${parcel.title_deed_number}`
                              : "No deed recorded"
                          }
                        />
                      </button>
                    </th>
                    {/* The three classifications are free text now, so they
                        wrap and are bounded: one parcel whose ownership runs
                        to a sentence must not push the figures off the
                        register for every other row. */}
                    <td className="cell-prose cell-prose-tight">
                      <PlaceCell
                        main={parcel.ownership_type ?? "Not established"}
                        sub={
                          parcel.ownership_share_fraction
                            ? `${percent(parcel.ownership_share_fraction)} share`
                            : undefined
                        }
                      />
                    </td>
                    <td className="cell-prose cell-prose-tight">
                      {parcel.title_status ?? <span className="muted">Not established</span>}
                    </td>
                    <td className="cell-prose cell-prose-tight">
                      {parcel.zoning ?? <span className="muted">Not established</span>}
                    </td>
                    <td className="num">
                      {parcel.land_area}
                      <span className="cell-secondary">{parcel.area_unit}</span>
                    </td>
                    <td className="figure">{businessDate(parcel.acquisition_date)}</td>
                    {canSeeCost ? (
                      <td className="num">
                        {parcel.purchase_price
                          ? money(parcel.purchase_price, parcel.base_currency_code)
                          : "—"}
                      </td>
                    ) : null}
                    <td>
                      {parcel.is_active ? (
                        <StatusDot tone="success">Active</StatusDot>
                      ) : (
                        <StatusDot tone="muted">Inactive</StatusDot>
                      )}
                    </td>
                    <td className="row-go" aria-hidden="true">
                      <Icon name="chevron" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </TableScroll>
          )}
        </Card>
      </div>

      {creating ? (
        <Drawer
          narrow
          eyebrow="New record"
          title="Register a parcel"
          subtitle="The opening facts. Site diligence, utilities and planning are recorded on the parcel afterwards."
          onClose={() => setCreating(false)}
        >
          <form onSubmit={createParcel}>
            {formError ? <Notice tone="error">{formError}</Notice> : null}
            <FormSection title="Identity">
              <FieldRow columns={2}>
                <Field label="Plot number">
                  <input
                    className="input input-medium"
                    required
                    maxLength={64}
                    value={form.plot_number}
                    onChange={(event) => setForm({ ...form, plot_number: event.target.value })}
                  />
                </Field>
                <Field label="Title deed number" optional>
                  <input
                    className="input"
                    maxLength={120}
                    value={form.title_deed_number}
                    onChange={(event) =>
                      setForm({ ...form, title_deed_number: event.target.value })
                    }
                  />
                </Field>
                <Field label="Land area">
                  <input
                    className="input input-short"
                    required
                    inputMode="decimal"
                    value={form.land_area}
                    onChange={(event) => setForm({ ...form, land_area: event.target.value })}
                  />
                </Field>
                <Field label="Area unit" optional hint="Defaults to the jurisdiction's unit.">
                  <select
                    className="input input-short"
                    value={form.area_unit}
                    onChange={(event) => setForm({ ...form, area_unit: event.target.value })}
                  >
                    <option value="">From the country pack</option>
                    <option value="sqm">sqm</option>
                    <option value="sqft">sqft</option>
                  </select>
                </Field>
                <Field label="Cadastral reference" optional>
                  <input
                    className="input"
                    maxLength={120}
                    value={form.cadastral_reference}
                    onChange={(event) =>
                      setForm({ ...form, cadastral_reference: event.target.value })
                    }
                  />
                </Field>
              </FieldRow>
            </FormSection>

            <FormSection
              title="Tenure and planning identity"
              description="Recorded in the words the title and the planning decision use. The lists only suggest."
            >
              {CLASSIFICATIONS.map((classification) => (
                <Field
                  key={classification.name}
                  label={classification.label}
                  optional
                  hint={classification.hint}
                >
                  <input
                    className="input"
                    maxLength={500}
                    list={`land-${classification.name}`}
                    value={form[classification.name]}
                    onChange={(event) =>
                      setForm({ ...form, [classification.name]: event.target.value })
                    }
                  />
                </Field>
              ))}
              <Field
                label="Ownership share"
                optional
                hint="A fraction of one: 0.500000 is a half share. Leave empty for the whole parcel."
              >
                <input
                  className="input input-short"
                  inputMode="decimal"
                  value={form.ownership_share_fraction}
                  onChange={(event) =>
                    setForm({ ...form, ownership_share_fraction: event.target.value })
                  }
                />
              </Field>
            </FormSection>

            <FormSection
              title="Acquisition"
              description={
                canSeeCost
                  ? "What was paid for the land, not what it is worth today."
                  : "Consideration is recorded by the roles cleared to see development cost."
              }
            >
              <FieldRow columns={2}>
                <Field label="Acquisition date" optional>
                  <input
                    className="input input-short"
                    type="date"
                    value={form.acquisition_date}
                    onChange={(event) => setForm({ ...form, acquisition_date: event.target.value })}
                  />
                </Field>
                <Field label="Seller" optional>
                  <input
                    className="input"
                    maxLength={200}
                    value={form.seller}
                    onChange={(event) => setForm({ ...form, seller: event.target.value })}
                  />
                </Field>
                {canSeeCost ? (
                  <>
                    <Field label="Purchase price" optional>
                      <input
                        className="input input-medium"
                        inputMode="decimal"
                        value={form.purchase_price}
                        onChange={(event) =>
                          setForm({ ...form, purchase_price: event.target.value })
                        }
                      />
                    </Field>
                    <Field label="Acquisition fees" optional>
                      <input
                        className="input input-medium"
                        inputMode="decimal"
                        value={form.acquisition_fees}
                        onChange={(event) =>
                          setForm({ ...form, acquisition_fees: event.target.value })
                        }
                      />
                    </Field>
                  </>
                ) : null}
              </FieldRow>
            </FormSection>

            <FormActions>
              <Button variant="primary" type="submit" disabled={busy}>
                {busy ? "Registering…" : "Register parcel"}
              </Button>
              <Button onClick={() => setCreating(false)} disabled={busy}>
                Cancel
              </Button>
            </FormActions>
          </form>
        </Drawer>
      ) : null}

      {/* One datalist per classification, rendered once for whichever form is
          open. Native suggestions: they cost no dependency, they never filter
          what may be typed, and a browser that ignores them changes nothing. */}
      {CLASSIFICATIONS.map((classification) => (
        <datalist key={classification.name} id={`land-${classification.name}`}>
          {suggestionsFor(classification.category).map((value) => (
            <option key={value.id} value={value.label} />
          ))}
        </datalist>
      ))}

      {selected ? (
        <Drawer
          eyebrow="Parcel"
          title={selected.plot_number}
          subtitle={
            [selected.zoning, selected.title_status].filter(Boolean).join(" · ") ||
            "Classification not yet established"
          }
          meta={
            <>
              {selected.is_active ? (
                <Badge tone="success">Active</Badge>
              ) : (
                <Badge tone="muted">Inactive</Badge>
              )}
              {planning?.variance_required ? (
                <Badge tone="warning">Variance required</Badge>
              ) : null}
              {selected.ownership_share_fraction ? (
                <StatusDot tone="info">
                  {percent(selected.ownership_share_fraction)} share
                </StatusDot>
              ) : null}
            </>
          }
          headline={{
            value: `${selected.land_area} ${selected.area_unit}`,
            label: "Land area, as recorded",
          }}
          facts={facts}
          actions={
            canWriteLand ? (
              <Button onClick={() => setEditingParcel((open) => !open)}>
                {editingParcel ? "Stop editing" : "Edit parcel"}
              </Button>
            ) : undefined
          }
          tabs={[
            { key: "overview", label: "Overview" },
            { key: "planning", label: "Planning" },
            { key: "site", label: "Site & utilities" },
            { key: "documents", label: "Documents" },
          ]}
          activeTab={section}
          onSelectTab={setSection}
          onClose={() => setSelected(null)}
        >
          {editingParcel ? (
            <Card title="Edit parcel">
              <EditForm
                fields={parcelFields(selected, selected.financials_visible)}
                columns={3}
                initial={Object.fromEntries(
                  parcelFields(selected, selected.financials_visible).map((field) => [
                    field.name,
                    asValue(selected[field.name as keyof LandParcel] as never),
                  ]),
                )}
                onSave={async (changes) => {
                  await projects.updateParcel(projectId, selected.id, changes);
                  await refreshSelected(selected.id);
                  setEditingParcel(false);
                  setNotice("Parcel updated.");
                }}
                onCancel={() => setEditingParcel(false)}
              />
            </Card>
          ) : null}

          {section === "overview" ? (
            <>
              <section>
                <SectionHeader title="Tenure" />
                <KeyValueGrid columns={3}>
                  <KeyValue label="Ownership" value={selected.ownership_type} />
                  <KeyValue
                    label="Ownership share"
                    value={
                      selected.ownership_share_fraction
                        ? percent(selected.ownership_share_fraction)
                        : "Whole parcel"
                    }
                  />
                  <KeyValue label="Title status" value={selected.title_status} />
                  <KeyValue label="Zoning" value={selected.zoning} />
                  <KeyValue label="Title deed" mono value={selected.title_deed_number} />
                  <KeyValue label="Cadastral reference" mono value={selected.cadastral_reference} />
                </KeyValueGrid>
              </section>
              <section>
                <SectionHeader
                  title="Acquisition"
                  description={
                    selected.financials_visible
                      ? "What the land cost to acquire. Not a valuation."
                      : undefined
                  }
                />
                <KeyValueGrid columns={3}>
                  <KeyValue
                    label="Acquisition date"
                    mono
                    value={businessDate(selected.acquisition_date)}
                  />
                  <KeyValue label="Seller" value={selected.seller} />
                  {selected.financials_visible ? (
                    <>
                      <KeyValue
                        label="Purchase price"
                        value={
                          selected.purchase_price
                            ? money(selected.purchase_price, selected.base_currency_code)
                            : null
                        }
                      />
                      <KeyValue
                        label="Acquisition fees"
                        value={
                          selected.acquisition_fees
                            ? money(selected.acquisition_fees, selected.base_currency_code)
                            : null
                        }
                      />
                    </>
                  ) : null}
                </KeyValueGrid>
                {selected.financials_visible ? null : (
                  <p className="footnote">
                    Development cost is shown to the roles cleared for it. This record is complete
                    otherwise.
                  </p>
                )}
              </section>
            </>
          ) : null}

          {section === "planning" ? (
            <section>
              <SectionHeader
                title="Planning envelope"
                description="What the authority permits on this parcel. Zoning says what it is classified as; this says what may be built."
                actions={
                  canWritePlanning ? (
                    <Button onClick={() => setEditingPlanning((open) => !open)}>
                      {editingPlanning ? "Stop editing" : planning ? "Edit planning" : "Record planning"}
                    </Button>
                  ) : undefined
                }
              />
              {planning === null && !editingPlanning ? (
                <EmptyState
                  compact
                  icon="permits"
                  title="No planning envelope recorded"
                  hint="Coverage, floor area ratio, height and setbacks come from the planning decision for this parcel. Until they are recorded, nothing downstream can rely on them."
                  actions={
                    canWritePlanning ? (
                      <Button onClick={() => setEditingPlanning(true)}>Record planning</Button>
                    ) : undefined
                  }
                />
              ) : null}

              {planning && !editingPlanning ? (
                <>
                  <KeyValueGrid columns={3}>
                    <KeyValue label="Permitted uses" value={planning.permitted_uses} />
                    <KeyValue
                      label="Site coverage"
                      value={
                        planning.site_coverage_rate_fraction
                          ? percent(planning.site_coverage_rate_fraction)
                          : null
                      }
                    />
                    <KeyValue label="Floor area ratio" value={planning.far_ratio} />
                    <KeyValue label="Maximum GFA" value={planning.maximum_gfa} />
                    <KeyValue
                      label="Maximum floors"
                      value={planning.maximum_floors?.toString() ?? null}
                    />
                    <KeyValue label="Maximum height" value={planning.maximum_height} />
                    <KeyValue label="Front setback" value={planning.front_setback} />
                    <KeyValue label="Side setback" value={planning.side_setback} />
                    <KeyValue label="Rear setback" value={planning.rear_setback} />
                    <KeyValue label="Minimum plot area" value={planning.minimum_plot_area} />
                    <KeyValue label="Minimum frontage" value={planning.minimum_frontage} />
                    <KeyValue label="Density" value={planning.density} />
                  </KeyValueGrid>
                  {planning.parking_requirement ? (
                    <>
                      <SectionHeader title="Parking" />
                      <p className="subtle">{planning.parking_requirement}</p>
                    </>
                  ) : null}
                  {planning.exclusions ? (
                    <>
                      <SectionHeader title="Exclusions" />
                      <p className="subtle">{planning.exclusions}</p>
                    </>
                  ) : null}
                  <SectionHeader title="Variance" />
                  {planning.variance_required ? (
                    <Notice tone="warning">
                      A variance is required for the intended scheme.
                      {planning.variance_notes ? ` ${planning.variance_notes}` : ""}
                    </Notice>
                  ) : (
                    <p className="subtle">
                      <StatusDot tone="success">Not required</StatusDot>
                    </p>
                  )}
                  <p className="footnote">
                    These are the controls as issued. Nothing here is multiplied out into a
                    buildable area or a yield: development capacity is a feasibility question, and
                    this is the authority record it would be based on.
                  </p>
                </>
              ) : null}

              {editingPlanning ? (
                <form onSubmit={savePlanning}>
                  <FormSection
                    title="Envelope"
                    description="The whole envelope is written at once: a half-updated set would describe a planning position no authority granted."
                  >
                    <Field label="Permitted uses" optional>
                      <input
                        className="input"
                        maxLength={2000}
                        value={planningForm.permitted_uses}
                        onChange={(event) =>
                          setPlanningForm({ ...planningForm, permitted_uses: event.target.value })
                        }
                      />
                    </Field>
                    <FieldRow columns={3}>
                      <Field label="Site coverage" optional>
                        <input
                          className="input input-short"
                          inputMode="decimal"
                          value={planningForm.site_coverage_percent}
                          onChange={(event) =>
                            setPlanningForm({
                              ...planningForm,
                              site_coverage_percent: event.target.value,
                            })
                          }
                        />
                      </Field>
                      <Field label="Floor area ratio" optional>
                        <input
                          className="input input-short"
                          inputMode="decimal"
                          value={planningForm.far_ratio}
                          onChange={(event) =>
                            setPlanningForm({ ...planningForm, far_ratio: event.target.value })
                          }
                        />
                      </Field>
                      <Field label="Maximum GFA" optional>
                        <input
                          className="input input-short"
                          inputMode="decimal"
                          value={planningForm.maximum_gfa}
                          onChange={(event) =>
                            setPlanningForm({ ...planningForm, maximum_gfa: event.target.value })
                          }
                        />
                      </Field>
                      <Field label="Maximum floors" optional>
                        <input
                          className="input input-short"
                          inputMode="numeric"
                          value={planningForm.maximum_floors}
                          onChange={(event) =>
                            setPlanningForm({ ...planningForm, maximum_floors: event.target.value })
                          }
                        />
                      </Field>
                      <Field label="Maximum height" optional>
                        <input
                          className="input input-short"
                          inputMode="decimal"
                          value={planningForm.maximum_height}
                          onChange={(event) =>
                            setPlanningForm({ ...planningForm, maximum_height: event.target.value })
                          }
                        />
                      </Field>
                      <Field label="Density" optional>
                        <input
                          className="input input-short"
                          inputMode="decimal"
                          value={planningForm.density}
                          onChange={(event) =>
                            setPlanningForm({ ...planningForm, density: event.target.value })
                          }
                        />
                      </Field>
                    </FieldRow>
                  </FormSection>
                  <FormSection title="Setbacks and minimums">
                    <FieldRow columns={3}>
                      <Field label="Front setback" optional>
                        <input
                          className="input input-short"
                          inputMode="decimal"
                          value={planningForm.front_setback}
                          onChange={(event) =>
                            setPlanningForm({ ...planningForm, front_setback: event.target.value })
                          }
                        />
                      </Field>
                      <Field label="Side setback" optional>
                        <input
                          className="input input-short"
                          inputMode="decimal"
                          value={planningForm.side_setback}
                          onChange={(event) =>
                            setPlanningForm({ ...planningForm, side_setback: event.target.value })
                          }
                        />
                      </Field>
                      <Field label="Rear setback" optional>
                        <input
                          className="input input-short"
                          inputMode="decimal"
                          value={planningForm.rear_setback}
                          onChange={(event) =>
                            setPlanningForm({ ...planningForm, rear_setback: event.target.value })
                          }
                        />
                      </Field>
                      <Field label="Minimum plot area" optional>
                        <input
                          className="input input-short"
                          inputMode="decimal"
                          value={planningForm.minimum_plot_area}
                          onChange={(event) =>
                            setPlanningForm({
                              ...planningForm,
                              minimum_plot_area: event.target.value,
                            })
                          }
                        />
                      </Field>
                      <Field label="Minimum frontage" optional>
                        <input
                          className="input input-short"
                          inputMode="decimal"
                          value={planningForm.minimum_frontage}
                          onChange={(event) =>
                            setPlanningForm({
                              ...planningForm,
                              minimum_frontage: event.target.value,
                            })
                          }
                        />
                      </Field>
                    </FieldRow>
                    <Field label="Parking requirement" optional hint="The rule as written, not a number.">
                      <input
                        className="input"
                        maxLength={500}
                        value={planningForm.parking_requirement}
                        onChange={(event) =>
                          setPlanningForm({
                            ...planningForm,
                            parking_requirement: event.target.value,
                          })
                        }
                      />
                    </Field>
                  </FormSection>
                  <FormSection title="Variance and exclusions">
                    <label className="checkbox">
                      <input
                        type="checkbox"
                        checked={planningForm.variance_required}
                        onChange={(event) =>
                          setPlanningForm({
                            ...planningForm,
                            variance_required: event.target.checked,
                          })
                        }
                      />
                      <span>A variance is required for the intended scheme</span>
                    </label>
                    <Field label="Variance notes" optional>
                      <textarea
                        className="input"
                        maxLength={2000}
                        value={planningForm.variance_notes}
                        onChange={(event) =>
                          setPlanningForm({ ...planningForm, variance_notes: event.target.value })
                        }
                      />
                    </Field>
                    <Field label="Exclusions" optional>
                      <textarea
                        className="input"
                        maxLength={2000}
                        value={planningForm.exclusions}
                        onChange={(event) =>
                          setPlanningForm({ ...planningForm, exclusions: event.target.value })
                        }
                      />
                    </Field>
                  </FormSection>
                  <FormActions>
                    <Button variant="primary" type="submit" disabled={busy}>
                      {busy ? "Saving…" : "Save planning envelope"}
                    </Button>
                    <Button onClick={() => setEditingPlanning(false)} disabled={busy}>
                      Cancel
                    </Button>
                  </FormActions>
                </form>
              ) : null}
            </section>
          ) : null}

          {section === "site" ? (
            <>
              <section>
                <SectionHeader title="Site" />
                <KeyValueGrid columns={2}>
                  <KeyValue label="Frontage" value={selected.frontage} />
                  <KeyValue label="Road access" value={selected.road_access} />
                  <KeyValue label="Topography" value={selected.topography} />
                  <KeyValue label="Geotechnical" value={selected.geotechnical_status} />
                  <KeyValue label="Contamination" value={selected.contamination_status} />
                  <KeyValue label="Flood and drainage" value={selected.flood_drainage_status} />
                  <KeyValue
                    label="Archaeology and heritage"
                    value={selected.archaeology_heritage_status}
                  />
                </KeyValueGrid>
              </section>
              <section>
                <SectionHeader
                  title="Utilities"
                  description="Not established is a different answer from not available."
                />
                <KeyValueGrid columns={3}>
                  <KeyValue label="Power" value={utility(selected.power_available)} />
                  <KeyValue label="Water" value={utility(selected.water_available)} />
                  <KeyValue label="Sewer" value={utility(selected.sewer_available)} />
                  <KeyValue label="Stormwater" value={utility(selected.stormwater_available)} />
                  <KeyValue label="Telecom" value={utility(selected.telecom_available)} />
                </KeyValueGrid>
                {selected.utility_notes ? <p className="footnote">{selected.utility_notes}</p> : null}
              </section>
              <section>
                <SectionHeader title="Encumbrances" />
                <KeyValueGrid columns={2}>
                  <KeyValue label="Easements" value={selected.easements} />
                  <KeyValue label="Encroachments" value={selected.encroachments} />
                  <KeyValue label="Constraints" value={selected.constraints_notes} />
                </KeyValueGrid>
              </section>
            </>
          ) : null}

          {section === "documents" ? (
            <section>
              <SectionHeader
                title="Documents"
                description="Where this parcel's papers live. The register records the reference; it does not hold the file."
              />
              {documents === null ? (
                <Loading label="Loading documents…" shape="rows" rows={3} />
              ) : documents.length === 0 ? (
                <EmptyState
                  compact
                  icon="documents"
                  title="No document recorded for this parcel"
                  hint="Title deeds, survey reports and planning decisions are referenced from the project's Documents section."
                />
              ) : (
                <TableScroll label="Parcel documents" compact>
                  <thead>
                    <tr>
                      <th scope="col">Document</th>
                      <th scope="col">Type</th>
                      <th scope="col">Reference</th>
                      <th scope="col">Where</th>
                    </tr>
                  </thead>
                  <tbody>
                    {documents.map((document) => (
                      <tr key={document.id}>
                        <th scope="row">{document.title}</th>
                        <td>{document.document_type_code}</td>
                        <td className="mono">{document.reference_number ?? "—"}</td>
                        <td>
                          <ExternalLink href={document.external_url}>Open</ExternalLink>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </TableScroll>
              )}
            </section>
          ) : null}
        </Drawer>
      ) : null}
    </>
  );
}
