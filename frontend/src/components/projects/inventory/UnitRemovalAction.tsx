"use client";

import { inventory } from "@/lib/api";
import { DeleteRecordButton } from "../DeleteRecordButton";

export function UnitRemovalAction({projectId, unitId, reference, roles, onRemoved}: {
  projectId: string; unitId: string; reference: string; roles: Set<string>; onRemoved: () => Promise<void>;
}) {
  if (!roles.has("master_admin")) return null;
  return <DeleteRecordButton label="unit" recordName={reference}
    destructive confirmLabel="Delete from Inventory & Sales"
    description="Master Administrator override: removes this unit from Inventory and its linked transactions from current Sales, even when reserved or sold. Contracts, payments and legal records remain in history; this does not cancel obligations or refund money. Retained units can be restored from Inventory → Removed units. Unused units that are permanently deleted cannot be restored."
    onDelete={reason => inventory.deleteRecord(projectId, "units", unitId, reason)}
    onDeleted={onRemoved} />;
}

export function UnitPermanentDeletionAction({projectId, unitId, reference, onDeleted}: {
  projectId: string; unitId: string; reference: string; onDeleted: () => Promise<void>;
}) {
  return <DeleteRecordButton label="permanently" recordName={reference}
    destructive confirmLabel="Delete permanently"
    description="Permanently deletes this unit and its inventory details from the database, freeing its number and reference. This cannot be undone. Linked pricing, sales, financial, legal and other business records block deletion; the app will explain the blocker and make no changes. The deletion audit remains."
    onDelete={reason => inventory.permanentlyDeleteUnit(projectId, unitId, reason)}
    onDeleted={onDeleted} />;
}
