"use client";

import Link from "next/link";
import { useState } from "react";
import { useRegisterFields } from "@/components/shell/registerState";
import { projectHref } from "@/components/shell/navigation";
import { Badge, Button, ButtonRow, Card, EmptyState, Field, FieldRow, FormDialog, KeyValue, KeyValueGrid, Loading, MoneyInput, Notice, SectionHeader, TableScroll } from "@/components/ui";
import { ApiError, construction } from "@/lib/api";
import type { BudgetDetail, BudgetLine, BudgetVersion, CostCode } from "@/lib/api";
import { useAnswer } from "@/lib/answer";
import { businessDate, eventTime, todayISO } from "@/lib/format";
import { hasAnyRole } from "@/lib/roles";
import { BudgetTable } from "./BudgetTable";
import { budgetLabel, budgetTone } from "./labels";

const PREPARERS = new Set(["project_manager", "finance"]);
const OPEN = new Set(["draft", "submitted", "approved"]);
type Editor = { kind: "create"; source?: string } | { kind: "line"; code: CostCode; line?: BudgetLine } | { kind: "code" } | { kind: "submit" | "approve" | "reject" | "activate" };
const actionLabels = { submit: "Submit for approval", approve: "Approve budget", reject: "Reject budget", activate: "Activate budget" };
const explanations = {
  submit: "Freeze these lines for review. They cannot be edited after submission; a rejected version can be copied into a new draft.",
  approve: "Approve this version as the agreed authorization. Approval does not replace the budget in force; activation is a separate decision.",
  reject: "Keep this version as rejected history. The preparer can copy it into a new draft; enter the reason they need to address.",
  activate: "Replace the budget in force with this approved version. Existing commitments, cost-code coverage, currency and effective date are checked again by the server.",
};

