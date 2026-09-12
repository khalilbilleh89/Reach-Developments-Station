import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
const settle = () => new Promise(resolve => setImmediate(resolve));
class ApiError extends Error {}
function harness(file, name, collections) {
  const slots = []; let cursor = 0; const effects = [];
  const react = {
    useState(initial) { const i = cursor++; slots[i] ??= { value: initial }; return [slots[i].value, value => { slots[i].value = typeof value === "function" ? value(slots[i].value) : value; }]; },
    useCallback(fn) { return fn; },
    useEffect(fn) { const i = cursor++; if (!slots[i]) { slots[i] = {}; effects.push(fn); } },
  };
  const ui = new Proxy({}, { get: (_, key) => key });
  const source = readFileSync(new URL(`../src/components/projects/collections/${file}.tsx`, import.meta.url), "utf8") + (name === "RefundsTab" ? "\nexport { RefundsTab };" : "");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const exports = {};
  runInNewContext(`(function(require, exports) { ${code}\n})`)(key => {
    if (key === "react") return react;
    if (key === "@/components/ui") return ui;
    if (key === "@/lib/api") return { collections, ApiError };
    if (key === "@/lib/format") return { money: value => value, businessDate: value => value, todayISO: () => "2026-09-12", isPositive: value => Number(value) > 0 };
    if (key === "./labels") return new Proxy({}, { get: () => value => value });
    if (key.startsWith("@/") || key.startsWith("./")) return {};
    return require(key);
  }, exports);
  const walk = node => {
    if (!node || typeof node !== "object") return [];
    if (Array.isArray(node)) return node.flatMap(walk);
    if (typeof node.type === "function") return walk(node.type(node.props));
    return [node, ...walk(node.props?.children)];
  };
  return props => { cursor = 0; const nodes = walk(exports[name](props)); effects.splice(0).forEach(fn => fn()); return nodes; };
}
const button = (nodes, text) => nodes.find(n => n.type === "Button" && n.props.children === text);
const dialog = nodes => nodes.find(n => n.type === "PromptDialog");
const summary = { installments: [], refund_due_total: "0.00", refund_confirmed_total: "0.00", refund_outstanding: "0.00" };
const receipt = { id: "receipt-1", receipt_number: "RCT-1", status: "recorded", confirmed_at: null, allocations: [], amount: "100.00", unapplied_amount: "100.00" };
const refund = { id: "refund-1", refund_number: "RFD-1", status: "recorded", confirmed_at: null, amount: "100.00" };

test("receipt Delete retains failure and reference, refreshes on success, and stays distinct from Finance Reverse", async () => {
  let fail = true, changed = 0; const calls = [];
  const api = { receipts: async () => [receipt], voidReceipt: async (...args) => { calls.push(args); if (fail) throw new ApiError("Reverse active allocations first"); } };
  const render = harness("ReceiptPanel", "ReceiptPanel", api);
  const props = { projectId: "p", saleId: "s", summary, canRecord: true, canConfirm: false, onChanged: () => changed++ };
  render(props); await settle();
  button(render(props), "Delete").props.onClick();
  assert.equal(dialog(render(props)).props.title, "Delete RCT-1");
  dialog(render(props)).props.onSubmit("Duplicate"); await settle();
  assert.equal(dialog(render(props)).props.error, "Reverse active allocations first");
  assert.equal(changed, 0);
  fail = false; dialog(render(props)).props.onSubmit("Duplicate"); await settle();
  assert.equal(dialog(render(props)), undefined); assert.equal(changed, 1);
  assert.deepEqual(calls, [["p", "receipt-1", "Duplicate"], ["p", "receipt-1", "Duplicate"]]);
  assert.equal(button(render({ ...props, canRecord: false }), "Delete"), undefined);
  receipt.status = "confirmed";
  assert.equal(button(render(props), "Delete"), undefined);
  assert.ok(button(render({ ...props, canConfirm: true }), "Reverse"));
  receipt.status = "recorded";
});

test("recorded refunds remain removable when due totals are zero; failure retains prompt and success reloads", async () => {
  let reads = 0, saved = false; const calls = [];
  const render = harness("CollectionAccount", "RefundsTab", {
    refunds: async () => { reads++; return [refund]; }, voidRefund: async (...args) => calls.push(args),
  });
  const props = { projectId: "p", saleId: "s", summary, canCollect: true, canConfirm: false, busy: false, error: null,
    onAct: async run => { if (!saved) return false; await run(); return true; } };
  render(props); await settle();
  button(render(props), "Delete").props.onClick();
  assert.equal(dialog(render(props)).props.title, "Delete RFD-1");
  await dialog(render(props)).props.onSubmit("Duplicate");
  props.error = "Try again";
  assert.equal(dialog(render(props)).props.error, "Try again"); assert.equal(reads, 1);
  saved = true; await dialog(render(props)).props.onSubmit("Duplicate");
  assert.equal(dialog(render(props)), undefined); assert.equal(reads, 2);
  assert.deepEqual(calls, [["p", "refund-1", "Duplicate"]]);
  assert.equal(button(render({ ...props, canCollect: false }), "Delete"), undefined);
  assert.ok(button(render({ ...props, busy: true }), "Delete").props.disabled);
});

test("refund read failure offers Retry instead of hiding recorded entries as no refund due", async () => {
  let fail = true;
  const render = harness("CollectionAccount", "RefundsTab", { refunds: async () => { if (fail) throw new ApiError("Unavailable"); return [refund]; } });
  const props = { summary, canCollect: true };
  render(props); await settle();
  assert.ok(button(render(props), "Retry")); assert.equal(button(render(props), "Delete"), undefined);
  fail = false; button(render(props), "Retry").props.onClick(); await settle();
  assert.ok(button(render(props), "Delete"));
});

test("confirmed refund stays Finance Reverse and retains a refused reversal prompt", async () => {
  let saved = false; const calls = [];
  const render = harness("CollectionAccount", "RefundsTab", {
    refunds: async () => [{ ...refund, status: "confirmed", confirmed_at: "2026-09-12" }],
    reverseRefund: async (...args) => calls.push(args),
  });
  const props = { projectId: "p", saleId: "s", summary, canCollect: false, canConfirm: true,
    onAct: async run => { if (!saved) return false; await run(); return true; } };
  render(props); await settle();
  assert.equal(button(render(props), "Delete"), undefined);
  button(render(props), "Reverse").props.onClick();
  assert.equal(dialog(render(props)).props.title, "Reverse RFD-1");
  assert.equal(dialog(render(props)).props.confirmLabel, "Reverse");
  await dialog(render(props)).props.onSubmit("Wrong payment");
  assert.ok(dialog(render(props)));
  saved = true; await dialog(render(props)).props.onSubmit("Wrong payment");
  assert.equal(dialog(render(props)), undefined);
  assert.deepEqual(calls, [["p", "refund-1", "Wrong payment"]]);
});
