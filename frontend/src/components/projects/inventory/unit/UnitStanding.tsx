import type { Unit } from "@/lib/api";
import { Badge } from "@/components/ui";
import { statusLabel, statusTone } from "../statusLabels";

const DIMENSIONS = [
  ["commercial_status", "Commercial"],
  ["legal_status", "Legal"],
  ["collection_status", "Collections"],
  ["delivery_status", "Delivery"],
] as const;

/** Independent owner-reported dimensions; no composite state or inferred progress. */
export function UnitStanding({ unit }: { unit: Unit }) {
  return <dl className="standing" aria-label="Asset states">
    {DIMENSIONS.map(([key, label]) => <div className="standing-cell" key={key}>
      <dt className="standing-label">{label}</dt>
      <dd><Badge tone={statusTone(unit[key])}>{statusLabel(unit[key])}</Badge></dd>
    </div>)}
  </dl>;
}
