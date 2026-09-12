import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { createRequire } from "node:module";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);
const settle = () => new Promise(resolve => setImmediate(resolve));

test("Permit deletion waits for confirmation and keeps server refusal visible", async () => {
  const calls = []; let removed = 0;
  class ApiError extends Error {}
  const render = mount("projects/PermitsTab", "PermitFile", {
    "@/lib/api": { ApiError, projects: { permitHistory: async () => [], removePermit: async (...args) => { calls.push(args); throw new ApiError("Clear dependent first"); } } },
    "@/lib/format": { todayISO: () => "2026-09-12", businessDate: value => value },
  }, { projectId: "project", permit: { id: "permit", permit_code: "TEST", status: "not_started", prerequisite_satisfied: true },
    types: [], permits: [], canWrite: false, canDelete: true, typeLabel: value => value,
    onClose() {}, onNotice() {}, onChanged: async () => {}, onDeleted: async () => { removed++; } });
  render(); await settle();
  const header = nodes(render()).find(n => n.type === "PageHeader");
  nodes(header.props.actions).find(n => n.type === "Button" && n.props.children === "Delete permit").props.onClick();
  assert.equal(calls.length, 0);
  nodes(render()).find(n => n.type === "ConfirmDialog").props.onConfirm();
  await settle();
  assert.equal(calls.length, 1);
  assert.equal(removed, 0);
  assert.equal(nodes(render()).find(n => n.type === "ConfirmDialog").props.body, "Clear dependent first");
});

test("Permit creation is a full-page single save, retaining all fields after failure", async () => {
  const calls = []; let fail = true; let completed = 0;
  class ApiError extends Error {}
  const render = mount("projects/PermitCreatePage", "PermitCreatePage", {
    "@/lib/api": { ApiError, projects: {
      permitAssignees: async () => [],
      createPermit: async (...args) => { calls.push(args); if (fail) throw new ApiError("Save refused"); return { id: "permit" }; },
    } },
    "@/lib/format": { todayISO: () => "2026-09-12" },
  }, { projectId: "project", types: [], parcels: [], permits: [], statuses: { issued: "Issued" }, canSeeCost: true,
    currencyCode: "EUR", onCancel() {}, onCreated: async () => { completed++; } });
  render(); await settle();
  const change = (label, value) => nodes(render()).find(n => n.type === "Field" && n.props.label === label).props.children.props.onChange({ target: { value } });
  nodes(render()).find(n => n.type === "input" && n.props.type === "checkbox").props.onChange({ target: { checked: true } });
  for (const [label, value] of [["Permit code", "TEST"], ["Authority", "Council"], ["New type code", "new"], ["New type name", "New consent"], ["Current status", "issued"], ["Fee", "1234.56"], ["Conditions", "Keep this condition"], ["Issued", "2026-09-10"]]) change(label, value);
  assert.ok(nodes(render()).some(n => n.type === "article"));
  assert.ok(!nodes(render()).some(n => ["RecordPage", "FormDialog"].includes(n.type)));
  await nodes(render()).find(n => n.type === "form").props.onSubmit({ preventDefault() {} });
  assert.equal(calls.length, 1);
  assert.equal(calls[0][1].new_permit_type.label, "New consent");
  assert.equal(calls[0][1].fee_amount, "1234.56");
  assert.equal(calls[0][1].initial_status, "issued");
  assert.equal(calls[0][1].issue_date, "2026-09-10");
  assert.equal(nodes(render()).find(n => n.type === "Field" && n.props.label === "Conditions").props.children.props.value, "Keep this condition");
  assert.equal(completed, 0);
  fail = false;
  await nodes(render()).find(n => n.type === "form").props.onSubmit({ preventDefault() {} });
  assert.equal(completed, 1);
});

