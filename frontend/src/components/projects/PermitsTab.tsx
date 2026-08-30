"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, projects, settings } from "@/lib/api";
import type { Permit, PermitRegister, PermitStatusEvent, ReferenceValue } from "@/lib/api";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  FilterBar,
  FormActions,
  KeyValue,
  KeyValueGrid,
  Loading,
  Notice,
  Stat,
  StatRow,
  SubPanel,
  TableScroll,
} from "@/components/ui";
import { EditForm, asValue } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";

/**
 * The moves the API will accept from each state. Mirrored here only so the
 * form offers plausible choices — the API validates every transition itself and
 * is the authority on what is allowed.
 */
const TRANSITIONS: Record<string, string[]> = {
  not_started: ["preparing", "on_hold", "withdrawn"],
  preparing: ["submitted", "on_hold", "withdrawn"],
  submitted: ["accepted_for_review", "comments_received", "rejected", "on_hold", "withdrawn"],
  accepted_for_review: [
    "comments_received",
    "approved_with_conditions",
    "issued",
    "rejected",
    "on_hold",
    "withdrawn",
  ],
  comments_received: ["resubmission", "rejected", "on_hold", "withdrawn"],
  resubmission: [
    "accepted_for_review",
    "comments_received",
    "approved_with_conditions",
    "issued",
    "rejected",
    "on_hold",
    "withdrawn",
  ],
  approved_with_conditions: ["issued", "expired", "on_hold", "withdrawn"],
  issued: ["expired", "renewed"],
  expired: ["renewed"],
  renewed: ["expired"],
  rejected: ["preparing", "withdrawn"],
  on_hold: [
    "preparing",
    "submitted",
    "accepted_for_review",
    "comments_received",
    "resubmission",
    "approved_with_conditions",
    "issued",
    "withdrawn",
  ],
  withdrawn: [],
};

const STATUS_LABELS: Record<string, string> = {
  not_started: "Not started",
  preparing: "Preparing",
  submitted: "Submitted",
  accepted_for_review: "Accepted for review",
  comments_received: "Comments received",
  resubmission: "Resubmission",
  approved_with_conditions: "Approved with conditions",
  issued: "Issued",
  expired: "Expired",
  renewed: "Renewed",
  rejected: "Rejected",
  on_hold: "On hold",
  withdrawn: "Withdrawn",
};

/**
 * The colour each permit status is drawn in.
 *
 * Presentation over a word that already says it. A consent that has been
 * refused, has expired or is on hold is the one a project manager needs to find
 * in a register of forty, so those carry weight; everything in flight is
 * neutral, because "submitted" is neither good news nor bad.
 */
const STATUS_TONES: Record<string, "neutral" | "muted" | "info" | "success" | "warning" | "danger"> =
  {
    not_started: "muted",
    preparing: "muted",
    submitted: "info",
    accepted_for_review: "info",
    comments_received: "warning",
    resubmission: "warning",
    approved_with_conditions: "success",
    issued: "success",
    expired: "danger",
    renewed: "success",
    rejected: "danger",
    on_hold: "warning",
    withdrawn: "muted",
  };

/** Moves the API requires an explanation for. */
const REASON_REQUIRED = new Set(["rejected", "on_hold", "withdrawn", "preparing"]);

const today = () => new Date().toISOString().slice(0, 10);

function slaLabel(permit: Permit): string {
  if (permit.sla_days_remaining === null) return "—";
  return permit.sla_overdue
    ? `${Math.abs(permit.sla_days_remaining)} days over`
    : `${permit.sla_days_remaining} days left`;
}

/**
 * The permit fields an ordinary update may carry.
 *
 * `status` and `permit_code` are absent by construction: status moves only
 * through a transition that records why, and a permit code is immutable. The
 * API rejects either outright, so they cannot be sent from here at all.
 *
 * Identity fields are still offered before submission; once the application is
 * with the authority the API refuses them and the conflict is shown.
 */
