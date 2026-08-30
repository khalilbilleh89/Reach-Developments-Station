"use client";

import { useState } from "react";

import type { Unit } from "@/lib/api";
import {
  Badge,
  Button,
  Field,
  FormActions,
  KeyValue,
  KeyValueGrid,
  Notice,
  SectionHeader,
  SubPanel,
} from "@/components/ui";
import { businessDate } from "@/lib/format";
import { EditForm, asValue } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";
import { statusLabel, statusTone } from "@/components/projects/inventory/statusLabels";

/**
 * The gates, each owned by a different role. `pricing_approved` is not here.
 *
 * The roles beside each field mirror the server's own matrix so the form offers
 * a person only what they can actually save. The server decides — this is an
 * affordance, not a permission check, and it holds no rule the API does not.
 */
export const RELEASE_FIELDS: (EditField & { roles: string[] })[] = [
  {
    name: "drawings_approved",
    label: "Drawings approved",
    kind: "checkbox",
    roles: ["system_admin", "project_manager", "design_engineering"],
  },
  {
    name: "legal_sale_eligible",
    label: "Legally saleable",
    kind: "checkbox",
    roles: ["system_admin", "project_manager", "legal"],
  },
  {
    name: "release_date",
    label: "Release date",
    kind: "date",
    roles: ["system_admin", "project_manager", "sales_operations"],
  },
  {
    name: "release_batch",
    label: "Release batch",
    roles: ["system_admin", "project_manager", "sales_operations"],
  },
  {
    name: "block_reason",
    label: "Block reason",
    roles: ["system_admin", "project_manager", "sales_operations"],
  },
];

/** The moves inventory owns. Everything else is a consequence of a sale. */
const TRANSITIONS: Record<string, string[]> = {
  unreleased: ["held", "available"],
  held: ["unreleased", "available"],
  available: ["held", "unreleased"],
};

const REASON_REQUIRED = new Set(["held", "unreleased"]);

const today = () => new Date().toISOString().slice(0, 10);

/**
 * What has to be true before this unit can be sold, and who says so.
 *
 * Four different teams own the four answers, so the form shows a person only
 * the gates their roles can actually move. The commercial status underneath is
 * inventory's to change while the unit is uncommitted; once a reservation or a
 * contract owns it, Sales moves it and this form offers nothing.
 */
export function UnitRelease({
  unit,
  roles,
  busy,
  onSaveControls,
  onTransition,
}: {
  unit: Unit;
  roles: Set<string>;
  busy: boolean;
  onSaveControls: (changes: Record<string, unknown>) => Promise<void>;
  onTransition: (move: { to_status: string; effective_date: string; reason: string }) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [move, setMove] = useState({ to_status: "", effective_date: today(), reason: "" });

  const releaseFields = RELEASE_FIELDS.filter((field) =>
    field.roles.some((role) => roles.has(role)),
  );
  const moves = TRANSITIONS[unit.commercial_status] ?? [];

  return (
    <>
      <section>
        <SectionHeader
          title="Release gates"
          description="Each gate is somebody's to give. The server refuses the rest, whoever is asking."
          actions={
            releaseFields.length > 0 ? (
              <Button small onClick={() => setEditing((open) => !open)}>
                {editing ? "Cancel" : "Edit gates"}
              </Button>
            ) : undefined
          }
        />
        {editing ? (
          <SubPanel title="Release controls">
            <EditForm
              fields={releaseFields}
              submitLabel="Save release controls"
              initial={Object.fromEntries(
                releaseFields.map((field) => [
                  field.name,
                  asValue(unit[field.name as keyof Unit] as never),
                ]),
              )}
              onSave={async (changes) => {
                await onSaveControls(changes);
                setEditing(false);
              }}
              onCancel={() => setEditing(false)}
            />
          </SubPanel>
        ) : null}
        <KeyValueGrid columns={3}>
          <KeyValue
            label="Data completeness"
            value={`${unit.completeness_percent}%${unit.is_complete ? " — complete" : ""}`}
          />
          <KeyValue label="Drawings approved" value={unit.drawings_approved ? "Yes" : "No"} />
          <KeyValue label="Legally saleable" value={unit.legal_sale_eligible ? "Yes" : "No"} />
          <KeyValue
            label="Pricing approved"
            value={unit.pricing_approved ? "Yes" : "No — set when a price is approved"}
          />
          <KeyValue label="Release date" mono value={businessDate(unit.release_date)} />
          <KeyValue label="Release batch" value={unit.release_batch} />
        </KeyValueGrid>
        {unit.block_reason ? (
          <Notice tone="warning">Held: {unit.block_reason}</Notice>
        ) : null}
        {unit.release_blockers.length > 0 ? (
          <Notice tone="info">Not releasable yet: {unit.release_blockers.join("; ")}.</Notice>
        ) : null}
        {unit.missing_requirements.length > 0 ? (
          <p className="footnote">Outstanding: {unit.missing_requirements.join(", ")}.</p>
        ) : null}
      </section>

      <section>
        <SectionHeader title="Commercial status" />
        <p className="section-description">
          Currently{" "}
          <Badge tone={statusTone(unit.commercial_status)}>
            {statusLabel(unit.commercial_status)}
          </Badge>
        </p>
        {moves.length === 0 ? (
          <p className="subtle">
            This unit is committed. Its commercial status now follows the reservation or contract
            on it, and is changed from Sales.
          </p>
        ) : (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              onTransition(move);
              setMove({ to_status: "", effective_date: today(), reason: "" });
            }}
          >
            <div className="form-inline">
              <Field label="Move to">
                <select
                  className="input"
                  required
                  value={move.to_status}
                  onChange={(event) => setMove({ ...move, to_status: event.target.value })}
                >
                  <option value="">Choose…</option>
                  {moves.map((status) => (
                    <option key={status} value={status}>
                      {statusLabel(status)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Effective date">
                <input
                  className="input input-short"
                  type="date"
                  required
                  value={move.effective_date}
                  onChange={(event) => setMove({ ...move, effective_date: event.target.value })}
                />
              </Field>
              <Field
                label="Reason"
                grow
                hint={
                  REASON_REQUIRED.has(move.to_status) ? "Required for this move." : "Optional."
                }
              >
                <input
                  className="input"
                  required={REASON_REQUIRED.has(move.to_status)}
                  value={move.reason}
                  onChange={(event) => setMove({ ...move, reason: event.target.value })}
                />
              </Field>
            </div>
            <FormActions>
              <Button variant="primary" type="submit" disabled={busy}>
                {busy ? "Recording…" : "Record status change"}
              </Button>
            </FormActions>
          </form>
        )}
      </section>
    </>
  );
}
