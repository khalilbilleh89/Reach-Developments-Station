"use client";

import { useCallback, useEffect, useState, useRef } from "react";

import { ApiError, inventory, pricing } from "@/lib/api";
import type {
  AreaSchedule,
  AreaType,
  CustomValue,
  SubAsset,
  Unit,
  UnitPricing,
} from "@/lib/api";
import { toAnswer } from "@/lib/answer";
import type { Answer } from "@/lib/answer";
import { useCurrencyCode } from "@/lib/currency";
import { money } from "@/lib/format";
import {
  INTERNAL_PRICE_READERS,
  LIST_PRICE_READERS,
  PRICING_APPROVERS,
  PRICING_WRITERS,
  hasAnyRole,
} from "@/lib/roles";
import { Button, Badge, PromptDialog, RecordWorkspace, Loading, Notice, useRecordTab } from "@/components/ui";
import type { WorkspaceFact, WorkspaceHeadline } from "@/components/ui";
import { SellingPriceForm } from "@/components/projects/inventory/unit/SellingPriceForm";
import { useRouter } from "next/navigation";


import { UnitPricingSection } from "@/components/projects/inventory/unit/UnitPricingSection";
import { UnitRelease } from "@/components/projects/inventory/unit/UnitRelease";
import { UnitProperty } from "./unit/UnitProperty";
import { UnitSummary } from "@/components/projects/inventory/unit/UnitSummary";
import { DeleteRecordButton } from "@/components/projects/DeleteRecordButton";

/** The unit fields an ordinary edit may carry. Status is absent by construction. */



/** Inventory facts, launch pricing and release for one unit. */
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
  const [supportError,setSupportError] = useState<string | null>(null);
  const [supportBusy, setSupportBusy] = useState(false);
  const [detailRevision, setDetailRevision] = useState(-1);
  const [supportRevision, setSupportRevision] = useState(0);
  const supportLoaded = useRef<Record<string, number>>({});


  const [unit, setUnit] = useState<Unit | null>(null);
  const [schedules, setSchedules] = useState<AreaSchedule[]>([]);
  const [areaTypes, setAreaTypes] = useState<AreaType[]>([]);
  const [assets, setAssets] = useState<SubAsset[]>([]);
  const [values, setValues] = useState<CustomValue[]>([]);
  // One answer per module, made once here and shared by the header facts and
  // the sections. Each is asked for only on behalf of a role the server
  // answers; a refusal it still returns is "denied" and a fault is "failed",
  // and neither is ever drawn as a unit with no price or no commitment.
  const [pricingAnswer, setPricingAnswer] = useState<Answer<UnitPricing>>({ status: "off" });
  const [section, setSection] = useRecordTab();
  const [pricingBusy, setPricingBusy] = useState(false);
  const [approvingPrice, setApprovingPrice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const currencyCodeOf = useCurrencyCode();

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

    await loadPricing();
  }, [projectId, unitId, seesListPrice]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  // Physical detail loads when the Property tab is opened.
  useEffect(() => {
    if (!unit || section !== "detail" || supportLoaded.current[section] === supportRevision) return;
    let cancelled = false;
    void (async () => {
      setSupportBusy(true);setSupportError(null);
      try {

          const [scheduleList, typeList, assetList, valueList] = await Promise.all([
            inventory.areaSchedules(projectId, unitId), inventory.areaTypes(projectId),
            inventory.subAssets(projectId, { unit_id: unitId }), inventory.unitValues(projectId, unitId),
          ]);
          if (!cancelled) { setSchedules(scheduleList); setAreaTypes(typeList); setAssets(assetList); setValues(valueList); setDetailRevision(supportRevision); }
        if (!cancelled) supportLoaded.current[section] = supportRevision;
      } catch (caught) { if (!cancelled) setSupportError(caught instanceof ApiError ? caught.message : "Could not load this section."); }
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
      setNotice("Unit released for sales.");
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

  const unitPricing = pricingAnswer.status === "ready" ? pricingAnswer.data : null;
  const price = unitPricing?.active_price ?? null;
  const priceCode = currencyCodeOf(price?.currency_id);

  const sections = [
    { key: "overview", label: "Overview" },
    { key: "detail", label: "Property" },
    ...(seesListPrice ? [{ key: "pricing", label: "Pricing" }] : []),
    { key: "release", label: "Release" },
  ];
  const activeSection = sections.some((entry) => entry.key === section) ? section : "overview";

  const headline: WorkspaceHeadline | undefined = unitPricing
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
      label: "Net area · Internal + balconies",
      value: unit.net_area == null ? "Not measured" : `${unit.net_area} ${unit.net_area_unit ?? ""}`,
    },
    {
      label: "Internal area",
      value: unit.internal_area === null ? "Not measured" : `${unit.internal_area} ${unit.weighted_saleable_area_unit ?? ""}`.trim(),
      tone: unit.internal_area === null ? ("muted" as const) : undefined,
    },
    {
      label: "Gross area · Net + roof garden + terrace + front garden + porches",
      value:
        unit.gross_area === null
          ? "Not measured"
          : `${unit.gross_area} ${unit.gross_area_unit ?? ""}`.trim(),
      tone: unit.gross_area === null ? ("muted" as const) : undefined,
    },
    ...(seesListPrice ? [{
      label: `Price per ${unitPricing?.gross_area_unit ?? "sqm"} · Launch price ÷ gross area`,
      value: unitPricing?.price_per_gross_area == null ? "Unavailable" : money(unitPricing.price_per_gross_area, priceCode),
    }] : []),
  ];

  return (
    <RecordWorkspace projectId={projectId} kind="unit"
      eyebrow="Inventory unit"
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
        {roles.has("system_admin") || roles.has("master_admin") ? <DeleteRecordButton label="unit" onDelete={reason => inventory.deleteRecord(projectId, "units", unitId, reason)} onDeleted={async () => { await onChanged(); router.push(`/projects/?project=${projectId}&section=inventory`); }} /> : null}
        </>
      }
      meta={<Badge tone={unit.is_active ? "success" : "neutral"}>{unit.is_active ? "Active unit" : "Inactive unit"}</Badge>}
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

      {activeSection === "overview" ? (
        <UnitSummary
          unit={unit}
          pricing={pricingAnswer}
          onOpenTab={setSection}
        />
      ) : null}

      {approvingPrice ? <PromptDialog title={`Approve price for ${unit.unit_reference}`} label="Approval rationale" description="Record what you checked and why this price is approved. Activation remains a separate step." confirmLabel="Approve price" error={error} busy={pricingBusy} onCancel={() => { if (!pricingBusy) setApprovingPrice(null); }} onSubmit={reason => void movePrice("approve", approvingPrice, reason)} /> : null}
      {activeSection === "detail" && supportError ? <Notice tone="error">{supportError}<Button onClick={()=>setSupportRevision(value=>value+1)}>Retry property</Button></Notice> : null}
      {activeSection === "detail" && supportBusy ? <Loading label="Loading property" /> : null}
      {activeSection === "detail" && !supportBusy && detailRevision === supportRevision ? (
        <UnitProperty canDelete={roles.has("system_admin") || roles.has("master_admin")} key={unitId} projectId={projectId} unit={unit} areaTypes={areaTypes} schedules={schedules} assets={assets} values={values}
          canWrite={canWriteStructure} canApprove={canConfigure} onChanged={async()=>{await load();await onChanged();}} />
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
          />
        </>
      ) : null}

    </RecordWorkspace>
  );
}
