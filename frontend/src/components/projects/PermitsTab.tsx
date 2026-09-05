"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, projects } from "@/lib/api";
import type {
  LandParcel,
  Permit,
  PermitRegister,
  PermitStatusEvent,
  PermitType,
} from "@/lib/api";
import { businessDate, money, todayISO } from "@/lib/format";
import { sectionDescription } from "@/components/shell/navigation";
import {
  Badge,
  Button,
  ButtonRow,
  Card,
  DataToolbar,
  IdentityCell,
  Drawer,
  EmptyState,
  Field,
  FieldRow,
  FormActions,
  FormDialog,
  FormSection,
  KeyValue,
  KeyValueGrid,
  Loading,
  StatStrip,
  StatStripItem,
  Notice,
  PageHeader,
  SectionHeader,
  StatusDot,
  TableScroll,
  Timeline,
  TimelineItem,
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

/** A blank permit form. Named once so the reset cannot drift from the initial. */
const EMPTY_PERMIT = {
  permit_code: "",
  permit_type_code: "",
  authority: "",
  parcel_id: "",
  planned_submission_date: "",
  planned_issue_date: "",
  statutory_sla_days: "",
};

/** A blank permit type. */
const EMPTY_TYPE = { code: "", label: "" };

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
function permitFields(permit: Permit, types: PermitType[]): EditField[] {
  const frozen = !["not_started", "preparing"].includes(permit.status);
  return [
    { name: "authority", label: "Authority", visible: !frozen, hint: "Fixed once the application is submitted.", group: "Application" },
    {
      name: "permit_type_code",
      label: "Permit type",
      kind: "select",
      visible: !frozen,
      group: "Application",
      width: "medium",
      // Only what may still be assigned. A retired type stays readable on the
      // permits already filed under it; it is not offered for a new one.
      options: types
        .filter((type) => type.is_active || type.code === permit.permit_type_code)
        .map((type) => ({ value: type.code, label: type.label })),
    },
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
  const [types, setTypes] = useState<PermitType[] | null>(null);
  const [selected, setSelected] = useState<Permit | null>(null);
  const [parcels, setParcels] = useState<LandParcel[]>([]);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState(EMPTY_PERMIT);
  const [formError, setFormError] = useState<string | null>(null);
  const [addingType, setAddingType] = useState(false);
  const [typeDraft, setTypeDraft] = useState(EMPTY_TYPE);
  const [typeBusy, setTypeBusy] = useState(false);
  const [typeError, setTypeError] = useState<string | null>(null);
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

  /**
   * The permit vocabulary for this project's jurisdiction.
   *
   * Read from the project rather than from generic Settings: the category and
   * the country pack are the route's, so this cannot accidentally offer another
   * jurisdiction's consents. Retired types come back too, marked inactive —
   * a permit filed years ago still has to render its label.
   */
  const loadTypes = useCallback(async () => {
    try {
      setTypes(await projects.permitTypes(projectId));
    } catch {
      // The register still reads without the vocabulary; the create form says so.
      setTypes([]);
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await loadTypes();
    })();
  }, [loadTypes]);

  // Where a consent applies, offered on the create form. A project with no
  // parcels registered simply does not get the question.
  useEffect(() => {
    void (async () => {
      try {
        setParcels(await projects.parcels(projectId));
      } catch {
        setParcels([]);
      }
    })();
  }, [projectId]);

  const typeLabel = (code: string) => types?.find((value) => value.code === code)?.label ?? code;

  /**
   * Add the missing consent type from inside the permit form.
   *
   * The point of the whole endpoint is what does *not* happen here: the permit
   * being drafted is untouched, so nothing typed so far is the price of
   * discovering the vocabulary was short one entry. On success the new type is
   * selected, because it is the one the operator went looking for.
   */
  const addPermitType = async () => {
    setTypeBusy(true);
    setTypeError(null);
    try {
      const created = await projects.createPermitType(projectId, {
        code: typeDraft.code.trim(),
        label: typeDraft.label.trim(),
      });
      await loadTypes();
      setForm((current) => ({ ...current, permit_type_code: created.code }));
      setTypeDraft(EMPTY_TYPE);
      setAddingType(false);
      setNotice(`Permit type ${created.label} added for this jurisdiction.`);
    } catch (caught) {
      setTypeError(
        caught instanceof ApiError ? caught.message : "Could not add the permit type.",
      );
    } finally {
      setTypeBusy(false);
    }
  };

  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      const payload: Record<string, unknown> = {
        permit_code: form.permit_code,
        permit_type_code: form.permit_type_code,
        authority: form.authority,
      };
      if (form.parcel_id) payload.parcel_id = form.parcel_id;
      if (form.planned_submission_date) payload.planned_submission_date = form.planned_submission_date;
      if (form.planned_issue_date) payload.planned_issue_date = form.planned_issue_date;
      if (form.statutory_sla_days) payload.statutory_sla_days = Number(form.statutory_sla_days);
      await projects.createPermit(projectId, payload);
      setNotice(`Permit ${form.permit_code} registered.`);
      setCreating(false);
      setForm(EMPTY_PERMIT);
      await load();
    } catch (caught) {
      setFormError(
        caught instanceof ApiError ? caught.message : "Could not register the permit.",
      );
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
            <Button
              variant="primary"
              onClick={() => {
                setFormError(null);
                setCreating((open) => !open);
              }}
            >
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
          <ToolbarFilter label="Show" active={filter !== ""}>
            <select className="input" value={filter} onChange={(event) => setFilter(event.target.value as Filter)}>
              <option value="">All permits</option>
              <option value="blocking">Blocking only</option>
              <option value="critical">Critical path only</option>
              <option value="overdue">Late or expired only</option>
            </select>
          </ToolbarFilter>
          <ToolbarFilter label="Status" active={status !== ""}>
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

      {creating ? (
        <Drawer
          narrow
          eyebrow="New record"
          title="Register a permit"
          subtitle="The consent, who issues it, and when it is planned. Everything else is maintained from the permit's file."
          onClose={() => {
            setCreating(false);
            setFormError(null);
          }}
        >
          <form onSubmit={create}>
            {formError ? <Notice tone="error">{formError}</Notice> : null}
            <FormSection title="Consent">
              <FieldRow columns={2}>
                <Field label="Permit code" hint="Unique within this project, e.g. BLD-001.">
                  <input
                    className="input input-medium"
                    required
                    maxLength={64}
                    value={form.permit_code}
                    onChange={(event) => setForm({ ...form, permit_code: event.target.value })}
                  />
                </Field>
                <Field label="Authority">
                  <input
                    className="input"
                    required
                    maxLength={200}
                    value={form.authority}
                    onChange={(event) => setForm({ ...form, authority: event.target.value })}
                  />
                </Field>
              </FieldRow>
              <PermitTypeChoice
                types={types}
                value={form.permit_type_code}
                canWrite={canWrite}
                onChange={(code) => setForm({ ...form, permit_type_code: code })}
                onAdd={() => setAddingType(true)}
              />
              {/* Only asked where there is something to answer with. A lone
                  "not tied to one parcel" option is a question the project
                  cannot yet have an opinion about. */}
              {parcels.length > 0 ? (
                <Field
                  label="Parcel"
                  optional
                  hint="Where the consent applies, where that is known."
                >
                  <select
                    className="input"
                    value={form.parcel_id}
                    onChange={(event) => setForm({ ...form, parcel_id: event.target.value })}
                  >
                    <option value="">Not tied to one parcel</option>
                    {parcels.map((parcel) => (
                      <option key={parcel.id} value={parcel.id}>
                        {parcel.plot_number}
                      </option>
                    ))}
                  </select>
                </Field>
              ) : null}
            </FormSection>
            <FormSection title="Programme">
              <FieldRow columns={3}>
                <Field label="Planned submission" optional>
                  <input
                    className="input input-short"
                    type="date"
                    value={form.planned_submission_date}
                    onChange={(event) =>
                      setForm({ ...form, planned_submission_date: event.target.value })
                    }
                  />
                </Field>
                <Field label="Planned issue" optional>
                  <input
                    className="input input-short"
                    type="date"
                    value={form.planned_issue_date}
                    onChange={(event) =>
                      setForm({ ...form, planned_issue_date: event.target.value })
                    }
                  />
                </Field>
                <Field
                  label="Statutory period"
                  optional
                  hint="How long the authority has by law."
                >
                  <span className="input-shell input-shell-rate">
                    <input
                      className="input"
                      type="number"
                      min="1"
                      value={form.statutory_sla_days}
                      onChange={(event) =>
                        setForm({ ...form, statutory_sla_days: event.target.value })
                      }
                    />
                    <span className="input-affix" aria-hidden="true">
                      days
                    </span>
                  </span>
                </Field>
              </FieldRow>
            </FormSection>
            <FormActions>
              <Button variant="primary" type="submit" disabled={busy || !form.permit_type_code}>
                {busy ? "Saving…" : "Register permit"}
              </Button>
              <Button onClick={() => setCreating(false)} disabled={busy}>
                Cancel
              </Button>
            </FormActions>
          </form>
        </Drawer>
      ) : null}

      {/* Opened from inside the permit form and closed back into it. The
          permit's own fields are untouched while this is open, so nothing
          typed so far is lost to adding the type it needed. */}
      {addingType ? (
        <FormDialog
          title="Add a permit type"
          description="Added to this project's jurisdiction and available immediately. It becomes part of the vocabulary every permit register here filters and reports on."
          confirmLabel="Add permit type"
          busy={typeBusy}
          disabled={!typeDraft.code.trim() || !typeDraft.label.trim()}
          onSubmit={() => void addPermitType()}
          onCancel={() => {
            setAddingType(false);
            setTypeError(null);
          }}
        >
          {typeError ? <Notice tone="error">{typeError}</Notice> : null}
          <Field label="Name" hint="What operators read: Civil defence approval.">
            <input
              className="input"
              required
              maxLength={200}
              value={typeDraft.label}
              onChange={(event) => setTypeDraft({ ...typeDraft, label: event.target.value })}
            />
          </Field>
          <Field
            label="Short code"
            hint="The identifier registers and reports group by. Chosen once and not generated: CIVIL_DEFENCE."
          >
            <input
              className="input input-medium mono"
              required
              maxLength={64}
              value={typeDraft.code}
              onChange={(event) => setTypeDraft({ ...typeDraft, code: event.target.value })}
            />
          </Field>
        </FormDialog>
      ) : null}

      {selected ? (
        <PermitFile
          projectId={projectId}
          permit={selected}
          types={types ?? []}
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

/**
 * Choosing the consent type, and adding one when the list is short of it.
 *
 * Permit type stayed a controlled vocabulary on purpose — it is filtered,
 * counted and reported on, and left open it becomes "Building Permit",
 * "building permit" and "BLDG" inside a month. What PR-V2-01 removes is the
 * detour: the operator who needs a type nobody configured used to abandon the
 * permit, find a System Administrator, learn what a reference category is, and
 * come back. So the way in is here, beside the field that needed it.
 *
 * Retired types are not offered. They still render on the permits already
 * filed under them; they are not choices for a new application.
 */
function PermitTypeChoice({
  types,
  value,
  canWrite,
  onChange,
  onAdd,
}: {
  /** `null` while the vocabulary is still loading. */
  types: PermitType[] | null;
  value: string;
  canWrite: boolean;
  onChange: (code: string) => void;
  onAdd: () => void;
}) {
  if (types === null) {
    return <Loading label="Loading permit types…" lines={1} />;
  }

  const available = types.filter((type) => type.is_active);

  // A jurisdiction nobody has configured yet. An empty dropdown would look
  // broken and say nothing; the reason and the way out belong in its place.
  if (available.length === 0) {
    return (
      <EmptyState
        title="No permit types yet"
        hint={
          canWrite
            ? "This project's jurisdiction has no consent types configured. Add the first one to file a permit under it."
            : "This project's jurisdiction has no consent types configured. Somebody with technical write access has to add one before a permit can be filed."
        }
        actions={
          canWrite ? (
            <Button variant="primary" onClick={onAdd}>
              Add permit type
            </Button>
          ) : undefined
        }
      />
    );
  }

  return (
    <>
      <Field
        label="Permit type"
        hint="The vocabulary this project's registers and reports group by."
      >
        <select
          className="input"
          required
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">Choose…</option>
          {available.map((type) => (
            <option key={type.id} value={type.code}>
              {type.label}
            </option>
          ))}
        </select>
      </Field>
      {canWrite ? (
        <ButtonRow>
          <Button onClick={onAdd}>Add permit type</Button>
        </ButtonRow>
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
  types,
  typeLabel,
  canWrite,
  onClose,
  onChanged,
  onNotice,
}: {
  projectId: string;
  permit: Permit;
  types: PermitType[];
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
      // Where the consent stands with the authority, set large. A permit is
      // opened to answer one question — is it late — and the statutory clock is
      // the server's answer to it, not a countdown computed here.
      headline={
        permit.sla_days_remaining === null
          ? undefined
          : {
              value: slaLabel(permit),
              label: permit.sla_overdue ? "Past the statutory period" : "Statutory period",
              tone: permit.sla_overdue ? "danger" : undefined,
            }
      }
      facts={[
        { label: "Status since", value: businessDate(permit.status_effective_date) },
        { label: "Days in stage", value: permit.days_in_stage },
        { label: "Required by", value: businessDate(permit.planned_issue_date) },
        ...(permit.statutory_sla_days === null
          ? [{ label: "Statutory period", value: "Not set", tone: "muted" as const }]
          : []),
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
                fields={permitFields(permit, types)}
                columns={2}
                initial={Object.fromEntries(
                  permitFields(permit, types).map((field) => [
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

          {/* What somebody has to do next, above the dates and the reference
              numbers. A permit file read top to bottom should say where the
              consent stands, then what is waiting on whom — a next action
              seventeen fields down is one nobody acts on. */}
          {permit.next_action || !permit.prerequisite_satisfied ? (
            <Card
              title="Next action"
              headingLevel={3}
              tone={permit.is_blocking || permit.sla_overdue ? "attention" : undefined}
            >
              <p className="subtle">{permit.next_action ?? "No next action recorded."}</p>
              {!permit.prerequisite_satisfied ? (
                <p className="subtle">
                  <StatusDot tone="warning">
                    A permit this one depends on has not been issued.
                  </StatusDot>
                </p>
              ) : null}
            </Card>
          ) : null}

          <section>
            <SectionHeader title="Dates" />
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
            <SectionHeader title="Application" />
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
              <KeyValue label="Notes" value={permit.notes} />
            </KeyValueGrid>
          </section>

          {canWrite && moves.length > 0 ? (
            <section>
              <SectionHeader
                title="Change status"
                description="Recorded with the date it took effect and the reason, and kept in the history. Status is never edited as a field."
              />
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
          // A permit's history is a sequence, and a four-column table of it
          // reads as a spreadsheet of a story. Newest first, because the
          // question is almost always what happened last.
          <Timeline>
            {[...history].reverse().map((event, index) => (
              <TimelineItem
                key={event.id}
                title={STATUS_LABELS[event.to_status] ?? event.to_status}
                date={businessDate(event.effective_date)}
                // A withdrawal is struck through rather than dropped: it
                // happened, and a history that tidies it away is a history
                // somebody edited.
                state={
                  event.to_status === "withdrawn" ? "void" : index === 0 ? "current" : "done"
                }
                detail={
                  <>
                    <p className="footnote">
                      From {STATUS_LABELS[event.from_status] ?? event.from_status}
                    </p>
                    {event.reason ? <p className="subtle">{event.reason}</p> : null}
                  </>
                }
              />
            ))}
          </Timeline>
        )
      ) : null}
    </Drawer>
  );
}
