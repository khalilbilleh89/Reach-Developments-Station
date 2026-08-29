"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, inventory, pricing } from "@/lib/api";
import type {
  AreaSchedule,
  AreaType,
  CustomValue,
  SubAsset,
  Unit,
  UnitPricing,
  UnitStatusEvent,
} from "@/lib/api";
import { Badge, Field, Loading, Notice, Panel } from "@/components/ui";
import { PriceWaterfall } from "@/components/projects/pricing/PriceWaterfall";
import { QuotePreviewPanel } from "@/components/projects/pricing/QuotePreviewPanel";
import { EditForm, asValue } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";
import {
  DIMENSION_LABELS,
  statusLabel,
} from "@/components/projects/inventory/statusLabels";

/** The unit fields an ordinary edit may carry. Status is absent by construction. */
const UNIT_FIELDS: EditField[] = [
  { name: "unit_reference", label: "Unit reference" },
  { name: "unit_number", label: "Unit number" },
  { name: "unit_type_code", label: "Unit type" },
  { name: "bedrooms", label: "Bedrooms", kind: "number" },
  { name: "bathrooms", label: "Bathrooms", kind: "number" },
  { name: "has_maid_room", label: "Maid room", kind: "checkbox" },
  { name: "is_duplex", label: "Duplex", kind: "checkbox" },
  { name: "is_penthouse", label: "Penthouse", kind: "checkbox" },
  { name: "furnishing_specification_code", label: "Furnishing" },
  { name: "floor_band_code", label: "Floor band" },
  { name: "orientation_code", label: "Orientation" },
  { name: "view_class_code", label: "View" },
  { name: "is_corner", label: "Corner unit", kind: "checkbox" },
  { name: "pool_access", label: "Pool access", kind: "checkbox" },
  { name: "accessibility_code", label: "Accessibility" },
  { name: "garden_class_code", label: "Garden" },
  { name: "is_active", label: "Unit is active", kind: "checkbox" },
];

/**
 * The gates, each owned by a different role. `pricing_approved` is not here.
 *
 * The roles beside each field mirror the server's own matrix so the form offers
 * a person only what they can actually save. The server decides — this is an
 * affordance, not a permission check, and it holds no rule the API does not.
 */
const RELEASE_FIELDS: (EditField & { roles: string[] })[] = [
  {
    name: "drawings_approved",
    label: "Drawings approved",
    kind: "checkbox",
    roles: ["system_admin", "project_manager", "design_engineering"],
  },
  {
    name: "legal_sale_eligible",
    label: "Legally saleable",
    kind: "checkbox",
    roles: ["system_admin", "project_manager", "legal"],
  },
  {
    name: "release_date",
    label: "Release date",
    kind: "date",
    roles: ["system_admin", "project_manager", "sales_operations"],
  },
  {
    name: "release_batch",
    label: "Release batch",
    roles: ["system_admin", "project_manager", "sales_operations"],
  },
  {
    name: "block_reason",
    label: "Block reason",
    roles: ["system_admin", "project_manager", "sales_operations"],
  },
];

const TRANSITIONS: Record<string, string[]> = {
  unreleased: ["held", "available"],
  held: ["unreleased", "available"],
  available: ["held", "unreleased"],
};

const REASON_REQUIRED = new Set(["held", "unreleased"]);

const today = () => new Date().toISOString().slice(0, 10);

/** Roles that may prepare a price and put it forward. */
const PRICING_WRITERS = new Set(["system_admin", "project_manager", "finance"]);

/** The one role that may sanction and release a price. */
const PRICING_APPROVERS = new Set(["approver_cfo"]);

/**
 * One unit, in as much depth as inventory owns.
 *
 * Not Unit 360: there is no price here, no client and no payment plan, because
 * none of those exist yet. PR-MVP-04 builds the full view on top of this.
 */
