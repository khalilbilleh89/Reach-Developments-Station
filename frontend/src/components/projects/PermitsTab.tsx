"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, projects, settings } from "@/lib/api";
import type { Permit, PermitRegister, PermitStatusEvent, ReferenceValue } from "@/lib/api";
import { businessDate, money, todayISO } from "@/lib/format";
import { sectionDescription } from "@/components/shell/navigation";
import {
  Badge,
  Button,
  Card,
  DataToolbar,
  IdentityCell,
  Drawer,
  EmptyState,
  Field,
  FieldRow,
  FormActions,
  FormSection,
  KeyValue,
  KeyValueGrid,
  Loading,
  StatStrip,
  StatStripItem,
  Notice,
  PageHeader,
  StatusDot,
  TableScroll,
  ToolbarFilter,
} from "@/components/ui";
import type { Tone } from "@/components/ui";
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
const STATUS_TONES: Record<string, Tone> = {
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
    { name: "authority", label: "Authority", visible: !frozen, hint: "Fixed once the application is submitted.", group: "Application" },
    { name: "permit_type_code", label: "Permit type", visible: !frozen, group: "Application", width: "medium" },
    { name: "authority_reference", label: "Authority reference", group: "Application", width: "medium" },
    { name: "consultant", label: "Consultant", group: "Application" },
    { name: "statutory_sla_days", label: "Statutory period", kind: "number", group: "Application", affix: "days" },
    {
      name: "fee_amount",
      label: "Fee",
      kind: "number",
      visible: permit.financials_visible,
      group: "Application",
      affix: permit.base_currency_code ?? undefined,
    },
    { name: "planned_submission_date", label: "Planned submission", kind: "date", group: "Submission" },
    { name: "forecast_submission_date", label: "Forecast submission", kind: "date", group: "Submission" },
    { name: "actual_submission_date", label: "Actual submission", kind: "date", group: "Submission" },
    { name: "accepted_for_review_date", label: "Accepted for review", kind: "date", group: "Submission" },
    { name: "comments_received_date", label: "Comments received", kind: "date", group: "Submission" },
    { name: "resubmission_date", label: "Resubmission", kind: "date", group: "Submission" },
    { name: "planned_issue_date", label: "Planned issue", kind: "date", group: "Issue" },
    { name: "forecast_issue_date", label: "Forecast issue", kind: "date", group: "Issue" },
    { name: "issue_date", label: "Issued", kind: "date", group: "Issue" },
    { name: "expiry_date", label: "Expiry", kind: "date", group: "Issue" },
    { name: "renewal_date", label: "Renewal", kind: "date", group: "Issue" },
    { name: "conditions", label: "Conditions", kind: "textarea", group: "Management" },
    { name: "next_action", label: "Next action", group: "Management" },
    { name: "notes", label: "Notes", kind: "textarea", group: "Management" },
    { name: "is_blocking", label: "Blocking the programme", kind: "checkbox", group: "Management" },
    { name: "is_critical_path", label: "On the critical path", kind: "checkbox", group: "Management" },
  ];
}

type Filter = "" | "blocking" | "critical" | "overdue";

/**
 * The permit register, and the one control that moves a permit.
 *
 * Built so the late and the blocking are obvious without inventing a
 * criticality of their own: the flags are the server's, the statutory clock
 * is the server's, and the register only draws them where a project manager
 * looks first. Status is deliberately not an editable field anywhere here. It
 * moves through "Change status", which records why and when, because the
 * history is the record of what the authority actually did.
 */
