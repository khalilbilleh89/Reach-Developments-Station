"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, projects, settings } from "@/lib/api";
import type { LandParcel, PlanningControl, ReferenceValue } from "@/lib/api";
import {
  Button,
  EmptyState,
  Field,
  Loading,
  Notice,
  Panel,
  TableScroll,
} from "@/components/ui";
import { EditForm, asValue } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";

/** Tri-state: null means nobody has established it yet, which is not "no". */
function utility(value: boolean | null): string {
  if (value === null) return "Unknown";
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
    site_coverage_rate_fraction: "",
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
  return [
    { name: "plot_number", label: "Plot number" },
    { name: "title_deed_number", label: "Title deed number" },
    { name: "cadastral_reference", label: "Cadastral reference" },
    { name: "land_area", label: "Land area", kind: "number" },
    {
      name: "area_unit",
      label: "Area unit",
      kind: "select",
      options: [
        { value: "sqm", label: "sqm" },
        { value: "sqft", label: "sqft" },
      ],
    },
    { name: "ownership_type_code", label: "Ownership type" },
    {
      name: "ownership_share_fraction",
      label: "Ownership share",
      kind: "number",
      hint: "A fraction of one: 0.500000 is a half share.",
    },
    { name: "acquisition_date", label: "Acquisition date", kind: "date" },
    { name: "seller", label: "Seller" },
    { name: "title_status_code", label: "Title status" },
    { name: "zoning_class_code", label: "Zoning class" },
    { name: "frontage", label: "Frontage", kind: "number" },
    { name: "road_access", label: "Road access" },
    { name: "topography", label: "Topography" },
    { name: "geotechnical_status", label: "Geotechnical status" },
    { name: "contamination_status", label: "Contamination status" },
    { name: "flood_drainage_status", label: "Flood and drainage" },
    { name: "archaeology_heritage_status", label: "Archaeology and heritage" },
    { name: "utility_notes", label: "Utility notes", kind: "textarea" },
    { name: "easements", label: "Easements", kind: "textarea" },
    { name: "encroachments", label: "Encroachments", kind: "textarea" },
    { name: "constraints_notes", label: "Constraints", kind: "textarea" },
    {
      name: "purchase_price",
      label: `Purchase price${parcel.base_currency_code ? ` (${parcel.base_currency_code})` : ""}`,
      kind: "number",
      visible: canSeeCost,
    },
    { name: "acquisition_fees", label: "Acquisition fees", kind: "number", visible: canSeeCost },
    { name: "is_active", label: "Parcel is active", kind: "checkbox" },
  ];
}

/**
 * The land register and, for the selected parcel, its planning envelope.
 *
 * Planning belongs to a parcel, so it lives here beside the parcel it governs
 * rather than on a disconnected page of its own.
 */
