"use client";

import { DraftBoundary } from "@/components/ui/UnsavedChangesGuard";

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
  ConfirmDialog,
  Tabs,
  TabPanel,
  EmptyState,
  Field,
  FieldRow,
  FormActions,
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
import { PermitCreatePage } from "./PermitCreatePage";
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
  issued: "Obtained / Issued",
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
function permitFields(permit: Permit, types: PermitType[], permits: Permit[]): EditField[] {
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
    { name: "prerequisite_permit_id", label: "Prerequisite permit", kind: "select", group: "Application", options: permits.filter(row => row.id !== permit.id).map(row => ({ value: row.id, label: row.permit_code })) },
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
export function PermitsTab({ projectId, canWrite, canDelete = false, canSeeCost = false, currencyCode = null }: { projectId: string; canWrite: boolean; canDelete?: boolean; canSeeCost?: boolean; currencyCode?: string | null }) {
  const [register, setRegister] = useState<PermitRegister | null>(null);
  const [types, setTypes] = useState<PermitType[] | null>(null);
  const [selected, setSelected] = useState<Permit | null>(null);
  const [parcels, setParcels] = useState<LandParcel[]>([]);
  const [creating, setCreating] = useState(false);
  const [filter, setFilter] = useState<Filter>("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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
      {!creating && !selected ? <>
      <PageHeader
        icon="permits"
        title="Permits"
        subtitle={sectionDescription("permits")}
        compact
        actions={
          canWrite ? (
            <Button data-leaves-editor
              variant="primary"
              onClick={() => {
                setCreating((open) => !open);
              }}
            >
              Add permit
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

      </> : null}
      {creating && canWrite ? <PermitCreatePage projectId={projectId} types={types} parcels={parcels}
        permits={register?.permits ?? []} statuses={STATUS_LABELS} canSeeCost={canSeeCost}
        currencyCode={currencyCode} onCancel={() => setCreating(false)}
        onCreated={async created => { setCreating(false); setSelected(created); setNotice(`Permit ${created.permit_code} added.`); await load(); await loadTypes(); }} /> : null}

      {selected ? (
        <PermitFile
          projectId={projectId}
          permit={selected}
          types={types ?? []}
          permits={register?.permits ?? []}
          typeLabel={typeLabel}
          canWrite={canWrite}
          canDelete={canDelete}
          onDeleted={async () => { setSelected(null); setNotice("Permit deleted from the active register."); await load(); }}
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
  types,
  typeLabel,
  permits,
  canWrite,
  onClose,
  onChanged,
  onNotice,
  canDelete,
  onDeleted,
}: {
  projectId: string;
  permit: Permit;
  types: PermitType[];
  permits: Permit[];
  typeLabel: (code: string) => string;
  canWrite: boolean;
  onClose: () => void;
  onChanged: (updated: Permit) => Promise<void>;
  onNotice: (message: string) => void;
  canDelete: boolean;
  onDeleted: () => Promise<void>;
}) {
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [section, setSection] = useState("permit");
  const [history, setHistory] = useState<PermitStatusEvent[] | null>(null);
  const [editing, setEditing] = useState(false);
  const [moveBaseline, setMoveBaseline] = useState({ to_status: "", effective_date: todayISO(), reason: "" });
  const [move, setMove] = useState(moveBaseline);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [historyError, setHistoryError] = useState(false);
  const loadHistory = useCallback(async () => {
    setHistoryError(false);
    try {
      setHistory(await projects.permitHistory(projectId, permit.id));
    } catch {
      setHistory(null);
      setHistoryError(true);
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
      const emptyMove = { to_status: "", effective_date: todayISO(), reason: "" };
      setMove(emptyMove);
      setMoveBaseline(emptyMove);
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
    <article className="record-workspace">
      <Button data-leaves-editor onClick={onClose} disabled={busy}>Back to permits</Button>
      <PageHeader icon="permits" title={permit.permit_code} subtitle={permit.authority}
        actions={<ButtonRow>
          {canWrite ? <Button data-leaves-editor onClick={() => setEditing(open => !open)}>{editing ? "Cancel edit" : "Edit permit"}</Button> : null}
          {canDelete ? <Button data-leaves-editor variant="danger" disabled={busy} onClick={() => { setDeleteError(null); setDeleting(true); }}>Delete permit</Button> : null}
        </ButtonRow>} />
      <div className="row-actions"><Badge tone={STATUS_TONES[permit.status] ?? "neutral"}>{STATUS_LABELS[permit.status] ?? permit.status}</Badge>
        <span>{typeLabel(permit.permit_type_code)}</span>
        {permit.is_blocking ? <Badge tone="warning">Blocking</Badge> : null}
        {permit.is_critical_path ? <Badge tone="info">Critical path</Badge> : null}
        {permit.sla_overdue ? <Badge tone="danger">{slaLabel(permit)}</Badge> : null}
      </div>
      <KeyValueGrid columns={3}>
        <KeyValue label="Status since" value={businessDate(permit.status_effective_date)} />
        <KeyValue label="Days in stage" value={permit.days_in_stage} />
        <KeyValue label="Statutory period" value={slaLabel(permit)} />
        {permit.financials_visible ? <KeyValue label="Fee" value={money(permit.fee_amount, permit.base_currency_code)} /> : null}
      </KeyValueGrid>
      <Tabs label="Permit sections" tabs={SECTIONS} active={section} onSelect={setSection} />
      <TabPanel group="Permit sections" tab={section}>
      {error ? <Notice tone="error">{error}</Notice> : null}

      {section === "permit" ? (
        <>
          {editing ? (
            <Card title="Edit permit">
              <EditForm
                fields={permitFields(permit, types, permits)}
                columns={2}
                initial={Object.fromEntries(
                  permitFields(permit, types, permits).map((field) => [
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
              <DraftBoundary dirty={JSON.stringify(move) !== JSON.stringify(moveBaseline)} busy={busy} onDiscard={() => setMove(moveBaseline)}>
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
              </DraftBoundary>
            </section>
          ) : null}
        </>
      ) : null}

      {section === "history" ? (
        historyError ? <><Notice tone="error">Permit history could not be loaded.</Notice><Button onClick={() => void loadHistory()}>Retry history</Button></> : history === null ? (
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
      </TabPanel>
      {deleting ? <ConfirmDialog title={`Delete permit ${permit.permit_code}?`}
        body={deleteError ?? "Remove this permit from active screens and counts? Audit history and document references are retained. An active dependent permit must be unlinked first."}
        confirmLabel="Delete permit" busy={busy} onCancel={() => { if (!busy) setDeleting(false); }}
        onConfirm={() => { if (busy) return; setBusy(true); setDeleteError(null);
          void projects.removePermit(projectId, permit.id).then(onDeleted)
            .catch(caught => setDeleteError(caught instanceof ApiError ? caught.message : "Could not delete the permit."))
            .finally(() => setBusy(false));
        }} /> : null}
    </article>
  );
}
