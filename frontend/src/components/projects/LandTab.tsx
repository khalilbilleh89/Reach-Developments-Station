"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, projects, settings } from "@/lib/api";
import type { LandParcel, PlanningControl, ReferenceValue } from "@/lib/api";
import { businessDate, fractionFromPercent, money, percent, percentInput } from "@/lib/format";
import { sectionDescription } from "@/components/shell/navigation";
import {
  Button,
  Card,
  EmptyState,
  Field,
  FieldRow,
  FormActions,
  FormSection,
  KeyValue,
  KeyValueGrid,
  Loading,
  Metric,
  MetricGroup,
  MoneyInput,
  Notice,
  PageHeader,
  RateInput,
  StatusDot,
  TableScroll,
} from "@/components/ui";
import { EditForm, asValue } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";

/** Tri-state: null means nobody has established it yet, which is not "no". */
function utility(value: boolean | null): string {
  if (value === null) return "Not established";
  return value ? "Available" : "Not available";
}

function emptyParcel() {
  return {
    plot_number: "",
    land_area: "",
    area_unit: "",
    title_deed_number: "",
    ownership_type_code: "",
    title_status_code: "",
    zoning_class_code: "",
    purchase_price: "",
    acquisition_fees: "",
  };
}

function emptyPlanning() {
  return {
    permitted_uses: "",
    site_coverage_percent: "",
    far_ratio: "",
    maximum_gfa: "",
    maximum_floors: "",
    maximum_height: "",
    front_setback: "",
    side_setback: "",
    rear_setback: "",
    parking_requirement: "",
    variance_required: false,
    variance_notes: "",
  };
}

/**
 * The parcel fields the API accepts on update.
 *
 * Cost is described only when the caller's own response said they may see it:
 * a caller who receives `financials_visible: false` never had the values, so
 * there is nothing to render and nothing to send back.
 */