export function PermitsTab({ projectId, canWrite }: { projectId: string; canWrite: boolean }) {
  const [register, setRegister] = useState<PermitRegister | null>(null);
  const [types, setTypes] = useState<ReferenceValue[]>([]);
  const [selected, setSelected] = useState<Permit | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    permit_code: "",
    permit_type_code: "",
    authority: "",
    planned_submission_date: "",
    planned_issue_date: "",
    statutory_sla_days: "",
  });
  const [filter, setFilter] = useState<Filter>("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setRegister(await projects.permits(projectId));
      setError(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not load permits.");
    }
  }, [projectId]);

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

  const typeLabel = (code: string) => types.find((value) => value.code === code)?.label ?? code;

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
      if (form.planned_submission_date) payload.planned_submission_date = form.planned_submission_date;
      if (form.planned_issue_date) payload.planned_issue_date = form.planned_issue_date;
      if (form.statutory_sla_days) payload.statutory_sla_days = Number(form.statutory_sla_days);
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

  // Narrowing happens here, over rows the server already decided this reader
  // may see. The counts on the strip stay the server's, over the whole set.
  const shown = useMemo(() => {
    const rows = register?.permits ?? [];
    const needle = search.trim().toLowerCase();
    return rows.filter((permit) => {
      if (filter === "blocking" && !permit.is_blocking) return false;
      if (filter === "critical" && !permit.is_critical_path) return false;
      if (filter === "overdue" && !permit.sla_overdue && !permit.expired_flag) return false;
      if (status && permit.status !== status) return false;
      if (
        needle &&
        !`${permit.permit_code} ${permit.authority} ${typeLabel(permit.permit_type_code)} ${permit.authority_reference ?? ""}`
          .toLowerCase()
          .includes(needle)
      ) {
        return false;
      }
      return true;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [register, filter, status, search, types]);

  const filtered = filter !== "" || status !== "" || search !== "";

  return (
    <>
      <PageHeader
        title="Permits"
        subtitle={sectionDescription("permits")}
        compact
        actions={
          canWrite ? (
            <Button variant="primary" onClick={() => setCreating((open) => !open)}>
              {creating ? "Cancel" : "New permit"}
            </Button>
          ) : undefined
        }
      />

      <div className="stack">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}

        {register ? (
          <StatStrip>
            <StatStripItem label="Permits" value={register.total} />
            <StatStripItem
              label="Blocking"
              value={register.blocking_count}
              tone={register.blocking_count > 0 ? "warning" : "neutral"}
            />
            <StatStripItem label="Critical path" value={register.critical_path_count} />
            <StatStripItem
              label="Past statutory period"
              value={register.sla_overdue_count}
              tone={register.sla_overdue_count > 0 ? "danger" : "neutral"}
            />
          </StatStrip>
        ) : null}

        {creating ? (
          <Card title="Register a permit" description="The consent, who issues it, and when it is planned. Everything else is maintained from the permit's file.">
            <form onSubmit={create}>
              <FormSection title="Consent">
                <FieldRow columns={3}>
                  <Field label="Permit code" hint="Unique within this project, e.g. BLD-001.">
                    <input
                      className="input input-medium"
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
                      onChange={(event) => setForm({ ...form, permit_type_code: event.target.value })}
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
                </FieldRow>
              </FormSection>
              <FormSection title="Programme">
                <FieldRow columns={3}>
                  <Field label="Planned submission" optional>
                    <input
                      className="input input-short"
                      type="date"
                      value={form.planned_submission_date}
                      onChange={(event) => setForm({ ...form, planned_submission_date: event.target.value })}
                    />
                  </Field>
                  <Field label="Planned issue" optional>
                    <input
                      className="input input-short"
                      type="date"
                      value={form.planned_issue_date}
                      onChange={(event) => setForm({ ...form, planned_issue_date: event.target.value })}
                    />
                  </Field>
                  <Field label="Statutory period" optional hint="How long the authority has by law.">
                    <span className="input-shell input-shell-rate">
                      <input
                        className="input"
                        type="number"
                        min="1"
                        value={form.statutory_sla_days}
                        onChange={(event) => setForm({ ...form, statutory_sla_days: event.target.value })}
                      />
                      <span className="input-affix" aria-hidden="true">
                        days
                      </span>
                    </span>
                  </Field>
                </FieldRow>
              </FormSection>
              <FormActions>
                <Button variant="primary" type="submit" disabled={busy}>
                  {busy ? "Saving…" : "Register permit"}
                </Button>
                <Button onClick={() => setCreating(false)} disabled={busy}>
                  Cancel
                </Button>
              </FormActions>
            </form>
          </Card>
        ) : null}

        <DataToolbar
          framed
          search={{ value: search, onChange: setSearch, placeholder: "Code, authority or type", label: "Search permits" }}
          count={register ? { shown: shown.length, total: register.total, noun: "permit" } : undefined}
          onReset={
            filtered
              ? () => {
                  setFilter("");
                  setStatus("");
                  setSearch("");
                }
              : undefined
          }
        >
          <ToolbarFilter label="Show">
            <select className="input" value={filter} onChange={(event) => setFilter(event.target.value as Filter)}>
              <option value="">All permits</option>
              <option value="blocking">Blocking only</option>
              <option value="critical">Critical path only</option>
              <option value="overdue">Late or expired only</option>
            </select>
          </ToolbarFilter>
          <ToolbarFilter label="Status">
            <select className="input" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">Any status</option>
              {Object.entries(STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </ToolbarFilter>
        </DataToolbar>

        <Card flush>
          {register === null ? (
            <Loading label="Loading permits…" shape="rows" />
          ) : shown.length === 0 ? (
            <div className="card-body">
              <EmptyState
                title={register.total === 0 ? "No permits registered" : "No permit matches"}
                hint={
                  register.total === 0
                    ? "Add the approvals this development needs, and track where each one stands with the authority."
                    : "Widen the filter to see the rest of the register."
                }
              />
            </div>
          ) : (
            <TableScroll label="Permit register" fixedFirst>
              <thead>
                <tr>
                  <th scope="col">Permit</th>
                  <th scope="col">Authority</th>
                  <th scope="col">Status</th>
                  <th scope="col">Required by</th>
                  <th scope="col">Forecast / received</th>
                  <th scope="col" className="num">
                    Days in stage
                  </th>
                  <th scope="col">Statutory clock</th>
                  <th scope="col">Flags</th>
                  <th scope="col">Next action</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((permit) => (
                  // A permit the authority has had longer than the law allows,
                  // or one consents management says is holding the programme,
                  // carries a rail rather than a red row: the words in the
                  // status and flag columns still say which of the two it is.
                  <tr
                    key={permit.id}
                    aria-selected={selected?.id === permit.id}
                    className={permit.sla_overdue || permit.is_blocking ? "row-flag" : undefined}
                  >
                    <th scope="row">
                      <button className="button-link" type="button" onClick={() => setSelected(permit)}>
                        <IdentityCell name={permit.permit_code} meta={typeLabel(permit.permit_type_code)} />
                      </button>
                    </th>
                    <td className="cell-prose">
                      {permit.authority}
                      {permit.authority_reference ? (
                        <span className="cell-secondary mono">{permit.authority_reference}</span>
                      ) : null}
                    </td>
                    <td>
                      <Badge tone={STATUS_TONES[permit.status] ?? "neutral"}>
                        {STATUS_LABELS[permit.status] ?? permit.status}
                      </Badge>
                    </td>
                    <td className="figure">{businessDate(permit.planned_issue_date)}</td>
                    <td className="figure">
                      {permit.issue_date
                        ? businessDate(permit.issue_date)
                        : permit.forecast_issue_date
                          ? businessDate(permit.forecast_issue_date)
                          : "—"}
                      {!permit.issue_date && permit.forecast_issue_date ? (
                        <span className="cell-secondary">forecast</span>
                      ) : null}
                    </td>
                    <td className="num">{permit.days_in_stage}</td>
                    <td>
                      {permit.sla_overdue ? (
                        <StatusDot tone="danger">{slaLabel(permit)}</StatusDot>
                      ) : permit.sla_days_remaining === null ? (
                        <span className="muted">—</span>
                      ) : (
                        <StatusDot tone="success">{slaLabel(permit)}</StatusDot>
                      )}
                    </td>
                    <td>
                      <div className="row-actions">
                        {permit.is_blocking ? <Badge tone="warning">Blocking</Badge> : null}
                        {permit.is_critical_path ? <Badge tone="info">Critical path</Badge> : null}
                        {permit.expired_flag ? <Badge tone="danger">Expired</Badge> : null}
                        {!permit.prerequisite_satisfied ? <Badge tone="muted">Prerequisite open</Badge> : null}
                      </div>
                    </td>
                    <td className="cell-prose">{permit.next_action ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </TableScroll>
          )}
        </Card>
      </div>

      {selected ? (
        <PermitFile
          projectId={projectId}
          permit={selected}
          typeLabel={typeLabel}
          canWrite={canWrite}
          onClose={() => setSelected(null)}
          onChanged={async (updated) => {
            setSelected(updated);
            await load();
          }}
          onNotice={setNotice}
        />
      ) : null}
    </>
  );
}

const SECTIONS = [
  { key: "permit", label: "Permit" },
  { key: "history", label: "Status history" },
];

/**
 * One permit's file, opened over the register.
 *
 * What the authority has, when it is expected, what it costs, and the one
 * control that moves it — plus every move it has made, in order, with the
 * reason each one was recorded with.
 */
function PermitFile({
  projectId,
  permit,
  typeLabel,
  canWrite,
  onClose,
  onChanged,
  onNotice,
}: {
  projectId: string;
  permit: Permit;
  typeLabel: (code: string) => string;
  canWrite: boolean;
  onClose: () => void;
  onChanged: (updated: Permit) => Promise<void>;
  onNotice: (message: string) => void;
}) {
  const [section, setSection] = useState("permit");
  const [history, setHistory] = useState<PermitStatusEvent[] | null>(null);
  const [editing, setEditing] = useState(false);
  const [move, setMove] = useState({ to_status: "", effective_date: todayISO(), reason: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await projects.permitHistory(projectId, permit.id));
    } catch {
      setHistory([]);
    }
  }, [projectId, permit.id]);

  useEffect(() => {
    void (async () => {
      await loadHistory();
    })();
  }, [loadHistory]);

  const transition = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const updated = await projects.transitionPermit(projectId, permit.id, {
        to_status: move.to_status,
        effective_date: move.effective_date,
        ...(move.reason ? { reason: move.reason } : {}),
      });
      onNotice(`${updated.permit_code} moved to ${STATUS_LABELS[updated.status] ?? updated.status}.`);
      setMove({ to_status: "", effective_date: todayISO(), reason: "" });
      await onChanged(updated);
      await loadHistory();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not change the status.");
    } finally {
      setBusy(false);
    }
  };

  const moves = TRANSITIONS[permit.status] ?? [];

  return (
    <Drawer
      narrow
      eyebrow={typeLabel(permit.permit_type_code)}
      title={permit.permit_code}
      subtitle={permit.authority}
      meta={
        <>
          <Badge tone={STATUS_TONES[permit.status] ?? "neutral"}>
            {STATUS_LABELS[permit.status] ?? permit.status}
          </Badge>
          {permit.is_blocking ? <Badge tone="warning">Blocking</Badge> : null}
          {permit.is_critical_path ? <Badge tone="info">Critical path</Badge> : null}
          {permit.sla_overdue ? <Badge tone="danger">{slaLabel(permit)}</Badge> : null}
        </>
      }
      facts={[
        { label: "Status since", value: businessDate(permit.status_effective_date) },
        { label: "Days in stage", value: permit.days_in_stage },
        { label: "Required by", value: businessDate(permit.planned_issue_date) },
        {
          label: "Statutory clock",
          value: permit.sla_days_remaining === null ? "Not set" : slaLabel(permit),
        },
        ...(permit.financials_visible
          ? [{ label: "Fee", value: money(permit.fee_amount, permit.base_currency_code) }]
          : []),
      ]}
      actions={
        canWrite ? (
          <Button onClick={() => setEditing((open) => !open)}>{editing ? "Cancel edit" : "Edit permit"}</Button>
        ) : undefined
      }
      tabs={SECTIONS}
      activeTab={section}
      onSelectTab={setSection}
      onClose={onClose}
    >
      {error ? <Notice tone="error">{error}</Notice> : null}

      {section === "permit" ? (
        <>
          {editing ? (
            <Card title="Edit permit">
              <EditForm
                fields={permitFields(permit)}
                columns={2}
                initial={Object.fromEntries(
                  permitFields(permit).map((field) => [
                    field.name,
                    asValue(permit[field.name as keyof Permit] as never),
                  ]),
                )}
                onSave={async (changes) => {
                  const updated = await projects.updatePermit(projectId, permit.id, changes);
                  onNotice(`${updated.permit_code} updated.`);
                  await onChanged(updated);
                }}
                onCancel={() => setEditing(false)}
              />
            </Card>
          ) : null}

          <section>
            <h3 className="section-heading">Dates</h3>
            <KeyValueGrid columns={3}>
              <KeyValue label="Planned submission" mono value={businessDate(permit.planned_submission_date)} />
              <KeyValue label="Forecast submission" mono value={businessDate(permit.forecast_submission_date)} />
              <KeyValue label="Submitted" mono value={businessDate(permit.actual_submission_date)} />
              <KeyValue label="Accepted for review" mono value={businessDate(permit.accepted_for_review_date)} />
              <KeyValue label="Comments received" mono value={businessDate(permit.comments_received_date)} />
              <KeyValue label="Resubmitted" mono value={businessDate(permit.resubmission_date)} />
              <KeyValue label="Planned issue" mono value={businessDate(permit.planned_issue_date)} />
              <KeyValue label="Forecast issue" mono value={businessDate(permit.forecast_issue_date)} />
              <KeyValue label="Issued" mono value={businessDate(permit.issue_date)} />
              <KeyValue label="Expiry" mono value={businessDate(permit.expiry_date)} />
              <KeyValue label="Renewal" mono value={businessDate(permit.renewal_date)} />
              <KeyValue
                label="Submission variance"
                mono
                value={permit.submission_variance_days === null ? null : `${permit.submission_variance_days} days`}
              />
              <KeyValue
                label="Issue variance"
                mono
                value={permit.issue_variance_days === null ? null : `${permit.issue_variance_days} days`}
              />
            </KeyValueGrid>
          </section>

          <section>
            <h3 className="section-heading">Application</h3>
            <KeyValueGrid columns={3}>
              <KeyValue label="Authority reference" mono value={permit.authority_reference} />
              <KeyValue label="Consultant" value={permit.consultant} />
              <KeyValue
                label="Statutory period"
                mono
                value={permit.statutory_sla_days === null ? null : `${permit.statutory_sla_days} days`}
              />
              <KeyValue label="Prerequisite" value={permit.prerequisite_satisfied ? "Satisfied" : "Still open"} />
              <KeyValue label="Conditions" value={permit.conditions} />
              <KeyValue label="Next action" value={permit.next_action} />
              <KeyValue label="Notes" value={permit.notes} />
            </KeyValueGrid>
          </section>

          {canWrite && moves.length > 0 ? (
            <section>
              <h3 className="section-heading">Change status</h3>
              <form onSubmit={transition}>
                <FieldRow columns={3}>
                  <Field label="Move to">
                    <select
                      className="input"
                      required
                      value={move.to_status}
                      onChange={(event) => setMove({ ...move, to_status: event.target.value })}
                    >
                      <option value="">Choose…</option>
                      {moves.map((value) => (
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
                      onChange={(event) => setMove({ ...move, effective_date: event.target.value })}
                    />
                  </Field>
                  <Field
                    label="Reason"
                    optional={!REASON_REQUIRED.has(move.to_status)}
                    hint={REASON_REQUIRED.has(move.to_status) ? "Required for this move." : undefined}
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
            </section>
          ) : null}
        </>
      ) : null}

      {section === "history" ? (
        history === null ? (
          <Loading label="Loading history…" lines={3} />
        ) : history.length === 0 ? (
          <EmptyState title="Nothing recorded yet" hint="Every status change is kept here with its effective date and reason." />
        ) : (
          <TableScroll label="Permit status history" compact>
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
                  <th scope="row" className="figure">
                    {businessDate(event.effective_date)}
                  </th>
                  <td>{STATUS_LABELS[event.from_status] ?? event.from_status}</td>
                  <td>
                    <Badge tone={STATUS_TONES[event.to_status] ?? "neutral"}>
                      {STATUS_LABELS[event.to_status] ?? event.to_status}
                    </Badge>
                  </td>
                  <td className="cell-prose">{event.reason ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        )
      ) : null}
    </Drawer>
  );
}
