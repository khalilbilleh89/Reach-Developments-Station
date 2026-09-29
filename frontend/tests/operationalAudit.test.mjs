// Regressions found by the platform operational audit (docs/SYSTEM_OPERATIONAL_AUDIT.md).
// Each test mounts the real component and drives its handlers, so it fails on the
// behaviour the operator saw, not on a source string.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const settle = () => new Promise(resolve => setImmediate(resolve));
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

export function mount(path, component, dependencies, props) {
  const slots = []; let cursor = 0; let effects = [];
  const react = {
    useState(initial) {const i = cursor++; if (!slots[i]) { slots[i] = {value: typeof initial === "function" ? initial() : initial}; slots[i].set = v => {slots[i].value = typeof v === "function" ? v(slots[i].value) : v;}; } return [slots[i].value, slots[i].set];},
    useId() { return react.useState(() => `test-${cursor}`)[0]; },
    useRef(initial) {const [slot] = react.useState({current:initial}); return slot;},
    useMemo(fn) {return fn();},
    useCallback(fn) {return fn;},
    useEffect(fn, deps) {const i = cursor++; if (!slots[i] || !deps || deps.some((v,n) => v !== slots[i].deps[n])) effects.push(() => {slots[i]?.cleanup?.(); slots[i]={deps: deps ?? [],cleanup:fn()};});},
  };
  const exports = {};
  const source = readFileSync(new URL(`../src/${path}`, import.meta.url),"utf8");
  const code = ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  const ui = new Proxy({}, {get:(_,key) => key});
  runInNewContext(`(function(require,exports){${code}\n})`,{crypto:{randomUUID:()=>"request-key"}, setTimeout, clearTimeout})(key => {
    if (key === "react") return react;
    if (key === "react/jsx-runtime") return {jsx:(type,props)=>({type,props}),jsxs:(type,props)=>({type,props}),Fragment:"Fragment"};
    if (key in dependencies) return dependencies[key];
    if (key.startsWith("@/components/ui")) return ui;
    return new Proxy({}, {get:(_,name)=>name});
  },exports);
  return {exports, render(){cursor=0;effects=[];const tree=exports[component](props);effects.forEach(fn=>fn());return tree;}};
}
export function nodes(tree) {if (!tree || typeof tree !== "object") return [];if (Array.isArray(tree)) return tree.flatMap(nodes);return [tree,...nodes(tree.props?.actions),...nodes(tree.props?.children)];}
export function text(tree) {return nodes(tree).flatMap(node => [node, ...(Array.isArray(node.props?.children) ? node.props.children : [node.props?.children])]).filter(v => typeof v === "string" || typeof v === "number").join(" ");}
class ApiError extends Error {constructor(message,status=422){super(message);this.status=status;this.fieldErrors=[];}}

test("Sales gates are saved with the six gates only, never the read-only project id", async () => {
  const written = [];
  const policy = {project_id: "7f1c2d4e-0000-4000-8000-000000000001", handover_requires_collection_clearance: true, handover_requires_legal_clearance: true, handover_requires_delivery_clearance: false, handover_requires_title_transfer: false, title_transfer_requires_collection_clearance: true, reservation_requires_deposit_confirmation: false};
  const view = mount("components/projects/sales/SalesGates.tsx", "SalesGates", {"@/lib/api": {ApiError, sales: {policy: async () => policy, writePolicy: async (_, body) => {written.push(body); return {...policy, ...body};}}}}, {projectId: "project", onClose() {}});
  view.render(); await settle();
  const box = nodes(view.render()).find(node => node.type === "input" && node.props.type === "checkbox" && node.props.checked === false);
  box.props.onChange({target: {checked: true}});
  const form = nodes(view.render()).find(node => node.type === "form");
  await form.props.onSubmit({preventDefault() {}});
  assert.equal(written.length, 1);
  assert.deepEqual(Object.keys(written[0]).sort(), Object.keys(policy).filter(key => key !== "project_id").sort());
  assert.equal(Object.values(written[0]).filter(Boolean).length, 4);
  assert.equal(nodes(view.render()).some(node => node.type === "Notice"), false);
});