export function UnitDetailPanel({
  projectId,
  roles,
  unitId,
  canWriteStructure,
  canConfigure,
  onClose,
  onChanged,
}: {
  projectId: string;
  roles: Set<string>;
  unitId: string;
  canWriteStructure: boolean;
  canConfigure: boolean;
  onClose: () => void;
  onChanged: () => Promise<void>;
}) {
  const [unit, setUnit] = useState<Unit | null>(null);
  const [schedules, setSchedules] = useState<AreaSchedule[]>([]);
  const [areaTypes, setAreaTypes] = useState<AreaType[]>([]);
  const [assets, setAssets] = useState<SubAsset[]>([]);
  const [values, setValues] = useState<CustomValue[]>([]);
  const [history, setHistory] = useState<UnitStatusEvent[]>([]);
  const [unitPricing, setUnitPricing] = useState<UnitPricing | null>(null);
  const [quoting, setQuoting] = useState(false);
  const [pricingBusy, setPricingBusy] = useState(false);
  const [editing, setEditing] = useState<"none" | "unit" | "release" | "fields">("none");
  const [move, setMove] = useState({ to_status: "", effective_date: today(), reason: "" });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [detail, scheduleList, typeList, assetList, valueList, events] = await Promise.all([
        inventory.unit(projectId, unitId),
        inventory.areaSchedules(projectId, unitId),
        inventory.areaTypes(projectId),
        inventory.subAssets(projectId, { unit_id: unitId }),
        inventory.unitValues(projectId, unitId),
        inventory.unitHistory(projectId, unitId),
      ]);
      // Pricing is loaded separately and allowed to fail quietly: a reader who
      // may open a unit may not always be entitled to its pricing, and a 403
      // there should not blank the unit they can see.
      try {
        setUnitPricing(await pricing.unit(projectId, unitId));
      } catch {
        setUnitPricing(null);
      }
      setUnit(detail);
      setSchedules(scheduleList);
      setAreaTypes(typeList);
      setAssets(assetList);
      setValues(valueList);
      setHistory(events);
      setError(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not load the unit.");
    }
  }, [projectId, unitId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const transition = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await inventory.transitionUnit(projectId, unitId, {
        to_status: move.to_status,
        effective_date: move.effective_date,
        ...(move.reason ? { reason: move.reason } : {}),
      });
      setNotice("Status recorded.");
      setMove({ to_status: "", effective_date: today(), reason: "" });
      await load();
      await onChanged();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not record the change.");
    } finally {
      setBusy(false);
    }
  };

  /**
   * Move the unit's pending price one step along.
   *
   * The buttons a caller is offered mirror the server's rule rather than
   * replacing it: the API refuses a submitter approving their own price, and an
   * administrator approving anything, whichever button was on screen.
   */
  const movePrice = async (
    action: "submit" | "approve" | "activate",
    versionId: string,
  ) => {
    setPricingBusy(true);
    setError(null);
    try {
      if (action === "submit") {
        await pricing.submitPriceVersion(projectId, versionId);
        setNotice("Submitted for approval.");
      } else if (action === "approve") {
        await pricing.approvePriceVersion(projectId, versionId, "Reviewed against feasibility");
        setNotice("Approved. Activate it to make it the list price.");
      } else {
        await pricing.activatePriceVersion(projectId, versionId);
        setNotice("Live. This is now the unit's list price.");
      }
      await load();
      await onChanged();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not move that price.");
    } finally {
      setPricingBusy(false);
    }
  };

  const approve = async (scheduleId: string) => {
    try {
      await inventory.approveAreaSchedule(projectId, unitId, scheduleId);
      setNotice("Revision approved.");
      await load();
      await onChanged();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not approve the revision.");
    }
  };

  if (error && unit === null) {
    return (
      <Panel title="Unit">
        <Notice tone="error">{error}</Notice>
        <button className="button" type="button" onClick={onClose}>
          Close
        </button>
      </Panel>
    );
  }
  if (unit === null) return <Loading label="Loading unit…" />;

  const editableValues = values.filter((value) => value.is_editable);
  const canPrice = [...roles].some((role) => PRICING_WRITERS.has(role));
  const canApprovePricing = [...roles].some((role) => PRICING_APPROVERS.has(role));
  // The newest version that is on its way somewhere. An active price has
  // arrived; a superseded one is history.
  const pending =
    unitPricing?.history.find((version) =>
      ["draft", "submitted", "approved"].includes(version.status),
    ) ?? null;
  const releaseFields = RELEASE_FIELDS.filter((field) =>
    field.roles.some((role) => roles.has(role)),
  );

  return (
    <Panel
      title={`${unit.unit_reference}`}
      description={`${unit.phase_code ?? "—"} · ${unit.building_code ?? "—"} · ${
        unit.floor_code ?? "—"
      }`}
      actions={
        <>
          {canWriteStructure ? (
            <button
              className="button button-small"
              type="button"
              onClick={() => setEditing(editing === "unit" ? "none" : "unit")}
            >
              {editing === "unit" ? "Cancel" : "Edit unit"}
            </button>
          ) : null}
          {releaseFields.length > 0 ? (
            <button
              className="button button-small"
              type="button"
              onClick={() => setEditing(editing === "release" ? "none" : "release")}
            >
              {editing === "release" ? "Cancel" : "Release controls"}
            </button>
          ) : null}
          {editableValues.length > 0 ? (
            <button
              className="button button-small"
              type="button"
              onClick={() => setEditing(editing === "fields" ? "none" : "fields")}
            >
              {editing === "fields" ? "Cancel" : "Additional fields"}
            </button>
          ) : null}
          {unitPricing?.active_price ? (
            <button
              className="button button-small"
              type="button"
              onClick={() => setQuoting((open) => !open)}
            >
              {quoting ? "Cancel" : "Quote preview"}
            </button>
          ) : null}
          <button className="button button-small" type="button" onClick={onClose}>
            Close
          </button>
        </>
      }
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      {editing === "unit" ? (
        <EditForm
          fields={UNIT_FIELDS}
          initial={Object.fromEntries(
            UNIT_FIELDS.map((field) => [
              field.name,
              asValue(unit[field.name as keyof Unit] as never),
            ]),
          )}
          onSave={async (changes) => {
            await inventory.updateUnit(projectId, unitId, changes);
            await load();
            await onChanged();
            setNotice("Unit updated.");
          }}
          onCancel={() => setEditing("none")}
        />
      ) : null}

      {editing === "release" ? (
        <EditForm
          fields={releaseFields}
          submitLabel="Save release controls"
          initial={Object.fromEntries(
            releaseFields.map((field) => [
              field.name,
              asValue(unit[field.name as keyof Unit] as never),
            ]),
          )}
          onSave={async (changes) => {
            await inventory.releaseControls(projectId, unitId, changes);
            await load();
            await onChanged();
            setNotice("Release controls updated.");
          }}
          onCancel={() => setEditing("none")}
        />
      ) : null}

      {editing === "fields" ? (
        <EditForm
          fields={editableValues.map((value) => ({
            name: value.field_key,
            label: value.display_label,
            hint: value.help_text ?? value.unit_of_measure ?? undefined,
            kind:
              value.data_type === "boolean"
                ? "checkbox"
                : value.data_type === "date"
                  ? "date"
                  : value.data_type === "option"
                    ? "select"
                    : value.data_type === "text"
                      ? "text"
                      : "number",
            options:
              value.data_type === "option"
                ? value.options.map((option) => ({ value: option.code, label: option.label }))
                : undefined,
          }))}
          submitLabel="Save fields"
          initial={Object.fromEntries(
            editableValues.map((value) => [value.field_key, asValue(value.value)]),
          )}
          onSave={async (changes) => {
            await inventory.writeUnitValues(projectId, unitId, changes);
            await load();
            await onChanged();
            setNotice("Fields updated.");
          }}
          onCancel={() => setEditing("none")}
        />
      ) : null}

      <h3 className="section-heading">Identity</h3>
      <dl className="reference-list">
        <div>
          <dt className="reference-term">Unit number</dt>
          <dd className="reference-value">{unit.unit_number}</dd>
        </div>
        <div>
          <dt className="reference-term">Type</dt>
          <dd className="reference-value">
            {unit.unit_type_code ?? "—"} · {unit.asset_class}
          </dd>
        </div>
        <div>
          <dt className="reference-term">Bedrooms / bathrooms</dt>
          <dd className="reference-value">
            {unit.bedrooms ?? "—"} / {unit.bathrooms ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="reference-term">Orientation / view</dt>
          <dd className="reference-value">
            {unit.orientation_code ?? "—"} · {unit.view_class_code ?? "—"}
          </dd>
        </div>
      </dl>

      <h3 className="section-heading">Areas</h3>
      {unit.area_lines.length === 0 ? (
        <p className="subtle">No approved measurement yet.</p>
      ) : (
        <div className="table-scroll">
          <table className="table">
            <caption className="visually-hidden">Approved areas</caption>
            <thead>
              <tr>
                <th scope="col">Area</th>
                <th scope="col">Measured</th>
                <th scope="col">Factor</th>
                <th scope="col">Weighted</th>
              </tr>
            </thead>
            <tbody>
              {unit.area_lines.map((line) => (
                <tr key={line.area_type_id}>
                  <th scope="row">{line.label}</th>
                  <td className="mono nowrap">
                    {line.raw_area} {line.unit_of_measure}
                  </td>
                  <td className="mono">{line.weight_factor}</td>
                  <td className="mono nowrap">{line.weighted_area}</td>
                </tr>
              ))}
              <tr>
                <th scope="row">Weighted saleable</th>
                <td colSpan={2} />
                <td className="mono nowrap">
                  {unit.weighted_saleable_area === null
                    ? "—"
                    : `${unit.weighted_saleable_area} ${unit.weighted_saleable_area_unit ?? ""}`.trim()}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
      {schedules.length > 0 ? (
        <div className="chip-list">
          {schedules.map((schedule) => (
            <span key={schedule.id} className="chip">
              {schedule.revision_code}: {schedule.status}
              {canConfigure && schedule.status === "draft" ? (
                <button
                  className="button button-small"
                  type="button"
                  onClick={() => void approve(schedule.id)}
                >
                  Approve
                </button>
              ) : null}
            </span>
          ))}
        </div>
      ) : null}

      <h3 className="section-heading">Sub-assets</h3>
      {assets.length === 0 ? (
        <p className="subtle">No parking or storage linked to this unit.</p>
      ) : (
        <ul className="chip-list">
          {assets.map((asset) => (
            <li key={asset.id} className="chip">
              {asset.asset_reference} · {asset.asset_type} · {asset.transfer_mode}
            </li>
          ))}
        </ul>
      )}

      <h3 className="section-heading">Release</h3>
      <dl className="reference-list">
        <div>
          <dt className="reference-term">Completeness</dt>
          <dd className="reference-value">
            {unit.completeness_percent}%{unit.is_complete ? " — complete" : ""}
          </dd>
        </div>
        <div>
          <dt className="reference-term">Drawings approved</dt>
          <dd className="reference-value">{unit.drawings_approved ? "Yes" : "No"}</dd>
        </div>
        <div>
          <dt className="reference-term">Legally saleable</dt>
          <dd className="reference-value">{unit.legal_sale_eligible ? "Yes" : "No"}</dd>
        </div>
        <div>
          <dt className="reference-term">Pricing approved</dt>
          <dd className="reference-value">
            {unit.pricing_approved ? "Yes" : "No — set when a price is approved"}
          </dd>
        </div>
        <div>
          <dt className="reference-term">Release date</dt>
          <dd className="reference-value">{unit.release_date ?? "—"}</dd>
        </div>
      </dl>
      {unit.release_blockers.length > 0 ? (
        <Notice tone="info">
          Not releasable yet: {unit.release_blockers.join("; ")}.
        </Notice>
      ) : null}
      {unit.missing_requirements.length > 0 ? (
        <p className="subtle">Outstanding: {unit.missing_requirements.join(", ")}.</p>
      ) : null}

      <h3 className="section-heading">Status</h3>
      <div className="chip-list">
        <Badge tone="neutral">Commercial: {statusLabel(unit.commercial_status)}</Badge>
        <span className="chip">Legal: {statusLabel(unit.legal_status)}</span>
        <span className="chip">Collection: {statusLabel(unit.collection_status)}</span>
        <span className="chip">Delivery: {statusLabel(unit.delivery_status)}</span>
      </div>

      {(TRANSITIONS[unit.commercial_status] ?? []).length > 0 ? (
        <form className="panel-section" onSubmit={transition}>
          <h3 className="section-heading">Change commercial status</h3>
          <div className="form-inline">
            <Field label="Move to">
              <select
                className="input"
                required
                value={move.to_status}
                onChange={(event) => setMove({ ...move, to_status: event.target.value })}
              >
                <option value="">Choose…</option>
                {(TRANSITIONS[unit.commercial_status] ?? []).map((status) => (
                  <option key={status} value={status}>
                    {statusLabel(status)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Effective date">
              <input
                className="input input-short"
                type="date"
                required
                value={move.effective_date}
                onChange={(event) => setMove({ ...move, effective_date: event.target.value })}
              />
            </Field>
            <Field
              label="Reason"
              hint={REASON_REQUIRED.has(move.to_status) ? "Required for this move." : "Optional."}
            >
              <input
                className="input"
                required={REASON_REQUIRED.has(move.to_status)}
                value={move.reason}
                onChange={(event) => setMove({ ...move, reason: event.target.value })}
              />
            </Field>
          </div>
          <div className="form-actions">
            <button className="button button-primary" type="submit" disabled={busy}>
              {busy ? "Recording…" : "Record status change"}
            </button>
          </div>
        </form>
      ) : null}

      <h3 className="section-heading">Commercial history</h3>
      {history.length === 0 ? (
        <p className="subtle">Nothing recorded yet.</p>
      ) : (
        <div className="table-scroll">
          <table className="table">
            <caption className="visually-hidden">Unit status history</caption>
            <thead>
              <tr>
                <th scope="col">Effective</th>
                <th scope="col">Dimension</th>
                <th scope="col">From</th>
                <th scope="col">To</th>
                <th scope="col">Reason</th>
              </tr>
            </thead>
            <tbody>
              {history.map((event) => (
                <tr key={event.id}>
                  <th scope="row" className="nowrap">
                    {event.effective_date}
                  </th>
                  <td>{DIMENSION_LABELS[event.dimension] ?? event.dimension}</td>
                  <td>{event.from_status ? statusLabel(event.from_status) : "—"}</td>
                  <td>{statusLabel(event.to_status)}</td>
                  <td>{event.reason ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {values.length > 0 ? (
        <>
          <h3 className="section-heading">Additional fields</h3>
          <dl className="reference-list">
            {values.map((value) => (
              <div key={value.definition_id}>
                <dt className="reference-term">{value.display_label}</dt>
                <dd className="reference-value">
                  {value.value === null || value.value === "" ? "—" : String(value.value)}
                  {value.unit_of_measure ? ` ${value.unit_of_measure}` : ""}
                </dd>
              </div>
            ))}
          </dl>
        </>
      ) : null}

      {unitPricing ? (
        <>
          <h3 className="section-heading">Pricing</h3>
          {pending ? (
            <div className="chip-list">
              <span className="chip">
                Version {pending.version_number} is {pending.status}
              </span>
              {canPrice && pending.status === "draft" ? (
                <button
                  className="button button-small"
                  type="button"
                  disabled={pricingBusy}
                  onClick={() => movePrice("submit", pending.id)}
                >
                  Submit for approval
                </button>
              ) : null}
              {canApprovePricing && pending.status === "submitted" ? (
                <button
                  className="button button-small"
                  type="button"
                  disabled={pricingBusy}
                  onClick={() => movePrice("approve", pending.id)}
                >
                  Approve
                </button>
              ) : null}
              {canApprovePricing && pending.status === "approved" ? (
                <button
                  className="button button-small"
                  type="button"
                  disabled={pricingBusy}
                  onClick={() => movePrice("activate", pending.id)}
                >
                  Activate
                </button>
              ) : null}
            </div>
          ) : null}
          {unitPricing.repricing_required ? (
            <Notice tone="error">
              Repricing required. This unit has changed since its list price was set, so the
              price below is what it was offered at and no longer describes it. The unit
              cannot be released until a new price is approved and activated.
            </Notice>
          ) : null}
          {unitPricing.active_price === null ? (
            <Notice tone="info">
              {unitPricing.has_active_configuration
                ? "Not priced. Generate a price from the Pricing tab."
                : "This project has no active pricing configuration yet."}
            </Notice>
          ) : (
            <>
              <div className="chip-list">
                <span className="chip mono">
                  {unitPricing.active_price.reference_price_ex_tax} ex tax
                </span>
                <span className="chip">v{unitPricing.active_price.version_number}</span>
                <span className="chip">from {unitPricing.active_price.valid_from ?? "—"}</span>
                <span className="chip mono">
                  {unitPricing.active_price.price_per_internal_area ?? "—"} per internal unit
                </span>
                {unitPricing.pricing_approved ? (
                  <Badge tone="success">Pricing approved</Badge>
                ) : (
                  <Badge tone="muted">Pricing not approved</Badge>
                )}
              </div>
              <PriceWaterfall version={unitPricing.active_price} />
            </>
          )}

          {unitPricing.history.length > 1 ? (
            <>
              <h3 className="section-heading">Price history</h3>
              <div className="table-scroll">
                <table className="table">
                  <caption className="visually-hidden">Price history</caption>
                  <thead>
                    <tr>
                      <th scope="col">Version</th>
                      <th scope="col">Status</th>
                      <th scope="col">From</th>
                      <th scope="col">To</th>
                      <th scope="col">Price</th>
                      <th scope="col">Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {unitPricing.history.map((version) => (
                      <tr key={version.id}>
                        <th scope="row">{version.version_number}</th>
                        <td>{version.status}</td>
                        <td>{version.valid_from ?? "—"}</td>
                        <td>{version.valid_to ?? "—"}</td>
                        <td className="mono nowrap">{version.reference_price_ex_tax}</td>
                        <td>{version.change_reason ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}
        </>
      ) : null}

      {quoting && unitPricing?.active_price ? (
        <QuotePreviewPanel
          projectId={projectId}
          unitId={unitId}
          onClose={() => setQuoting(false)}
        />
      ) : null}

      {areaTypes.length === 0 ? (
        <Notice tone="info">
          This project has no area types configured yet, so no unit can be measured or released.
        </Notice>
      ) : null}
    </Panel>
  );
}