export function LandTab({
  projectId,
  canWriteLand,
  canWritePlanning,
}: {
  projectId: string;
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
        // Only the create form needs these.
      }
    })();
  }, []);

  const optionsFor = (category: string) =>
    references.filter((value) => value.category === category);

  const open = async (parcel: LandParcel) => {
    setSelected(parcel);
    setEditingParcel(false);
    setNotice(null);
    try {
      const control = await projects.planning(projectId, parcel.id);
      setPlanning(control);
      setPlanningForm({
        permitted_uses: control.permitted_uses ?? "",
        site_coverage_rate_fraction: control.site_coverage_rate_fraction ?? "",
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
        "site_coverage_rate_fraction",
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

  return (
    <>
      <Panel
        title="Land"
        description="Parcels under this project."
        actions={
          canWriteLand ? (
            <Button
              small
              onClick={() => setCreating((open) => !open)}
            >
              {creating ? "Cancel" : "New parcel"}
            </Button>
          ) : undefined
        }
      >
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}

        {creating ? (
          <form onSubmit={createParcel}>
            <div className="form-grid">
              <Field label="Plot number">
                <input
                  className="input"
                  required
                  value={form.plot_number}
                  onChange={(event) => setForm({ ...form, plot_number: event.target.value })}
                />
              </Field>
              <Field label="Land area" hint="In the project's area unit.">
                <input
                  className="input input-short"
                  required
                  value={form.land_area}
                  onChange={(event) => setForm({ ...form, land_area: event.target.value })}
                />
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
              <Field label="Title deed number">
                <input
                  className="input"
                  value={form.title_deed_number}
                  onChange={(event) =>
                    setForm({ ...form, title_deed_number: event.target.value })
                  }
                />
              </Field>
              {(
                [
                  ["ownership_type_code", "Ownership type", "ownership_type"],
                  ["title_status_code", "Title status", "title_status"],
                  ["zoning_class_code", "Zoning class", "zoning_class"],
                ] as const
              ).map(([key, label, category]) => (
                <Field key={key} label={label}>
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
              <Field label="Purchase price" hint="Project base currency.">
                <input
                  className="input input-short"
                  value={form.purchase_price}
                  onChange={(event) => setForm({ ...form, purchase_price: event.target.value })}
                />
              </Field>
              <Field label="Acquisition fees">
                <input
                  className="input input-short"
                  value={form.acquisition_fees}
                  onChange={(event) =>
                    setForm({ ...form, acquisition_fees: event.target.value })
                  }
                />
              </Field>
            </div>
            <div className="form-actions">
              <Button variant="primary" type="submit" disabled={busy}>
                {busy ? "Saving…" : "Register parcel"}
              </Button>
            </div>
          </form>
        ) : null}

        {parcels === null ? (
          <Loading label="Loading parcels…" />
        ) : parcels.length === 0 ? (
          <EmptyState
            title="No parcels registered"
            hint="Record the land this development controls."
          />
        ) : (
          <TableScroll label="Land parcels">
              <thead>
                <tr>
                  <th scope="col">Plot</th>
                  <th scope="col">Title deed</th>
                  <th scope="col">Area</th>
                  <th scope="col">Ownership</th>
                  <th scope="col">Title status</th>
                  <th scope="col">Zoning</th>
                  {parcels[0]?.financials_visible ? <th scope="col">Purchase price</th> : null}
                  {parcels[0]?.financials_visible ? <th scope="col">Fees</th> : null}
                </tr>
              </thead>
              <tbody>
                {parcels.map((parcel) => (
                  <tr key={parcel.id}>
                    <th scope="row">
                      <Button
                        small
                        onClick={() => void open(parcel)}
                      >
                        {parcel.plot_number}
                      </Button>
                    </th>
                    <td>{parcel.title_deed_number ?? "—"}</td>
                    <td className="nowrap">
                      {parcel.land_area} {parcel.area_unit}
                    </td>
                    <td>{parcel.ownership_type_code ?? "—"}</td>
                    <td>{parcel.title_status_code ?? "—"}</td>
                    <td>{parcel.zoning_class_code ?? "—"}</td>
                    {parcel.financials_visible ? (
                      <td className="mono nowrap">
                        {parcel.purchase_price ?? "—"} {parcel.base_currency_code ?? ""}
                      </td>
                    ) : null}
                    {parcel.financials_visible ? (
                      <td className="mono nowrap">{parcel.acquisition_fees ?? "—"}</td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
</TableScroll>
        )}
      </Panel>

      {selected ? (
        <Panel
          title={`Plot ${selected.plot_number}`}
          description="Physical facts and the current planning envelope."
          actions={
            <>
              {canWriteLand ? (
                <Button
                  small
                  onClick={() => setEditingParcel((open) => !open)}
                >
                  {editingParcel ? "Cancel" : "Edit parcel"}
                </Button>
              ) : null}
              <Button
                small
                onClick={() => setSelected(null)}
              >
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
          ) : null}
          <dl className="reference-list">
            <div>
              <dt className="reference-term">Cadastral reference</dt>
              <dd className="reference-value">{selected.cadastral_reference ?? "—"}</dd>
            </div>
            <div>
              <dt className="reference-term">Frontage</dt>
              <dd className="reference-value">{selected.frontage ?? "—"}</dd>
            </div>
            <div>
              <dt className="reference-term">Road access</dt>
              <dd className="reference-value">{selected.road_access ?? "—"}</dd>
            </div>
            <div>
              <dt className="reference-term">Topography</dt>
              <dd className="reference-value">{selected.topography ?? "—"}</dd>
            </div>
            <div>
              <dt className="reference-term">Power</dt>
              <dd className="reference-value">{utility(selected.power_available)}</dd>
            </div>
            <div>
              <dt className="reference-term">Water</dt>
              <dd className="reference-value">{utility(selected.water_available)}</dd>
            </div>
            <div>
              <dt className="reference-term">Sewer</dt>
              <dd className="reference-value">{utility(selected.sewer_available)}</dd>
            </div>
            <div>
              <dt className="reference-term">Telecom</dt>
              <dd className="reference-value">{utility(selected.telecom_available)}</dd>
            </div>
            <div>
              <dt className="reference-term">Constraints</dt>
              <dd className="reference-value">{selected.constraints_notes ?? "—"}</dd>
            </div>
          </dl>

          <h3 className="section-heading">
            Planning controls {planning ? "" : "(not recorded yet)"}
          </h3>
          {canWritePlanning ? (
            <form onSubmit={savePlanning}>
              <div className="form-grid">
                <Field label="Permitted uses">
                  <input
                    className="input"
                    value={planningForm.permitted_uses}
                    onChange={(event) =>
                      setPlanningForm({ ...planningForm, permitted_uses: event.target.value })
                    }
                  />
                </Field>
                <Field label="Site coverage" hint="A fraction of one: 0.450000 is 45%.">
                  <input
                    className="input input-short"
                    value={planningForm.site_coverage_rate_fraction}
                    onChange={(event) =>
                      setPlanningForm({
                        ...planningForm,
                        site_coverage_rate_fraction: event.target.value,
                      })
                    }
                  />
                </Field>
                <Field label="Floor area ratio">
                  <input
                    className="input input-short"
                    value={planningForm.far_ratio}
                    onChange={(event) =>
                      setPlanningForm({ ...planningForm, far_ratio: event.target.value })
                    }
                  />
                </Field>
                <Field label="Maximum GFA">
                  <input
                    className="input input-short"
                    value={planningForm.maximum_gfa}
                    onChange={(event) =>
                      setPlanningForm({ ...planningForm, maximum_gfa: event.target.value })
                    }
                  />
                </Field>
                <Field label="Maximum floors">
                  <input
                    className="input input-short"
                    type="number"
                    min="1"
                    value={planningForm.maximum_floors}
                    onChange={(event) =>
                      setPlanningForm({ ...planningForm, maximum_floors: event.target.value })
                    }
                  />
                </Field>
                <Field label="Maximum height">
                  <input
                    className="input input-short"
                    value={planningForm.maximum_height}
                    onChange={(event) =>
                      setPlanningForm({ ...planningForm, maximum_height: event.target.value })
                    }
                  />
                </Field>
                <Field label="Front setback">
                  <input
                    className="input input-short"
                    value={planningForm.front_setback}
                    onChange={(event) =>
                      setPlanningForm({ ...planningForm, front_setback: event.target.value })
                    }
                  />
                </Field>
                <Field label="Side setback">
                  <input
                    className="input input-short"
                    value={planningForm.side_setback}
                    onChange={(event) =>
                      setPlanningForm({ ...planningForm, side_setback: event.target.value })
                    }
                  />
                </Field>
                <Field label="Rear setback">
                  <input
                    className="input input-short"
                    value={planningForm.rear_setback}
                    onChange={(event) =>
                      setPlanningForm({ ...planningForm, rear_setback: event.target.value })
                    }
                  />
                </Field>
                <Field label="Parking requirement">
                  <input
                    className="input"
                    value={planningForm.parking_requirement}
                    onChange={(event) =>
                      setPlanningForm({
                        ...planningForm,
                        parking_requirement: event.target.value,
                      })
                    }
                  />
                </Field>
                <Field label="Variance notes">
                  <input
                    className="input"
                    value={planningForm.variance_notes}
                    onChange={(event) =>
                      setPlanningForm({ ...planningForm, variance_notes: event.target.value })
                    }
                  />
                </Field>
              </div>
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
                <span>A variance is required</span>
              </label>
              <p className="footnote">
                Saving replaces the whole envelope: controls left blank are cleared, because
                these limits are issued and read as one set.
              </p>
              <div className="form-actions">
                <Button variant="primary" type="submit" disabled={busy}>
                  {busy ? "Saving…" : "Save planning controls"}
                </Button>
              </div>
            </form>
          ) : planning ? (
            <dl className="reference-list">
              <div>
                <dt className="reference-term">Floor area ratio</dt>
                <dd className="reference-value">{planning.far_ratio ?? "—"}</dd>
              </div>
              <div>
                <dt className="reference-term">Maximum floors</dt>
                <dd className="reference-value">{planning.maximum_floors ?? "—"}</dd>
              </div>
              <div>
                <dt className="reference-term">Permitted uses</dt>
                <dd className="reference-value">{planning.permitted_uses ?? "—"}</dd>
              </div>
            </dl>
          ) : (
            <p className="subtle">No planning controls recorded for this parcel.</p>
          )}
        </Panel>
      ) : null}
    </>
  );
}