function refundsTab(overrides = {}) {
  const calls = [];
  const cancellation = {id: "c0ffee00-0000-4000-8000-000000000002", status: "completed", unit_return_date: "2026-09-25", financial_approval_required: true, financial_approved_at: "2026-09-20T10:00:00Z"};
  const summary = {refund_due_total: "40000.00", refund_confirmed_total: "0.00", refund_outstanding: "40000.00"};
  const api = {ApiError,
    collections: {refunds: async () => [], recordRefund: async (_, __, body) => {calls.push(body); return {id: "r"};}},
    sales: {contract: async () => ({cancellation: overrides.cancellation === undefined ? cancellation : overrides.cancellation})}};
  const props = {projectId: "p", saleId: "s", summary: {...summary, ...(overrides.summary ?? {})}, currencyCode: "JOD", canCollect: overrides.canCollect ?? true, canConfirm: false, busy: false, error: null,
    onAct: async (run) => {await run(); return true;}};
  const view = mount("components/projects/collections/CollectionAccount.tsx", "RefundsTab", {"@/lib/api": api, "@/lib/format": {businessDate: v => v, isPositive: v => Number(v) > 0, money: (v, c) => `${c} ${v}`, todayISO: () => "2026-09-29", percent: v => v}}, props);
  return {view, calls, cancellation};
}

test("an approved refund can be recorded from Collections once the cancellation is complete and the unit returned", async () => {
  const {view, calls, cancellation} = refundsTab();
  view.render(); await settle(); await settle();
  const types = nodes(view.render()).map(node => node.type);
  assert.ok(types.includes("SubPanel"), types.join(","));
  const open = nodes(view.render()).find(node => node.type === "Button" && node.props.children === "Record a repayment");
  assert.ok(open, "the refund recording action is offered");
  open.props.onClick();
  const tree = view.render();
  nodes(tree).find(node => node.type === "MoneyInput").props.onChange("15000.00");
  const bank = nodes(view.render()).find(node => node.type === "input" && node.props.maxLength === 200);
  bank.props.onChange({target: {value: "TRF-991"}});
  const form = nodes(view.render()).find(node => node.type === "Form");
  assert.equal(nodes(view.render()).find(node => node.type === "input" && node.props.type === "date").props.min, "2026-09-25");
  form.props.onSubmit({preventDefault() {}}); await settle(); await settle();
  assert.deepEqual(JSON.parse(JSON.stringify(calls)), [{cancellation_id: cancellation.id, amount: "15000.00", refund_date: "2026-09-29", bank_reference: "TRF-991", notes: null}]);
  assert.equal(nodes(view.render()).some(node => node.type === "Form"), false);
});

test("approved terms on a cancellation still in progress explain that repayment waits for completion (B-01)", async () => {
  const approved = {id: "c", financial_approval_required: true, financial_approved_at: "2026-09-20T10:00:00Z"};
  for (const cancellation of [
    {...approved, status: "approved", unit_return_date: null},
    {...approved, status: "termination_pending_approval", unit_return_date: null},
    {...approved, status: "ready_for_unit_return", unit_return_date: null},
    {...approved, status: "completed", unit_return_date: null},
  ]) {
    const {view} = refundsTab({cancellation});
    view.render(); await settle();
    const tree = view.render();
    assert.equal(nodes(tree).some(node => node.type === "Button" && node.props.children === "Record a repayment"), false, cancellation.status);
    assert.equal(nodes(tree).some(node => node.type === "SubPanel"), false, cancellation.status);
    assert.match(text(tree), /Refund terms are approved\. Repayment can be recorded after the cancellation is completed\s+and the unit has been returned\./, cancellation.status);
  }
  const {view} = refundsTab({canCollect: false, cancellation: {...approved, status: "approved", unit_return_date: null}});
  view.render(); await settle();
  assert.doesNotMatch(text(view.render()), /Refund terms are approved/, "a reader is not told about an action they cannot take");
});