function permitFields(permit: Permit): EditField[] {
  const frozen = !["not_started", "preparing"].includes(permit.status);
  return [
    {
      name: "authority",
      label: "Authority",
      visible: !frozen,
      hint: "Fixed once the application is submitted.",
    },
    { name: "permit_type_code", label: "Permit type", visible: !frozen },
    { name: "authority_reference", label: "Authority reference" },
    { name: "consultant", label: "Consultant" },
    { name: "planned_submission_date", label: "Planned submission", kind: "date" },
    { name: "forecast_submission_date", label: "Forecast submission", kind: "date" },
    { name: "actual_submission_date", label: "Actual submission", kind: "date" },
    { name: "accepted_for_review_date", label: "Accepted for review", kind: "date" },
    { name: "comments_received_date", label: "Comments received", kind: "date" },
    { name: "resubmission_date", label: "Resubmission", kind: "date" },
    { name: "planned_issue_date", label: "Planned issue", kind: "date" },
    { name: "forecast_issue_date", label: "Forecast issue", kind: "date" },
    { name: "issue_date", label: "Issued", kind: "date" },
    { name: "expiry_date", label: "Expiry", kind: "date" },
    { name: "renewal_date", label: "Renewal", kind: "date" },
    { name: "statutory_sla_days", label: "Statutory period (days)", kind: "number" },
    {
      name: "fee_amount",
      label: `Fee${permit.base_currency_code ? ` (${permit.base_currency_code})` : ""}`,
      kind: "number",
      visible: permit.financials_visible,
    },
    { name: "conditions", label: "Conditions", kind: "textarea" },
    { name: "next_action", label: "Next action" },
    { name: "notes", label: "Notes", kind: "textarea" },
    { name: "is_blocking", label: "Blocking", kind: "checkbox" },
    { name: "is_critical_path", label: "On the critical path", kind: "checkbox" },
  ];
}

/**
 * The permit tracker: the register plus the one control that moves a permit.
 *
 * Status is deliberately not an editable field anywhere here. It moves through
 * "Change status", which records why and when, because the history is the
 * record of what the authority actually did.
 */
