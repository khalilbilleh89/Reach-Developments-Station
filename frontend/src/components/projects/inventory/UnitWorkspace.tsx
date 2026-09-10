"use client";

import { useCallback, useEffect, useState, useRef } from "react";
import { UnitStages } from "@/components/projects/construction/StageWorkspace";

import { ApiError, collections, inventory, pricing, sales } from "@/lib/api";
import type {
  AreaSchedule,
  AreaType,
  CollectionSaleSummary,
  CustomValue,
  SaleContract,
  SubAsset,
  Unit,
  UnitPricing,
  UnitStatusEvent,
} from "@/lib/api";
import { toAnswer } from "@/lib/answer";
import type { Answer } from "@/lib/answer";
import { useCurrencyCode } from "@/lib/currency";
import { money } from "@/lib/format";
import {
  COLLECTION_READERS,
  INTERNAL_PRICE_READERS,
  LIST_PRICE_READERS,
  PRICING_APPROVERS,
  PRICING_WRITERS,
  SALES_READERS,
  hasAnyRole,
} from "@/lib/roles";
import { Button, Card, FormDialog, Field, Badge, PromptDialog, RecordWorkspace, RecordLink, Loading, Notice, useRecordTab } from "@/components/ui";
import type { WorkspaceFact, WorkspaceHeadline } from "@/components/ui";
import { QuotePreviewPanel } from "@/components/projects/pricing/QuotePreviewPanel";
import { EditForm, asValue } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";
import { UnitCollections } from "@/components/projects/collections/UnitCollections";
import { UnitStanding } from "./unit/UnitStanding";
import { SellingPriceForm } from "@/components/projects/inventory/unit/SellingPriceForm";
import { PhysicalRecord } from "@/components/projects/inventory/unit/PhysicalRecord";
import { UnitAreas } from "@/components/projects/inventory/unit/UnitAreas";
import { useRouter } from "next/navigation";
import { recordHref } from "@/components/shell/recordRoutes";
import { PlanSummary } from "@/components/projects/payments/PlanSummary";
import { ReservationForm } from "@/components/projects/sales/ReservationForm";
import { UnitCommitment } from "@/components/projects/inventory/unit/UnitCommitment";
import type { Commitment } from "@/components/projects/inventory/unit/UnitCommitment";
import { UnitHistory } from "@/components/projects/inventory/unit/UnitHistory";
import { UnitPricingSection } from "@/components/projects/inventory/unit/UnitPricingSection";
import { UnitRelease } from "@/components/projects/inventory/unit/UnitRelease";
import { UnitSummary } from "@/components/projects/inventory/unit/UnitSummary";

/** The unit fields an ordinary edit may carry. Status is absent by construction. */
const UNIT_FIELDS: EditField[] = [
  { name: "unit_reference", label: "Unit reference", group: "Identity", width: "medium" },
  { name: "unit_number", label: "Unit number", group: "Identity", width: "short" },
  { name: "bedrooms", label: "Bedrooms", kind: "number", group: "Identity" },
  { name: "bathrooms", label: "Bathrooms", kind: "number", group: "Identity" },
  { name: "furnishing_specification_code", label: "Furnishing", group: "Features", width: "medium" },
  { name: "floor_band_code", label: "Floor band", group: "Features", width: "short" },
  { name: "orientation_code", label: "Orientation", group: "Features", width: "short" },
  { name: "view_class_code", label: "View", group: "Features", width: "short" },
  { name: "accessibility_code", label: "Accessibility", group: "Features", width: "short" },
  { name: "garden_class_code", label: "Garden", group: "Features", width: "short" },
  { name: "has_maid_room", label: "Maid room", kind: "checkbox", group: "Features" },
  { name: "is_duplex", label: "Duplex", kind: "checkbox", group: "Features" },
  { name: "is_penthouse", label: "Penthouse", kind: "checkbox", group: "Features" },
  { name: "is_corner", label: "Corner unit", kind: "checkbox", group: "Features" },
  { name: "pool_access", label: "Pool access", kind: "checkbox", group: "Features" },
];