test("no repayment form is offered before approval, after withdrawal or to a reader", async () => {
  for (const overrides of [
    {cancellation: {id: "c", status: "pending_financial_approval", financial_approval_required: true, financial_approved_at: null}},
    {cancellation: {id: "c", status: "withdrawn", financial_approval_required: true, financial_approved_at: "2026-09-20T10:00:00Z"}},
    {summary: {refund_outstanding: "0.00", refund_confirmed_total: "40000.00"}},
    {canCollect: false},
  ]) {
    const {view} = refundsTab(overrides);
    view.render(); await settle();
    assert.equal(nodes(view.render()).some(node => node.type === "Button" && node.props.children === "Record a repayment"), false, JSON.stringify(overrides));
  }
});

const formatStub = {businessDate: v => v, isPositive: v => Number(v) > 0, money: (v, c) => `${c} ${v}`, todayISO: () => "2026-09-29", eventTime: v => v};

test("applying cash: a failed suggestion read is an error with retry, and a refused allocation keeps the entry", async () => {
  const receipt = {id: "rcpt", receipt_number: "RC-0001", status: "confirmed", amount: "10000.00", allocated_amount: "5000.00", unapplied_amount: "5000.00", receipt_date: "2026-01-15", allocations: []};
  let suggestionCalls = 0;
  const api = {ApiError, collections: {
    receipts: async () => [receipt],
    suggestions: async () => {suggestionCalls += 1; throw new ApiError("Unavailable", 500);},
    allocate: async () => {throw new ApiError("That instalment is already paid.", 409);},
  }};
  const summary = {installments: [{installment_id: "inst-2", sequence: 2, label: "Second", outstanding: "30000.00"}]};
  const view = mount("components/projects/collections/ReceiptPanel.tsx", "ReceiptPanel", {"@/lib/api": api, "@/lib/format": formatStub, "./labels": new Proxy({}, {get: () => () => "x"})},
    {projectId: "p", saleId: "s", summary, currencyCode: "JOD", canRecord: true, canConfirm: false, canRestrictCash: false, onChanged() {}});
  view.render(); await settle(); await settle();
  const apply = nodes(view.render()).find(node => node.type === "Button" && node.props.children === "Apply");
  await apply.props.onClick(); await settle();
  let tree = view.render();
  assert.doesNotMatch(text(tree), /nothing is outstanding/);
  const retry = nodes(tree).find(node => node.type === "Button" && node.props.children === "Retry suggestions");
  assert.ok(retry, "a failed suggestion read offers Retry");
  retry.props.onClick(); await settle();
  assert.equal(suggestionCalls, 2);
  nodes(view.render()).find(node => node.type === "select").props.onChange({target: {value: "inst-2"}});
  nodes(view.render()).find(node => node.type === "MoneyInput").props.onChange("5000.00");
  nodes(view.render()).filter(node => node.type === "Form").at(-1).props.onSubmit({preventDefault() {}});
  await settle(); await settle();
  tree = view.render();
  assert.equal(nodes(tree).find(node => node.type === "select").props.value, "inst-2");
  assert.equal(nodes(tree).find(node => node.type === "MoneyInput").props.value, "5000.00");
  assert.match(text(tree), /already paid/);
});

test("old Agent & Buyer and Pricing links open the screens that replaced them", () => {
  const source = readFileSync(new URL("../src/components/shell/navigation.ts", import.meta.url), "utf8");
  const code = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText;
  const exports = {};
  runInNewContext(`(function(require,exports){${code}\n})`, {URLSearchParams})(key => key === "@/lib/roles" ? {hasAnyRole: () => true, ROLE_SYSTEM_ADMIN: "system_admin"} : {}, exports);
  assert.equal(exports.resolveProjectSection("agent-buyer"), "buyers");
  assert.equal(exports.resolveProjectSection("pricing"), "inventory");
  assert.equal(exports.resolveProjectSection("team"), "team");
  assert.equal(exports.resolveProjectSection("nonsense"), "overview");
  assert.equal(exports.resolveProjectSection(null), "overview");
});

function loadModule(path, resolve = () => ({})) {
  const source = readFileSync(new URL(`../src/${path}`, import.meta.url), "utf8");
  const code = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText;
  const exports = {};
  runInNewContext(`(function(require,exports){${code}\n})`, {URLSearchParams, Set})(resolve, exports);
  return exports;
}

