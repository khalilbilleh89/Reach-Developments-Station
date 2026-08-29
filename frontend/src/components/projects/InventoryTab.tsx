"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, inventory } from "@/lib/api";
import type {
  AreaType,
  Building,
  Floor,
  Phase,
  UnitRegister,
  UnitSummary,
} from "@/lib/api";
import { Badge, EmptyState, Field, Loading, Notice, Panel } from "@/components/ui";
import { AreaTypesPanel } from "@/components/projects/inventory/AreaTypesPanel";
import { HierarchyForms } from "@/components/projects/inventory/HierarchyForms";
import { ImportPanel } from "@/components/projects/inventory/ImportPanel";
import { UnitDetailPanel } from "@/components/projects/inventory/UnitDetailPanel";
import { statusLabel } from "@/components/projects/inventory/statusLabels";

/**
 * The inventory register, inside the project workspace.
 *
 * Deliberately one filter strip and one table rather than a tree: a development
 * is Phase → Building → Floor → Unit, and four select boxes say that as clearly
 * as a component library would, without the component library.
 *
 * Secondary attributes live in the detail panel. A register showing thirty-five
 * columns is a register nobody reads.
 */
export function InventoryTab({
  projectId,
  projectStatus,
  roles,
  canWriteStructure,
  canConfigure,
}: {
  projectId: string;
  projectStatus: string;
  roles: Set<string>;
  canWriteStructure: boolean;
  canConfigure: boolean;
}) {
  const [register, setRegister] = useState<UnitRegister | null>(null);
  const [phases, setPhases] = useState<Phase[]>([]);
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [floors, setFloors] = useState<Floor[]>([]);
  const [areaTypes, setAreaTypes] = useState<AreaType[]>([]);
  const [filters, setFilters] = useState({
    phase_id: "",
    building_id: "",
    floor_id: "",
    commercial_status: "",
    search: "",
  });
  const [selected, setSelected] = useState<UnitSummary | null>(null);
  const [open, setOpen] = useState<"none" | "hierarchy" | "areas" | "import">("none");
  const [error, setError] = useState<string | null>(null);

  // Typing in the search box fires a request per change, and responses can come
  // back out of order. Without this ticket the register can end up showing the
  // results of a filter the user has already moved on from — which reads as the
  // filter being broken rather than late.
  const latestRequest = useRef(0);

  const loadRegister = useCallback(async () => {
    const ticket = latestRequest.current + 1;
    latestRequest.current = ticket;
    try {
      const query: Record<string, string> = { limit: "100" };
      for (const [key, value] of Object.entries(filters)) {
        if (value) query[key] = value;
      }
      const result = await inventory.units(projectId, query);
      if (ticket !== latestRequest.current) return;
      setRegister(result);
      setError(null);
    } catch (caught) {
      if (ticket !== latestRequest.current) return;
      setRegister({
        units: [],
        total: 0,
        available_count: 0,
        held_count: 0,
        unreleased_count: 0,
      });
      setError(caught instanceof ApiError ? caught.message : "Could not load the inventory.");
    }
  }, [projectId, filters]);

  const loadHierarchy = useCallback(async () => {
    try {
      const [phaseList, buildingList, floorList, areaTypeList] = await Promise.all([
        inventory.phases(projectId),
        inventory.buildings(projectId),
        inventory.floors(projectId),
        inventory.areaTypes(projectId),
      ]);
      setPhases(phaseList);
      setBuildings(buildingList);
      setFloors(floorList);
      setAreaTypes(areaTypeList);
    } catch {
      // The filters degrade to "all"; the register itself still loads.
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await loadRegister();
    })();
  }, [loadRegister]);

  useEffect(() => {
    void (async () => {
      await loadHierarchy();
    })();
  }, [loadHierarchy]);

  const refresh = async () => {
    await Promise.all([loadRegister(), loadHierarchy()]);
  };

  // Buildings and floors narrow with the selection above them, so the strip
  // reads as one hierarchy rather than three unrelated lists.
  const visibleBuildings = filters.phase_id
    ? buildings.filter((building) => building.phase_id === filters.phase_id)
    : buildings;
  const visibleFloors = filters.building_id
    ? floors.filter((floor) => floor.building_id === filters.building_id)
    : floors;

  // Inventory is refused while the project is in setup, because that is the
  // window in which its country and currencies can still change under whatever
  // was validated against them. Saying so beats eleven identical 409s.
  if (projectStatus === "setup") {
    return (
      <Panel title="Inventory" description="Not yet — the project basis is still open.">
        <EmptyState
          title="Finalize project setup"
          hint="Confirm country and currency settings, then move the project to
                Pre-development before loading inventory."
        />
      </Panel>
    );
  }

  return (
    <>
      <Panel
        title="Inventory"
        description="Every unit in this development, and what stops each one being released."
        actions={
          <>
            {canWriteStructure ? (
              <button
                className="button button-small"
                type="button"
                onClick={() => setOpen(open === "hierarchy" ? "none" : "hierarchy")}
              >
                {open === "hierarchy" ? "Cancel" : "Add structure"}
              </button>
            ) : null}
            {canConfigure ? (
              <button
                className="button button-small"
                type="button"
                onClick={() => setOpen(open === "areas" ? "none" : "areas")}
              >
                {open === "areas" ? "Cancel" : "Area types"}
              </button>
            ) : null}
            {canWriteStructure ? (
              <button
                className="button button-small"
                type="button"
                onClick={() => setOpen(open === "import" ? "none" : "import")}
              >
                {open === "import" ? "Cancel" : "Import inventory"}
              </button>
            ) : null}
          </>
        }
      >
        {error ? <Notice tone="error">{error}</Notice> : null}

        {open === "hierarchy" ? (
          <HierarchyForms
            projectId={projectId}
            phases={phases}
            buildings={buildings}
            floors={floors}
            canConfigure={canConfigure}
            onChanged={refresh}
          />
        ) : null}
        {open === "areas" ? (
          <AreaTypesPanel projectId={projectId} areaTypes={areaTypes} onChanged={refresh} />
        ) : null}
        {open === "import" ? (
          <ImportPanel projectId={projectId} onApplied={refresh} />
        ) : null}

        <div className="form-inline">
          <Field label="Phase">
            <select
              className="input"
              value={filters.phase_id}
              onChange={(event) =>
                setFilters({
                  ...filters,
                  phase_id: event.target.value,
                  building_id: "",
                  floor_id: "",
                })
              }
            >
              <option value="">All phases</option>
              {phases.map((phase) => (
                <option key={phase.id} value={phase.id}>
                  {phase.code} — {phase.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Building">
            <select
              className="input"
              value={filters.building_id}
              onChange={(event) =>
                setFilters({ ...filters, building_id: event.target.value, floor_id: "" })
              }
            >
              <option value="">All buildings</option>
              {visibleBuildings.map((building) => (
                <option key={building.id} value={building.id}>
                  {building.code}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Floor">
            <select
              className="input input-short"
              value={filters.floor_id}
              onChange={(event) => setFilters({ ...filters, floor_id: event.target.value })}
            >
              <option value="">All floors</option>
              {visibleFloors.map((floor) => (
                <option key={floor.id} value={floor.id}>
                  {floor.code}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Commercial status">
            <select
              className="input"
              value={filters.commercial_status}
              onChange={(event) =>
                setFilters({ ...filters, commercial_status: event.target.value })
              }
            >
              <option value="">Any status</option>
              {["unreleased", "held", "available", "reserved", "contracted"].map((status) => (
                <option key={status} value={status}>
                  {statusLabel(status)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Search">
            <input
              className="input"
              value={filters.search}
              placeholder="Unit reference or number"
              onChange={(event) => setFilters({ ...filters, search: event.target.value })}
            />
          </Field>
        </div>

        {register === null ? (
          <Loading label="Loading inventory…" />
        ) : register.units.length === 0 ? (
          <EmptyState
            title="No units match"
            hint="Add a phase, building and floor, then create units or import them from a CSV."
          />
        ) : (
          <>
            <div className="chip-list">
              <span className="chip">{register.total} units</span>
              <span className="chip">{register.unreleased_count} unreleased</span>
              <span className="chip">{register.held_count} held</span>
              <span className="chip">{register.available_count} available</span>
            </div>
            <div className="table-scroll">
              <table className="table">
                <caption className="visually-hidden">Unit register</caption>
                <thead>
                  <tr>
                    <th scope="col">Unit</th>
                    <th scope="col">Phase</th>
                    <th scope="col">Building / floor</th>
                    <th scope="col">Type</th>
                    <th scope="col">Beds</th>
                    <th scope="col">Internal</th>
                    <th scope="col">Weighted</th>
                    <th scope="col">Parking</th>
                    <th scope="col">Storage</th>
                    <th scope="col">Commercial</th>
                    <th scope="col">Legal</th>
                    <th scope="col">Collection</th>
                    <th scope="col">Delivery</th>
                    <th scope="col">Complete</th>
                    <th scope="col">Release</th>
                  </tr>
                </thead>
                <tbody>
                  {register.units.map((unit) => (
                    <tr key={unit.id}>
                      <th scope="row">
                        <button
                          className="button button-small"
                          type="button"
                          onClick={() => setSelected(unit)}
                        >
                          {unit.unit_reference}
                        </button>
                      </th>
                      <td>{unit.phase_code ?? "—"}</td>
                      <td className="nowrap">
                        {unit.building_code ?? "—"} / {unit.floor_code ?? "—"}
                      </td>
                      <td>{unit.unit_type_code ?? "—"}</td>
                      <td>{unit.bedrooms ?? "—"}</td>
                      <td className="mono nowrap">{unit.internal_area ?? "—"}</td>
                      <td className="mono nowrap">{unit.weighted_saleable_area ?? "—"}</td>
                      <td>{unit.parking_count}</td>
                      <td>{unit.storage_count}</td>
                      <td>
                        <Badge tone={unit.commercial_status === "available" ? "success" : "neutral"}>
                          {statusLabel(unit.commercial_status)}
                        </Badge>
                      </td>
                      <td>{statusLabel(unit.legal_status)}</td>
                      <td>{statusLabel(unit.collection_status)}</td>
                      <td>{statusLabel(unit.delivery_status)}</td>
                      <td>
                        {unit.is_complete ? (
                          <Badge tone="success">Complete</Badge>
                        ) : (
                          <span className="subtle">{unit.completeness_percent}%</span>
                        )}
                      </td>
                      <td>
                        {unit.release_eligible ? (
                          <Badge tone="success">Eligible</Badge>
                        ) : (
                          <Badge tone="muted">Blocked</Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Panel>

      {selected ? (
        <UnitDetailPanel
          projectId={projectId}
          roles={roles}
          unitId={selected.id}
          canWriteStructure={canWriteStructure}
          canConfigure={canConfigure}
          onClose={() => setSelected(null)}
          onChanged={refresh}
        />
      ) : null}
    </>
  );
}
