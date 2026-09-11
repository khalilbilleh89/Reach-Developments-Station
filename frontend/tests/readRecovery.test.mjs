import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { createRequire } from "node:module";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);
const settle = () => new Promise(resolve => setImmediate(resolve));

// Execute the real reader callbacks and render branches with a small hook
// lifecycle. No requests are made and no component implementation is copied.
function mount(file, name, dependencies, props) {
  const slots = []; let cursor = 0; let effects = [];
  const same = (a, b) => a?.length === b.length && b.every((v, i) => Object.is(v, a[i]));
  const react = {
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
function apiFixture() {
  let failed = true; const calls = [];
  class ApiError extends Error {}
  const api = new Proxy({}, { get: (_, name) => async () => { calls.push(name); if (failed) throw new ApiError("Temporary read failure"); return []; } });
  return { ApiError, api, calls, recover() { failed = false; } };
}
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
  ["PreLaunchTab", "prelaunch", { expenses: [], recorded_amount: "0", confirmed_paid_amount: "0" }, "Retry Pre-Launch expenses"],
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
