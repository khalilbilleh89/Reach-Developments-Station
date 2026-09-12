"use client";

import { useState } from "react";

import type { Unit } from "@/lib/api";
import {
  Badge,
  Button,
  Field,
  FieldRow,
  FormActions,
  KeyValue,
  KeyValueGrid,
  Notice,
  SectionHeader,
  SubPanel,
} from "@/components/ui";
import { todayISO } from "@/lib/format";
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

const today = todayISO;

/**
 * What has to be true before this unit can be sold, and who says so.
 *
 * Four different teams own the four answers, so the form shows a person only
 * the gates their roles can actually move. The commercial status underneath is
 * inventory's to change while the unit is uncommitted; once a reservation or a
 * contract owns it, Sales moves it and this form offers nothing.
 */
export function CommercialUnitControls({
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
  onTransition: (move: { to_status: string; effective_date: string; reason: string }) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [move, setMove] = useState({ to_status: "", effective_date: today(), reason: "" });

  const releaseFields = RELEASE_FIELDS.filter((field) =>
    ["legal_sale_eligible", "block_reason"].includes(field.name) && (roles.has("master_admin") || field.roles.some((role) => roles.has(role))),
  );
  const moves = ["master_admin", "system_admin", "project_manager", "sales_operations"].some(role => roles.has(role)) ? TRANSITIONS[unit.commercial_status] ?? [] : [];

  return (
    <>
      <section>
        <SectionHeader level={2}
          title="Commercial controls"
          description="Legal eligibility and commercial holds."
          actions={
            releaseFields.length > 0 ? (
              <Button small data-leaves-editor onClick={() => setEditing((open) => !open)}>
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
          <KeyValue label="Legally saleable" value={unit.legal_sale_eligible ? "Yes" : "No"} />
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
        <SectionHeader level={2} title="Commercial status" />
        <p className="section-description">
          Currently{" "}
          <Badge tone={statusTone(unit.commercial_status)}>
            {statusLabel(unit.commercial_status)}
          </Badge>
        </p>
        {moves.length === 0 ? (
          <p className="subtle">
            No manual transition is available. Committed units follow their reservation or sale; other changes require release-control permission.
          </p>
        ) : (
          <form
            onSubmit={async (event) => {
              event.preventDefault();
              try { await onTransition(move); } catch { return; }
              setMove({ to_status: "", effective_date: today(), reason: "" });
            }}
          >
            <FieldRow columns={3}>
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
                  className="input"
                  type="date"
                  required
                  value={move.effective_date}
                  onChange={(event) => setMove({ ...move, effective_date: event.target.value })}
                />
              </Field>
              <Field
                label="Reason"
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
            </FieldRow>
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
