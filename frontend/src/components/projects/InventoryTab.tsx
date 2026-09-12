"use client";

import { RegisterPagination } from "@/components/ui";

import { useRegisterFields, useRegisterRestore } from "@/components/shell/registerState";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, inventory } from "@/lib/api";
import type { AreaType, Building, Floor, Phase, UnitRegister } from "@/lib/api";
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
import { UnassignedAssets } from "./inventory/UnassignedAssets";
import { InventoryConfiguration } from "./inventory/InventoryConfiguration";
import { StockSummary, StockTable } from "./inventory/StockView";
import { AreaTypesPanel } from "@/components/projects/inventory/AreaTypesPanel";
import { ImportPanel } from "@/components/projects/inventory/ImportPanel";
import {
  BuildingsView,
  FloorsView,
  PhasesView,
  UnitForm,
} from "@/components/projects/inventory/StructureViews";
import { RecordLink } from "@/components/ui";
import { money } from "@/lib/format";
import { useCurrencyCode } from "@/lib/currency";
import { LIST_PRICE_READERS, hasAnyRole } from "@/lib/roles";
import type { LaunchRegister } from "@/lib/api";

const PAGE = "200";

/** The physical hierarchy and launch list, scoped and totalled by the server. */
export function InventoryTab({
  roles,
  projectId,
  projectStatus,
  canWriteStructure,
  canConfigure,
}: {
  projectId: string;
  projectStatus: string;
  roles: Set<string>;
  canWriteStructure: boolean;
  canConfigure: boolean;
}) {
  const [pageFields, setPageFields] = useRegisterFields({offset: ""});
  const parsedOffset = Number(pageFields.offset);
  const offset = Number.isSafeInteger(parsedOffset) && parsedOffset >= 0 ? parsedOffset : 0;
  const setOffset = (value: number) => setPageFields({offset: String(value)});
  const [pageTotal, setPageTotal] = useState(0);
  const codeOf = useCurrencyCode();
  const seesPrice = hasAnyRole(roles, LIST_PRICE_READERS);
  const [launchValues, setLaunchValues] = useState<LaunchRegister | null>(null);
  const [priceError,setPriceError] = useState<string | null>(null);
  const [register, setRegister] = useState<UnitRegister | null>(null);
  useRegisterRestore(register !== null);
  const [phases, setPhases] = useState<Phase[]>([]);
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [floors, setFloors] = useState<Floor[]>([]);
  const [areaTypes, setAreaTypes] = useState<AreaType[]>([]);
  const [filters, updateFilters] = useRegisterFields({
    phase_id: "",
    building_id: "",
    floor_id: "",
    asset_class: "",
    is_active: "",
    search: "",
  });
  const setFilters = (changes: Partial<typeof filters>) => { updateFilters(changes); setPageFields({offset: ""}); };
  const [open, setOpen] = useState<"none" | "areas" | "import">("none");
  const [error, setError] = useState<string | null>(null);
  const [hierarchyError, setHierarchyError] = useState<string | null>(null);
  // The unit is the record this business runs on, so it stays the view an
  // operator lands on. The other three are beside it and equally first-class,
  // which is the whole correction: they are no longer hidden inside a dialog
  // called "Add structure".
  const [viewFields, setViewFields] = useRegisterFields({ view: "units" });
  const view = (["phases", "buildings", "floors", "units", "stock", "configuration"].includes(viewFields.view) ? viewFields.view : "units") as "phases" | "buildings" | "floors" | "units" | "stock" | "configuration";
  const [stockFields,setStockFields]=useRegisterFields({stock_areas:""});
  const setView = (view: string) => setViewFields({ view });
  const [addingUnit, setAddingUnit] = useState(false);

  // Typing in the search box fires a request per change, and responses can come
  // back out of order. Without this ticket the register can end up showing the
  // results of a filter the user has already moved on from — which reads as the
  // filter being broken rather than late.
  const latestRequest = useRef(0);

  const loadRegister = useCallback(async () => {
    const ticket = latestRequest.current + 1;
    latestRequest.current = ticket;
    setRegister(null);
    setLaunchValues(null);setPriceError(null);
    setError(null);
    try {
      const query: Record<string, string> = { limit: PAGE, offset: String(offset) };
      for (const [key, value] of Object.entries(filters)) {
        if (value) query[key] = value;
      }
      const [result, prices] = await Promise.all([
        inventory.units(projectId, query),
        seesPrice ? inventory.launchValues(projectId, query).then(data => ({data,error:null})).catch(() => ({data:null,error:"Launch prices could not be loaded."})) : Promise.resolve({data:null,error:null}),
      ]);
      if (ticket !== latestRequest.current) return;
      setRegister(result);
      setLaunchValues(prices.data);setPriceError(prices.error);
      setPageTotal(result.total);
      setError(null);
    } catch (caught) {
      if (ticket !== latestRequest.current) return;
      setRegister(null);
      setError(caught instanceof ApiError ? caught.message : "Could not load the inventory.");
    }
  }, [projectId, filters, offset, seesPrice]);

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
      setHierarchyError(null);
    } catch {
      setHierarchyError("Could not load phases, buildings, floors or area types. Creation and hierarchy choices are unavailable until retried.");
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
    stock: "units",
    configuration: "choices",
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
    if (!floor.is_active || !buildings.some(b => b.id === floor.building_id && b.is_active && phases.some(p => p.id === b.phase_id && p.is_active))) return false;
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
  if (projectStatus === "setup" && view === "configuration") {
    return <><PageHeader icon="inventory" title="Inventory Configuration" subtitle="Project-specific unit choices" compact /><InventoryConfiguration key={projectId} projectId={projectId} canConfigure={canConfigure} /></>;
  }
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
        title={view === "configuration" ? "Inventory Configuration" : view === "stock" ? "Stock" : "Inventory"}
        subtitle={view === "configuration" ? "Set the unit choices for this project." : view === "stock" ? "Your inventory, clearly laid out." : sectionDescription("inventory")}
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
            {canWriteStructure && view !== "configuration" ? (
              <Button onClick={() => setOpen(open === "import" ? "none" : "import")} aria-expanded={open === "import"}>
                Import
              </Button>
            ) : null}
          </>
        }
      />

      <div className="stack">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {hierarchyError ? <><Notice tone="error">{hierarchyError}</Notice><Button onClick={() => void loadHierarchy()}>Retry hierarchy</Button></> : null}

        {open === "areas" ? (
          <Card
            title="Area types"
            description="How this project measures its units, and how much of each area it sells."
            actions={<Button variant="quiet" onClick={() => setOpen("none")}>Close</Button>}
          >
            <AreaTypesPanel canDelete={roles.has("system_admin") || roles.has("master_admin")} projectId={projectId} areaTypes={areaTypes} onChanged={refresh} />
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
            { key: "stock", label: "Stock" },
            { key: "configuration", label: "Configuration" },
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
            canAdmin={roles.has("system_admin") || roles.has("master_admin")}
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
            canAdmin={roles.has("system_admin") || roles.has("master_admin")}
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
            canAdmin={roles.has("system_admin") || roles.has("master_admin")}
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
            <div className="asset-position-identity"><Icon name="inventory" /><span>Property inventory<span className="cell-secondary">Unit features · launch prices</span></span></div>
            <Position compact>
              <PositionFigure lead label="Units" value={register.total} />
              {launchValues ? <><PositionFigure label="Priced units" value={launchValues.priced_count} /><PositionFigure label="Needs price" value={launchValues.unpriced_count} /><PositionFigure label="Needs repricing" value={launchValues.repricing_count} />{launchValues.totals.map(total=><PositionFigure key={total.currency_id} label="Launch list value · ex tax" value={money(total.amount,codeOf(total.currency_id))} />)}</> : null}
            </Position>
            {priceError ? <Notice tone="error">{priceError}</Notice> : null}
            <p className="footnote">Totals cover all matching inventory, including previously released units. Only current approved list prices contribute; unpriced units and prices requiring review are excluded.</p>
            {areaTypes.length === 0 ? <p className="footnote">No area types configured — no unit can be measured or released.</p> : null}
          </section>
        ) : null}

        {view === "configuration" ? <div className="stack"><InventoryConfiguration key={projectId} projectId={projectId} canConfigure={canConfigure} />{roles.has("system_admin") || roles.has("master_admin") ? <UnassignedAssets key={`assets-${projectId}`} projectId={projectId} /> : null}</div> : null}
        {view === "stock" && register ? <StockSummary register={register} prices={launchValues} /> : null}
        {view === "stock" && priceError ? <Notice tone="error">{priceError}</Notice> : null}
        {view === "units" || view === "stock" ? (
        <>
        <DataToolbar
          framed
          activeSummary={[
            phases.find((phase) => phase.id === filters.phase_id)?.name,
            buildings.find((building) => building.id === filters.building_id)?.name,
            floors.find((floor) => floor.id === filters.floor_id)?.label,
            filters.asset_class || null,
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
            canWriteStructure && view !== "stock" ? (
              <Button variant="primary" disabled={!!hierarchyError} onClick={() => setAddingUnit(true)}>
                Add unit
              </Button>
            ) : undefined
          }
          onReset={
            filtered
              ? () => setFilters({ phase_id: "", building_id: "", floor_id: "", asset_class: "", is_active: "", search: "" })
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
          <ToolbarFilter label="Activity" active={filters.is_active !== ""}><select className="input" value={filters.is_active} onChange={e => setFilters({...filters, is_active: e.target.value})}><option value="">Active and inactive</option><option value="true">Active only</option><option value="false">Inactive only</option></select></ToolbarFilter>
          <ToolbarFilter label="Property class" active={filters.asset_class !== ""}><select className="input" value={filters.asset_class} onChange={event=>setFilters({...filters,asset_class:event.target.value})}><option value="">All classes</option>{["apartment","villa","townhouse","commercial","other"].map(value=><option key={value} value={value}>{value}</option>)}</select></ToolbarFilter>
        </DataToolbar>

        <Card flush>
          {register === null ? (
            error ? <Button onClick={() => void loadRegister()}>Retry inventory</Button> : <Loading label="Loading inventory…" shape="rows" rows={8} />
          ) : view === "stock" ? (
            <StockTable projectId={projectId} register={register} prices={launchValues} seesPrice={seesPrice} priceError={priceError} expanded={stockFields.stock_areas==="all"} onExpanded={()=>setStockFields({stock_areas:stockFields.stock_areas==="all" ? "" : "all"})} />
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
                    {seesPrice ? <th scope="col">Launch price · ex tax</th> : null}
                    <th scope="col">Release preparation</th>
                    <th scope="col">
                      <span className="visually-hidden">Open</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {register.units.map((unit) => (
                    <tr key={unit.id}>
                      <th scope="row">
                        <RecordLink projectId={projectId} kind="unit" id={unit.id}>
                          <IdentityCell
                            icon="inventory"
                            name={unit.unit_reference}
                            meta={
                              [unit.asset_class, unit.bedrooms === null ? null : `${unit.bedrooms} bed`]
                                .filter(Boolean)
                                .join(" · ") || unit.asset_class
                            }
                          />
                        </RecordLink>
                        {!unit.is_active ? <Badge tone="neutral">Inactive</Badge> : null}
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
                      {seesPrice ? <td className="num">{priceError ? "Unavailable" : (()=>{const price=launchValues?.rows.find(row=>row.unit_id===unit.id);return price?.repricing_required ? "Review price" : price?.price ? money(price.price,codeOf(price.currency_id)) : "Not priced";})()}</td> : null}
                      <td><StatusDot tone={unit.release_eligible ? "success" : "neutral"}>{unit.release_eligible ? "Ready" : "Review release"}</StatusDot></td>
                      <td className="row-go" aria-hidden="true">
                        <Icon name="chevron" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </TableScroll>

            </>
          )}
        </Card>
        {pageTotal > 0 || register ? <RegisterPagination offset={offset} total={pageTotal} busy={!register} onChange={setOffset} /> : null}
        </>
        ) : null}
        </TabPanel>
      </div>

      {addingUnit ? (
        <UnitForm
          projectId={projectId}
          floors={floorsForNewUnit}
          buildings={buildings}
          phases={phases}
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

    </>
  );
}
