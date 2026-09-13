"use client";

import { inventory } from "@/lib/api";
import { DeleteRecordButton } from "../DeleteRecordButton";

export function UnitRemovalAction({projectId, unitId, reference, roles, onRemoved}: {
  projectId: string; unitId: string; reference: string; roles: Set<string>; onRemoved: () => Promise<void>;
}) {
  if (!roles.has("master_admin")) return null;
  return <DeleteRecordButton label="unit" recordName={reference}
    destructive confirmLabel="Delete from Inventory & Sales"
    description="Master Administrator override: removes this unit from Inventory and its linked transactions from current Sales, even when reserved or sold. Contracts, payments and legal records remain in history; this does not cancel obligations or refund money. This removal cannot be undone here."
    onDelete={reason => inventory.deleteRecord(projectId, "units", unitId, reason)}
    onDeleted={onRemoved} />;
}
