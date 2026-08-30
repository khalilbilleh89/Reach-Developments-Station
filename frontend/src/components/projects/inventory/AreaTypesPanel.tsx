"use client";

import { useState } from "react";

import { ApiError, inventory } from "@/lib/api";
import type { AreaType } from "@/lib/api";
import { Badge, Button, Field, Notice, TableScroll } from "@/components/ui";

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
}: {
  projectId: string;
  areaTypes: AreaType[];
  onChanged: () => Promise<void>;
}) {
  const [form, setForm] = useState({
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
      await inventory.createAreaType(projectId, form);
      setForm({
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
    <div>
      <h3 className="section-heading">Area types</h3>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <p className="subtle">
        A balcony of 20 sqm with a factor of 0.500000 contributes 10 weighted sqm. The measured
        area stays 20 sqm — a factor never changes what a drawing says.
      </p>

      {areaTypes.length > 0 ? (
        <TableScroll label="Configured area types">
            <thead>
              <tr>
                <th scope="col">Code</th>
                <th scope="col">Label</th>
                <th scope="col">Role</th>
                <th scope="col">Unit</th>
                <th scope="col">Factor</th>
                <th scope="col">Required</th>
                <th scope="col">State</th>
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              {areaTypes.map((areaType) => (
                <tr key={areaType.id}>
                  <th scope="row">{areaType.code}</th>
                  <td>{areaType.label}</td>
                  <td>
                    {areaType.area_role === "internal" ? (
                      <Badge tone="success">Primary internal</Badge>
                    ) : (
                      areaType.area_role
                    )}
                  </td>
                  <td>{areaType.unit_of_measure}</td>
                  <td className="mono nowrap">{areaType.weight_factor}</td>
                  <td>{areaType.required_for_release ? "Yes" : "No"}</td>
                  <td>
                    {areaType.is_active ? (
                      <Badge tone="success">Active</Badge>
                    ) : (
                      <Badge tone="muted">Retired</Badge>
                    )}
                  </td>
                  <td className="chip-list">
                    <Button
                      small
                      onClick={() =>
                        void toggle(areaType, {
                          required_for_release: !areaType.required_for_release,
                        })
                      }
                    >
                      {areaType.required_for_release ? "Not required" : "Require"}
                    </Button>
                    <Button
                      small
                      onClick={() => void toggle(areaType, { is_active: !areaType.is_active })}
                    >
                      {areaType.is_active ? "Retire" : "Restore"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
</TableScroll>
      ) : null}

      <form className="form-grid" onSubmit={submit}>
        <Field label="Code">
          <input
            className="input input-short"
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
            onChange={(event) => setForm({ ...form, area_role: event.target.value })}
          >
            {ROLES.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Weight factor" hint="A fraction of one: 0.500000 is half.">
          <input
            className="input input-short"
            required
            value={form.weight_factor}
            onChange={(event) => setForm({ ...form, weight_factor: event.target.value })}
          />
        </Field>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={form.required_for_release}
            onChange={(event) =>
              setForm({ ...form, required_for_release: event.target.checked })
            }
          />
          <span>Required before a unit can be released</span>
        </label>
        <div className="form-actions">
          <Button variant="primary" type="submit" disabled={busy}>
            {busy ? "Saving…" : "Add area type"}
          </Button>
        </div>
      </form>
    </div>
  );
}