function parcelFields(parcel: LandParcel, canSeeCost: boolean): EditField[] {
  const code = parcel.base_currency_code ?? undefined;
  return [
    { name: "plot_number", label: "Plot number", group: "Parcel", width: "medium" },
    { name: "title_deed_number", label: "Title deed number", group: "Parcel", width: "medium" },
    { name: "cadastral_reference", label: "Cadastral reference", group: "Parcel", width: "medium" },
    { name: "land_area", label: "Land area", kind: "number", group: "Parcel", affix: parcel.area_unit },
    {
      name: "area_unit",
      label: "Area unit",
      kind: "select",
      group: "Parcel",
      options: [
        { value: "sqm", label: "sqm" },
        { value: "sqft", label: "sqft" },
      ],
    },
    { name: "ownership_type_code", label: "Ownership type", group: "Tenure", width: "medium" },
    {
      name: "ownership_share_fraction",
      label: "Ownership share",
      kind: "number",
      hint: "A fraction of one: 0.500000 is a half share.",
      group: "Tenure",
    },
    { name: "acquisition_date", label: "Acquisition date", kind: "date", group: "Tenure" },
    { name: "seller", label: "Seller", group: "Tenure" },
    { name: "title_status_code", label: "Title status", group: "Tenure", width: "medium" },
    { name: "zoning_class_code", label: "Zoning class", group: "Tenure", width: "medium" },
    { name: "purchase_price", label: "Purchase price", kind: "number", group: "Consideration", visible: canSeeCost, affix: code },
    { name: "acquisition_fees", label: "Acquisition fees", kind: "number", group: "Consideration", visible: canSeeCost, affix: code },
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
 * The land register and, for the selected parcel, its due diligence.
 *
 * Planning belongs to a parcel, so it lives beside the parcel it governs
 * rather than on a disconnected page of its own. The consideration — what
 * the land cost — is shown only to the roles the server cleared, and it is
 * the register's figure that the unit economics land pool later draws on.
 */
export function LandTab({
  projectId,
  baseCurrencyCode,
  canWriteLand,
  canWritePlanning,
}: {
  projectId: string;
  baseCurrencyCode: string | null;
  canWriteLand: boolean;
  canWritePlanning: boolean;
}) {
  const [parcels, setParcels] = useState<LandParcel[] | null>(null);
  const [references, setReferences] = useState<ReferenceValue[]>([]);
  const [selected, setSelected] = useState<LandParcel | null>(null);
  const [planning, setPlanning] = useState<PlanningControl | null>(null);
  const [planningForm, setPlanningForm] = useState(emptyPlanning());
  const [form, setForm] = useState(emptyParcel());
  const [creating, setCreating] = useState(false);
  const [editingParcel, setEditingParcel] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
        setReferences((await settings.referenceValues()).filter((value) => value.is_active));
      } catch {
        // Only the forms need these; the register reads without them.
      }
    })();
  }, []);

  const optionsFor = (category: string) => references.filter((value) => value.category === category);
  const labelFor = (category: string, code: string | null) =>
    code ? (optionsFor(category).find((value) => value.code === code)?.label ?? code) : null;

  const open = async (parcel: LandParcel) => {
    setSelected(parcel);
    setEditingParcel(false);
    setNotice(null);
    try {
      const control = await projects.planning(projectId, parcel.id);
      setPlanning(control);
      setPlanningForm({
        permitted_uses: control.permitted_uses ?? "",
        site_coverage_percent: percentInput(control.site_coverage_rate_fraction),
        far_ratio: control.far_ratio ?? "",
        maximum_gfa: control.maximum_gfa ?? "",
        maximum_floors: control.maximum_floors?.toString() ?? "",
        maximum_height: control.maximum_height ?? "",
        front_setback: control.front_setback ?? "",
        side_setback: control.side_setback ?? "",
        rear_setback: control.rear_setback ?? "",
        parking_requirement: control.parking_requirement ?? "",
        variance_required: control.variance_required,
        variance_notes: control.variance_notes ?? "",
      });
    } catch (caught) {
      // No planning recorded yet is an ordinary state, not an error.
      if (caught instanceof ApiError && caught.status === 404) {
        setPlanning(null);
        setPlanningForm(emptyPlanning());
      } else {
        setError("Could not load planning controls.");
      }
    }
  };

  const createParcel = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        plot_number: form.plot_number,
        land_area: form.land_area,
      };
      for (const key of [
        "area_unit",
        "title_deed_number",
        "ownership_type_code",
        "title_status_code",
        "zoning_class_code",
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
      setError(caught instanceof ApiError ? caught.message : "Could not register the parcel.");
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
        "variance_notes",
      ] as const) {
        if (planningForm[key]) payload[key] = planningForm[key];
      }
      if (planningForm.site_coverage_percent) {
        payload.site_coverage_rate_fraction = fractionFromPercent(planningForm.site_coverage_percent);
      }
      if (planningForm.maximum_floors) {
        payload.maximum_floors = Number(planningForm.maximum_floors);
      }
      setPlanning(await projects.writePlanning(projectId, selected.id, payload));
      setNotice("Planning controls saved.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save planning controls.");
    } finally {
      setBusy(false);
    }
  };

  const seesCost = parcels?.some((parcel) => parcel.financials_visible) ?? false;
  const areaUnit = parcels?.[0]?.area_unit ?? "sqm";

  return (
    <>
      <PageHeader
        title="Land"
        subtitle={sectionDescription("land")}
        compact
        actions={
          canWriteLand ? (
            <Button variant="primary" onClick={() => setCreating((open) => !open)}>
              {creating ? "Cancel" : "New parcel"}
            </Button>
          ) : undefined
        }
      />

      <div className="stack">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}

        {creating ? (
          <Card title="Register a parcel" description="The plot, its tenure, and what was paid for it. Everything else is added from the parcel's own file.">
            <form onSubmit={createParcel}>
              <FormSection title="Parcel">
                <FieldRow columns={3}>
                  <Field label="Plot number">
                    <input
                      className="input input-medium"
                      required
                      value={form.plot_number}
                      onChange={(event) => setForm({ ...form, plot_number: event.target.value })}
                    />
                  </Field>
                  <Field label="Land area">
                    <span className="input-shell input-shell-money">
                      <input
                        className="input"
                        inputMode="decimal"
                        required
                        value={form.land_area}
                        onChange={(event) => setForm({ ...form, land_area: event.target.value })}
                      />
                      <span className="input-affix" aria-hidden="true">
                        {form.area_unit || areaUnit}
                      </span>
                    </span>
                  </Field>
                  <Field label="Area unit" hint="Defaults to the country pack's unit.">
                    <select
                      className="input input-short"
                      value={form.area_unit}
                      onChange={(event) => setForm({ ...form, area_unit: event.target.value })}
                    >
                      <option value="">Country default</option>
                      <option value="sqm">sqm</option>
                      <option value="sqft">sqft</option>
                    </select>
                  </Field>
                </FieldRow>
              </FormSection>
              <FormSection title="Tenure">
                <FieldRow columns={4}>
                  <Field label="Title deed number" optional>
                    <input
                      className="input"
                      value={form.title_deed_number}
                      onChange={(event) => setForm({ ...form, title_deed_number: event.target.value })}
                    />
                  </Field>
                  {(
                    [
                      ["ownership_type_code", "Ownership type", "ownership_type"],
                      ["title_status_code", "Title status", "title_status"],
                      ["zoning_class_code", "Zoning class", "zoning_class"],
                    ] as const
                  ).map(([key, label, category]) => (
                    <Field key={key} label={label} optional>
                      <select
                        className="input"
                        value={form[key]}
                        onChange={(event) => setForm({ ...form, [key]: event.target.value })}
                      >
                        <option value="">Not set</option>
                        {optionsFor(category).map((value) => (
                          <option key={value.id} value={value.code}>
                            {value.label}
                          </option>
                        ))}
                      </select>
                    </Field>
                  ))}
                </FieldRow>
              </FormSection>
              <FormSection
                title="Consideration"
                description="In the project's base currency. Visible only to the roles cleared to see development cost."
              >
                <FieldRow columns={3}>
                  <Field label="Purchase price" optional>
                    <MoneyInput
                      code={baseCurrencyCode}
                      value={form.purchase_price}
                      onChange={(value) => setForm({ ...form, purchase_price: value })}
                    />
                  </Field>
                  <Field label="Acquisition fees" optional>
                    <MoneyInput
                      code={baseCurrencyCode}
                      value={form.acquisition_fees}
                      onChange={(value) => setForm({ ...form, acquisition_fees: value })}
                    />
                  </Field>
                </FieldRow>
              </FormSection>
              <FormActions>
                <Button variant="primary" type="submit" disabled={busy}>
                  {busy ? "Saving…" : "Register parcel"}
                </Button>
                <Button onClick={() => setCreating(false)} disabled={busy}>
                  Cancel
                </Button>
              </FormActions>
            </form>
          </Card>
        ) : null}

        <Card flush>
          {parcels === null ? (
            <Loading label="Loading parcels…" shape="rows" rows={3} />
          ) : parcels.length === 0 ? (
            <div className="card-body">
              <EmptyState
                title="No parcels registered"
                hint="Record the land this development controls. The land cost recorded here is what the unit economics land pool draws on."
              />
            </div>
          ) : (
            <TableScroll label="Land parcels" fixedFirst>
              <thead>
                <tr>
                  <th scope="col">Plot</th>
                  <th scope="col">Title deed</th>
                  <th scope="col" className="num">
                    Area
                  </th>
                  <th scope="col">Ownership</th>
                  <th scope="col">Title status</th>
                  <th scope="col">Zoning</th>
                  {seesCost ? (
                    <th scope="col" className="num">
                      Purchase price
                    </th>
                  ) : null}
                  {seesCost ? (
                    <th scope="col" className="num">
                      Acquisition fees
                    </th>
                  ) : null}
                  <th scope="col">State</th>
                </tr>
              </thead>
              <tbody>
                {parcels.map((parcel) => (
                  <tr key={parcel.id}>
                    <th scope="row">
                      <button
                        className="button-link mono"
                        type="button"
                        aria-expanded={selected?.id === parcel.id}
                        onClick={() => void open(parcel)}
                      >
                        {parcel.plot_number}
                      </button>
                    </th>
                    <td className="mono">{parcel.title_deed_number ?? "—"}</td>
                    <td className="num">
                      {parcel.land_area} {parcel.area_unit}
                    </td>
                    <td>{labelFor("ownership_type", parcel.ownership_type_code) ?? "—"}</td>
                    <td>{labelFor("title_status", parcel.title_status_code) ?? "—"}</td>
                    <td>{labelFor("zoning_class", parcel.zoning_class_code) ?? "—"}</td>
                    {seesCost ? (
                      <td className="num">
                        {parcel.financials_visible ? money(parcel.purchase_price, parcel.base_currency_code) : "—"}
                      </td>
                    ) : null}
                    {seesCost ? (
                      <td className="num">
                        {parcel.financials_visible ? money(parcel.acquisition_fees, parcel.base_currency_code) : "—"}
                      </td>
                    ) : null}
                    <td>
                      {parcel.is_active ? (
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

        {selected ? (
          <Card
            title={`Plot ${selected.plot_number}`}
            description={[
              selected.title_deed_number ? `Title deed ${selected.title_deed_number}` : null,
              selected.cadastral_reference ? `Cadastral ${selected.cadastral_reference}` : null,
            ]
              .filter(Boolean)
              .join(" · ") || "Physical facts, tenure, and the planning envelope."}
            actions={
              <>
                {canWriteLand ? (
                  <Button onClick={() => setEditingParcel((open) => !open)}>
                    {editingParcel ? "Cancel" : "Edit parcel"}
                  </Button>
                ) : null}
                <Button variant="quiet" onClick={() => setSelected(null)}>
                  Close
                </Button>
              </>
            }
          >
            {editingParcel ? (
              <EditForm
                fields={parcelFields(selected, selected.financials_visible)}
                initial={Object.fromEntries(
                  parcelFields(selected, selected.financials_visible).map((field) => [
                    field.name,
                    asValue(selected[field.name as keyof LandParcel] as never),
                  ]),
                )}
                onSave={async (changes) => {
                  const updated = await projects.updateParcel(projectId, selected.id, changes);
                  setSelected(updated);
                  await load();
                  setNotice(`Plot ${updated.plot_number} updated.`);
                }}
                onCancel={() => setEditingParcel(false)}
              />
            ) : (
              <>
                {selected.financials_visible ? (
                  <MetricGroup>
                    <Metric label="Purchase price" value={money(selected.purchase_price, selected.base_currency_code)} />
                    <Metric label="Acquisition fees" value={money(selected.acquisition_fees, selected.base_currency_code)} />
                    <Metric label="Land area" value={`${selected.land_area} ${selected.area_unit}`} />
                    <Metric label="Acquired" value={businessDate(selected.acquisition_date)} size="sm" />
                  </MetricGroup>
                ) : (
                  <MetricGroup>
                    <Metric label="Land area" value={`${selected.land_area} ${selected.area_unit}`} />
                    <Metric label="Acquired" value={businessDate(selected.acquisition_date)} size="sm" />
                  </MetricGroup>
                )}

                <h3 className="section-heading">Tenure</h3>
                <KeyValueGrid columns={4}>
                  <KeyValue label="Ownership" value={labelFor("ownership_type", selected.ownership_type_code)} />
                  <KeyValue
                    label="Ownership share"
                    mono
                    value={selected.ownership_share_fraction ? percent(selected.ownership_share_fraction) : null}
                  />
                  <KeyValue label="Seller" value={selected.seller} />
                  <KeyValue label="Title status" value={labelFor("title_status", selected.title_status_code)} />
                  <KeyValue label="Zoning" value={labelFor("zoning_class", selected.zoning_class_code)} />
                  <KeyValue label="Frontage" mono value={selected.frontage} />
                  <KeyValue label="Road access" value={selected.road_access} />
                  <KeyValue label="Topography" value={selected.topography} />
                </KeyValueGrid>

                <h3 className="section-heading">Site conditions</h3>
                <KeyValueGrid columns={4}>
                  <KeyValue label="Geotechnical" value={selected.geotechnical_status} />
                  <KeyValue label="Contamination" value={selected.contamination_status} />
                  <KeyValue label="Flood and drainage" value={selected.flood_drainage_status} />
                  <KeyValue label="Archaeology and heritage" value={selected.archaeology_heritage_status} />
                  <KeyValue label="Power" value={utility(selected.power_available)} />
                  <KeyValue label="Water" value={utility(selected.water_available)} />
                  <KeyValue label="Sewer" value={utility(selected.sewer_available)} />
                  <KeyValue label="Stormwater" value={utility(selected.stormwater_available)} />
                  <KeyValue label="Telecom" value={utility(selected.telecom_available)} />
                  <KeyValue label="Utility notes" value={selected.utility_notes} />
                  <KeyValue label="Easements" value={selected.easements} />
                  <KeyValue label="Encroachments" value={selected.encroachments} />
                  <KeyValue label="Constraints" value={selected.constraints_notes} />
                </KeyValueGrid>
              </>
            )}

            <h3 className="section-heading">Planning controls{planning ? "" : " — not recorded yet"}</h3>
            {canWritePlanning ? (
              <form onSubmit={savePlanning}>
                <FormSection title="Envelope">
                  <FieldRow columns={4}>
                    <Field label="Permitted uses" className="field-span-2">
                      <input
                        className="input"
                        value={planningForm.permitted_uses}
                        onChange={(event) => setPlanningForm({ ...planningForm, permitted_uses: event.target.value })}
                      />
                    </Field>
                    <Field label="Site coverage">
                      <RateInput
                        value={planningForm.site_coverage_percent}
                        onChange={(value) => setPlanningForm({ ...planningForm, site_coverage_percent: value })}
                      />
                    </Field>
                    <Field label="Floor area ratio">
                      <input
                        className="input input-short"
                        inputMode="decimal"
                        value={planningForm.far_ratio}
                        onChange={(event) => setPlanningForm({ ...planningForm, far_ratio: event.target.value })}
                      />
                    </Field>
                    <Field label="Maximum GFA">
                      <span className="input-shell input-shell-money">
                        <input
                          className="input"
                          inputMode="decimal"
                          value={planningForm.maximum_gfa}
                          onChange={(event) => setPlanningForm({ ...planningForm, maximum_gfa: event.target.value })}
                        />
                        <span className="input-affix" aria-hidden="true">
                          {selected.area_unit}
                        </span>
                      </span>
                    </Field>
                    <Field label="Maximum floors">
                      <input
                        className="input input-xs"
                        type="number"
                        min="1"
                        value={planningForm.maximum_floors}
                        onChange={(event) => setPlanningForm({ ...planningForm, maximum_floors: event.target.value })}
                      />
                    </Field>
                    <Field label="Maximum height">
                      <input
                        className="input input-short"
                        inputMode="decimal"
                        value={planningForm.maximum_height}
                        onChange={(event) => setPlanningForm({ ...planningForm, maximum_height: event.target.value })}
                      />
                    </Field>
                    <Field label="Parking requirement">
                      <input
                        className="input"
                        value={planningForm.parking_requirement}
                        onChange={(event) => setPlanningForm({ ...planningForm, parking_requirement: event.target.value })}
                      />
                    </Field>
                  </FieldRow>
                </FormSection>
                <FormSection title="Setbacks">
                  <FieldRow columns={4}>
                    <Field label="Front">
                      <input
                        className="input input-short"
                        inputMode="decimal"
                        value={planningForm.front_setback}
                        onChange={(event) => setPlanningForm({ ...planningForm, front_setback: event.target.value })}
                      />
                    </Field>
                    <Field label="Side">
                      <input
                        className="input input-short"
                        inputMode="decimal"
                        value={planningForm.side_setback}
                        onChange={(event) => setPlanningForm({ ...planningForm, side_setback: event.target.value })}
                      />
                    </Field>
                    <Field label="Rear">
                      <input
                        className="input input-short"
                        inputMode="decimal"
                        value={planningForm.rear_setback}
                        onChange={(event) => setPlanningForm({ ...planningForm, rear_setback: event.target.value })}
                      />
                    </Field>
                  </FieldRow>
                </FormSection>
                <FormSection title="Variance">
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={planningForm.variance_required}
                      onChange={(event) => setPlanningForm({ ...planningForm, variance_required: event.target.checked })}
                    />
                    <span>A variance is required</span>
                  </label>
                  <FieldRow columns={1}>
                    <Field label="Variance notes" optional>
                      <input
                        className="input"
                        value={planningForm.variance_notes}
                        onChange={(event) => setPlanningForm({ ...planningForm, variance_notes: event.target.value })}
                      />
                    </Field>
                  </FieldRow>
                </FormSection>
                <p className="footnote">
                  Saving replaces the whole envelope: controls left blank are cleared, because these
                  limits are issued and read as one set.
                </p>
                <FormActions>
                  <Button variant="primary" type="submit" disabled={busy}>
                    {busy ? "Saving…" : "Save planning controls"}
                  </Button>
                </FormActions>
              </form>
            ) : planning ? (
              <KeyValueGrid columns={4}>
                <KeyValue label="Permitted uses" value={planning.permitted_uses} />
                <KeyValue label="Site coverage" mono value={percent(planning.site_coverage_rate_fraction)} />
                <KeyValue label="Floor area ratio" mono value={planning.far_ratio} />
                <KeyValue label="Maximum GFA" mono value={planning.maximum_gfa} />
                <KeyValue label="Maximum floors" mono value={planning.maximum_floors} />
                <KeyValue label="Maximum height" mono value={planning.maximum_height} />
                <KeyValue
                  label="Setbacks"
                  mono
                  value={[planning.front_setback, planning.side_setback, planning.rear_setback]
                    .map((value) => value ?? "—")
                    .join(" / ")}
                />
                <KeyValue label="Parking" value={planning.parking_requirement} />
                <KeyValue
                  label="Variance"
                  value={planning.variance_required ? `Required${planning.variance_notes ? ` — ${planning.variance_notes}` : ""}` : "Not required"}
                />
              </KeyValueGrid>
            ) : (
              <p className="footnote">No planning controls recorded for this parcel.</p>
            )}
          </Card>
        ) : null}
      </div>
    </>
  );
}