/** One governed budget journey. The server owns financial validation and eligibility. */
export function BudgetWorkspace({ projectId, roles, onChanged }: { projectId: string; roles: Set<string>; onChanged: () => Promise<void> }) {
  const [view, setView] = useRegisterFields({ budgetVersion: "" });
  const [revision, setRevision] = useState(0);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<ApiError | Error | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const register = useAnswer(true, () => construction.budgets(projectId), [projectId, revision]);
  const codes = useAnswer(true, () => construction.costCodes(projectId), [projectId, revision]);
  const record = useAnswer(!!view.budgetVersion, () => construction.budget(projectId, view.budgetVersion), [projectId, view.budgetVersion, revision]);
  const versions = register.status === "ready" ? register.data : [];
  const detail = record.status === "ready" ? record.data : null;
  const costCodes = codes.status === "ready" ? codes.data : [];
  const active = versions.find(version => version.status === "active");
  const open = versions.find(version => OPEN.has(version.status));
  const canPrepare = hasAnyRole(roles, PREPARERS);
  const listHref = `${projectHref(projectId, "construction")}&constructionTab=budget`;
  const versionHref = (id: string) => `${listHref}&budgetVersion=${encodeURIComponent(id)}`;
  function begin(next: Editor) { setFailure(null); setNotice(null); setEditor(next); }
  function refresh() { setRevision(value => value + 1); }
  async function save(body: Record<string, unknown>) {
    if (!editor || busy) return;
    setBusy(true); setFailure(null);
    try {
      if (editor.kind === "create") {
        const created = await construction.createBudget(projectId, body);
        setView({ budgetVersion: created.id });
        setNotice(`Budget v${created.version_number} created. Record every active cost code before submitting.`);
      } else if (editor.kind === "code") {
        await construction.createCostCode(projectId, body);
        setNotice("Cost code created. Record its budget line explicitly, even when zero is authorized.");
      } else {
        if (!detail) throw new Error("Reload the selected budget before continuing.");
        if (editor.kind === "line") await construction.writeBudgetLine(projectId, detail.id, body);
        else if (editor.kind === "submit") await construction.submitBudget(projectId, detail.id);
        else if (editor.kind === "approve") await construction.approveBudget(projectId, detail.id);
        else if (editor.kind === "reject") await construction.rejectBudget(projectId, detail.id, String(body.reason));
        else await construction.activateBudget(projectId, detail.id);
        setNotice(editor.kind === "line" ? "Budget line saved." : `Budget v${detail.version_number}: ${actionLabels[editor.kind]} completed.`);
      }
      // A successful write is complete even if the following read needs Retry.
      setEditor(null); refresh(); void onChanged();
    } catch (caught) {
      setFailure(caught instanceof Error ? caught : new Error("The action could not be completed."));
      // Refresh eligibility after a conflict/refusal without replaying the write.
      if (caught instanceof ApiError && [403, 409].includes(caught.status)) refresh();
    } finally { setBusy(false); }
  }
  const decision = detail?.workflow;
  const missing = detail ? costCodes.filter(code => code.is_active && !detail.lines.some(line => line.cost_code_id === code.id)) : [];
  return <div className="stack">
    <SectionHeader title="Construction budget" description="Prepare an authorization, have it checked, then put it into force. Draft and approved versions do not change the current budget." />
    <ButtonRow>
      {view.budgetVersion ? <Link className="button" href={listHref}>Back to budget versions</Link> : null}
      {canPrepare && register.status === "ready" && !open ? <Button variant="primary" onClick={() => begin({ kind: "create", source: detail?.id })}>{versions.length ? "Create budget revision" : "Create first budget"}</Button> : null}
      {open && open.id !== view.budgetVersion ? <Link className="button button-primary" href={versionHref(open.id)}>Continue v{open.version_number} · {budgetLabel(open.status)}</Link> : null}
      {canPrepare && register.status === "ready" && codes.status === "ready" && (!open || open.status === "draft") ? <Button onClick={() => begin({ kind: "code" })}>Add cost code</Button> : null}
    </ButtonRow>
    {notice ? <Notice tone="success">{notice}</Notice> : null}
    {register.status === "failed" ? <><Notice tone="error">{register.message}</Notice><Button onClick={register.retry}>Retry budget versions</Button></> : register.status === "denied" ? <Notice tone="info">Whole-project Construction access is required to read budgets.</Notice> : register.status === "loading" ? <Loading label="Loading budget versions" shape="rows" /> : <>
      <Notice tone={active ? "info" : "warning"}>{active ? `Budget v${active.version_number} is in force. Other versions do not authorize commitments.` : "No construction budget is in force. Preparing or approving a draft does not activate it."}</Notice>
      {!view.budgetVersion ? versions.length ? <TableScroll label="Budget versions"><thead><tr><th scope="col">Version</th><th scope="col">Status</th><th scope="col">Effective</th><th scope="col">Reason / source</th></tr></thead><tbody>{versions.map(version => <tr key={version.id}><th scope="row"><Link href={versionHref(version.id)}>Budget v{version.version_number}</Link></th><td><Badge tone={budgetTone(version.status)}>{budgetLabel(version.status)}</Badge></td><td>{businessDate(version.effective_date)}</td><td className="cell-prose">{version.change_reason}{version.source_version_id ? <p><Link href={versionHref(version.source_version_id)}>Open source version</Link></p> : null}</td></tr>)}</tbody></TableScroll> : <EmptyState title="No budget versions" hint="Create the first budget, add any missing cost codes, and enter their authorizations. Finance or a Project Manager prepares; an Approver / CFO reviews." /> : null}
    </>}
    {codes.status === "failed" ? <><Notice tone="error">Cost codes could not be loaded. Budget lines are unavailable for editing until this read recovers.</Notice><Button onClick={codes.retry}>Retry cost codes</Button></> : codes.status === "denied" ? <Notice tone="info">Cost codes are unavailable to your current scope.</Notice> : null}
    {view.budgetVersion && record.status === "loading" ? <Loading label="Loading selected budget" shape="rows" /> : null}
    {record.status === "failed" ? <><Notice tone="error">{record.message}</Notice><Button onClick={record.retry}>Retry selected budget</Button></> : record.status === "denied" ? <Notice tone="info">This budget is not available to your current scope.</Notice> : null}
    {detail && decision ? <>
      <Card title={`Work on budget v${detail.version_number}`}>
        <p>{detail.change_reason}</p>
        {detail.status === "draft" ? <>
          <Notice tone={decision.submission_blocker ? "warning" : "success"}>{decision.submission_blocker ?? "Every active cost code is addressed. This budget can be submitted for approval."}</Notice>
          {decision.editing_blocker ? <p className="footnote">{decision.editing_blocker}</p> : null}
          <Button disabled={busy || !!decision.submission_blocker} onClick={() => begin({ kind: "submit" })}>Submit for approval</Button>
        </> : null}
        {detail.status === "submitted" ? <>
          <p>{decision.approval_blocker ?? "You may approve or reject this submitted version. Approval alone does not put it into force."}</p>
          <ButtonRow><Button disabled={busy || !!decision.approval_blocker} onClick={() => begin({ kind: "approve" })}>Approve budget</Button><Button disabled={busy || !!decision.rejection_blocker} onClick={() => begin({ kind: "reject" })}>Reject budget</Button></ButtonRow>
        </> : null}
        {detail.status === "approved" ? <><p>{decision.activation_blocker ?? "This approved version currently covers standing commitments and can be put into force."}</p><Button variant="primary" disabled={busy || !!decision.activation_blocker} onClick={() => begin({ kind: "activate" })}>Activate budget</Button><p className="footnote">If this version needs corrections before activation, an independent Approver / CFO can return it with a reason, then a preparer can copy it into a corrected draft.</p><Button disabled={busy || !!decision.rejection_blocker} onClick={() => begin({ kind: "reject" })}>Return for correction</Button>{decision.rejection_blocker ? <p className="footnote">{decision.rejection_blocker}</p> : null}</> : null}
        {detail.status === "rejected" ? <Notice tone="warning">Rejected: {detail.rejection_reason}. Create a revision from this version to address the feedback; this history stays unchanged.</Notice> : null}
        {detail.status === "active" || detail.status === "superseded" ? <p>This version is read-only. Use a revision to change the authorization.</p> : null}
        <Button small variant="quiet" disabled={busy} onClick={refresh}>Refresh validation</Button>
      </Card>
      {missing.length && !decision.editing_blocker ? <Card title="Cost codes needing an answer" description="A missing line is not a zero authorization. Record each amount explicitly.">{missing.map(code => <p key={code.id}><Button onClick={() => begin({ kind: "line", code })}>Record {code.code} · {code.name}</Button></p>)}</Card> : null}
      <BudgetTable detail={detail} editableCodes={new Set(costCodes.filter(code => code.is_active).map(code => code.id))} onEdit={!decision.editing_blocker && codes.status === "ready" ? line => { const code = costCodes.find(code => code.id === line.cost_code_id); if (code?.is_active) begin({ kind: "line", code, line }); else setNotice("This cost code is retired; its recorded authorization remains historical."); } : undefined} />
      <Card title="Version history"><KeyValueGrid columns={3}>{([['Created', detail.created_at], ['Submitted', detail.submitted_at], ['Approved', detail.approved_at], ['Rejected', detail.rejected_at], ['Activated', detail.activated_at], ['Superseded', detail.superseded_at]] as const).map(([label, date]) => <KeyValue key={label} label={label} value={date ? eventTime(date) : "—"} />)}</KeyValueGrid>{detail.source_version_id ? <Link href={versionHref(detail.source_version_id)}>Open the source version</Link> : <p>Opening version; no source was copied.</p>}</Card>
    </> : null}
    {editor ? <BudgetEditor key={editor.kind === "line" ? editor.code.id : editor.kind} editor={editor} detail={detail} versions={versions} busy={busy} failure={failure} onSubmit={body => void save(body)} onCancel={() => { if (!busy) { setEditor(null); setFailure(null); } }} /> : null}
  </div>;
}

