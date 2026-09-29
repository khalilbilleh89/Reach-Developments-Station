// Regressions found by the platform operational audit (docs/SYSTEM_OPERATIONAL_AUDIT.md).
// Each test mounts the real component and drives its handlers, so it fails on the
// behaviour the operator saw, not on a source string.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);
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
  const cancellation = {id: "c0ffee00-0000-4000-8000-000000000002", status: "approved", financial_approval_required: true, financial_approved_at: "2026-09-20T10:00:00Z"};
  const summary = {refund_due_total: "40000.00", refund_confirmed_total: "0.00", refund_outstanding: "40000.00"};
  const api = {ApiError,
    collections: {refunds: async () => [], recordRefund: async (_, __, body) => {calls.push(body); return {id: "r"};}},
    sales: {contract: async () => ({cancellation: overrides.cancellation === undefined ? cancellation : overrides.cancellation})}};
  const props = {projectId: "p", saleId: "s", summary: {...summary, ...(overrides.summary ?? {})}, currencyCode: "JOD", canCollect: overrides.canCollect ?? true, canConfirm: false, busy: false, error: null,
    onAct: async (run) => {await run(); return true;}};
  const view = mount("components/projects/collections/CollectionAccount.tsx", "RefundsTab", {"@/lib/api": api, "@/lib/format": {businessDate: v => v, isPositive: v => Number(v) > 0, money: (v, c) => `${c} ${v}`, todayISO: () => "2026-09-29", percent: v => v}}, props);
  return {view, calls, cancellation};
}

test("an approved refund can be recorded from Collections, against the cancellation that approved it", async () => {
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
  form.props.onSubmit({preventDefault() {}}); await settle(); await settle();
  assert.deepEqual(JSON.parse(JSON.stringify(calls)), [{cancellation_id: cancellation.id, amount: "15000.00", refund_date: "2026-09-29", bank_reference: "TRF-991", notes: null}]);
  assert.equal(nodes(view.render()).some(node => node.type === "Form"), false);
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
