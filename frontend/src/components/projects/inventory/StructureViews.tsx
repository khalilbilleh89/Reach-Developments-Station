"use client";

import { useState } from "react";

import { ApiError, inventory } from "@/lib/api";
import type { Building, Floor, Phase } from "@/lib/api";
import {
  Badge,
  Button,
  Card,
  DataToolbar,
  Drawer,
  EmptyState,
  Field,
  FieldRow,
  FormDialog,
  Icon,
  IdentityCell,
  KeyValue,
  KeyValueGrid,
  Notice,
  PlaceCell,
  TableScroll,
  ToolbarFilter,
} from "@/components/ui";

/**
 * The three hierarchy registers: phases, buildings and floors.
 *
 * Each shows the objects it is named after. That sounds too obvious to state,
 * and it is the whole point of this file: before it, choosing "Phase" in
 * Inventory produced the *unit* register filtered by phase, so every level of
 * the hierarchy was one screen wearing four labels and an operator could never
 * see what a phase actually was.
 *
 * There is no tree component here and there will not be one. This domain has
 * exactly four levels and knows all four of their names. A recursive component
 * would be a general answer to a question nobody asked, and it would draw every
 * level as equally important when the unit is the record the business runs on.
 *
 * Drill-down is a filter carried forward, never a navigation stack. Opening a
 * phase and choosing "View buildings" moves to the buildings register with that
 * phase selected — and the selection is visible in the toolbar, where it can be
 * cleared. Nobody gets trapped inside a path.
 */

const PHASE_STATUSES = ["planning", "active", "on_hold", "completed", "cancelled"] as const;

function statusLabel(status: string): string {
  return status.replace(/_/g, " ").replace(/^./, (first) => first.toUpperCase());
}

function phaseTone(status: string): "success" | "warning" | "neutral" {
  if (status === "active") return "success";
  if (status === "on_hold" || status === "cancelled") return "warning";
  return "neutral";
}

function matches(haystack: string, needle: string): boolean {
  return haystack.toLowerCase().includes(needle.trim().toLowerCase());
}

// --------------------------------------------------------------------------- //
// Phases
// --------------------------------------------------------------------------- //

