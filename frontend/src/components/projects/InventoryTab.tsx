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
  Position,
  PositionFigure,
  StatusDot,
  TableScroll,
  Tabs,
  TabPanel,
  ToolbarFilter,
} from "@/components/ui";
import { AreaTypesPanel } from "@/components/projects/inventory/AreaTypesPanel";
import { ImportPanel } from "@/components/projects/inventory/ImportPanel";
import {
  BuildingsView,
  FloorsView,
  PhasesView,
  UnitForm,
} from "@/components/projects/inventory/StructureViews";
import { UnitDetailPanel } from "@/components/projects/inventory/UnitDetailPanel";
import { statusLabel, statusTone } from "@/components/projects/inventory/statusLabels";

const PAGE = "200";

/**
 * The inventory workspace, inside the project workspace.
 *
 * A development is Phase → Building → Floor → Unit, and until now this screen
 * showed that as one unit register with three narrowing selects. It read as
 * four levels and behaved as one: choosing "Phase" produced units filtered by
 * phase, so an operator clicking into a hierarchy concept always arrived back
 * at the same table and could never see what a phase or a building *was*.
 *
 * Four object views now, one workspace. Phases shows phases. Buildings shows
 * buildings. Floors shows floors. Units shows units, unchanged — it is the
 * record the business runs on and it stays the default.
 *
 * Drill-down is a filter carried between views, not a navigation stack: "View
 * buildings" from a phase moves to the buildings register with that phase
 * selected, the selection is stated above the register in words, and one
 * action clears it. There is no tree component and no recursive hierarchy
 * engine; this domain has exactly four levels and knows all four of their
 * names.
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
  const [open, setOpen] = useState<"none" | "areas" | "import">("none");
  const [error, setError] = useState<string | null>(null);
  // The unit is the record this business runs on, so it stays the view an
  // operator lands on. The other three are beside it and equally first-class,
  // which is the whole correction: they are no longer hidden inside a dialog
  // called "Add structure".
  const [view, setView] = useState<"phases" | "buildings" | "floors" | "units">("units");
  const [addingUnit, setAddingUnit] = useState(false);

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

  //: What the current parent selection is, said in codes rather than left for
  //: the operator to read out of three dropdowns. Nothing here is derived from
  //: a rendered row: these are the records the server returned.
  const noun = {
    phases: "phases",
    buildings: "buildings",
    floors: "floors",
    units: "units",
  } as const;
  const context = [
    phases.find((phase) => phase.id === filters.phase_id)?.code,
    buildings.find((building) => building.id === filters.building_id)?.code,
    floors.find((floor) => floor.id === filters.floor_id)?.code,
  ].filter((code): code is string => Boolean(code));
  const clearContext = () =>
    setFilters({ ...filters, phase_id: "", building_id: "", floor_id: "" });

  //: Which floors "Add unit" may offer. Narrowed by the context the operator
  //: already chose, and drawn only from what the server returned for them —
  //: a forbidden phase is absent from `floors`, never fetched and hidden.
  const floorsForNewUnit = floors.filter((floor) => {
    if (filters.building_id) return floor.building_id === filters.building_id;
    if (filters.phase_id) {
      return buildings.some(
        (building) => building.id === floor.building_id && building.phase_id === filters.phase_id,
      );
    }
    return true;
  });

  // Inventory is refused while the project is in setup, because that is the
  // window in which its country and currencies can still change under whatever
  // was validated against them. Saying so beats eleven identical 409s.
  if (projectStatus === "setup") {
    return (
      <>
        <PageHeader icon="inventory" title="Inventory" subtitle={sectionDescription("inventory")} compact />
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
        icon="inventory"
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
          </>
        }
      />

      <div className="stack">
        {error ? <Notice tone="error">{error}</Notice> : null}

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
            description="Download the workbook, fill it in, validate, read what is wrong, fix it, apply. Nothing is written until the batch is clean."
            actions={<Button variant="quiet" onClick={() => setOpen("none")}>Close</Button>}
          >
            <ImportPanel projectId={projectId} onApplied={refresh} />
          </Card>
        ) : null}

        <Tabs
          label="Inventory views"
          group="inventory"
          active={view}
          onSelect={(key) => setView(key as typeof view)}
          tabs={[
            { key: "phases", label: "Phases" },
            { key: "buildings", label: "Buildings" },
            { key: "floors", label: "Floors" },
            { key: "units", label: "Units" },
          ]}
        />

        <TabPanel group="inventory" tab={view}>
        {context.length > 0 ? (
          <Notice tone="info">
            Showing {noun[view]} in {context.join(" · ")}.{" "}
            <button className="button-link" type="button" onClick={clearContext}>
              Clear context
            </button>
          </Notice>
        ) : null}

        {view === "phases" ? (
          <PhasesView
            projectId={projectId}
            phases={phases}
            canConfigure={canConfigure}
            onChanged={refresh}
            onViewBuildings={(phase) => {
              setFilters({ ...filters, phase_id: phase.id, building_id: "", floor_id: "" });
              setView("buildings");
            }}
          />
        ) : null}

        {view === "buildings" ? (
          <BuildingsView
            projectId={projectId}
            phases={phases}
            buildings={buildings}
            phaseId={filters.phase_id}
            onPhase={(phase_id) => setFilters({ ...filters, phase_id, building_id: "", floor_id: "" })}
            canWriteStructure={canWriteStructure}
            onChanged={refresh}
            onViewFloors={(building) => {
              setFilters({
                ...filters,
                phase_id: building.phase_id,
                building_id: building.id,
                floor_id: "",
              });
              setView("floors");
            }}
          />
        ) : null}

        {view === "floors" ? (
          <FloorsView
            projectId={projectId}
            phases={phases}
            buildings={buildings}
            floors={floors}
            phaseId={filters.phase_id}
            buildingId={filters.building_id}
            onPhase={(phase_id) => setFilters({ ...filters, phase_id, building_id: "", floor_id: "" })}
            onBuilding={(building_id) => setFilters({ ...filters, building_id, floor_id: "" })}
            canWriteStructure={canWriteStructure}
            onChanged={refresh}
            onViewUnits={(floor) => {
              setFilters({ ...filters, building_id: floor.building_id, floor_id: floor.id });
              setView("units");
            }}
          />
        ) : null}

        {view === "units" && register ? (
          <section className="asset-position" aria-label="Inventory position">
            <div className="asset-position-identity"><Icon name="inventory" /><span>Property inventory<span className="cell-secondary">Physical assets · commercial readiness</span></span></div>
            <Position compact>
              <PositionFigure lead label="Units" value={register.total} />
              <PositionFigure label="Available" value={register.available_count} />
              <PositionFigure label="Held" value={register.held_count} tone={register.held_count > 0 ? "warning" : "neutral"} />
              <PositionFigure label="Unreleased" value={register.unreleased_count} />
            </Position>
            {areaTypes.length === 0 ? <p className="footnote">No area types configured — no unit can be measured or released.</p> : null}
          </section>
        ) : null}

        {view === "units" ? (
        <>
        <DataToolbar
          framed
          activeSummary={[
            phases.find((phase) => phase.id === filters.phase_id)?.name,
            buildings.find((building) => building.id === filters.building_id)?.name,
            floors.find((floor) => floor.id === filters.floor_id)?.label,
            filters.commercial_status ? statusLabel(filters.commercial_status) : null,
            filters.search ? `“${filters.search}”` : null,
          ].filter(Boolean).join(" · ")}
          search={{
            value: filters.search,
            onChange: (value) => setFilters({ ...filters, search: value }),
            placeholder: "Unit reference or number",
            label: "Search units",
          }}
          count={register ? { shown: register.units.length, total: register.total, noun: "unit" } : undefined}
          actions={
            canWriteStructure ? (
              <Button variant="primary" onClick={() => setAddingUnit(true)}>
                Add unit
              </Button>
            ) : undefined
          }
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
                    : "Add a unit, or import the whole development from the Excel template."
                }
              />
            </div>
          ) : (
            <>
              <TableScroll label="Unit register" fixedFirst stickyHeader>
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
                            icon="inventory"
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
                        {unit.internal_area === null ? "Not measured" : `${unit.internal_area} ${unit.weighted_saleable_area_unit ?? ""} internal`}
                        {unit.gross_area !== null ? (
                          <span className="cell-secondary">
                            {unit.gross_area} {unit.gross_area_unit ?? ""} gross
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
        </>
        ) : null}
        </TabPanel>
      </div>

      {addingUnit ? (
        <UnitForm
          projectId={projectId}
          floors={floorsForNewUnit}
          defaultFloorId={filters.floor_id}
          onCancel={() => setAddingUnit(false)}
          onSaved={async () => {
            setAddingUnit(false);
            // The context the operator drilled through is kept: they are very
            // likely adding a second unit to the same floor.
            await refresh();
          }}
        />
      ) : null}

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