export function PermitsTab({ projectId, canWrite }: { projectId: string; canWrite: boolean }) {
  const [register, setRegister] = useState<PermitRegister | null>(null);
  const [types, setTypes] = useState<ReferenceValue[]>([]);
  const [selected, setSelected] = useState<Permit | null>(null);
  const [history, setHistory] = useState<PermitStatusEvent[]>([]);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    permit_code: "",
    permit_type_code: "",
    authority: "",
    planned_submission_date: "",
    planned_issue_date: "",
    statutory_sla_days: "",
  });
  const [move, setMove] = useState({ to_status: "", effective_date: today(), reason: "" });
  const [filter, setFilter] = useState("");
  const [editingPermit, setEditingPermit] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const query: Record<string, string> =
        filter === "blocking" ? { is_blocking: "true" } : {};
      setRegister(await projects.permits(projectId, query));
      setError(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not load permits.");
    }
  }, [projectId, filter]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  useEffect(() => {
    void (async () => {
      try {
        const values = await settings.referenceValues();
        setTypes(values.filter((v) => v.is_active && v.category === "permit_type"));
      } catch {
        // The register still reads without the create form's options.
      }
    })();
  }, []);

  const open = async (permit: Permit) => {
    setSelected(permit);
    setEditingPermit(false);
    setMove({ to_status: "", effective_date: today(), reason: "" });
    setHistory(await projects.permitHistory(projectId, permit.id));
  };

  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        permit_code: form.permit_code,
        permit_type_code: form.permit_type_code,
        authority: form.authority,
      };
      if (form.planned_submission_date) {
        payload.planned_submission_date = form.planned_submission_date;
      }
      if (form.planned_issue_date) payload.planned_issue_date = form.planned_issue_date;
      if (form.statutory_sla_days) {
        payload.statutory_sla_days = Number(form.statutory_sla_days);
      }
      await projects.createPermit(projectId, payload);
      setNotice(`Permit ${form.permit_code} registered.`);
      setCreating(false);
      setForm({
        permit_code: "",
        permit_type_code: "",
        authority: "",
        planned_submission_date: "",
        planned_issue_date: "",
        statutory_sla_days: "",
      });
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not register the permit.");
    } finally {
      setBusy(false);
    }
  };

  const transition = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await projects.transitionPermit(projectId, selected.id, {
        to_status: move.to_status,
        effective_date: move.effective_date,
        ...(move.reason ? { reason: move.reason } : {}),
      });
      setNotice(`${updated.permit_code} moved to ${STATUS_LABELS[updated.status]}.`);
      await load();
      await open(updated);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not change the status.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Card
        title="Permits"
        description="The consents this development needs, where each one stands, and which of them are holding units back."
        actions={
          canWrite ? (
            <Button onClick={() => setCreating((open) => !open)}>
              {creating ? "Cancel" : "New permit"}
            </Button>
          ) : undefined
        }
      >
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}

        {register ? (
          <StatRow>
            <Stat label="Permits" value={register.total} small />
            <Stat label="Blocking" value={register.blocking_count} small />
            <Stat label="Critical path" value={register.critical_path_count} small />
            <Stat label="Past statutory period" value={register.sla_overdue_count} small />
          </StatRow>
        ) : null}

        <FilterBar>
          <Field label="Show">
            <select
              className="input input-short"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            >
              <option value="">All permits</option>
              <option value="blocking">Blocking only</option>
            </select>
          </Field>
        </FilterBar>

        {creating ? (
          <SubPanel title="New permit">
          <form onSubmit={create}>
            <div className="form-grid">
              <Field label="Permit code" hint="Unique within this project, e.g. BLD-001.">
                <input
                  className="input"
                  required
                  value={form.permit_code}
                  onChange={(event) => setForm({ ...form, permit_code: event.target.value })}
                />
              </Field>
              <Field label="Permit type">
                <select
                  className="input"
                  required
                  value={form.permit_type_code}
                  onChange={(event) =>
                    setForm({ ...form, permit_type_code: event.target.value })
                  }
                >
                  <option value="">Choose…</option>
                  {types.map((value) => (
                    <option key={value.id} value={value.code}>
                      {value.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Authority">
                <input
                  className="input"
                  required
                  value={form.authority}
                  onChange={(event) => setForm({ ...form, authority: event.target.value })}
                />
              </Field>
              <Field label="Planned submission">
                <input
                  className="input input-short"
                  type="date"
                  value={form.planned_submission_date}
                  onChange={(event) =>
                    setForm({ ...form, planned_submission_date: event.target.value })
                  }
                />
              </Field>
              <Field label="Planned issue">
                <input
                  className="input input-short"
                  type="date"
                  value={form.planned_issue_date}
                  onChange={(event) =>
                    setForm({ ...form, planned_issue_date: event.target.value })
                  }
                />
              </Field>
              <Field label="Statutory period (days)">
                <input
                  className="input input-short"
                  type="number"
                  min="1"
                  value={form.statutory_sla_days}
                  onChange={(event) =>
                    setForm({ ...form, statutory_sla_days: event.target.value })
                  }
                />
              </Field>
              <FormActions>
                <Button variant="primary" type="submit" disabled={busy}>
                  {busy ? "Saving…" : "Register permit"}
                </Button>
              </FormActions>
            </div>
          </form>
          </SubPanel>
        ) : null}

        {register === null ? (
          <Loading label="Loading permits…" lines={4} />
        ) : register.permits.length === 0 ? (
          <EmptyState
            title="No permits registered"
            hint="Add the approvals this development needs, and track where each one stands."
          />
        ) : (
          <TableScroll label="Permit register" fixedFirst>
              <thead>
                <tr>
                  <th scope="col">Code</th>
                  <th scope="col">Type</th>
                  <th scope="col">Authority</th>
                  <th scope="col">Status</th>
                  <th scope="col" className="num">
                    Days in stage
                  </th>
                  <th scope="col">Statutory period</th>
                  <th scope="col">Next action</th>
                  <th scope="col">Flags</th>
                </tr>
              </thead>
              <tbody>
                {register.permits.map((permit) => (
                  <tr key={permit.id}>
                    <th scope="row">
                      <button
                        className="button-link mono"
                        type="button"
                        onClick={() => void open(permit)}
                      >
                        {permit.permit_code}
                      </button>
                    </th>
                    <td>{permit.permit_type_code}</td>
                    <td>{permit.authority}</td>
                    <td>
                      <Badge tone={STATUS_TONES[permit.status] ?? "neutral"}>
                        {STATUS_LABELS[permit.status] ?? permit.status}
                      </Badge>
                    </td>
                    <td className="num">{permit.days_in_stage}</td>
                    <td className="nowrap">
                      {permit.sla_overdue ? (
                        <Badge tone="danger">{slaLabel(permit)}</Badge>
                      ) : (
                        slaLabel(permit)
                      )}
                    </td>
                    <td>{permit.next_action ?? "—"}</td>
                    <td>
                      <div className="row-actions">
                        {permit.is_blocking ? <Badge tone="warning">Blocking</Badge> : null}
                        {permit.is_critical_path ? (
                          <Badge tone="info">Critical path</Badge>
                        ) : null}
                        {!permit.prerequisite_satisfied ? (
                          <Badge tone="muted">Prerequisite open</Badge>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
          </TableScroll>
        )}
      </Card>

      {selected ? (
        <Card
          title={`${selected.permit_code} — ${STATUS_LABELS[selected.status] ?? selected.status}`}
          description={selected.authority}
          actions={
            <>
              {canWrite ? (
                <Button onClick={() => setEditingPermit((open) => !open)}>
                  {editingPermit ? "Cancel" : "Edit permit"}
                </Button>
              ) : null}
              <Button onClick={() => setSelected(null)}>Close</Button>
            </>
          }
        >
          {editingPermit ? (
            <EditForm
              fields={permitFields(selected)}
              initial={Object.fromEntries(
                permitFields(selected).map((field) => [
                  field.name,
                  asValue(selected[field.name as keyof Permit] as never),
                ]),
              )}
              onSave={async (changes) => {
                const updated = await projects.updatePermit(projectId, selected.id, changes);
                await load();
                await open(updated);
                setNotice(`${updated.permit_code} updated.`);
              }}
              onCancel={() => setEditingPermit(false)}
            />
          ) : null}
          <KeyValueGrid columns={3}>
            <KeyValue label="Status since" mono value={selected.status_effective_date} />
            <KeyValue label="Submitted" mono value={selected.actual_submission_date} />
            <KeyValue label="Issued" mono value={selected.issue_date} />
            <KeyValue
              label="Submission variance"
              mono
              value={
                selected.submission_variance_days === null
                  ? null
                  : `${selected.submission_variance_days} days`
              }
            />
            <KeyValue
              label="Issue variance"
              mono
              value={
                selected.issue_variance_days === null
                  ? null
                  : `${selected.issue_variance_days} days`
              }
            />
            <KeyValue label="Consultant" value={selected.consultant} />
            <KeyValue label="Conditions" value={selected.conditions} />
            {selected.financials_visible ? (
              <KeyValue
                label="Fee"
                mono
                value={`${selected.fee_amount ?? "—"} ${selected.base_currency_code ?? ""}`.trim()}
              />
            ) : null}
          </KeyValueGrid>

          {canWrite && TRANSITIONS[selected.status].length > 0 ? (
            <form onSubmit={transition}>
              <h3 className="section-heading">Change status</h3>
              <div className="form-inline">
                <Field label="Move to">
                  <select
                    className="input"
                    required
                    value={move.to_status}
                    onChange={(event) => setMove({ ...move, to_status: event.target.value })}
                  >
                    <option value="">Choose…</option>
                    {TRANSITIONS[selected.status].map((value) => (
                      <option key={value} value={value}>
                        {STATUS_LABELS[value]}
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
                    onChange={(event) =>
                      setMove({ ...move, effective_date: event.target.value })
                    }
                  />
                </Field>
                <Field
                  label="Reason"
                  hint={
                    REASON_REQUIRED.has(move.to_status)
                      ? "Required for this move."
                      : "Optional."
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
          ) : null}

          <h3 className="section-heading">Status history</h3>
          {history.length === 0 ? (
            <p className="subtle">Nothing recorded yet.</p>
          ) : (
            <TableScroll label="Permit status history">
                <thead>
                  <tr>
                    <th scope="col">Effective</th>
                    <th scope="col">From</th>
                    <th scope="col">To</th>
                    <th scope="col">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((event) => (
                    <tr key={event.id}>
                      <th scope="row" className="mono nowrap">
                        {event.effective_date}
                      </th>
                      <td>{STATUS_LABELS[event.from_status] ?? event.from_status}</td>
                      <td>
                        <Badge tone={STATUS_TONES[event.to_status] ?? "neutral"}>
                          {STATUS_LABELS[event.to_status] ?? event.to_status}
                        </Badge>
                      </td>
                      <td>{event.reason ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
            </TableScroll>
          )}
        </Card>
      ) : null}
    </>
  );
}