function BudgetEditor({ editor, detail, versions, busy, failure, onSubmit, onCancel }: { editor: Editor; detail: BudgetDetail | null; versions: BudgetVersion[]; busy: boolean; failure: Error | null; onSubmit: (body: Record<string, unknown>) => void; onCancel: () => void }) {
  const line = editor.kind === "line" ? editor.line : undefined;
  const [form, setForm] = useState({ effective_date: todayISO(), change_reason: "", source_version_id: editor.kind === "create" ? editor.source ?? "" : "", approved_budget_amount: line?.approved_budget_amount ?? "", contingency_amount: line?.contingency_amount ?? "", baseline_amount: "", funding_source: line?.funding_source ?? "", notes: line?.notes ?? "", code: "", name: "", cost_category: "hard", reason: "" });
  const change = (key: keyof typeof form, value: string) => setForm(current => ({ ...current, [key]: value }));
  const error = (key: string) => failure instanceof ApiError ? failure.fieldErrors.filter(item => item.path.includes(key)).map(item => item.message).join(" ") || undefined : undefined;
  const title = editor.kind === "create" ? "Create budget draft" : editor.kind === "code" ? "Add cost code" : editor.kind === "line" ? `Budget line · ${editor.code.code}` : editor.kind === "reject" && detail?.status === "approved" ? "Return budget for correction" : actionLabels[editor.kind];
  function submit() {
    if (editor.kind === "create") onSubmit({ effective_date: form.effective_date, change_reason: form.change_reason.trim(), ...(form.source_version_id ? { source_version_id: form.source_version_id } : {}) });
    else if (editor.kind === "code") onSubmit({ code: form.code.trim(), name: form.name.trim(), cost_category: form.cost_category });
    else if (editor.kind === "line") onSubmit({ cost_code_id: editor.code.id, approved_budget_amount: form.approved_budget_amount, contingency_amount: form.contingency_amount, funding_source: form.funding_source, notes: form.notes, ...(!line && !detail?.source_version_id && form.baseline_amount ? { baseline_amount: form.baseline_amount } : {}) });
    else onSubmit(editor.kind === "reject" ? { reason: form.reason.trim() } : {});
  }
  return <FormDialog title={title} confirmLabel={editor.kind === "line" ? "Save budget line" : title} busy={busy} disabled={editor.kind === "create" ? !form.change_reason.trim() : editor.kind === "reject" ? !form.reason.trim() : editor.kind === "code" ? !form.code.trim() || !form.name.trim() : false} onSubmit={submit} onCancel={onCancel}>
    {failure ? <Notice tone="error">{failure.message}</Notice> : null}
    {editor.kind === "create" ? <>
      <Field label="Effective date" error={error("effective_date")} hint="A replacement takes effect today or later. Future-dated approval waits for explicit activation on or after that date."><input className="input" type="date" required value={form.effective_date} onChange={e => change("effective_date", e.target.value)} /></Field>
      <Field label="Reason for this budget" error={error("change_reason")}><textarea className="input" required maxLength={1000} value={form.change_reason} onChange={e => change("change_reason", e.target.value)} /></Field>
      <Field label="Copy from" hint="Copied lines keep their original baselines. Rejected versions can be used to prepare a corrected draft."><select className="input" value={form.source_version_id} onChange={e => change("source_version_id", e.target.value)}><option value="">{versions.some(v => v.status === "active") ? "Budget currently in force" : "Blank opening budget"}</option>{versions.map(v => <option key={v.id} value={v.id}>v{v.version_number} · {budgetLabel(v.status)}</option>)}</select></Field>
    </> : editor.kind === "code" ? <>
      <p>A project cost code groups budget and future contract lines. This creates a project-wide code; it does not authorize spending.</p>
      <Field label="Code" error={error("code")}><input className="input" required maxLength={32} value={form.code} onChange={e => change("code", e.target.value)} /></Field>
      <Field label="Name" error={error("name")}><input className="input" required maxLength={200} value={form.name} onChange={e => change("name", e.target.value)} /></Field>
      <Field label="Category"><select className="input" value={form.cost_category} onChange={e => change("cost_category", e.target.value)}><option value="hard">Hard costs</option><option value="soft">Soft costs</option><option value="contingency">Contingency</option><option value="other">Other</option></select></Field>
    </> : editor.kind === "line" ? <>
      <p>{editor.code.name}. Enter zero explicitly when no amount is authorized. Control budget and headroom are calculated by the server.</p>
      <FieldRow><Field label="Budget authorization" error={error("approved_budget_amount")}><MoneyInput code={detail?.currency_code ?? null} required value={form.approved_budget_amount} onChange={v => change("approved_budget_amount", v)} /></Field><Field label="Contingency" error={error("contingency_amount")}><MoneyInput code={detail?.currency_code ?? null} required value={form.contingency_amount} onChange={v => change("contingency_amount", v)} /></Field></FieldRow>
      {!line && !detail?.source_version_id ? <Field label="Historical opening baseline" optional error={error("baseline_amount")} hint="Only for an existing project's original authorization. Omit to start at zero; this baseline cannot be restated after saving."><MoneyInput code={detail?.currency_code ?? null} value={form.baseline_amount} onChange={v => change("baseline_amount", v)} /></Field> : <p className="footnote">The original baseline is preserved. Edit the authorization and contingency to revise the budget.</p>}
      <Field label="Funding source" optional error={error("funding_source")}><input className="input" maxLength={120} value={form.funding_source} onChange={e => change("funding_source", e.target.value)} /></Field>
      <Field label="Notes" optional error={error("notes")}><textarea className="input" maxLength={2000} value={form.notes} onChange={e => change("notes", e.target.value)} /></Field>
    </> : <><p>{editor.kind === "reject" && detail?.status === "approved" ? "Return this approved candidate to rejected history with a reason. Its approval history and the budget currently in force remain unchanged. A preparer can then copy it into a corrected draft." : explanations[editor.kind]}</p>{editor.kind === "reject" ? <Field label="Rejection reason" error={error("reason")}><textarea className="input" required maxLength={1000} value={form.reason} onChange={e => change("reason", e.target.value)} /></Field> : null}</>}
  </FormDialog>;
}
