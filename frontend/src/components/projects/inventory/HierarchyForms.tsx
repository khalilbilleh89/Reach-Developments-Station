"use client";

import { useState } from "react";

import { ApiError, inventory } from "@/lib/api";
import type { Building, Floor, Phase } from "@/lib/api";
import { Button, Field, FieldRow, FormActions, Notice, Tabs } from "@/components/ui";

type Kind = "phase" | "building" | "floor" | "unit";

const KINDS: { key: Kind; label: string }[] = [
  { key: "phase", label: "Phase" },
  { key: "building", label: "Building" },
  { key: "floor", label: "Floor" },
  { key: "unit", label: "Unit" },
];

/**
 * The small administration actions that make a development's structure.
 *
 * Inside the Inventory section rather than on four separate pages: a phase
 * only means something in the project that owns it, and making somebody
 * navigate away to create one loses the context they are working in.
 *
 * For a first load of two hundred units the CSV import is the right tool, and
 * the import panel says so.
 */
export function HierarchyForms({
  projectId,
  phases,
  buildings,
  floors,
  canConfigure,
  onChanged,
}: {
  projectId: string;
  phases: Phase[];
  buildings: Building[];
  floors: Floor[];
  canConfigure: boolean;
  onChanged: () => Promise<void>;
}) {
  const [kind, setKind] = useState<Kind>(canConfigure ? "phase" : "building");
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (name: string, value: string) => setValues({ ...values, [name]: value });

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (kind === "phase") {
        await inventory.createPhase(projectId, {
          code: values.code,
          name: values.name,
          ...(values.sequence ? { sequence: Number(values.sequence) } : {}),
        });
      } else if (kind === "building") {
        await inventory.createBuilding(projectId, {
          phase_id: values.phase_id,
          code: values.code,
          name: values.name,
        });
      } else if (kind === "floor") {
        await inventory.createFloor(projectId, {
          building_id: values.building_id,
          code: values.code,
          label: values.label,
          ...(values.level_number ? { level_number: Number(values.level_number) } : {}),
        });
      } else {
        await inventory.createUnit(projectId, {
          floor_id: values.floor_id,
          unit_number: values.unit_number,
          unit_reference: values.unit_reference,
          asset_class: values.asset_class || "apartment",
          ...(values.unit_type_code ? { unit_type_code: values.unit_type_code } : {}),
          ...(values.bedrooms ? { bedrooms: Number(values.bedrooms) } : {}),
        });
      }
      setNotice("Created.");
      setValues({});
      await onChanged();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not create that record.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="stack">
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      <Tabs
        label="What to create"
        tabs={KINDS.filter((entry) => entry.key !== "phase" || canConfigure).map((entry) => ({
          key: entry.key,
          label: entry.label,
        }))}
        active={kind}
        onSelect={(key) => {
          setKind(key as Kind);
          setValues({});
        }}
      />

      {kind === "phase" ? (
        <FieldRow columns={3}>
          <Field label="Phase code" hint="Immutable once issued, e.g. PHASE-1.">
            <input className="input" required value={values.code ?? ""} onChange={(event) => set("code", event.target.value)} />
          </Field>
          <Field label="Name">
            <input className="input" required value={values.name ?? ""} onChange={(event) => set("name", event.target.value)} />
          </Field>
          <Field label="Sequence" hint="Where it sits in the delivery order." optional>
            <input
              className="input"
              inputMode="numeric"
              value={values.sequence ?? ""}
              onChange={(event) => set("sequence", event.target.value)}
            />
          </Field>
        </FieldRow>
      ) : null}

      {kind === "building" ? (
        <FieldRow columns={3}>
          <Field label="Phase">
            <select
              className="input"
              required
              value={values.phase_id ?? ""}
              onChange={(event) => set("phase_id", event.target.value)}
            >
              <option value="">Choose…</option>
              {phases.map((phase) => (
                <option key={phase.id} value={phase.id}>
                  {phase.code} — {phase.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Building code">
            <input className="input" required value={values.code ?? ""} onChange={(event) => set("code", event.target.value)} />
          </Field>
          <Field label="Name">
            <input className="input" required value={values.name ?? ""} onChange={(event) => set("name", event.target.value)} />
          </Field>
        </FieldRow>
      ) : null}

      {kind === "floor" ? (
        <FieldRow columns={4}>
          <Field label="Building">
            <select
              className="input"
              required
              value={values.building_id ?? ""}
              onChange={(event) => set("building_id", event.target.value)}
            >
              <option value="">Choose…</option>
              {buildings.map((building) => (
                <option key={building.id} value={building.id}>
                  {building.code} — {building.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Floor code" hint="B2, B1, GF, M, 01, RF — whatever the building uses.">
            <input className="input" required value={values.code ?? ""} onChange={(event) => set("code", event.target.value)} />
          </Field>
          <Field label="Label">
            <input className="input" required value={values.label ?? ""} onChange={(event) => set("label", event.target.value)} />
          </Field>
          <Field label="Level number" hint="Numeric ordering." optional>
            <input
              className="input"
              inputMode="numeric"
              value={values.level_number ?? ""}
              onChange={(event) => set("level_number", event.target.value)}
            />
          </Field>
        </FieldRow>
      ) : null}

      {kind === "unit" ? (
        <>
          <FieldRow columns={3}>
            <Field label="Floor">
              <select
                className="input"
                required
                value={values.floor_id ?? ""}
                onChange={(event) => set("floor_id", event.target.value)}
              >
                <option value="">Choose…</option>
                {floors.map((floor) => (
                  <option key={floor.id} value={floor.id}>
                    {floor.code} — {floor.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Unit number" hint="Unique on its floor.">
              <input
                className="input"
                required
                value={values.unit_number ?? ""}
                onChange={(event) => set("unit_number", event.target.value)}
              />
            </Field>
            <Field label="Unit reference" hint="Shown to people. Can be corrected later.">
              <input
                className="input"
                required
                value={values.unit_reference ?? ""}
                onChange={(event) => set("unit_reference", event.target.value)}
              />
            </Field>
          </FieldRow>
          <FieldRow columns={3}>
            <Field label="Asset class">
              <select
                className="input"
                value={values.asset_class ?? "apartment"}
                onChange={(event) => set("asset_class", event.target.value)}
              >
                {["apartment", "villa", "townhouse", "commercial", "other"].map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Unit type" hint="A configured code." optional>
              <input
                className="input"
                value={values.unit_type_code ?? ""}
                onChange={(event) => set("unit_type_code", event.target.value)}
              />
            </Field>
            <Field label="Bedrooms" optional>
              <input
                className="input"
                inputMode="numeric"
                value={values.bedrooms ?? ""}
                onChange={(event) => set("bedrooms", event.target.value)}
              />
            </Field>
          </FieldRow>
        </>
      ) : null}

      <FormActions>
        <Button variant="primary" type="submit" disabled={busy}>
          {busy ? "Saving…" : `Create ${KINDS.find((entry) => entry.key === kind)?.label.toLowerCase() ?? ""}`}
        </Button>
        {kind === "unit" ? (
          <span className="subtle">Loading a whole development? Import a CSV instead.</span>
        ) : null}
      </FormActions>
    </form>
  );
}
