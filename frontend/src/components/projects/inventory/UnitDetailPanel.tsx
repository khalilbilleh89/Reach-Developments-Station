"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, inventory, pricing, sales } from "@/lib/api";
import type {
  AreaSchedule,
  AreaType,
  CustomValue,
  Reservation,
  SaleContract,
  SaleDetail,
  SubAsset,
  Unit,
  UnitPricing,
  UnitStatusEvent,
} from "@/lib/api";
import { Badge, Drawer, Loading, Notice, SubPanel } from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { QuotePreviewPanel } from "@/components/projects/pricing/QuotePreviewPanel";
import { EditForm, asValue } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";
import { statusLabel, statusTone } from "@/components/projects/inventory/statusLabels";
import { UnitAreas } from "@/components/projects/inventory/unit/UnitAreas";
import { UnitCommitment } from "@/components/projects/inventory/unit/UnitCommitment";
import { UnitHistory } from "@/components/projects/inventory/unit/UnitHistory";
import { UnitPricingSection } from "@/components/projects/inventory/unit/UnitPricingSection";
import { UnitRelease } from "@/components/projects/inventory/unit/UnitRelease";
import { UnitSummary } from "@/components/projects/inventory/unit/UnitSummary";

/** The unit fields an ordinary edit may carry. Status is absent by construction. */
const UNIT_FIELDS: EditField[] = [
  { name: "unit_reference", label: "Unit reference" },
  { name: "unit_number", label: "Unit number" },
  { name: "unit_type_code", label: "Unit type" },
  { name: "bedrooms", label: "Bedrooms", kind: "number" },
  { name: "bathrooms", label: "Bathrooms", kind: "number" },
  { name: "has_maid_room", label: "Maid room", kind: "checkbox" },
  { name: "is_duplex", label: "Duplex", kind: "checkbox" },
  { name: "is_penthouse", label: "Penthouse", kind: "checkbox" },
  { name: "furnishing_specification_code", label: "Furnishing" },
  { name: "floor_band_code", label: "Floor band" },
  { name: "orientation_code", label: "Orientation" },
  { name: "view_class_code", label: "View" },
  { name: "is_corner", label: "Corner unit", kind: "checkbox" },
  { name: "pool_access", label: "Pool access", kind: "checkbox" },
  { name: "accessibility_code", label: "Accessibility" },
  { name: "garden_class_code", label: "Garden" },
  { name: "is_active", label: "Unit is active", kind: "checkbox" },
];

/** Roles that may prepare a price and put it forward. */
const PRICING_WRITERS = new Set(["system_admin", "project_manager", "finance"]);

/** The one role that may sanction and release a price. */
const PRICING_APPROVERS = new Set(["approver_cfo"]);

const SECTIONS = [
  { key: "summary", label: "Summary" },
  { key: "detail", label: "Detail" },
  { key: "release", label: "Release" },
  { key: "pricing", label: "Pricing" },
  { key: "commercial", label: "Sale and legal" },
  { key: "history", label: "History" },
];