test("System Administrator sees Consultant Engineer and Commissions; the roles outside them still do not (B-03)", () => {
  const roles = loadModule("lib/roles.ts");
  const navigation = loadModule("components/shell/navigation.ts", key => key === "@/lib/roles" ? roles : {});
  const sections = held => navigation.visibleNavigation(navigation.PROJECT_NAVIGATION, new Set(held)).flatMap(group => group.items.map(item => item.key));
  const admin = sections(["system_admin"]);
  assert.ok(admin.includes("consultant"), admin.join(","));
  assert.ok(admin.includes("commissions"), admin.join(","));
  // Reading only: editing, preparing and releasing stay with the business roles.
  for (const writers of [roles.CONSULTANT_EDITORS, roles.COMMISSION_PREPARERS, roles.COMMISSION_RELEASERS]) {
    assert.equal(writers.has("system_admin"), false);
  }
  assert.equal(sections(["legal"]).includes("consultant"), false);
  assert.equal(sections(["sales_advisor"]).includes("commissions"), false);
  assert.equal(sections(["collections"]).includes("commissions"), false);
});

function collectionsTab(component, collectionsApi) {
  const api = {ApiError, sales: {}, collections: collectionsApi};
  const summary = {installments: [], confirmed_receipts_total: "0.00", allocated_total: "0.00", unapplied_cash: "0.00", refund_due_total: "0.00", refund_confirmed_total: "0.00", refund_outstanding: "0.00"};
  return mount("components/projects/collections/CollectionAccount.tsx", component, {"@/lib/api": api, "@/lib/format": formatStub, "@/lib/roles": {hasAnyRole: () => false, CASHFLOW_RECORDERS: new Set()}, "./labels": new Proxy({}, {get: () => () => "label"})},
    {projectId: "p", saleId: "s", summary, currencyCode: "JOD", canCollect: true, canApprove: false, canConfirm: false, busy: false, error: null, onAct: async () => true});
}
const failing = async () => {throw new ApiError("Service unavailable", 503);};

test("Collections follow-up, disputes, waivers and restructures never turn a failed read into an empty record", async () => {
  const cases = [
    ["ActionsTab", {actions: failing}, /No follow-up recorded/],
    ["ExceptionsTab", {disputes: failing, waivers: async () => []}, /No disputes/],
    ["ExceptionsTab", {disputes: async () => [], waivers: failing}, /No waivers/],
    ["RestructureTab", {restructures: failing}, /never been restructured/],
  ];
  for (const [component, api, falseClaim] of cases) {
    const view = collectionsTab(component, api);
    view.render(); await settle(); await settle();
    const tree = view.render();
    assert.doesNotMatch(text(tree), falseClaim, component);
    assert.ok(nodes(tree).some(node => node.type === "Notice" && node.props.tone === "error"), `${component} shows the failure`);
    assert.ok(nodes(tree).some(node => node.type === "Button" && node.props.children === "Retry"), `${component} offers Retry`);
    if (component === "RestructureTab") {
      assert.equal(nodes(tree).some(node => node.type === "SubPanel" && node.props.title === "Raise a restructure"), false, "no second restructure is offered over unknown history");
    }
  }
});

test("the restructure carry-forward names receipts and instalments, never identifier fragments", async () => {
  const open = {id: "0b5c7a1e-1111-4000-8000-000000000003", status: "open"};
  const preview = {ready_to_apply: true, blockers: [], carried_total: "5000.00", unapplied_total: "0.00", confirmed_receipts_total: "5000.00", superseding: 1,
    lines: [{receipt_id: "9d3f2b10-2222-4000-8000-000000000004", receipt_number: "RC-0007", installment_id: "5e6a8c20-3333-4000-8000-000000000005", installment_sequence: 2, installment_label: "On completion", amount: "5000.00"}]};
  const view = collectionsTab("RestructureTab", {restructures: async () => [open], previewRestructure: async () => preview});
  view.render(); await settle(); await settle();
  const rendered = text(view.render());
  assert.match(rendered, /RC-0007/);
  assert.match(rendered, /On completion/);
  assert.doesNotMatch(rendered, /9d3f2b10|5e6a8c20/);
  assert.doesNotMatch(rendered, UUID);
});
