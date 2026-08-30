"use client";

import type { AreaSchedule, CustomValue, SubAsset, Unit } from "@/lib/api";
import {
  Badge,
  Button,
  EmptyState,
  KeyValue,
  KeyValueGrid,
  SectionHeader,
  TableScroll,
} from "@/components/ui";

/**
 * What this unit is, and how much of it there is.
 *
 * The measured areas are shown with the factor applied to each, because a
 * weighted saleable area with no visible arithmetic behind it is exactly the
 * spreadsheet cell this product exists to replace. The figures are the
 * backend's; the browser only lays them out.
 */
export function UnitAreas({
  unit,
  schedules,
  assets,
  values,
  canApproveSchedule,
  onApproveSchedule,
  onEditUnit,
  onEditFields,
  editableFieldCount,
}: {
  unit: Unit;
  schedules: AreaSchedule[];
  assets: SubAsset[];
  values: CustomValue[];
  canApproveSchedule: boolean;
  onApproveSchedule: (scheduleId: string) => void;
  onEditUnit?: () => void;
  onEditFields?: () => void;
  editableFieldCount: number;
}) {
  return (
    <>
      <section>
        <SectionHeader
          title="Identity"
          actions={onEditUnit ? <Button small onClick={onEditUnit}>Edit unit</Button> : undefined}
        />
        <KeyValueGrid columns={3}>
          <KeyValue label="Unit number" mono value={unit.unit_number} />
          <KeyValue label="Type" value={`${unit.unit_type_code ?? "—"} · ${unit.asset_class}`} />
          <KeyValue
            label="Bedrooms / bathrooms"
            value={`${unit.bedrooms ?? "—"} / ${unit.bathrooms ?? "—"}`}
          />
          <KeyValue label="Orientation" value={unit.orientation_code} />
          <KeyValue label="View" value={unit.view_class_code} />
          <KeyValue label="Floor band" value={unit.floor_band_code} />
        </KeyValueGrid>
      </section>

      <section>
        <SectionHeader title="Areas" />
        {unit.area_lines.length === 0 ? (
          <EmptyState
            title="No approved measurement yet"
            hint="A unit cannot be priced or released until an area schedule has been approved."
          />
        ) : (
          <TableScroll label="Approved areas">
            <thead>
              <tr>
                <th scope="col">Area</th>
                <th scope="col" className="num">
                  Measured
                </th>
                <th scope="col" className="num">
                  Factor
                </th>
                <th scope="col" className="num">
                  Weighted
                </th>
              </tr>
            </thead>
            <tbody>
              {unit.area_lines.map((line) => (
                <tr key={line.area_type_id}>
                  <th scope="row">{line.label}</th>
                  <td className="num">
                    {line.raw_area} {line.unit_of_measure}
                  </td>
                  <td className="num">{line.weight_factor}</td>
                  <td className="num">{line.weighted_area}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row" colSpan={3}>
                  Weighted saleable
                </th>
                <td className="num">
                  {unit.weighted_saleable_area === null
                    ? "—"
                    : `${unit.weighted_saleable_area} ${unit.weighted_saleable_area_unit ?? ""}`.trim()}
                </td>
              </tr>
            </tfoot>
          </TableScroll>
        )}
        {schedules.length > 0 ? (
          <ul className="chip-list">
            {schedules.map((schedule) => (
              <li key={schedule.id} className="chip">
                <span className="mono">{schedule.revision_code}</span>
                <Badge tone={schedule.status === "approved" ? "success" : "warning"}>
                  {schedule.status}
                </Badge>
                {canApproveSchedule && schedule.status === "draft" ? (
                  <Button small variant="quiet" onClick={() => onApproveSchedule(schedule.id)}>
                    Approve
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section>
        <SectionHeader title="Parking and storage" />
        {assets.length === 0 ? (
          <p className="subtle">No parking or storage linked to this unit.</p>
        ) : (
          <ul className="chip-list">
            {assets.map((asset) => (
              <li key={asset.id} className="chip">
                <span className="mono">{asset.asset_reference}</span>
                <span className="chip-label">
                  {asset.asset_type} · {asset.transfer_mode}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {values.length > 0 ? (
        <section>
          <SectionHeader
            title="Additional fields"
            actions={
              onEditFields && editableFieldCount > 0 ? (
                <Button small onClick={onEditFields}>
                  Edit fields
                </Button>
              ) : undefined
            }
          />
          <KeyValueGrid columns={3}>
            {values.map((value) => (
              <KeyValue
                key={value.definition_id}
                label={value.display_label}
                value={
                  value.value === null || value.value === ""
                    ? null
                    : `${String(value.value)}${value.unit_of_measure ? ` ${value.unit_of_measure}` : ""}`
                }
              />
            ))}
          </KeyValueGrid>
        </section>
      ) : null}
    </>
  );
}
