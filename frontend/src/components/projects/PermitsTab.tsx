"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, projects, settings } from "@/lib/api";
import type { Permit, PermitRegister, PermitStatusEvent, ReferenceValue } from "@/lib/api";
import { Badge, EmptyState, Field, Loading, Notice, Panel } from "@/components/ui";

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
      <Panel
        title="Permits"
        description={
          register
            ? `${register.total} permits · ${register.blocking_count} blocking · ` +
              `${register.critical_path_count} on the critical path · ` +
              `${register.sla_overdue_count} past their statutory period`
            : undefined
        }
        actions={
          canWrite ? (
            <button
              className="button button-small"
              type="button"
              onClick={() => setCreating((open) => !open)}
            >
              {creating ? "Cancel" : "New permit"}
            </button>
          ) : undefined
        }
      >
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}

        <div className="form-inline">
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
        </div>

        {creating ? (
          <form className="panel-section" onSubmit={create}>
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
            </div>
            <div className="form-actions">
              <button className="button button-primary" type="submit" disabled={busy}>
                {busy ? "Saving…" : "Register permit"}
              </button>
            </div>
          </form>
        ) : null}

        {register === null ? (
          <Loading label="Loading permits…" />
        ) : register.permits.length === 0 ? (
          <EmptyState
            title="No permits registered"
            hint="Add the approvals this development needs, and track where each one stands."
          />
        ) : (
          <div className="table-scroll">
            <table className="table">
              <caption className="visually-hidden">Permit register</caption>
              <thead>
                <tr>
                  <th scope="col">Code</th>
                  <th scope="col">Type</th>
                  <th scope="col">Authority</th>
                  <th scope="col">Status</th>
                  <th scope="col">Days in stage</th>
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
                        className="button button-small"
                        type="button"
                        onClick={() => void open(permit)}
                      >
                        {permit.permit_code}
                      </button>
                    </th>
                    <td>{permit.permit_type_code}</td>
                    <td>{permit.authority}</td>
                    <td>{STATUS_LABELS[permit.status] ?? permit.status}</td>
                    <td>{permit.days_in_stage}</td>
                    <td className="nowrap">
                      {permit.sla_overdue ? (
                        <Badge tone="neutral">{slaLabel(permit)}</Badge>
                      ) : (
                        slaLabel(permit)
                      )}
                    </td>
                    <td>{permit.next_action ?? "—"}</td>
                    <td className="chip-list">
                      {permit.is_blocking ? <span className="chip">Blocking</span> : null}
                      {permit.is_critical_path ? (
                        <span className="chip">Critical path</span>
                      ) : null}
                      {!permit.prerequisite_satisfied ? (
                        <span className="chip">Prerequisite open</span>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {selected ? (
        <Panel
          title={`${selected.permit_code} — ${STATUS_LABELS[selected.status] ?? selected.status}`}
          description={selected.authority}
          actions={
            <button
              className="button button-small"
              type="button"
              onClick={() => setSelected(null)}
            >
              Close
            </button>
          }
        >
          <dl className="reference-list">
            <div>
              <dt className="reference-term">Status since</dt>
              <dd className="reference-value">{selected.status_effective_date}</dd>
            </div>
            <div>
              <dt className="reference-term">Submitted</dt>
              <dd className="reference-value">{selected.actual_submission_date ?? "—"}</dd>
            </div>
            <div>
              <dt className="reference-term">Issued</dt>
              <dd className="reference-value">{selected.issue_date ?? "—"}</dd>
            </div>
            <div>
              <dt className="reference-term">Submission variance</dt>
              <dd className="reference-value">
                {selected.submission_variance_days === null
                  ? "—"
                  : `${selected.submission_variance_days} days`}
              </dd>
            </div>
            <div>
              <dt className="reference-term">Issue variance</dt>
              <dd className="reference-value">
                {selected.issue_variance_days === null
                  ? "—"
                  : `${selected.issue_variance_days} days`}
              </dd>
            </div>
            <div>
              <dt className="reference-term">Consultant</dt>
              <dd className="reference-value">{selected.consultant ?? "—"}</dd>
            </div>
            <div>
              <dt className="reference-term">Conditions</dt>
              <dd className="reference-value">{selected.conditions ?? "—"}</dd>
            </div>
            {selected.financials_visible ? (
              <div>
                <dt className="reference-term">Fee</dt>
                <dd className="reference-value mono">
                  {selected.fee_amount ?? "—"} {selected.base_currency_code ?? ""}
                </dd>
              </div>
            ) : null}
          </dl>

          {canWrite && TRANSITIONS[selected.status].length > 0 ? (
            <form className="panel-section" onSubmit={transition}>
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
              <div className="form-actions">
                <button className="button button-primary" type="submit" disabled={busy}>
                  {busy ? "Recording…" : "Record status change"}
                </button>
              </div>
            </form>
          ) : null}

          <h3 className="section-heading">Status history</h3>
          {history.length === 0 ? (
            <p className="subtle">Nothing recorded yet.</p>
          ) : (
            <div className="table-scroll">
              <table className="table">
                <caption className="visually-hidden">Permit status history</caption>
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
                      <th scope="row" className="nowrap">
                        {event.effective_date}
                      </th>
                      <td>{STATUS_LABELS[event.from_status] ?? event.from_status}</td>
                      <td>{STATUS_LABELS[event.to_status] ?? event.to_status}</td>
                      <td>{event.reason ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      ) : null}
    </>
  );
}