export function PhasesView({
  projectId,
  phases,
  canConfigure,
  onChanged,
  onViewBuildings,
}: {
  projectId: string;
  phases: Phase[];
  canConfigure: boolean;
  onChanged: () => Promise<void>;
  onViewBuildings: (phase: Phase) => void;
}) {
  const [selected, setSelected] = useState<Phase | null>(null);
  const [editing, setEditing] = useState<Phase | "new" | null>(null);
  const [search, setSearch] = useState("");

  const shown = phases.filter((phase) => matches(`${phase.code} ${phase.name}`, search));

  return (
    <>
      <DataToolbar
        framed
        search={{
          value: search,
          onChange: setSearch,
          placeholder: "Phase code or name",
          label: "Search phases",
        }}
        count={{ shown: shown.length, total: phases.length, noun: "phase" }}
        onReset={search ? () => setSearch("") : undefined}
        actions={
          canConfigure ? (
            <Button variant="primary" onClick={() => setEditing("new")}>
              Add phase
            </Button>
          ) : undefined
        }
      />

      <Card flush>
        {shown.length === 0 ? (
          <div className="card-body">
            <EmptyState
              title={phases.length === 0 ? "No phases yet" : "No phase matches"}
              hint={
                phases.length === 0
                  ? "Create the first phase, or import the project structure from the Excel template."
                  : "Widen the search to see the rest of the register."
              }
            />
          </div>
        ) : (
          <TableScroll label="Phase register" fixedFirst>
            <thead>
              <tr>
                <th scope="col">Phase</th>
                <th scope="col">Status</th>
                <th scope="col">Planned start</th>
                <th scope="col">Planned completion</th>
                <th scope="col">Active</th>
                <th scope="col">
                  <span className="visually-hidden">Open</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.map((phase) => (
                <tr key={phase.id} aria-selected={selected?.id === phase.id}>
                  <th scope="row">
                    <button className="button-link" type="button" onClick={() => setSelected(phase)}>
                      <IdentityCell name={phase.code} meta={phase.name} />
                    </button>
                  </th>
                  <td>
                    <Badge tone={phaseTone(phase.status)}>{statusLabel(phase.status)}</Badge>
                  </td>
                  <td>{phase.planned_start ?? "—"}</td>
                  <td>{phase.planned_completion ?? "—"}</td>
                  <td>{phase.is_active ? "Yes" : "No"}</td>
                  <td className="row-go" aria-hidden="true">
                    <Icon name="chevron" />
                  </td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        )}
      </Card>

      {selected ? (
        <Drawer inspector
          eyebrow={selected.code}
          title={selected.name}
          onClose={() => setSelected(null)}
          facts={[
            { label: "Status", value: statusLabel(selected.status) },
            { label: "Sequence", value: String(selected.sequence) },
            { label: "Active", value: selected.is_active ? "Yes" : "No" },
          ]}
          actions={
            <>
              <Button
                onClick={() => {
                  onViewBuildings(selected);
                  setSelected(null);
                }}
              >
                View buildings
              </Button>
              {canConfigure ? (
                <Button variant="quiet" onClick={() => setEditing(selected)}>
                  Edit
                </Button>
              ) : null}
            </>
          }
        >
          <KeyValueGrid>
            <KeyValue label="Planned start" value={selected.planned_start ?? "Not stated"} />
            <KeyValue
              label="Planned completion"
              value={selected.planned_completion ?? "Not stated"}
            />
            <KeyValue label="Notes" value={selected.notes ?? "None"} />
          </KeyValueGrid>
        </Drawer>
      ) : null}

      {editing ? (
        <PhaseForm
          projectId={projectId}
          phase={editing === "new" ? null : editing}
          onCancel={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            setSelected(null);
            await onChanged();
          }}
        />
      ) : null}
    </>
  );
}

function PhaseForm({
  projectId,
  phase,
  onCancel,
  onSaved,
}: {
  projectId: string;
  phase: Phase | null;
  onCancel: () => void;
  onSaved: () => Promise<void>;
}) {
  const [values, setValues] = useState({
    code: phase?.code ?? "",
    name: phase?.name ?? "",
    sequence: String(phase?.sequence ?? 0),
    status: phase?.status ?? "planning",
    planned_start: phase?.planned_start ?? "",
    planned_completion: phase?.planned_completion ?? "",
    notes: phase?.notes ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        name: values.name,
        sequence: Number(values.sequence) || 0,
        status: values.status,
        planned_start: values.planned_start || null,
        planned_completion: values.planned_completion || null,
        notes: values.notes || null,
      };
      if (phase === null) {
        await inventory.createPhase(projectId, { ...body, code: values.code });
      } else {
        // `code` is absent on purpose: a phase code is immutable once issued
        // and the request schema refuses it rather than quietly ignoring it.
        await inventory.updatePhase(projectId, phase.id, body);
      }
      await onSaved();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save the phase.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <FormDialog
      title={phase === null ? "Add phase" : `Edit ${phase.code}`}
      confirmLabel="Save phase"
      busy={busy}
      disabled={values.name.trim() === "" || (phase === null && values.code.trim() === "")}
      onCancel={onCancel}
      onSubmit={() => void save()}
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      <FieldRow columns={2}>
        <Field
          label="Phase code"
          hint={phase === null ? "Stable identity — it cannot be changed later." : "Immutable once issued."}
        >
          <input
            className="input"
            value={values.code}
            disabled={phase !== null}
            onChange={(event) => setValues({ ...values, code: event.target.value })}
          />
        </Field>
        <Field label="Name">
          <input
            className="input"
            value={values.name}
            onChange={(event) => setValues({ ...values, name: event.target.value })}
          />
        </Field>
      </FieldRow>
      <FieldRow columns={2}>
        <Field label="Status">
          <select
            className="input"
            value={values.status}
            onChange={(event) => setValues({ ...values, status: event.target.value })}
          >
            {PHASE_STATUSES.map((status) => (
              <option key={status} value={status}>
                {statusLabel(status)}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Sequence" hint="Where this phase sits in the running order.">
          <input
            className="input"
            type="number"
            min={0}
            value={values.sequence}
            onChange={(event) => setValues({ ...values, sequence: event.target.value })}
          />
        </Field>
      </FieldRow>
      <FieldRow columns={2}>
        <Field label="Planned start" optional>
          <input
            className="input"
            type="date"
            value={values.planned_start}
            onChange={(event) => setValues({ ...values, planned_start: event.target.value })}
          />
        </Field>
        <Field label="Planned completion" optional>
          <input
            className="input"
            type="date"
            value={values.planned_completion}
            onChange={(event) => setValues({ ...values, planned_completion: event.target.value })}
          />
        </Field>
      </FieldRow>
      <Field label="Notes" optional>
        <textarea
          className="input"
          rows={3}
          value={values.notes}
          onChange={(event) => setValues({ ...values, notes: event.target.value })}
        />
      </Field>
    </FormDialog>
  );
}

// --------------------------------------------------------------------------- //
// Buildings
// --------------------------------------------------------------------------- //

export function BuildingsView({
  projectId,
  phases,
  buildings,
  phaseId,
  onPhase,
  canWriteStructure,
  onChanged,
  onViewFloors,
}: {
  projectId: string;
  phases: Phase[];
  buildings: Building[];
  phaseId: string;
  onPhase: (phaseId: string) => void;
  canWriteStructure: boolean;
  onChanged: () => Promise<void>;
  onViewFloors: (building: Building) => void;
}) {
  const [selected, setSelected] = useState<Building | null>(null);
  const [editing, setEditing] = useState<Building | "new" | null>(null);
  const [search, setSearch] = useState("");

  const phaseOf = (building: Building) => phases.find((phase) => phase.id === building.phase_id);
  const inPhase = phaseId ? buildings.filter((b) => b.phase_id === phaseId) : buildings;
  const shown = inPhase.filter((building) => matches(`${building.code} ${building.name}`, search));

  return (
    <>
      <DataToolbar
        framed
        search={{
          value: search,
          onChange: setSearch,
          placeholder: "Building code or name",
          label: "Search buildings",
        }}
        count={{ shown: shown.length, total: inPhase.length, noun: "building" }}
        onReset={
          search || phaseId
            ? () => {
                setSearch("");
                onPhase("");
              }
            : undefined
        }
        actions={
          canWriteStructure && phases.length > 0 ? (
            <Button variant="primary" onClick={() => setEditing("new")}>
              Add building
            </Button>
          ) : undefined
        }
      >
        <ToolbarFilter label="Phase" active={phaseId !== ""}>
          <select className="input" value={phaseId} onChange={(event) => onPhase(event.target.value)}>
            <option value="">All phases</option>
            {phases.map((phase) => (
              <option key={phase.id} value={phase.id}>
                {phase.code} — {phase.name}
              </option>
            ))}
          </select>
        </ToolbarFilter>
      </DataToolbar>

      <Card flush>
        {shown.length === 0 ? (
          <div className="card-body">
            <EmptyState
              title={inPhase.length === 0 ? "No buildings yet" : "No building matches"}
              hint={
                phases.length === 0
                  ? "A building belongs to a phase. Create a phase first."
                  : inPhase.length === 0
                    ? "Add a building, or import the project structure from the Excel template."
                    : "Widen the search to see the rest of the register."
              }
            />
          </div>
        ) : (
          <TableScroll label="Building register" fixedFirst>
            <thead>
              <tr>
                <th scope="col">Building</th>
                <th scope="col">Phase</th>
                <th scope="col">Zone</th>
                <th scope="col">Block</th>
                <th scope="col" className="num">
                  Sequence
                </th>
                <th scope="col">Active</th>
                <th scope="col">
                  <span className="visually-hidden">Open</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.map((building) => {
                const phase = phaseOf(building);
                return (
                  <tr key={building.id} aria-selected={selected?.id === building.id}>
                    <th scope="row">
                      <button
                        className="button-link"
                        type="button"
                        onClick={() => setSelected(building)}
                      >
                        <IdentityCell name={building.code} meta={building.name} />
                      </button>
                    </th>
                    <td>
                      <PlaceCell main={phase ? phase.code : "—"} sub={phase?.name} />
                    </td>
                    <td>{building.zone ?? "—"}</td>
                    <td>{building.block ?? "—"}</td>
                    <td className="num">{building.sequence}</td>
                    <td>{building.is_active ? "Yes" : "No"}</td>
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

      {selected ? (
        <Drawer inspector
          eyebrow={selected.code}
          title={selected.name}
          subtitle={phaseOf(selected)?.name ?? undefined}
          onClose={() => setSelected(null)}
          facts={[
            { label: "Phase", value: phaseOf(selected)?.code ?? "—" },
            { label: "Sequence", value: String(selected.sequence) },
            { label: "Active", value: selected.is_active ? "Yes" : "No" },
          ]}
          actions={
            <>
              <Button
                onClick={() => {
                  onViewFloors(selected);
                  setSelected(null);
                }}
              >
                View floors
              </Button>
              {canWriteStructure ? (
                <Button variant="quiet" onClick={() => setEditing(selected)}>
                  Edit
                </Button>
              ) : null}
            </>
          }
        >
          <KeyValueGrid>
            <KeyValue label="Zone" value={selected.zone ?? "Not stated"} />
            <KeyValue label="Block" value={selected.block ?? "Not stated"} />
            <KeyValue label="Entrance / wing" value={selected.entrance_wing ?? "Not stated"} />
          </KeyValueGrid>
        </Drawer>
      ) : null}

      {editing ? (
        <BuildingForm
          projectId={projectId}
          phases={phases}
          building={editing === "new" ? null : editing}
          defaultPhaseId={phaseId}
          onCancel={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            setSelected(null);
            await onChanged();
          }}
        />
      ) : null}
    </>
  );
}

function BuildingForm({
  projectId,
  phases,
  building,
  defaultPhaseId,
  onCancel,
  onSaved,
}: {
  projectId: string;
  phases: Phase[];
  building: Building | null;
  defaultPhaseId: string;
  onCancel: () => void;
  onSaved: () => Promise<void>;
}) {
  const [values, setValues] = useState({
    // Preselected from the register's own filter: a building added while
    // looking at Phase 1 belongs to Phase 1, and asking again is asking the
    // operator to restate something the screen already knows.
    phase_id: building?.phase_id ?? defaultPhaseId ?? "",
    code: building?.code ?? "",
    name: building?.name ?? "",
    zone: building?.zone ?? "",
    block: building?.block ?? "",
    entrance_wing: building?.entrance_wing ?? "",
    sequence: String(building?.sequence ?? 0),
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        name: values.name,
        zone: values.zone || null,
        block: values.block || null,
        entrance_wing: values.entrance_wing || null,
        sequence: Number(values.sequence) || 0,
      };
      if (building === null) {
        await inventory.createBuilding(projectId, {
          ...body,
          phase_id: values.phase_id,
          code: values.code,
        });
      } else {
        // Neither `phase_id` nor `code` is sent: a building does not change
        // phase and its code is identity. The update schema refuses both.
        await inventory.updateBuilding(projectId, building.id, body);
      }
      await onSaved();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save the building.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <FormDialog
      title={building === null ? "Add building" : `Edit ${building.code}`}
      confirmLabel="Save building"
      busy={busy}
      disabled={
        values.name.trim() === "" ||
        (building === null && (values.code.trim() === "" || values.phase_id === ""))
      }
      onCancel={onCancel}
      onSubmit={() => void save()}
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      <FieldRow columns={2}>
        <Field label="Phase" hint={building === null ? undefined : "A building does not change phase."}>
          <select
            className="input"
            value={values.phase_id}
            disabled={building !== null}
            onChange={(event) => setValues({ ...values, phase_id: event.target.value })}
          >
            <option value="">Choose a phase</option>
            {phases.map((phase) => (
              <option key={phase.id} value={phase.id}>
                {phase.code} — {phase.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Building code" hint="Unique within its phase. B1 in two phases is two buildings.">
          <input
            className="input"
            value={values.code}
            disabled={building !== null}
            onChange={(event) => setValues({ ...values, code: event.target.value })}
          />
        </Field>
      </FieldRow>
      <FieldRow columns={2}>
        <Field label="Name">
          <input
            className="input"
            value={values.name}
            onChange={(event) => setValues({ ...values, name: event.target.value })}
          />
        </Field>
        <Field label="Sequence">
          <input
            className="input"
            type="number"
            min={0}
            value={values.sequence}
            onChange={(event) => setValues({ ...values, sequence: event.target.value })}
          />
        </Field>
      </FieldRow>
      <FieldRow columns={3}>
        <Field label="Zone" optional>
          <input
            className="input"
            value={values.zone}
            onChange={(event) => setValues({ ...values, zone: event.target.value })}
          />
        </Field>
        <Field label="Block" optional>
          <input
            className="input"
            value={values.block}
            onChange={(event) => setValues({ ...values, block: event.target.value })}
          />
        </Field>
        <Field label="Entrance / wing" optional>
          <input
            className="input"
            value={values.entrance_wing}
            onChange={(event) => setValues({ ...values, entrance_wing: event.target.value })}
          />
        </Field>
      </FieldRow>
    </FormDialog>
  );
}

// --------------------------------------------------------------------------- //
// Floors
// --------------------------------------------------------------------------- //

export function FloorsView({
  projectId,
  phases,
  buildings,
  floors,
  phaseId,
  buildingId,
  onPhase,
  onBuilding,
  canWriteStructure,
  onChanged,
  onViewUnits,
}: {
  projectId: string;
  phases: Phase[];
  buildings: Building[];
  floors: Floor[];
  phaseId: string;
  buildingId: string;
  onPhase: (phaseId: string) => void;
  onBuilding: (buildingId: string) => void;
  canWriteStructure: boolean;
  onChanged: () => Promise<void>;
  onViewUnits: (floor: Floor) => void;
}) {
  const [selected, setSelected] = useState<Floor | null>(null);
  const [editing, setEditing] = useState<Floor | "new" | null>(null);
  const [search, setSearch] = useState("");

  const buildingOf = (floor: Floor) => buildings.find((b) => b.id === floor.building_id);
  const phaseOfBuilding = (building?: Building) =>
    building ? phases.find((phase) => phase.id === building.phase_id) : undefined;

  const offered = phaseId ? buildings.filter((b) => b.phase_id === phaseId) : buildings;
  const scoped = floors.filter((floor) => {
    if (buildingId) return floor.building_id === buildingId;
    if (phaseId) return offered.some((building) => building.id === floor.building_id);
    return true;
  });
  const shown = scoped.filter((floor) => matches(`${floor.code} ${floor.label}`, search));

  return (
    <>
      <DataToolbar
        framed
        search={{
          value: search,
          onChange: setSearch,
          placeholder: "Floor code or label",
          label: "Search floors",
        }}
        count={{ shown: shown.length, total: scoped.length, noun: "floor" }}
        onReset={
          search || phaseId || buildingId
            ? () => {
                setSearch("");
                onPhase("");
                onBuilding("");
              }
            : undefined
        }
        actions={
          canWriteStructure && buildings.length > 0 ? (
            <Button variant="primary" onClick={() => setEditing("new")}>
              Add floor
            </Button>
          ) : undefined
        }
      >
        <ToolbarFilter label="Phase" active={phaseId !== ""}>
          <select className="input" value={phaseId} onChange={(event) => onPhase(event.target.value)}>
            <option value="">All phases</option>
            {phases.map((phase) => (
              <option key={phase.id} value={phase.id}>
                {phase.code} — {phase.name}
              </option>
            ))}
          </select>
        </ToolbarFilter>
        <ToolbarFilter label="Building" active={buildingId !== ""}>
          <select
            className="input"
            value={buildingId}
            onChange={(event) => onBuilding(event.target.value)}
          >
            <option value="">All buildings</option>
            {offered.map((building) => (
              <option key={building.id} value={building.id}>
                {building.code} — {building.name}
              </option>
            ))}
          </select>
        </ToolbarFilter>
      </DataToolbar>

      <Card flush>
        {shown.length === 0 ? (
          <div className="card-body">
            <EmptyState
              title={scoped.length === 0 ? "No floors yet" : "No floor matches"}
              hint={
                buildings.length === 0
                  ? "A floor belongs to a building. Create a building first."
                  : scoped.length === 0
                    ? "Add the first floor, or import the project structure from the Excel template."
                    : "Widen the search to see the rest of the register."
              }
            />
          </div>
        ) : (
          <TableScroll label="Floor register" fixedFirst>
            <thead>
              <tr>
                <th scope="col">Floor</th>
                <th scope="col">Building</th>
                <th scope="col">Phase</th>
                <th scope="col" className="num">
                  Level
                </th>
                <th scope="col" className="num">
                  Sequence
                </th>
                <th scope="col">Active</th>
                <th scope="col">
                  <span className="visually-hidden">Open</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.map((floor) => {
                const building = buildingOf(floor);
                const phase = phaseOfBuilding(building);
                return (
                  <tr key={floor.id} aria-selected={selected?.id === floor.id}>
                    <th scope="row">
                      <button className="button-link" type="button" onClick={() => setSelected(floor)}>
                        <IdentityCell name={floor.code} meta={floor.label} />
                      </button>
                    </th>
                    <td>
                      <PlaceCell main={building ? building.code : "—"} sub={building?.name} />
                    </td>
                    <td>{phase ? phase.code : "—"}</td>
                    <td className="num">{floor.level_number ?? "—"}</td>
                    <td className="num">{floor.sequence}</td>
                    <td>{floor.is_active ? "Yes" : "No"}</td>
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

      {selected ? (
        <Drawer inspector
          eyebrow={selected.code}
          title={selected.label}
          subtitle={(() => {
            const building = buildingOf(selected);
            const phase = phaseOfBuilding(building);
            return [building?.name, phase?.name].filter(Boolean).join(" · ") || undefined;
          })()}
          onClose={() => setSelected(null)}
          facts={[
            { label: "Building", value: buildingOf(selected)?.code ?? "—" },
            {
              label: "Level",
              value: selected.level_number === null ? "Not stated" : String(selected.level_number),
            },
            { label: "Active", value: selected.is_active ? "Yes" : "No" },
          ]}
          actions={
            <>
              <Button
                onClick={() => {
                  onViewUnits(selected);
                  setSelected(null);
                }}
              >
                View units
              </Button>
              {canWriteStructure ? (
                <Button variant="quiet" onClick={() => setEditing(selected)}>
                  Edit
                </Button>
              ) : null}
            </>
          }
        >
          <KeyValueGrid>
            <KeyValue label="Sequence" value={String(selected.sequence)} />
            <KeyValue
              label="Level number"
              value={selected.level_number === null ? "Not stated" : String(selected.level_number)}
            />
          </KeyValueGrid>
        </Drawer>
      ) : null}

      {editing ? (
        <FloorForm
          projectId={projectId}
          buildings={offered.length > 0 ? offered : buildings}
          floor={editing === "new" ? null : editing}
          defaultBuildingId={buildingId}
          onCancel={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            setSelected(null);
            await onChanged();
          }}
        />
      ) : null}
    </>
  );
}

function FloorForm({
  projectId,
  buildings,
  floor,
  defaultBuildingId,
  onCancel,
  onSaved,
}: {
  projectId: string;
  buildings: Building[];
  floor: Floor | null;
  defaultBuildingId: string;
  onCancel: () => void;
  onSaved: () => Promise<void>;
}) {
  const [values, setValues] = useState({
    building_id: floor?.building_id ?? defaultBuildingId ?? "",
    code: floor?.code ?? "",
    label: floor?.label ?? "",
    level_number: floor?.level_number === null || floor === null ? "" : String(floor.level_number),
    sequence: String(floor?.sequence ?? 0),
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        label: values.label,
        level_number: values.level_number === "" ? null : Number(values.level_number),
        sequence: Number(values.sequence) || 0,
      };
      if (floor === null) {
        await inventory.createFloor(projectId, {
          ...body,
          building_id: values.building_id,
          code: values.code,
        });
      } else {
        await inventory.updateFloor(projectId, floor.id, body);
      }
      await onSaved();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save the floor.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <FormDialog
      title={floor === null ? "Add floor" : `Edit ${floor.code}`}
      confirmLabel="Save floor"
      busy={busy}
      disabled={
        values.label.trim() === "" ||
        (floor === null && (values.code.trim() === "" || values.building_id === ""))
      }
      onCancel={onCancel}
      onSubmit={() => void save()}
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      <FieldRow columns={2}>
        <Field label="Building">
          <select
            className="input"
            value={values.building_id}
            disabled={floor !== null}
            onChange={(event) => setValues({ ...values, building_id: event.target.value })}
          >
            <option value="">Choose a building</option>
            {buildings.map((building) => (
              <option key={building.id} value={building.id}>
                {building.code} — {building.name}
              </option>
            ))}
          </select>
        </Field>
        <Field
          label="Floor code"
          hint="What the building calls it: B2, B1, GF, M, 01, RF. Text, not a number."
        >
          <input
            className="input"
            value={values.code}
            disabled={floor !== null}
            onChange={(event) => setValues({ ...values, code: event.target.value })}
          />
        </Field>
      </FieldRow>
      <FieldRow columns={3}>
        <Field label="Label">
          <input
            className="input"
            value={values.label}
            onChange={(event) => setValues({ ...values, label: event.target.value })}
          />
        </Field>
        <Field label="Level number" optional hint="Ordering context. A basement is negative.">
          <input
            className="input"
            type="number"
            value={values.level_number}
            onChange={(event) => setValues({ ...values, level_number: event.target.value })}
          />
        </Field>
        <Field label="Sequence">
          <input
            className="input"
            type="number"
            min={0}
            value={values.sequence}
            onChange={(event) => setValues({ ...values, sequence: event.target.value })}
          />
        </Field>
      </FieldRow>
    </FormDialog>
  );
}

// --------------------------------------------------------------------------- //
// Units — the one form that is not a hierarchy record
// --------------------------------------------------------------------------- //

/** The asset classes the domain accepts. Mirrors `ASSET_CLASSES` server-side. */
const ASSET_CLASSES = ["apartment", "villa", "townhouse", "commercial", "other"] as const;

/**
 * Create one unit, from the Units register.
 *
 * This form exists because retiring the generic "Add structure" dialog took
 * manual unit creation with it — the dialog was four forms behind tabs, and
 * removing the abstraction removed the only way to add a unit by hand. Import
 * is the other way in, not the only one: an operator adding a single unit to a
 * finished floor should not have to open a spreadsheet.
 *
 * Deliberately small. Everything a unit physically *is* — internal area,
 * balcony, terrace, parking, storage, features — is PR-V2-03's, and putting it
 * here now would fix its shape before that design exists.
 */
export function UnitForm({
  projectId,
  floors,
  defaultFloorId,
  onCancel,
  onSaved,
}: {
  projectId: string;
  floors: Floor[];
  defaultFloorId: string;
  onCancel: () => void;
  onSaved: () => Promise<void>;
}) {
  const [values, setValues] = useState({
    // Preselected from the register's own context. Reaching Units through
    // Phase → Building → Floor → View units and then being asked which floor
    // is the screen forgetting what it just did.
    floor_id: defaultFloorId || (floors.length === 1 ? floors[0].id : ""),
    unit_number: "",
    unit_reference: "",
    asset_class: "apartment",
    unit_type_code: "",
    bedrooms: "",
    bathrooms: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await inventory.createUnit(projectId, {
        floor_id: values.floor_id,
        unit_number: values.unit_number,
        unit_reference: values.unit_reference,
        asset_class: values.asset_class,
        ...(values.unit_type_code ? { unit_type_code: values.unit_type_code } : {}),
        ...(values.bedrooms ? { bedrooms: Number(values.bedrooms) } : {}),
        ...(values.bathrooms ? { bathrooms: Number(values.bathrooms) } : {}),
      });
      await onSaved();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not create the unit.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <FormDialog
      title="Add unit"
      confirmLabel="Create unit"
      busy={busy}
      disabled={
        values.floor_id === "" ||
        values.unit_number.trim() === "" ||
        values.unit_reference.trim() === ""
      }
      onCancel={onCancel}
      onSubmit={() => void save()}
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      {floors.length === 0 ? (
        <Notice tone="warning">
          A unit belongs to a floor, and this project has none yet. Add a floor first, or import
          the structure from the Excel template.
        </Notice>
      ) : null}
      <FieldRow columns={2}>
        <Field label="Floor">
          {/* Only the floors the server already returned for this project and
              this operator. Nothing forbidden is fetched and then hidden. */}
          <select
            className="input"
            value={values.floor_id}
            onChange={(event) => setValues({ ...values, floor_id: event.target.value })}
          >
            <option value="">Choose a floor</option>
            {floors.map((floor) => (
              <option key={floor.id} value={floor.id}>
                {floor.code} — {floor.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Asset class">
          <select
            className="input"
            value={values.asset_class}
            onChange={(event) => setValues({ ...values, asset_class: event.target.value })}
          >
            {ASSET_CLASSES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </Field>
      </FieldRow>
      <FieldRow columns={2}>
        <Field label="Unit number" hint="Unique on its floor.">
          <input
            className="input"
            value={values.unit_number}
            onChange={(event) => setValues({ ...values, unit_number: event.target.value })}
          />
        </Field>
        <Field label="Unit reference" hint="What people call it. Can be corrected later.">
          <input
            className="input"
            value={values.unit_reference}
            onChange={(event) => setValues({ ...values, unit_reference: event.target.value })}
          />
        </Field>
      </FieldRow>
      <FieldRow columns={3}>
        <Field label="Unit type" hint="A configured code." optional>
          <input
            className="input"
            value={values.unit_type_code}
            onChange={(event) => setValues({ ...values, unit_type_code: event.target.value })}
          />
        </Field>
        <Field label="Bedrooms" optional>
          <input
            className="input"
            type="number"
            min={0}
            value={values.bedrooms}
            onChange={(event) => setValues({ ...values, bedrooms: event.target.value })}
          />
        </Field>
        <Field label="Bathrooms" optional>
          <input
            className="input"
            type="number"
            min={0}
            value={values.bathrooms}
            onChange={(event) => setValues({ ...values, bathrooms: event.target.value })}
          />
        </Field>
      </FieldRow>
    </FormDialog>
  );
}