/**
 * Unit 360: everything the product knows about one unit, in one place.
 *
 * It opens over the register rather than under it, because the register is a
 * thousand rows long and a person comparing units should not lose their place
 * to look at one. Six sections rather than one long scroll: a design engineer
 * arrives for the areas, Finance for the price, Legal for the contract, and
 * none of them should have to read the other three to find their own.
 *
 * Nothing here computes anything. Every price, status, blocker and gate came
 * back from the API on this request — the browser lays them out and offers the
 * actions the server would accept, and the server refuses regardless of which
 * button was on screen.
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
  // The unit's commercial commitment, if it has one. Loaded separately and
  // allowed to fail quietly for the same reason pricing is: a reader who may
  // open a unit is not always entitled to the deal on it, and a 403 there
  // should not blank the unit they can see.
  const [commitment, setCommitment] = useState<{
    reservation: Reservation | null;
    sale: SaleDetail | null;
  } | null>(null);
  const [section, setSection] = useState("summary");
  const [quoting, setQuoting] = useState(false);
  const [pricingBusy, setPricingBusy] = useState(false);
  const [editing, setEditing] = useState<"none" | "unit" | "fields">("none");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const currencyCodeOf = useCurrencyCode();

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
      // Pricing is loaded separately and allowed to fail quietly: a reader who
      // may open a unit may not always be entitled to its pricing, and a 403
      // there should not blank the unit they can see.
      try {
        setUnitPricing(await pricing.unit(projectId, unitId));
      } catch {
        setUnitPricing(null);
      }
      try {
        const reservations = await sales.reservations(projectId, { unit_id: unitId });
        const contracts: SaleContract[] = await sales.contracts(projectId, { unit_id: unitId });
        const live = contracts.find((entry) =>
          ["signature_pending", "active", "termination_pending"].includes(entry.status),
        );
        setCommitment({
          reservation:
            reservations.find((entry) =>
              ["active", "extended", "converted"].includes(entry.status),
            ) ?? null,
          sale: live ? await sales.contract(projectId, live.id) : null,
        });
      } catch {
        setCommitment(null);
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
  }, [projectId, unitId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const transition = async (move: {
    to_status: string;
    effective_date: string;
    reason: string;
  }) => {
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
        <Loading label="Loading unit…" lines={5} />
      </Drawer>
    );
  }

  const editableValues = values.filter((value) => value.is_editable);
  const canPrice = [...roles].some((role) => PRICING_WRITERS.has(role));
  const canApprovePricing = [...roles].some((role) => PRICING_APPROVERS.has(role));

  return (
    <Drawer
      eyebrow="Unit"
      title={unit.unit_reference}
      subtitle={`${unit.phase_code ?? "—"} · ${unit.building_code ?? "—"} · ${unit.floor_code ?? "—"}`}
      meta={
        <>
          <Badge tone={statusTone(unit.commercial_status)}>
            {statusLabel(unit.commercial_status)}
          </Badge>
          <Badge tone={statusTone(unit.legal_status)}>{statusLabel(unit.legal_status)}</Badge>
          {unit.release_eligible ? (
            <Badge tone="success">Releasable</Badge>
          ) : (
            <Badge tone="muted">Not releasable</Badge>
          )}
        </>
      }
      tabs={SECTIONS}
      activeTab={section}
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

      {section === "summary" ? (
        <UnitSummary
          unit={unit}
          unitPricing={unitPricing}
          commitment={commitment}
          onOpenTab={setSection}
        />
      ) : null}

      {section === "detail" ? (
        <>
          {editing === "unit" ? (
            <SubPanel title="Edit unit">
              <EditForm
                fields={UNIT_FIELDS}
                initial={Object.fromEntries(
                  UNIT_FIELDS.map((field) => [
                    field.name,
                    asValue(unit[field.name as keyof Unit] as never),
                  ]),
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
            </SubPanel>
          ) : null}
          {editing === "fields" ? (
            <SubPanel title="Additional fields">
              <EditForm
                fields={editableValues.map((value) => ({
                  name: value.field_key,
                  label: value.display_label,
                  hint: value.help_text ?? value.unit_of_measure ?? undefined,
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
                      ? value.options.map((option) => ({
                          value: option.code,
                          label: option.label,
                        }))
                      : undefined,
                }))}
                submitLabel="Save fields"
                initial={Object.fromEntries(
                  editableValues.map((value) => [value.field_key, asValue(value.value)]),
                )}
                onSave={async (changes) => {
                  await inventory.writeUnitValues(projectId, unitId, changes);
                  await load();
                  await onChanged();
                  setNotice("Fields updated.");
                  setEditing("none");
                }}
                onCancel={() => setEditing("none")}
              />
            </SubPanel>
          ) : null}
          <UnitAreas
            unit={unit}
            schedules={schedules}
            assets={assets}
            values={values}
            canApproveSchedule={canConfigure}
            onApproveSchedule={(scheduleId) => void approveSchedule(scheduleId)}
            onEditUnit={
              canWriteStructure
                ? () => setEditing(editing === "unit" ? "none" : "unit")
                : undefined
            }
            onEditFields={() => setEditing(editing === "fields" ? "none" : "fields")}
            editableFieldCount={editableValues.length}
          />
        </>
      ) : null}

      {section === "release" ? (
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

      {section === "pricing" ? (
        <>
          <UnitPricingSection
            unitPricing={unitPricing}
            canPrice={canPrice}
            canApprove={canApprovePricing}
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

      {section === "commercial" ? (
        <UnitCommitment projectId={projectId} commitment={commitment} />
      ) : null}

      {section === "history" ? <UnitHistory history={history} /> : null}
    </Drawer>
  );
}
