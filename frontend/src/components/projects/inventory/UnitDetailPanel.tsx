"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, collections, inventory, pricing, sales, unitEconomics } from "@/lib/api";
import type {
  AreaSchedule,
  AreaType,
  CollectionSaleSummary,
  CustomValue,
  SaleContract,
  SaleDetail,
  SubAsset,
  Unit,
  UnitEconomicsDetail,
  UnitPricing,
  UnitStatusEvent,
} from "@/lib/api";
import { toAnswer } from "@/lib/answer";
import type { Answer } from "@/lib/answer";
import { useCurrencyCode } from "@/lib/currency";
import { money, percent } from "@/lib/format";
import {
  COLLECTION_READERS,
  ECONOMICS_READERS,
  INTERNAL_PRICE_READERS,
  LIST_PRICE_READERS,
  PRICING_APPROVERS,
  PRICING_WRITERS,
  SALES_READERS,
  hasAnyRole,
} from "@/lib/roles";
import { Badge, Button, Card, Drawer, Loading, Notice, StatusDot } from "@/components/ui";
import type { DrawerFact } from "@/components/ui";
import { QuotePreviewPanel } from "@/components/projects/pricing/QuotePreviewPanel";
import { EditForm, asValue } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";
import { profitabilityLabel } from "@/components/projects/economics/labels";
import { UnitEconomicsSection } from "@/components/projects/economics/UnitEconomicsSection";
import { UnitCollections } from "@/components/projects/collections/UnitCollections";
import { unitCollectionLabel } from "@/components/projects/collections/labels";
import { statusLabel, statusTone } from "@/components/projects/inventory/statusLabels";
import { UnitAreas } from "@/components/projects/inventory/unit/UnitAreas";
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
  { name: "unit_type_code", label: "Unit type", group: "Identity", width: "short" },
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
  { name: "is_active", label: "Unit is active", kind: "checkbox", group: "Features" },
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
export function UnitDetailPanel({
  projectId,
  roles,
  unitId,
  canWriteStructure,
  canConfigure,
  onClose,
  onChanged,
}: {
  projectId: string;
  roles: Set<string>;
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
  const [unitPricing, setUnitPricing] = useState<UnitPricing | null>(null);
  const [commitment, setCommitment] = useState<Commitment | null>(null);
  const [economics, setEconomics] = useState<Answer<UnitEconomicsDetail>>({ status: "off" });
  const [collection, setCollection] = useState<Answer<CollectionSaleSummary>>({ status: "off" });
  const [section, setSection] = useState("summary");
  const [quoting, setQuoting] = useState(false);
  const [pricingBusy, setPricingBusy] = useState(false);
  const [editing, setEditing] = useState<"none" | "unit" | "fields">("none");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const currencyCodeOf = useCurrencyCode();

  const seesSales = hasAnyRole(roles, SALES_READERS);
  const seesEconomics = hasAnyRole(roles, ECONOMICS_READERS);
  const seesCollections = hasAnyRole(roles, COLLECTION_READERS);
  const seesInternalPrices = hasAnyRole(roles, INTERNAL_PRICE_READERS);
  const seesListPrice = hasAnyRole(roles, LIST_PRICE_READERS);
  const canPrice = hasAnyRole(roles, PRICING_WRITERS);
  const canApprovePricing = hasAnyRole(roles, PRICING_APPROVERS);

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
      // The list price is asked for only on behalf of a role the server
      // answers — Legal and Collections are refused it, so their unit file
      // never requests it — and a refusal it still returns must not blank
      // the unit they can see.
      if (seesListPrice) {
        try {
          setUnitPricing(await pricing.unit(projectId, unitId));
        } catch {
          setUnitPricing(null);
        }
      } else {
        setUnitPricing(null);
      }
      // The commercial commitment is asked for only on behalf of a role that
      // reads sales at all.
      let sale: SaleDetail | null = null;
      if (seesSales) {
        try {
          const reservations = await sales.reservations(projectId, { unit_id: unitId });
          const contracts: SaleContract[] = await sales.contracts(projectId, { unit_id: unitId });
          const live = contracts.find((entry) =>
            ["signature_pending", "active", "termination_pending"].includes(entry.status),
          );
          sale = live ? await sales.contract(projectId, live.id) : null;
          setCommitment({
            reservation:
              reservations.find((entry) => ["active", "extended", "converted"].includes(entry.status)) ?? null,
            sale,
          });
        } catch {
          setCommitment(null);
        }
      } else {
        setCommitment(null);
      }
      // Economics and collections are requested once, here, and only for the
      // roles the server answers. The header facts and the sections below
      // share the same answer, so nothing is fetched twice.
      if (seesEconomics) {
        setEconomics({ status: "loading" });
        try {
          setEconomics({ status: "ready", data: await unitEconomics.unit(projectId, unitId) });
        } catch (caught) {
          setEconomics(toAnswer(caught));
        }
      }
      if (seesCollections && sale) {
        setCollection({ status: "loading" });
        try {
          setCollection({ status: "ready", data: await collections.account(projectId, sale.sale.id) });
        } catch (caught) {
          setCollection(toAnswer(caught));
        }
      } else {
        setCollection({ status: "off" });
      }
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
  }, [projectId, unitId, seesSales, seesEconomics, seesCollections, seesListPrice]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

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
  const movePrice = async (action: "submit" | "approve" | "activate", versionId: string) => {
    setPricingBusy(true);
    setError(null);
    try {
      if (action === "submit") {
        await pricing.submitPriceVersion(projectId, versionId);
        setNotice("Submitted for approval.");
      } else if (action === "approve") {
        await pricing.approvePriceVersion(projectId, versionId, "Reviewed against feasibility");
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
      <Drawer title="Unit" onClose={onClose}>
        <Notice tone="error">{error}</Notice>
      </Drawer>
    );
  }

  if (unit === null) {
    return (
      <Drawer title="Loading unit…" onClose={onClose}>
        <Loading label="Loading unit…" shape="page" />
      </Drawer>
    );
  }

  const editableValues = values.filter((value) => value.is_editable);
  const price = unitPricing?.active_price ?? null;
  const priceCode = currencyCodeOf(price?.currency_id);
  const hasSale = commitment?.sale !== null && commitment?.sale !== undefined;

  const sections = [
    { key: "summary", label: "Overview" },
    { key: "detail", label: "Areas & features" },
    ...(seesListPrice ? [{ key: "pricing", label: "Pricing" }] : []),
    ...(seesSales ? [{ key: "commercial", label: "Sales & legal" }] : []),
    ...(seesCollections && hasSale ? [{ key: "collections", label: "Collections" }] : []),
    ...(seesEconomics ? [{ key: "economics", label: "Economics" }] : []),
    { key: "release", label: "Release" },
    { key: "history", label: "History" },
  ];
  const activeSection = sections.some((entry) => entry.key === section) ? section : "summary";

  const facts: DrawerFact[] = [
    ...(unitPricing
      ? [
          {
            label: "List price",
            value: price ? money(price.reference_price_ex_tax, priceCode) : "Not priced",
            note: price ? (unitPricing.repricing_required ? "Repricing required" : `v${price.version_number} · ex tax`) : undefined,
          },
        ]
      : []),
    ...(economics.status === "ready"
      ? [
          {
            label: "Margin",
            value:
              economics.data.economics.profitability_status === "ready"
                ? percent(economics.data.economics.margin_fraction)
                : profitabilityLabel(economics.data.economics.profitability_status),
            note:
              economics.data.economics.profitability_status === "ready"
                ? `${economics.data.economics.basis === "sold" ? "Sold" : "Forecast"} basis`
                : undefined,
          },
        ]
      : []),
    ...(collection.status === "ready"
      ? [
          {
            label: "Outstanding",
            value: money(collection.data.outstanding_total, currencyCodeOf(collection.data.currency_id)),
            note: unitCollectionLabel(collection.data.derived_collection_status),
          },
        ]
      : []),
    {
      label: "Weighted area",
      value:
        unit.weighted_saleable_area === null
          ? "Not measured"
          : `${unit.weighted_saleable_area} ${unit.weighted_saleable_area_unit ?? ""}`.trim(),
    },
  ];

  return (
    <Drawer
      eyebrow="Unit"
      title={unit.unit_reference}
      subtitle={[
        [unit.unit_type_code, unit.bedrooms === null ? null : `${unit.bedrooms} bed`].filter(Boolean).join(" · ") || unit.asset_class,
        unit.phase_code ? `Phase ${unit.phase_code}` : null,
        unit.building_code ? `Building ${unit.building_code}` : null,
        unit.floor_code ? `Floor ${unit.floor_code}` : null,
      ]
        .filter(Boolean)
        .join(" · ")}
      meta={
        <>
          <Badge tone={statusTone(unit.commercial_status)}>{statusLabel(unit.commercial_status)}</Badge>
          {unit.release_eligible ? (
            <StatusDot tone="success">Releasable</StatusDot>
          ) : (
            <StatusDot tone="muted">Not releasable</StatusDot>
          )}
          {unitPricing?.repricing_required ? <Badge tone="danger">Repricing required</Badge> : null}
        </>
      }
      facts={facts}
      tabs={sections}
      activeTab={activeSection}
      onSelectTab={setSection}
      onClose={onClose}
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      {areaTypes.length === 0 ? (
        <Notice tone="info">
          This project has no area types configured yet, so no unit can be measured or released.
        </Notice>
      ) : null}

      {activeSection === "summary" ? (
        <UnitSummary
          unit={unit}
          unitPricing={unitPricing}
          commitment={seesSales ? commitment : undefined}
          economics={economics}
          collection={collection}
          onOpenTab={setSection}
        />
      ) : null}

      {activeSection === "detail" ? (
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
          <UnitPricingSection
            unitPricing={unitPricing}
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

      {activeSection === "commercial" ? <UnitCommitment projectId={projectId} commitment={commitment} /> : null}

      {activeSection === "collections" ? <UnitCollections answer={collection} /> : null}

      {activeSection === "economics" ? <UnitEconomicsSection answer={economics} /> : null}

      {activeSection === "history" ? <UnitHistory history={history} /> : null}

      {activeSection === "summary" ? (
        <p className="footnote">
          <Button small variant="quiet" onClick={() => setSection("history")}>
            Status history
          </Button>
        </p>
      ) : null}
    </Drawer>
  );
}
