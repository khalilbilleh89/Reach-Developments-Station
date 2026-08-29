"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, inventory } from "@/lib/api";
import type {
  AreaSchedule,
  AreaType,
  CustomValue,
  SubAsset,
  Unit,
  UnitStatusEvent,
} from "@/lib/api";
import { Badge, Field, Loading, Notice, Panel } from "@/components/ui";
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

/** The gates, each owned by a different role. `pricing_approved` is not here. */
const RELEASE_FIELDS: EditField[] = [
  { name: "drawings_approved", label: "Drawings approved", kind: "checkbox" },
  { name: "legal_sale_eligible", label: "Legally saleable", kind: "checkbox" },
  { name: "release_date", label: "Release date", kind: "date" },
  { name: "release_batch", label: "Release batch" },
  { name: "block_reason", label: "Block reason" },
];

const TRANSITIONS: Record<string, string[]> = {
  unreleased: ["held", "available"],
  held: ["unreleased", "available"],
  available: ["held", "unreleased"],
};

const REASON_REQUIRED = new Set(["held", "unreleased"]);

const today = () => new Date().toISOString().slice(0, 10);

/**
 * One unit, in as much depth as inventory owns.
 *
 * Not Unit 360: there is no price here, no client and no payment plan, because
 * none of those exist yet. PR-MVP-04 builds the full view on top of this.
 */
export function UnitDetailPanel({
  projectId,
  unitId,
  canWriteStructure,
  canConfigure,
  onClose,
  onChanged,
}: {
  projectId: string;
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
          <button
            className="button button-small"
            type="button"
            onClick={() => setEditing(editing === "release" ? "none" : "release")}
          >
            {editing === "release" ? "Cancel" : "Release controls"}
          </button>
          {editableValues.length > 0 ? (
            <button
              className="button button-small"
              type="button"
              onClick={() => setEditing(editing === "fields" ? "none" : "fields")}
            >
              {editing === "fields" ? "Cancel" : "Additional fields"}
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
          fields={RELEASE_FIELDS}
          submitLabel="Save release controls"
          initial={Object.fromEntries(
            RELEASE_FIELDS.map((field) => [
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
                <td className="mono nowrap">{unit.weighted_saleable_area ?? "—"}</td>
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

      {areaTypes.length === 0 ? (
        <Notice tone="info">
          This project has no area types configured yet, so no unit can be measured or released.
        </Notice>
      ) : null}
    </Panel>
  );
}