const landFormat = {};
runInNewContext(ts.transpileModule(readFileSync(new URL("../src/lib/format.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, { exports: landFormat });

function landFixture(canWrite = true) {
  let rejectWrite = true;
  const calls = [];
  const analytics = {
    land_area_sqm: "100", max_buildable_area_sqm: "200", purchase_cost_per_sqm: "1000.00",
    purchase_cost_per_buildable_sqm: "500.00", acquisition_cost_per_sqm: "1100.00",
    acquisition_cost_per_buildable_sqm: "550.00", purchase_cost_to_gdv_fraction: null,
    acquisition_cost_to_gdv_fraction: null, market_years: [],
  };
  const props = { projectId: "project", parcel: { id: "parcel", expected_gdv_amount: null, base_currency_code: "EUR", purchase_price: "100000.00", total_acquisition_cost: "110000.00" }, canWrite,
    onChanged: async () => { props.parcel = { ...props.parcel, expected_gdv_amount: "200000.00" }; } };
  class ApiError extends Error {}
  const projects = {
    landAnalytics: async () => analytics,
    writeLandMarketYear: async (...args) => { calls.push(args); if (rejectWrite) throw new ApiError("Write refused"); return analytics; },
    updateParcel: async (...args) => { calls.push(args); return { ...props.parcel, expected_gdv_amount: "200000.00" }; },
  };
  const render = mount("projects/land/LandAnalytics", "LandAnalytics", {
    "@/lib/api": { ApiError, projects }, "@/lib/format": landFormat,
  }, props);
  return { render, calls, recover() { rejectWrite = false; } };
}

test("Land analytics preserves a failed annual draft and sends the exact signed percentage", async () => {
  const f = landFixture(); f.render(); await settle();
  let tree = nodes(f.render());
  tree.find(n => n.type === "Field" && n.props.label === "Year").props.children.props.onChange({ target: { value: "2027" } });
  tree.find(n => n.type === "Field" && n.props.label === "Expected increase / decrease (%)").props.children.props.onChange({ target: { value: "-5.25" } });
  await nodes(f.render()).filter(n => n.type === "form")[1].props.onSubmit({ preventDefault() {} });
  tree = nodes(f.render());
  assert.equal(f.calls[0][3], "-0.0525");
  assert.equal(tree.find(n => n.type === "Field" && n.props.label === "Year").props.children.props.value, "2027");
  assert.ok(JSON.stringify(tree).includes("Write refused"));
  f.recover();
  await tree.filter(n => n.type === "form")[1].props.onSubmit({ preventDefault() {} });
  assert.equal(nodes(f.render()).find(n => n.type === "Field" && n.props.label === "Year").props.children.props.value, "");
});

test("Land analytics canonicalizes saved GDV so a successful save leaves no false dirty draft", async () => {
  const f = landFixture(); f.render(); await settle();
  nodes(f.render()).find(n => n.type === "Field" && n.props.label === "Expected GDV for this parcel").props.children.props.onChange({ target: { value: "200000" } });
  await nodes(f.render()).find(n => n.type === "form").props.onSubmit({ preventDefault() {} });
  assert.equal(f.calls[0][2].expected_gdv_amount, "200000");
  assert.equal(f.render().props.dirty, false);
});

test("Land analytics read-only permission exposes metrics but no write controls", async () => {
  const f = landFixture(false); f.render(); await settle();
  const tree = nodes(f.render());
  assert.ok(tree.some(n => n.type === "KeyValue" && n.props.value === "EUR 1,000.00"));
  assert.ok(!tree.some(n => n.type === "form"));
  assert.equal(f.calls.length, 0);
});

// Execute the real reader callbacks and render branches with a small hook
// lifecycle. No requests are made and no component implementation is copied.
function mount(file, name, dependencies, props) {
  const slots = []; let cursor = 0; let effects = [];
  const same = (a, b) => a?.length === b.length && b.every((v, i) => Object.is(v, a[i]));
  const react = {
    useRef(initial) { const i = cursor++; slots[i] ??= { current: initial }; return slots[i]; },
    useState(initial) { const i = cursor++; slots[i] ??= { value: typeof initial === "function" ? initial() : initial }; return [slots[i].value, v => { slots[i].value = typeof v === "function" ? v(slots[i].value) : v; }]; },
    useMemo(fn, deps) { const i = cursor++; if (!same(slots[i]?.deps, deps)) slots[i] = { deps, value: fn() }; return slots[i].value; },
    useCallback(fn, deps) { return react.useMemo(() => fn, deps); },
    useEffect(fn, deps) { const i = cursor++; if (!same(slots[i]?.deps, deps)) effects.push(() => { slots[i]?.cleanup?.(); slots[i] = { deps, cleanup: fn() }; }); },
  };
  const exports = {};
  const source = readFileSync(new URL(`../src/components/${file}.tsx`, import.meta.url), "utf8") + `\nexport { ${name} as TestedComponent };`;
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const ui = new Proxy({}, { get: (_, key) => key });
  runInNewContext(`(function(require, exports) { ${code}\n})`)(key => {
    if (key === "react") return react;
    if (key in dependencies) return dependencies[key];
    if (key === "@/lib/api") return { ApiError: class extends Error { fieldErrors = []; } };
    if (key === "@/components/ui") return ui;
    if (key === "@/components/shell/navigation") return { sectionDescription: () => "", projectHref: () => "/projects/" };
    if (key === "@/lib/roles") return { hasAnyRole: () => false };
    if (key.startsWith("@/") || key.startsWith("./")) return {};
    return require(key);
  }, exports);
  return () => { cursor = 0; effects = []; const tree = exports.TestedComponent(props); effects.forEach(fn => fn()); return tree; };
}
function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children)];
}

test("active consultant agreement edits the same record and keeps a refused save open", async () => {
  const row = { id: "agreement", consultant_name: "Original", agreement_reference: "CE-1", status: "active", updated_at: "version-1" };
  const calls = []; let fail = true;
  class ApiError extends Error {}
  const render = mount("projects/ConsultantEngineerTab", "ConsultantEngineerTab", {
    "@/lib/api": { ApiError, consultantEngineering: {
      workspace: async () => ({ active_engagement: row, engagements: [row], disciplines: [], stages: [], deliverables: [] }),
      updateEngagement: async (...args) => { calls.push(args); if (fail) throw new ApiError("Agreement changed. Reload before saving."); },
    } },
    "@/lib/roles": { hasAnyRole: () => true },
    "@/lib/format": { businessDate: value => value ?? "—" },
  }, { projectId: "project", roles: new Set(["master_admin"]) });
  render(); await settle();
  nodes(render()).find(n => n.type === "Button" && n.props.children === "Edit agreement").props.onClick();
  let dialog = nodes(render()).find(n => n.props?.editor);
  assert.equal(dialog.props.editor.row.id, "agreement");
  await dialog.props.onSubmit({ consultant_name: "Corrected", agreement_reference: "CE-2" }); await settle();
  assert.equal(calls[0][0], "project"); assert.equal(calls[0][1], "agreement");
  assert.equal(calls[0][2].expected_updated_at, "version-1");
  dialog = nodes(render()).find(n => n.props?.editor);
  assert.ok(dialog.props.error.includes("Reload"));
  fail = false; await dialog.props.onSubmit({ consultant_name: "Corrected", agreement_reference: "CE-2" }); await settle();
  assert.ok(!nodes(render()).some(n => n.props?.editor));
});

test("Pre-Launch renders server category amounts above the register and honors confirmation eligibility", async () => {
  const calls = [];
  const row = { id: "expense", category: "design", amount: "1.01", movement_date: "2026-09-12", status: "recorded", can_confirm: true };
  const render = mount("projects/PreLaunchTab", "PreLaunchTab", {
    "@/lib/api": { ApiError: Error, prelaunch: {
      register: async () => ({ expenses: [row], recorded_amount: "1.01", confirmed_paid_amount: "2.02", categories: [{ category: "design", recorded_amount: "1.01", confirmed_paid_amount: "2.02", total_amount: "3.03", confirmed_share_percent: "100.00" }] }),
      confirm: async (...args) => { calls.push(args); row.can_confirm = false; row.status = "confirmed"; },
    } },
    "@/lib/roles": { hasAnyRole: () => true }, "@/lib/format": landFormat,
  }, { projectId: "project", roles: new Set(["master_admin"]), currencyCode: "USD" });
  render(); await settle();
  const tree = nodes(render());
  assert.ok(tree.findIndex(n => n.type === "TableScroll" && n.props.label === "Expenses by category") < tree.findIndex(n => n.type === "TableScroll" && n.props.label === "Pre-Launch expense register"));
  assert.ok(tree.some(n => n.type === "td" && n.props.children === landFormat.money("3.03", "USD")));
  const confirm = tree.find(n => n.type === "Button" && n.props.children === "Confirm");
  assert.equal(confirm.props.disabled, false);
  await confirm.props.onClick(); await settle();
  assert.equal(calls[0][1], "expense"); assert.equal(calls[0][2].amount, "1.01");
  assert.ok(!nodes(render()).some(n => n.type === "Button" && n.props.children === "Confirm"));
});
function apiFixture() {
  let failed = true; const calls = [];
  class ApiError extends Error {}
  const api = new Proxy({}, { get: (_, name) => async () => { calls.push(name); if (failed) throw new ApiError("Temporary read failure"); return []; } });
  return { ApiError, api, calls, recover() { failed = false; } };
}

test("Pre-Launch keeps a failed removal open, refreshes eligibility and blocks duplicate submits", async () => {
  const row = { id: "expense", category: "utilities", amount: "1250.25", movement_date: "2026-01-01",
    notes: "Water fee", counterparty_reference: null, invoice_reference: null, evidence_reference: null,
    status: "recorded", can_edit: true, can_remove: true, currency_code: "USD" };
  const calls = []; let reject; let reads = 0;
  class ApiError extends Error { constructor(status, message) { super(message); this.status = status; } }
  const prelaunch = {
    register: async () => { reads++; return { expenses: [row], categories: [], recorded_amount: "1250.25", confirmed_paid_amount: "0" }; },
    remove: (...args) => { calls.push(args); return new Promise((_, no) => { reject = no; }); },
  };
  const render = mount("projects/PreLaunchTab", "PreLaunchTab", {
    "@/lib/api": { ApiError, prelaunch }, "@/lib/format": landFormat,
  }, { projectId: "project", currencyId: "currency", currencyCode: "USD", roles: [] });
  render(); await settle();
  nodes(render()).find(n => n.type === "Button" && n.props.children === "Remove").props.onClick();
  const dialog = nodes(render()).find(n => n.type === "PromptDialog");
  dialog.props.onSubmit("Duplicate"); dialog.props.onSubmit("Duplicate");
  assert.equal(calls.length, 1);
  assert.equal(calls[0][2].expected.amount, "1250.25");
  reject(new ApiError(409, "Expense changed")); await settle();
  const failed = nodes(render()).find(n => n.type === "PromptDialog");
  assert.equal(failed.props.error, "Expense changed");
  assert.equal(failed.props.busy, false);
  assert.equal(reads, 2);
});

test("Pre-Launch editor sends only editable fields and retains corrected values after an error", () => {
  const initial = { id: "expense", category: "utilities", amount: "1250.25", movement_date: "2026-01-01",
    notes: "Water fee", counterparty_reference: "Authority", invoice_reference: "INV", evidence_reference: "proof" };
  let submitted;
  const props = { initial, currencyId: "currency", currencyCode: "USD", busy: false, error: null,
    onCancel() {}, onSubmit(body) { submitted = body; } };
  const render = mount("projects/PreLaunchTab", "ExpenseDialog", {}, props);
  nodes(render()).find(n => n.type === "MoneyInput").props.onChange("99.99");
  nodes(render()).find(n => n.type === "FormDialog").props.onSubmit();
  assert.equal(submitted.amount, "99.99");
  assert.equal(submitted.invoice_reference, "INV");
  assert.ok(!("currency_id" in submitted));
  props.error = "Validation refused";
  assert.equal(nodes(render()).find(n => n.type === "MoneyInput").props.value, "99.99");
  assert.ok(nodes(render()).some(n => n.type === "Notice" && n.props.children === "Validation refused"));
});
for (const component of ["ContractsSection", "VariationsSection", "CertificatesSection", "CashSection", "MilestonesSection", "ForecastSection"]) {
  test(`${component}: failed read retries GETs and accepts a recovered empty response`, async () => {
    const f = apiFixture();
    const render = mount("projects/ConstructionTab", component, { "@/lib/api": { ApiError: f.ApiError, construction: f.api }, "@/components/shell/registerState": { useRegisterFields: () => [{ contractSearch: "", contractStatus: "", constructionContract: "" }, () => {}] } }, { projectId: "synthetic" });
    render(); await settle();
    const failed = nodes(render());
    assert.ok(failed.some(node => node.type === "Notice" && node.props.children === "Temporary read failure"));
    assert.ok(!failed.some(node => node.type === "EmptyState"));
    const retry = failed.find(node => node.type === "Button" && node.props.children === "Retry");
    assert.ok(retry);
    f.recover(); const before = f.calls.length; await retry.props.onClick(); await settle();
    const ready = nodes(render());
    assert.ok(f.calls.length > before);
    assert.ok(!ready.some(node => node.type === "Notice"));
    assert.ok(!ready.some(node => node.type === "Loading"));
    assert.ok(!ready.some(node => node.type === "Button" && node.props.children === "Retry"));
    assert.ok(f.calls.every(name => ["budgets", "contracts", "variations", "certificates", "invoices", "payments", "milestones", "forecasts"].includes(name)));
  });
}

for (const [component, dependency, readyData, label] of [
  ["DocumentsTab", "projects", [], "Retry documents"],
  ["PreLaunchTab", "prelaunch", { expenses: [], categories: [], recorded_amount: "0", confirmed_paid_amount: "0" }, "Retry Pre-Launch expenses"],
  ["ConsultantEngineerTab", "consultantEngineering", { engagements: [], disciplines: [], stages: [], deliverables: [] }, "Retry Consultant Engineer"],
]) {
  test(`${component}: retry clears the read error without calling a write`, async () => {
    let failed = true; const calls = [];
    class ApiError extends Error {}
    const api = new Proxy({}, { get: (_, method) => async () => {
      calls.push(method);
      if (failed) throw new ApiError("Temporary read failure");
      return readyData;
    } });
    const render = mount(`projects/${component}`, component, {
      "@/lib/api": { ApiError, [dependency]: api, settings: { referenceValues: async () => [] } },
      "@/lib/format": { money: () => "JOD 0.00" },
    }, { projectId: "synthetic", roles: new Set(), canWrite: false, currencyId: "synthetic", currencyCode: "JOD" });
    render(); await settle();
    const errorTree = nodes(render());
    const retry = errorTree.find(node => node.type === "Button" && node.props.children === label);
    assert.ok(retry);
    failed = false; const before = calls.length; await retry.props.onClick(); await settle();
    const recovered = nodes(render());
    assert.ok(calls.length > before);
    assert.ok(!recovered.some(node => node.type === "Notice" && node.props.children === "Temporary read failure"));
    assert.ok(calls.every(method => ["documents", "parcels", "permits", "register", "workspace"].includes(method)));
  });
}

test("Payment Plans retries its register without submitting a new plan", async () => {
  let failed = true; let reads = 0;
  class ApiError extends Error {}
  const render = mount("projects/PaymentPlansTab", "PaymentPlansTab", {
    "@/lib/api": { ApiError, paymentPlans: { register: async () => { reads++; if (failed) throw new ApiError("Temporary read failure"); return { rows: [] }; } } },
    "@/lib/currency": { useCurrencyCode: () => () => "JOD" },
    "@/lib/format": { todayISO: () => "2026-09-11" },
    "@/components/projects/payments/labels": { versionLabel: value => value },
    "next/navigation": { useRouter: () => ({}) },
    "@/components/ui": new Proxy({ useRecordHref: () => () => "" }, { get: (target, key) => target[key] ?? key }),
    "@/components/shell/registerState": { useRegisterRestore() {}, useRegisterFields: () => [{ search: "", status: "" }, () => {}] },
    "@/components/shell/navigation": { sectionDescription: () => "", projectHref: () => "/projects/" },
  }, { projectId: "synthetic", projectStatus: "active", roles: new Set() });
  render(); await settle();
  const retry = nodes(render()).find(node => node.type === "Button" && node.props.children === "Retry payment plans");
  assert.ok(retry); failed = false; await retry.props.onClick(); await settle();
  assert.equal(reads, 2);
  assert.ok(!nodes(render()).some(node => node.type === "Notice"));
});

test("Portfolio offers the existing retry on failure, never on denied access", () => {
  let calls = 0;
  const retry = () => calls++;
  const render = mount("portfolio/Portfolio", "Pending", {}, { answer: { status: "failed", message: "Temporary read failure", retry } });
  const button = nodes(render()).find(node => node.type === "Button");
  button.props.onClick(); assert.equal(calls, 1);
  const denied = mount("portfolio/Portfolio", "Pending", {}, { answer: { status: "denied", retry } });
  assert.ok(!nodes(denied()).some(node => node.type === "Button"));
});


test("Budget workspace retains failed-read recovery after adding the version register", () => {
  let failed = true; let retries = 0;
  const render = mount("projects/construction/BudgetWorkspace", "BudgetWorkspace", {
    "@/lib/answer": { useAnswer: () => failed ? { status: "failed", message: "Temporary read failure", retry() { retries++; failed = false; } } : { status: "ready", data: [], retry() {} } },
    "@/components/shell/registerState": { useRegisterFields: () => [{ budgetVersion: "" }, () => {}] },
    "@/components/shell/navigation": { projectHref: () => "/projects/" },
  }, { projectId: "synthetic", roles: new Set(), onChanged: async () => {} });
  const button = nodes(render()).find(node => node.type === "Button" && node.props.children === "Retry budget versions");
  assert.ok(button); button.props.onClick(); assert.equal(retries, 1);
  const recovered = nodes(render());
  assert.ok(recovered.some(node => node.type === "EmptyState" && node.props.title === "No budget versions"));
  assert.ok(!recovered.some(node => node.type === "Notice" && node.props.children === "Temporary read failure"));
});

test("Budget line editor submits exact decimal strings and never rewrites a copied baseline", () => {
  let payload;
  const render = mount("projects/construction/BudgetWorkspace", "BudgetEditor", {
    "@/lib/format": { todayISO: () => "2026-09-11" },
  }, { editor: { kind: "line", code: { id: "code", code: "HARD", name: "Works" }, line: { approved_budget_amount: "1.00", contingency_amount: "0.00", baseline_amount: "900.00" } }, detail: { source_version_id: "source", currency_code: "JOD" }, versions: [], busy: false, failure: null, onSubmit: body => { payload = body; }, onCancel() {} });
  const amount = nodes(render()).find(node => node.type === "Field" && node.props.label === "Budget authorization");
  amount.props.children.props.onChange("123456789.12");
  render().props.onSubmit();
  assert.equal(payload.approved_budget_amount, "123456789.12");
  assert.equal(payload.contingency_amount, "0.00");
  assert.ok(!("baseline_amount" in payload));
});

test("Budget rejection keeps the typed reason when the server refuses the write", () => {
  let payload;
  const props = { editor: { kind: "reject" }, detail: { status: "approved" }, versions: [], busy: false, failure: null, onSubmit: body => { payload = body; }, onCancel() {} };
  const render = mount("projects/construction/BudgetWorkspace", "BudgetEditor", { "@/lib/format": { todayISO: () => "2026-09-11" } }, props);
  const reason = nodes(render()).find(node => node.type === "Field" && node.props.label === "Rejection reason");
  reason.props.children.props.onChange({ target: { value: "Recheck commitment coverage" } });
  render().props.onSubmit();
  assert.equal(payload.reason, "Recheck commitment coverage");
  props.failure = new Error("Conflict: version changed");
  const failed = render();
  assert.equal(failed.props.title, "Return budget for correction");
  assert.equal(nodes(failed).find(node => node.type === "Field" && node.props.label === "Rejection reason").props.children.props.value, "Recheck commitment coverage");
  assert.ok(nodes(failed).some(node => node.type === "Notice" && node.props.children === props.failure.message));
});

test("Budget workspace offers correction when activation is blocked, without opening a second candidate", () => {
  let count = 0;
  const detail = { id: "candidate", version_number: 2, status: "approved", lines: [], workflow: { editing_blocker: "Frozen", activation_blocker: "Existing commitments exceed authorization", rejection_blocker: null } };
  const render = mount("projects/construction/BudgetWorkspace", "BudgetWorkspace", {
    "@/lib/answer": { useAnswer: () => ({ status: "ready", data: [[{ id: "candidate", status: "approved", version_number: 2 }], [], detail][count++ % 3], retry() {} }) },
    "@/components/shell/registerState": { useRegisterFields: () => [{ budgetVersion: "candidate" }, () => {}] },
    "@/components/shell/navigation": { projectHref: () => "/projects/" },
    "@/lib/roles": { hasAnyRole: () => true },
    "@/lib/format": { businessDate: () => "Date" },
  }, { projectId: "synthetic", roles: new Set(["approver_cfo"]), onChanged: async () => {} });
  const tree = nodes(render());
  assert.equal(tree.find(node => node.type === "Button" && node.props.children === "Activate budget").props.disabled, true);
  assert.equal(tree.find(node => node.type === "Button" && node.props.children === "Return for correction").props.disabled, false);
  assert.ok(!tree.some(node => node.type === "Button" && node.props.children === "Create budget revision"));
});


test("Budget revision waits for its selected source instead of silently copying the active version", () => {
  let count = 0;
  const render = mount("projects/construction/BudgetWorkspace", "BudgetWorkspace", {
    "@/lib/answer": { useAnswer: () => [
      { status: "ready", data: [{ id: "active", status: "active", version_number: 1 }] },
      { status: "ready", data: [] },
      { status: "failed", message: "Selected version unavailable", retry() {} },
    ][count++ % 3] },
    "@/components/shell/registerState": { useRegisterFields: () => [{ budgetVersion: "rejected-source" }, () => {}] },
    "@/components/shell/navigation": { projectHref: () => "/projects/" },
    "@/lib/roles": { hasAnyRole: () => true },
  }, { projectId: "synthetic", roles: new Set(["finance"]), onChanged: async () => {} });
  const tree = nodes(render());
  assert.equal(tree.find(node => node.type === "Button" && node.props.children === "Create budget revision").props.disabled, true);
  assert.ok(tree.some(node => node.type === "Button" && node.props.children === "Retry selected budget"));
});

const contractFormat = {};
runInNewContext(ts.transpileModule(readFileSync(new URL('../src/lib/format.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, { exports: contractFormat });

test("Contract draft preserves exact amounts, percentage conversion and unstated tax", () => {
  let payload;
  const render = mount("projects/construction/ContractWorkflow", "ContractHeaderEditor", { "@/lib/format": contractFormat }, { currencyId: "jod", currencyCode: "JOD", busy: false, failure: null, onSubmit: body => { payload = body; }, onCancel() {} });
  const set = (label, value, custom = false) => {
    const field = nodes(render()).find(node => node.type === "Field" && node.props.label === label);
    field.props.children.props.onChange(custom ? value : { target: { value } });
  };
  set("Contract reference", "CT-EXACT"); set("Vendor name", "Vendor");
  set("Contract value excluding tax", "123456789.12", true); set("Retention percentage", "5.5", true);
  render().props.onSubmit();
  assert.equal(payload.original_contract_value_ex_tax, "123456789.12");
  assert.equal(payload.retention_rate_fraction, "0.055");
  assert.equal(payload.tax_rate_fraction, null);
  assert.equal(payload.currency_id, "jod");
  set("Tax percentage", "0", true); render().props.onSubmit();
  assert.equal(payload.tax_rate_fraction, "0");
});

test("Contract line edits retain sequence and send explicit zero without deleting history", () => {
  let payload;
  const render = mount("projects/construction/ContractWorkflow", "ContractLineEditor", {}, { detail: { currency_code: "JOD", lines: [] }, line: { sequence: 7, cost_code_id: "code", description: "Retained line", original_amount_ex_tax: "50.00" }, codes: [{ id: "code", is_active: true }], failure: null, busy: false, onSubmit: body => { payload = body; }, onCancel() {} });
  const field = nodes(render()).find(node => node.type === "Field" && node.props.label === "Line value excluding tax");
  field.props.children.props.onChange("0.00"); render().props.onSubmit();
  assert.equal(payload.sequence, 7); assert.equal(payload.original_amount_ex_tax, "0.00");
});

test("Contract cancellation keeps the reason after a failed request and remains cancelable on failed refresh", () => {
  const props = { action: "cancel", busy: false, failure: null, onSubmit() {}, onCancel() {} };
  const render = mount("projects/construction/ContractWorkflow", "ContractDecision", {}, props);
  nodes(render()).find(node => node.type === "Field").props.children.props.onChange({ target: { value: "Wrong scope; prepare replacement" } });
  props.failure = new Error("Conflict"); props.unavailable = true;
  const tree = render();
  assert.equal(tree.props.disabled, true); assert.equal(tree.props.busy, false);
  assert.equal(nodes(tree).find(node => node.type === "Field").props.children.props.value, "Wrong scope; prepare replacement");
});

test("Contract workspace renders server activation blockers and offers no draft edits after submission", () => {
  const render = mount("projects/construction/ContractWorkflow", "ContractWorkflow", { "@/lib/format": contractFormat }, { projectId: "project", detail: { status: "submitted", original_contract_value_ex_tax: "100.00", line_total: "100.00", currency_code: "JOD", lines: [], workflow: { editing_blocker: "Frozen", activation_blocker: "Budget has no room", cancellation_blocker: null } }, codes: [], codesReady: true, reading: false, unavailable: false, onChanged: async () => {}, onRefresh: async () => {} });
  const tree = nodes(render());
  assert.equal(tree.find(node => node.type === "Button" && node.props.children === "Authorize and activate").props.disabled, true);
  assert.ok(!tree.some(node => node.type === "Button" && node.props.children === "Edit draft terms"));
  assert.ok(tree.some(node => node.props.children === "Budget has no room"));
});

test("Contract confirmation disables itself when refreshed eligibility changes", () => {
  const props = { projectId: "project", detail: { status: "submitted", original_contract_value_ex_tax: "100.00", line_total: "100.00", currency_code: "JOD", lines: [], workflow: { editing_blocker: "Frozen", activation_blocker: null, cancellation_blocker: null } }, codes: [], codesReady: true, reading: false, unavailable: false, onChanged: async () => {}, onRefresh: async () => {} };
  const render = mount("projects/construction/ContractWorkflow", "ContractWorkflow", { "@/lib/format": contractFormat }, props);
  nodes(render()).find(node => node.type === "Button" && node.props.children === "Authorize and activate").props.onClick();
  props.detail.workflow.activation_blocker = "Already activated by another operator";
  const dialog = nodes(render()).find(node => typeof node.type === "function" && node.type.name === "ContractDecision");
  assert.equal(dialog.props.unavailable, true);
  assert.equal(dialog.props.failure.message, "Already activated by another operator");
});