/**
 * Unit 360: the file for one property.
 *
 * It opens over the register rather than under it, because the register is a
 * thousand rows long and a person comparing units should not lose their place
 * to look at one. The header is the unit's identity and the three or four
 * figures somebody opened it for; the sections beneath are the departments —
 * a design engineer arrives for the areas, Finance for the price, Legal for
 * the contract, Collections for the cash — and none of them should have to
 * read the other three to find their own.
 *
 * Every figure here came back from the API on this request, and every module
 * is asked only on behalf of a role the server would answer: a Sales Advisor's
 * Unit 360 never requests the unit's cost or margin, so there is nothing to
 * hide. The browser lays out what it was given and offers the actions the
 * server would accept, and the server refuses regardless of which button was
 * on screen.
 */
export function UnitWorkspace({
  projectId,
  roles,
  unitId,
  canWriteStructure,
  canConfigure,
  onChanged,
}: {
  projectId: string;
  roles: Set<string>;
  unitId: string;
  canWriteStructure: boolean;
  canConfigure: boolean;
  onChanged: () => Promise<void>;
}) {
  const router = useRouter();
  const [supportBusy, setSupportBusy] = useState(false);
  const [activityOpen, setActivityOpen] = useState(false);
  const [moving, setMoving] = useState(false);
  const [moveFloor, setMoveFloor] = useState("");
  const [destinations, setDestinations] = useState<{value: string; label: string}[]>([]);
  const [moveError, setMoveError] = useState<string | null>(null);
  const loadDestinations = async () => {
    setMoveError(null); setDestinations([]);
    try {
      const [floors, buildings, phases] = await Promise.all([inventory.floors(projectId), inventory.buildings(projectId), inventory.phases(projectId)]);
      setDestinations(floors.filter(f => f.is_active && buildings.some(b => b.id === f.building_id && b.is_active && phases.some(p => p.id === b.phase_id && p.is_active))).map(f => {
        const b = buildings.find(b => b.id === f.building_id)!;
        const p = phases.find(p => p.id === b.phase_id)!;
        return {value: f.id, label: `${p.code} / ${b.code} / ${f.code} — ${f.label}`};
      }));
    } catch (caught) { setMoveError(caught instanceof ApiError ? caught.message : "Could not load destination floors."); }
  };
  const [detailRevision, setDetailRevision] = useState(-1);
  const [supportRevision, setSupportRevision] = useState(0);
  const supportLoaded = useRef<Record<string, number>>({});
  const [reserving, setReserving] = useState(false);
  const [unit, setUnit] = useState<Unit | null>(null);
  const [schedules, setSchedules] = useState<AreaSchedule[]>([]);
  const [areaTypes, setAreaTypes] = useState<AreaType[]>([]);
  const [assets, setAssets] = useState<SubAsset[]>([]);
  const [values, setValues] = useState<CustomValue[]>([]);
  const [history, setHistory] = useState<UnitStatusEvent[]>([]);
  // One answer per module, made once here and shared by the header facts and
  // the sections. Each is asked for only on behalf of a role the server
  // answers; a refusal it still returns is "denied" and a fault is "failed",
  // and neither is ever drawn as a unit with no price or no commitment.
  const [pricingAnswer, setPricingAnswer] = useState<Answer<UnitPricing>>({ status: "off" });
  const [commitmentAnswer, setCommitmentAnswer] = useState<Answer<Commitment>>({ status: "off" });
  const [collection, setCollection] = useState<Answer<CollectionSaleSummary>>({ status: "off" });
  const [section, setSection] = useRecordTab();
  const [quoting, setQuoting] = useState(false);
  const [pricingBusy, setPricingBusy] = useState(false);
  const [approvingPrice, setApprovingPrice] = useState<string | null>(null);
  const [editing, setEditing] = useState<"none" | "unit" | "fields">("none");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const currencyCodeOf = useCurrencyCode();

  const seesSales = hasAnyRole(roles, SALES_READERS);
  const seesCollections = hasAnyRole(roles, COLLECTION_READERS);
  const seesInternalPrices = hasAnyRole(roles, INTERNAL_PRICE_READERS);
  const seesListPrice = hasAnyRole(roles, LIST_PRICE_READERS);
  const canPrice = hasAnyRole(roles, PRICING_WRITERS);
  const canApprovePricing = hasAnyRole(roles, PRICING_APPROVERS);

  const load = useCallback(async () => {
    try {
      const detail = await inventory.unit(projectId, unitId);
      setUnit(detail);
      setSupportRevision(value => value + 1);
      setError(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not load the unit.");
      return;
    }

    // The modules, each one answer, each requested only for a role the server
    // answers, and each loading on its own so the unit is on screen while
    // they arrive. The list price is refused to Legal and Collections, so
    // their unit file never asks for it.
    const loadPricing = async () => {
      if (!seesListPrice) {
        setPricingAnswer({ status: "off" });
        return;
      }
      setPricingAnswer({ status: "loading" });
      try {
        setPricingAnswer({ status: "ready", data: await pricing.unit(projectId, unitId) });
      } catch (caught) {
        setPricingAnswer(toAnswer(caught));
      }
    };

    // The commercial commitment, and behind it the collections position,
    // which needs the sale's identifier and so waits for a successful read.
    const loadCommercial = async () => {
      if (!seesSales) {
        setCommitmentAnswer({ status: "off" });
        setCollection({ status: "off" });
        return;
      }
      setCommitmentAnswer({ status: "loading" });
      let sale: { sale: SaleContract } | null = null;
      try {
        const reservations = await sales.reservations(projectId, { unit_id: unitId });
        const contracts: SaleContract[] = await sales.contracts(projectId, { unit_id: unitId });
        const live = contracts.find((entry) =>
          ["signature_pending", "active", "termination_pending"].includes(entry.status),
        ) ?? contracts.find((entry) => entry.status === "draft");
        sale = live ? { sale: live } : null;
        setCommitmentAnswer({
          status: "ready",
          data: {
            reservation:
              reservations.find((entry) => entry.id === sale?.sale.reservation_id) ??
              reservations.find((entry) => ["active", "extended"].includes(entry.status)) ??
              reservations.find((entry) => ["draft", "deposit_pending"].includes(entry.status)) ?? null,
            sale,
          },
        });
      } catch (caught) {
        setCommitmentAnswer(toAnswer(caught));
        setCollection({ status: "off" });
        return;
      }
      if (seesCollections && sale && sale.sale.status !== "draft") {
        setCollection({ status: "loading" });
        try {
          setCollection({ status: "ready", data: await collections.account(projectId, sale.sale.id) });
        } catch (caught) {
          setCollection(toAnswer(caught));
        }
      } else {
        setCollection({ status: "off" });
      }
    };

    await Promise.all([loadPricing(), loadCommercial()]);
  }, [projectId, unitId, seesSales, seesCollections, seesListPrice]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  // Identity and commercial summaries load once; physical detail and history follow intent.
  useEffect(() => {
    if (!unit || !["detail", "history"].includes(section) || supportLoaded.current[section] === supportRevision) return;
    let cancelled = false;
    void (async () => {
      setSupportBusy(true);
      try {
        if (section === "history") {
          const events = await inventory.unitHistory(projectId, unitId);
          if (!cancelled) setHistory(events);
        } else {
          const [scheduleList, typeList, assetList, valueList] = await Promise.all([
            inventory.areaSchedules(projectId, unitId), inventory.areaTypes(projectId),
            inventory.subAssets(projectId, { unit_id: unitId }), inventory.unitValues(projectId, unitId),
          ]);
          if (!cancelled) { setSchedules(scheduleList); setAreaTypes(typeList); setAssets(assetList); setValues(valueList); setDetailRevision(supportRevision); }
        }
        if (!cancelled) supportLoaded.current[section] = supportRevision;
      } catch (caught) { if (!cancelled) setError(caught instanceof ApiError ? caught.message : "Could not load this section."); }
      finally { if (!cancelled) setSupportBusy(false); }
    })();
    return () => { cancelled = true; };
  }, [section, projectId, unitId, supportRevision, unit]);

  const transition = async (move: { to_status: string; effective_date: string; reason: string }) => {
    setBusy(true);
    setError(null);
    try {
      await inventory.transitionUnit(projectId, unitId, {
        to_status: move.to_status,
        effective_date: move.effective_date,
        ...(move.reason ? { reason: move.reason } : {}),
      });
      setNotice("Status recorded.");
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
  const movePrice = async (action: "submit" | "approve" | "activate", versionId: string, reason?: string) => {
    if (action === "approve" && reason === undefined) { setApprovingPrice(versionId); setError(null); return; }
    setPricingBusy(true);
    setError(null);
    try {
      if (action === "submit") {
        await pricing.submitPriceVersion(projectId, versionId);
        setNotice("Submitted for approval.");
      } else if (action === "approve") {
        await pricing.approvePriceVersion(projectId, versionId, reason!);
        setApprovingPrice(null);
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

  const approveSchedule = async (scheduleId: string) => {
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
      <RecordWorkspace projectId={projectId} kind="unit" title="Unit">
        <Notice tone="error">{error}</Notice>
      </RecordWorkspace>
    );
  }

  if (unit === null) {
    return (
      <RecordWorkspace projectId={projectId} kind="unit" eyebrow="Unit" title="Loading…">
        <Loading label="Loading unit…" shape="record" />
      </RecordWorkspace>
    );
  }

  const editableValues = values.filter((value) => value.is_editable);
  const unitPricing = pricingAnswer.status === "ready" ? pricingAnswer.data : null;
  const price = unitPricing?.active_price ?? null;
  const priceCode = currencyCodeOf(price?.currency_id);
  const hasSale = commitmentAnswer.status === "ready" && commitmentAnswer.data.sale !== null && commitmentAnswer.data.sale.sale.status !== "draft";
  const liveSale = commitmentAnswer.status === "ready" ? commitmentAnswer.data.sale?.sale : null;

  const sections = [
    { key: "overview", label: "Overview" },
    { key: "detail", label: "Property" },
    ...(seesListPrice ? [{ key: "pricing", label: "Pricing" }] : []),
    ...(seesSales ? [{ key: "commercial", label: "Sale" }] : []),
    ...(seesCollections && hasSale ? [{ key: "collections", label: "Payment & collections" }] : []),
    { key: "construction", label: "Delivery" },
    { key: "release", label: "Release" },
    { key: "history", label: "History" },
  ];
  const activeSection = sections.some((entry) => entry.key === section) ? section : "overview";

  // Each fact follows its module's answer: shown when the module answered,
  // shown as unavailable when the request failed, and absent while loading,
  // when refused, or when never asked. A failure is never drawn as "not
  // priced", "no margin" or a cleared balance.
  // The one value the file is about, set beside the identity. The list price
  // is requested only for a role the server answers, so for Legal and
  // Collections there is no headline and nothing to hide; a failed request is
  // said as a failure, never drawn as "not priced".
  const soldContract = liveSale && ["active", "termination_pending"].includes(liveSale.status) ? liveSale : null;
  const committedUnit = ["contract_pending", "contracted"].includes(unit.commercial_status);
  const headline: WorkspaceHeadline | undefined = soldContract
    ? { value: money(soldContract.net_contract_price_ex_tax, currencyCodeOf(soldContract.currency_id)), label: `${soldContract.sale_number} · Active contract · ex tax` }
    : committedUnit
      ? commitmentAnswer.status === "failed"
        ? { value: "Unavailable", label: "Contract could not be loaded", tone: "muted" }
        : undefined
      : unitPricing
    ? {
        value: price ? money(price.reference_price_ex_tax, priceCode) : "Not priced",
        label: price
          ? unitPricing.repricing_required
            ? "List price · repricing required"
            : `Current list price · v${price.version_number} · ex tax`
          : unitPricing.has_active_configuration
            ? "No live price yet"
            : "No live selling price yet",
        tone: unitPricing.repricing_required ? "danger" : price ? undefined : "muted",
      }
    : pricingAnswer.status === "failed"
      ? { value: "Unavailable", label: "List price could not be loaded", tone: "muted" }
      : undefined;
  const facts: WorkspaceFact[] = [
    {
      label: "Internal area",
      value: unit.internal_area === null ? "Not measured" : `${unit.internal_area} ${unit.weighted_saleable_area_unit ?? ""}`.trim(),
      tone: unit.internal_area === null ? ("muted" as const) : undefined,
    },
    {
      label: "Gross area",
      value:
        unit.gross_area === null
          ? "Not measured"
          : `${unit.gross_area} ${unit.gross_area_unit ?? ""}`.trim(),
      tone: unit.gross_area === null ? ("muted" as const) : undefined,
    },
  ];

  return (
    <RecordWorkspace projectId={projectId} kind="unit"
      eyebrow="Unit 360"
      icon="inventory"
      title={unit.unit_reference}
      subtitle={[
        [unit.asset_class, unit.bedrooms === null ? null : `${unit.bedrooms} bedroom`].filter(Boolean).join(" · ") ||
          unit.asset_class,
        [
          unit.phase_code ? `Phase ${unit.phase_code}` : null,
          unit.building_code ? `Building ${unit.building_code}` : null,
          unit.floor_code ? `Floor ${unit.floor_code}` : null,
        ]
          .filter(Boolean)
          .join(" / "),
      ]
        .filter(Boolean)
        .join(" · ")}
      headline={headline}
      actions={
        <>
        {liveSale ? <RecordLink projectId={projectId} kind="sale" id={liveSale.id} className="button button-primary">Open Sale</RecordLink> : commitmentAnswer.status === "ready" && commitmentAnswer.data.reservation ? <RecordLink projectId={projectId} kind="reservation" id={commitmentAnswer.data.reservation.id} className="button button-primary">Open reservation</RecordLink> : seesSales ? <Button onClick={() => setSection("commercial")}>Sale options</Button> : null}
        {canWriteStructure ? (
          <Button
            data-leaves-editor
            onClick={() => {
              setSection("detail");
              setEditing(editing === "unit" ? "none" : "unit");
            }}
          >
            Edit unit
          </Button>
        ) : null}
        {canWriteStructure ? <>
          <Button disabled={busy} onClick={() => { setActivityOpen(true); setError(null); }}>{unit.is_active ? "Deactivate unit" : "Reactivate unit"}</Button>
          {unit.commercial_status === "unreleased" ? <Button onClick={() => { setMoveFloor(unit.floor_id); setMoving(true); void loadDestinations(); }}>Move unit</Button> : null}
        </> : null}
        </>
      }
      meta={<Badge tone={unit.is_active ? "success" : "neutral"}>{unit.is_active ? "Active unit" : "Inactive unit"}</Badge>}
      status={<UnitStanding unit={unit} />}
      facts={facts}
      tabs={sections}
      activeTab={activeSection}
      onSelectTab={setSection}
     
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      {activeSection === "detail" && !supportBusy && detailRevision === supportRevision && areaTypes.length === 0 ? (
        <Notice tone="info">
          This project has no area types configured yet, so no unit can be measured or released.
        </Notice>
      ) : null}

      {activeSection === "construction" ? <UnitStages projectId={projectId} unitId={unitId} roles={roles} /> : null}
      {activeSection === "overview" ? (
        <UnitSummary
          unit={unit}
          pricing={pricingAnswer}
          commitment={commitmentAnswer}
          collection={collection}
          onOpenTab={setSection}
        />
      ) : null}

      {approvingPrice ? <PromptDialog title={`Approve price for ${unit.unit_reference}`} label="Approval rationale" description="Record what you checked and why this price is approved. Activation remains a separate step." confirmLabel="Approve price" error={error} busy={pricingBusy} onCancel={() => { if (!pricingBusy) setApprovingPrice(null); }} onSubmit={reason => void movePrice("approve", approvingPrice, reason)} /> : null}
      {activityOpen ? <PromptDialog title={`${unit.is_active ? "Deactivate" : "Reactivate"} ${unit.unit_reference}`} label="Reason" description={unit.is_active ? "Only unreleased units can be deactivated. The unit leaves active sales and eligible reporting populations; existing records and historical reports remain. Use Hold for a temporary sales pause." : "The unit returns to active inventory. Its hierarchy must be active and pricing must be reviewed before release."} busy={busy} error={error} confirmLabel={unit.is_active ? "Deactivate unit" : "Reactivate unit"} onCancel={() => { if (!busy) setActivityOpen(false); }} onSubmit={async reason => {
        setBusy(true); setError(null);
        try { await inventory.updateUnit(projectId, unitId, {is_active: !unit.is_active, activity_reason: reason}); setActivityOpen(false); await load(); await onChanged(); }
        catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not change unit activity."); }
        finally { setBusy(false); }
      }} /> : null}
      {moving ? <FormDialog title={`Move ${unit.unit_reference}`} description="Only an unreleased unit may move. Its building, phase and phase-based access follow the destination floor; the price requires review again." confirmLabel="Move unit" busy={busy} disabled={!moveFloor || moveFloor === unit.floor_id || !!moveError} onCancel={() => { if (!busy) setMoving(false); }} onSubmit={async () => {
        setBusy(true); setMoveError(null);
        try { await inventory.updateUnit(projectId, unitId, {floor_id: moveFloor}); setMoving(false); await load(); await onChanged(); }
        catch (caught) { setMoveError(caught instanceof ApiError ? caught.message : "Could not move the unit."); }
        finally { setBusy(false); }
      }}>
        {moveError ? <><Notice tone="error">{moveError}</Notice><Button onClick={() => void loadDestinations()}>Retry floors</Button></> : null}
        <Field label="Destination floor"><select className="input" value={moveFloor} onChange={e => setMoveFloor(e.target.value)}><option value="">Choose a floor</option>{destinations.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}</select></Field>
      </FormDialog> : null}
      {activeSection === "detail" && supportBusy ? <Loading label="Loading property" /> : null}
      {activeSection === "detail" && !supportBusy ? (
        <>
          {editing === "unit" ? (
            <Card title="Edit unit">
              <EditForm
                fields={UNIT_FIELDS}
                columns={3}
                initial={Object.fromEntries(
                  UNIT_FIELDS.map((field) => [field.name, asValue(unit[field.name as keyof Unit] as never)]),
                )}
                onSave={async (changes) => {
                  await inventory.updateUnit(projectId, unitId, changes);
                  await load();
                  await onChanged();
                  setNotice("Unit updated.");
                  setEditing("none");
                }}
                onCancel={() => setEditing("none")}
              />
            </Card>
          ) : null}
          {editing === "fields" ? (
            <Card title="Additional fields">
              <EditForm
                fields={editableValues.map((value) => ({
                  name: value.field_key,
                  label: value.display_label,
                  hint: value.help_text ?? undefined,
                  affix: value.unit_of_measure ?? undefined,
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
                columns={3}
                submitLabel="Save fields"
                initial={Object.fromEntries(editableValues.map((value) => [value.field_key, asValue(value.value)]))}
                onSave={async (changes) => {
                  await inventory.writeUnitValues(projectId, unitId, changes);
                  await load();
                  await onChanged();
                  setNotice("Fields updated.");
                  setEditing("none");
                }}
                onCancel={() => setEditing("none")}
              />
            </Card>
          ) : null}
          <PhysicalRecord key={unitId} projectId={projectId} unit={unit} areaTypes={areaTypes}
            schedules={schedules} assets={assets} canWrite={canWriteStructure}
            onChanged={async () => { await load(); await onChanged(); }} />
          <UnitAreas
            unit={unit}
            schedules={schedules}
            assets={assets}
            values={values}
            canApproveSchedule={canConfigure}
            onApproveSchedule={(scheduleId) => void approveSchedule(scheduleId)}
            onEditUnit={canWriteStructure ? () => setEditing(editing === "unit" ? "none" : "unit") : undefined}
            onEditFields={() => setEditing(editing === "fields" ? "none" : "fields")}
            editableFieldCount={editableValues.length}
          />
        </>
      ) : null}

      {activeSection === "release" ? (
        <UnitRelease
          unit={unit}
          roles={roles}
          busy={busy}
          onSaveControls={async (changes) => {
            await inventory.releaseControls(projectId, unitId, changes);
            await load();
            await onChanged();
            setNotice("Release controls updated.");
          }}
          onTransition={(move) => void transition(move)}
        />
      ) : null}

      {activeSection === "pricing" ? (
        <>
          {canPrice ? <SellingPriceForm projectId={projectId} unitId={unitId} currencyCode={currencyCodeOf(unitPricing?.direct_price_currency_id)} onChanged={async () => { await load(); await onChanged(); }} /> : null}
          <UnitPricingSection
            answer={pricingAnswer}
            canPrice={canPrice}
            canApprove={canApprovePricing}
            canSeeInternal={seesInternalPrices}
            busy={pricingBusy}
            onMove={(action, versionId) => void movePrice(action, versionId)}
            onQuote={() => setQuoting((open) => !open)}
          />
          {quoting && unitPricing?.active_price ? (
            <QuotePreviewPanel
              projectId={projectId}
              unitId={unitId}
              currencyCode={currencyCodeOf(unitPricing.active_price.currency_id)}
              onClose={() => setQuoting(false)}
            />
          ) : null}
        </>
      ) : null}

      {activeSection === "commercial" ? (
        <>
          {commitmentAnswer.status === "ready" ? (
            commitmentAnswer.data.reservation || commitmentAnswer.data.sale ? (
              <RecordLink projectId={projectId} kind={liveSale ? "sale" : "reservation"} id={liveSale?.id ?? commitmentAnswer.data.reservation!.id} className="button button-primary">Open Sale Workspace</RecordLink>
            ) : (roles.has("sales_operations") || roles.has("sales_advisor")) && unit.commercial_status === "available" ? (
              reserving ? <ReservationForm key={unitId} projectId={projectId} unitId={unitId} currencyId={price?.currency_id ?? null}
                onCancel={() => setReserving(false)} onCreated={(reservationId) => { setReserving(false); router.push(recordHref(projectId, "reservation", reservationId)); }} />
                : <Button variant="primary" onClick={() => setReserving(true)}>Add buyer & reserve</Button>
            ) : null
          ) : null}
          {!reserving ? <UnitCommitment projectId={projectId} commercialStatus={unit.commercial_status} answer={commitmentAnswer} roles={roles} /> : null}
        </>
      ) : null}

      {activeSection === "collections" && liveSale ? <div className="stack"><RecordLink projectId={projectId} kind="sale" id={liveSale.id} tab="collections">Open Sale collections</RecordLink><PlanSummary projectId={projectId} saleId={liveSale.id} roles={roles} saleStatus={liveSale.status} onOpenPlan={(id) => router.push(recordHref(projectId, "payment-plan", id))} /><UnitCollections answer={collection} /></div> : null}


      {activeSection === "history" ? supportBusy ? <Loading label="Loading history" /> : <UnitHistory history={history} /> : null}

      {activeSection === "overview" ? (
        <p className="footnote">
          <Button small variant="quiet" onClick={() => setSection("history")}>
            Status history
          </Button>
        </p>
      ) : null}
    </RecordWorkspace>
  );
}
