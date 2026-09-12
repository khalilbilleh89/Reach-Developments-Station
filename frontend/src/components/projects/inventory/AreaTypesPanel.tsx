"use client";

import { DeleteRecordButton } from "../DeleteRecordButton";
import { useState } from "react";

import { ApiError, inventory } from "@/lib/api";
import type { AreaType } from "@/lib/api";
import {
  Badge,
  Button,
  EmptyState,
  Field,
  FieldRow,
  FormActions,
  FormSection,
  Notice,
  StatusDot,
  TableScroll,
} from "@/components/ui";

import { PHYSICAL_COMPONENTS } from "@/components/projects/inventory/unit/PhysicalRecord";

const ROLES = ["internal", "outdoor", "ancillary", "plot", "gross", "other"];

/**
 * How a project measures its units, and how much of each area it sells.
 *
 * The factor never changes a measured area. It decides how much of that area
 * counts toward the weighted figure a commercial team quotes on, which is why
 * the worked example is on the screen rather than in a help page: the two
 * numbers are easy to confuse and expensive to confuse.
 */
export function AreaTypesPanel({
  projectId,
  areaTypes,
  onChanged,
  canDelete = false,
}: {
  canDelete?: boolean;
  projectId: string;
  areaTypes: AreaType[];
  onChanged: () => Promise<void>;
}) {
  const [form, setForm] = useState({
    physical_component: "",
    code: "",
    label: "",
    area_role: "outdoor",
    weight_factor: "1.000000",
    required_for_release: false,
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await inventory.createAreaType(projectId, { ...form, physical_component: form.physical_component || null });
      setForm({
        physical_component: "",
        code: "",
        label: "",
        area_role: "outdoor",
        weight_factor: "1.000000",
        required_for_release: false,
      });
      await onChanged();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save the area type.");
    } finally {
      setBusy(false);
    }
  };

  const toggle = async (areaType: AreaType, changes: Record<string, unknown>) => {
    try {
      await inventory.updateAreaType(projectId, areaType.id, changes);
      await onChanged();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not update the area type.");
    }
  };

  return (
    <div className="stack">
      {error ? <Notice tone="error">{error}</Notice> : null}

      {areaTypes.length === 0 ? (
        <EmptyState
          compact
          title="No area types yet"
          hint="Until one is configured no unit can be measured, priced or released."
        />
      ) : (
        <TableScroll label="Configured area types" compact>
          <thead>
            <tr>
              <th scope="col">Code</th>
              <th scope="col">Label</th>
              <th scope="col">Role</th>
              <th scope="col">Gross component</th>
              <th scope="col">Unit</th>
              <th scope="col" className="num">
                Factor
              </th>
              <th scope="col">Required for release</th>
              <th scope="col">State</th>
              <th scope="col">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {areaTypes.map((areaType) => (
              <tr key={areaType.id}>
                <th scope="row" className="mono">
                  {areaType.code}
                </th>
                <td>{areaType.label}</td>
                <td>
                  {areaType.area_role === "internal" ? (
                    <Badge tone="info">Primary internal</Badge>
                  ) : (
                    areaType.area_role
                  )}
                </td>
                <td><select className="input" aria-label={`Gross component for ${areaType.label}`}
                  value={areaType.physical_component ?? ""}
                  onChange={event => void toggle(areaType, { physical_component: event.target.value || null })}>
                  <option value="">Not mapped</option>
                  {PHYSICAL_COMPONENTS.filter(([key]) => areaType.area_role === "internal" ? key === "internal" : areaType.area_role === "outdoor" && key !== "internal").map(([key, label]) => <option key={key} value={key}>{label}</option>)}
                </select></td>
                <td>{areaType.unit_of_measure}</td>
                <td className="num">{areaType.weight_factor}</td>
                <td>
                  {areaType.required_for_release ? (
                    <StatusDot tone="warning">Required</StatusDot>
                  ) : (
                    <StatusDot tone="muted">Optional</StatusDot>
                  )}
                </td>
                <td>
                  {areaType.is_active ? (
                    <StatusDot tone="success">Active</StatusDot>
                  ) : (
                    <StatusDot tone="muted">Retired</StatusDot>
                  )}
                </td>
                <td>
                  <div className="button-row">
                    <Button
                      small
                      variant="quiet"
                      onClick={() => void toggle(areaType, { required_for_release: !areaType.required_for_release })}
                    >
                      {areaType.required_for_release ? "Make optional" : "Require"}
                    </Button>
                    <Button small variant="quiet" onClick={() => void toggle(areaType, { is_active: !areaType.is_active })}>
                      {areaType.is_active ? "Retire" : "Restore"}
                    </Button>
                    {canDelete ? <DeleteRecordButton label={areaType.label} description="Delete this unused area type permanently. Existing measurements and pricing references are protected. The audit trail is retained." onDelete={reason => inventory.deleteRecord(projectId, "area-types", areaType.id, reason)} onDeleted={onChanged} /> : null}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      )}

      <form onSubmit={submit}>
        <FormSection
          title="Add an area type"
          description="A balcony of 20 sqm with a factor of 0.500000 contributes 10 weighted sqm. The measured area stays 20 sqm — a factor never changes what a drawing says."
        >
          <FieldRow columns={4}>
            <Field label="Code">
              <input
                className="input"
                required
                value={form.code}
                onChange={(event) => setForm({ ...form, code: event.target.value })}
              />
            </Field>
            <Field label="Label">
              <input
                className="input"
                required
                value={form.label}
                onChange={(event) => setForm({ ...form, label: event.target.value })}
              />
            </Field>
            <Field label="Role" hint="A project has one primary internal area.">
              <select
                className="input"
                value={form.area_role}
                onChange={(event) => setForm({ ...form, area_role: event.target.value, physical_component: event.target.value === "internal" ? "internal" : "" })}
              >
                {ROLES.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Gross component" hint="Explicitly map the six physical areas; parking and storage stay separate.">
              <select className="input" value={form.physical_component} onChange={event => setForm({ ...form, physical_component: event.target.value, area_role: event.target.value === "internal" ? "internal" : event.target.value ? "outdoor" : form.area_role })}>
                <option value="">Not a gross component</option>
                {PHYSICAL_COMPONENTS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </select>
            </Field>
            <Field label="Weight factor" hint="A fraction of one: 0.500000 is half.">
              <input
                className="input figure"
                inputMode="decimal"
                required
                value={form.weight_factor}
                onChange={(event) => setForm({ ...form, weight_factor: event.target.value })}
              />
            </Field>
          </FieldRow>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.required_for_release}
              onChange={(event) => setForm({ ...form, required_for_release: event.target.checked })}
            />
            <span>Required before a unit can be released</span>
          </label>
        </FormSection>
        <FormActions>
          <Button variant="primary" type="submit" disabled={busy}>
            {busy ? "Saving…" : "Add area type"}
          </Button>
        </FormActions>
      </form>
    </div>
  );
}
