"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, inventory } from "@/lib/api";
import type { AreaType, Building, Floor, Phase, UnitRegister, UnitSummary } from "@/lib/api";
import { sectionDescription } from "@/components/shell/navigation";
import {
  Badge,
  Button,
  Card,
  DataToolbar,
  EmptyState,
  Icon,
  IdentityCell,
  Loading,
  Meter,
  Notice,
  PageHeader,
  PlaceCell,
  StatStrip,
  StatStripItem,
  StatStripNote,
  StatusDot,
  TableScroll,
  ToolbarFilter,
} from "@/components/ui";
import { AreaTypesPanel } from "@/components/projects/inventory/AreaTypesPanel";
import { HierarchyForms } from "@/components/projects/inventory/HierarchyForms";
import { ImportPanel } from "@/components/projects/inventory/ImportPanel";
import { UnitDetailPanel } from "@/components/projects/inventory/UnitDetailPanel";
import { statusLabel, statusTone } from "@/components/projects/inventory/statusLabels";

const PAGE = "200";

/**
 * The inventory register, inside the project workspace.
 *
 * One toolbar and one table rather than a tree: a development is
 * Phase → Building → Floor → Unit, and three narrowing selects say that as
 * clearly as a component library would, without the component library.
 *
 * The register is built to be scanned down: the unit's identity pinned on the
 * left, where it sits and how big it is in the middle, and its four status
 * dimensions on the right — commercial carrying the weight, the other three as
 * a dot and a word, because the column heading already says they are statuses.
 *
 * Every column here is one somebody filters or sorts a development by. Parking
 * and storage, the sub-assets, the custom fields and the release blockers are
 * all real and all live in Unit 360: a register wide enough to hold them is a
 * register that scrolls sideways before it answers anything.
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
      const query: Record<string, string> = { limit: PAGE };
      for (const [key, value] of Object.entries(filters)) {
        if (value) query[key] = value;
      }
      const result = await inventory.units(projectId, query);
      if (ticket !== latestRequest.current) return;
      setRegister(result);
      setError(null);
    } catch (caught) {
      if (ticket !== latestRequest.current) return;
      setRegister({ units: [], total: 0, available_count: 0, held_count: 0, unreleased_count: 0 });
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
  const filtered = Object.values(filters).some((value) => value !== "");

  // Inventory is refused while the project is in setup, because that is the
  // window in which its country and currencies can still change under whatever
  // was validated against them. Saying so beats eleven identical 409s.
  if (projectStatus === "setup") {
    return (
      <>
        <PageHeader title="Inventory" subtitle={sectionDescription("inventory")} compact />
        <Card>
          <EmptyState
            title="Finalize project setup first"
            hint="Confirm country and currency settings, then move the project to Pre-development before loading inventory."
          />
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Inventory"
        subtitle={sectionDescription("inventory")}
        compact
        actions={
          <>
            {canConfigure ? (
              <Button
                variant="quiet"
                onClick={() => setOpen(open === "areas" ? "none" : "areas")}
                aria-expanded={open === "areas"}
              >
                Area types
              </Button>
            ) : null}
            {canWriteStructure ? (
              <Button onClick={() => setOpen(open === "import" ? "none" : "import")} aria-expanded={open === "import"}>
                Import
              </Button>
            ) : null}
            {canWriteStructure ? (
              <Button
                variant="primary"
                onClick={() => setOpen(open === "hierarchy" ? "none" : "hierarchy")}
                aria-expanded={open === "hierarchy"}
              >
                Add structure
              </Button>
            ) : null}
          </>
        }
      />

      <div className="stack">
        {error ? <Notice tone="error">{error}</Notice> : null}

        {open === "hierarchy" ? (
          <Card
            title="Add structure"
            description="A phase, a building, a floor or a unit. For a whole development, import a CSV instead."
            actions={<Button variant="quiet" onClick={() => setOpen("none")}>Close</Button>}
          >
            <HierarchyForms
              projectId={projectId}
              phases={phases}
              buildings={buildings}
              floors={floors}
              canConfigure={canConfigure}
              onChanged={refresh}
            />
          </Card>
        ) : null}
        {open === "areas" ? (
          <Card
            title="Area types"
            description="How this project measures its units, and how much of each area it sells."
            actions={<Button variant="quiet" onClick={() => setOpen("none")}>Close</Button>}
          >
            <AreaTypesPanel projectId={projectId} areaTypes={areaTypes} onChanged={refresh} />
          </Card>
        ) : null}
        {open === "import" ? (
          <Card
            title="Import inventory"
            description="Validate a CSV, read what is wrong, fix the file, apply. Nothing is written until the batch is clean."
            actions={<Button variant="quiet" onClick={() => setOpen("none")}>Close</Button>}
          >
            <ImportPanel projectId={projectId} onApplied={refresh} />
          </Card>
        ) : null}

        {register ? (
          <StatStrip>
            <StatStripItem label="Units" value={register.total} />
            <StatStripItem label="Available" value={register.available_count} />
            <StatStripItem
              label="Held"
              value={register.held_count}
              tone={register.held_count > 0 ? "warning" : "neutral"}
            />
            <StatStripItem label="Unreleased" value={register.unreleased_count} />
            {areaTypes.length === 0 ? (
              <StatStripNote>No area types configured — no unit can be measured or released.</StatStripNote>
            ) : null}
          </StatStrip>
        ) : null}

        <DataToolbar
          framed
          search={{
            value: filters.search,
            onChange: (value) => setFilters({ ...filters, search: value }),
            placeholder: "Unit reference or number",
            label: "Search units",
          }}
          count={register ? { shown: register.units.length, total: register.total, noun: "unit" } : undefined}
          onReset={
            filtered
              ? () => setFilters({ phase_id: "", building_id: "", floor_id: "", commercial_status: "", search: "" })
              : undefined
          }
        >
          <ToolbarFilter label="Phase" active={filters.phase_id !== ""}>
            <select
              className="input"
              value={filters.phase_id}
              onChange={(event) =>
                setFilters({ ...filters, phase_id: event.target.value, building_id: "", floor_id: "" })
              }
            >
              <option value="">All phases</option>
              {phases.map((phase) => (
                <option key={phase.id} value={phase.id}>
                  {phase.code} — {phase.name}
                </option>
              ))}
            </select>
          </ToolbarFilter>
          <ToolbarFilter label="Building" active={filters.building_id !== ""}>
            <select
              className="input"
              value={filters.building_id}
              onChange={(event) => setFilters({ ...filters, building_id: event.target.value, floor_id: "" })}
            >
              <option value="">All buildings</option>
              {visibleBuildings.map((building) => (
                <option key={building.id} value={building.id}>
                  {building.code} — {building.name}
                </option>
              ))}
            </select>
          </ToolbarFilter>
          <ToolbarFilter label="Floor" active={filters.floor_id !== ""}>
            <select
              className="input"
              value={filters.floor_id}
              onChange={(event) => setFilters({ ...filters, floor_id: event.target.value })}
            >
              <option value="">All floors</option>
              {visibleFloors.map((floor) => (
                <option key={floor.id} value={floor.id}>
                  {floor.code} — {floor.label}
                </option>
              ))}
            </select>
          </ToolbarFilter>
          <ToolbarFilter label="Commercial status" active={filters.commercial_status !== ""}>
            <select
              className="input"
              value={filters.commercial_status}
              onChange={(event) => setFilters({ ...filters, commercial_status: event.target.value })}
            >
              <option value="">Any status</option>
              {["unreleased", "held", "available", "reserved", "contract_pending", "contracted", "returned"].map(
                (status) => (
                  <option key={status} value={status}>
                    {statusLabel(status)}
                  </option>
                ),
              )}
            </select>
          </ToolbarFilter>
        </DataToolbar>

        <Card flush>
          {register === null ? (
            <Loading label="Loading inventory…" shape="rows" rows={8} />
          ) : register.units.length === 0 ? (
            <div className="card-body">
              <EmptyState
                title={filtered ? "No unit matches" : "No units yet"}
                hint={
                  filtered
                    ? "Widen the filter to see the rest of the register."
                    : "Add a phase, building and floor, then create units or import them from a CSV."
                }
              />
            </div>
          ) : (
            <>
              <TableScroll label="Unit register" fixedFirst>
                <thead>
                  <tr>
                    <th scope="col">Unit</th>
                    <th scope="col">Location</th>
                    <th scope="col" className="num">
                      Area
                    </th>
                    <th scope="col">Commercial</th>
                    <th scope="col">Legal</th>
                    <th scope="col">Collection</th>
                    <th scope="col">Delivery</th>
                    <th scope="col">Readiness</th>
                    <th scope="col">
                      <span className="visually-hidden">Open</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {register.units.map((unit) => (
                    <tr key={unit.id} aria-selected={selected?.id === unit.id}>
                      <th scope="row">
                        <button className="button-link" type="button" onClick={() => setSelected(unit)}>
                          <IdentityCell
                            name={unit.unit_reference}
                            meta={
                              [unit.unit_type_code, unit.bedrooms === null ? null : `${unit.bedrooms} bed`]
                                .filter(Boolean)
                                .join(" · ") || unit.asset_class
                            }
                          />
                        </button>
                      </th>
                      <td>
                        <PlaceCell
                          main={unit.building_code ? `Building ${unit.building_code}` : null}
                          sub={
                            [
                              unit.phase_code ? `Phase ${unit.phase_code}` : null,
                              unit.floor_code ? `Floor ${unit.floor_code}` : null,
                            ]
                              .filter(Boolean)
                              .join(" · ") || undefined
                          }
                        />
                      </td>
                      <td className="num">
                        {unit.internal_area ?? "—"}
                        {unit.weighted_saleable_area ? (
                          <span className="cell-secondary">
                            {unit.weighted_saleable_area} {unit.weighted_saleable_area_unit ?? ""} weighted
                          </span>
                        ) : null}
                      </td>
                      <td>
                        <Badge tone={statusTone(unit.commercial_status)}>{statusLabel(unit.commercial_status)}</Badge>
                      </td>
                      <td>
                        <StatusDot tone={statusTone(unit.legal_status)}>{statusLabel(unit.legal_status)}</StatusDot>
                      </td>
                      <td>
                        <StatusDot tone={statusTone(unit.collection_status)}>
                          {statusLabel(unit.collection_status)}
                        </StatusDot>
                      </td>
                      <td>
                        <StatusDot tone={statusTone(unit.delivery_status)}>{statusLabel(unit.delivery_status)}</StatusDot>
                      </td>
                      <td>
                        {unit.release_eligible ? (
                          <StatusDot tone="success">Releasable</StatusDot>
                        ) : (
                          <Meter
                            percent={unit.completeness_percent}
                            label={`Data completeness ${unit.completeness_percent} per cent`}
                            note={unit.is_complete ? "Not releasable" : "Incomplete"}
                          />
                        )}
                      </td>
                      <td className="row-go" aria-hidden="true">
                        <Icon name="chevron" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </TableScroll>
              {register.total > register.units.length ? (
                <p className="table-foot">
                  Showing the first {register.units.length} of {register.total} units. Narrow the filter to
                  reach the rest.
                </p>
              ) : null}
            </>
          )}
        </Card>
      </div>

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
