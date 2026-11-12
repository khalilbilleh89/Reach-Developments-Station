import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);

function harness() {
  const slots = []; let cursor = 0;
  const source = readFileSync(new URL("../src/components/projects/OperationsCommissions.tsx", import.meta.url), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const exports = {};
  let answer = { status: "loading", retry() {} };
  let enabled;
  class ApiError extends Error {}
  runInNewContext(`(function(require,exports){${code}\n})`)((key) => {
    if (key === "react") return { useState(initial) {
      const i = cursor++; slots[i] ??= { value: typeof initial === "function" ? initial() : initial };
      return [slots[i].value, value => { slots[i].value = value; }];
    }};
    if (key === "@/lib/format") return { money: (value, code) => `${code ?? ""} ${value}` };
    if (key === "@/lib/api") return { ApiError, settings: { currencies() {} } };
    if (key === "@/lib/api/operationsCommissions") return { operationsCommissions: {} };
    if (key === "@/lib/answer") return { useAnswer(gate) { enabled = gate; return answer; } };
    if (key === "@/lib/roles") return { COMMISSION_READERS: new Set(["finance", "auditor"]), COMMISSION_PREPARERS: new Set(["finance"]), hasAnyRole: (roles, allowed) => [...roles].some(role => allowed.has(role)) };
    if (key === "./DeleteRecordButton") return { DeleteRecordButton: "DeleteRecordButton" };
    if (key === "@/components/ui") return new Proxy({}, { get: (_, name) => name });
    return require(key);
  }, exports);
  return { exports, ApiError, setAnswer(value) { answer = { retry() {}, ...value }; },
    enabled: () => enabled, render(component, props) { cursor = 0; return exports[component](props); } };
}
function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children), ...nodes(tree.props?.actions)];
}
const find = (tree, type) => nodes(tree).filter(node => node.type === type);

const currency = "00000000-0000-0000-0000-000000000001";
const row = { id: "entry", client_id: "client", client_display: "Example client", beneficiary_name: "Recipient", amount: "1250.50", reason: "Coordination", currency_id: currency, version: 1 };
const data = { items: [row], clients: [{ id: "client", display_name: "Example client", client_number: "C-001" }], currency_id: currency };
const props = { projectId: "project", roles: new Set(["finance"]), currencyCodes: { [currency]: "EUR" } };

test("operations register resolves denomination and opens retained deletion", () => {
  const h = harness(); h.setAnswer({ status: "ready", data });
  let tree = h.render("OperationsCommissions", props);
  assert.equal(h.enabled(), true);
  assert.ok(find(tree, "td").some(node => node.props.children === "EUR 1250.50"));
  find(tree, "Button").find(node => node.props.children === "Recipient").props.onClick();
  tree = h.render("OperationsCommissions", props);
  assert.equal(find(tree, "RecordPage").length, 1);
  assert.equal(find(tree, "DeleteRecordButton")[0].props.confirmLabel, "Delete commission");
  assert.match(find(tree, "DeleteRecordButton")[0].props.description, /retained/);
});

test("readers cannot write and denied roles do not fetch", () => {
  const h = harness(); h.setAnswer({ status: "ready", data });
  let tree = h.render("OperationsCommissions", { ...props, roles: new Set(["auditor"]) });
  assert.equal(find(tree, "PageHeader")[0].props.actions, undefined);
  h.setAnswer({ status: "off" });
  h.render("OperationsCommissions", { ...props, roles: new Set(["sales_advisor"]) });
  assert.equal(h.enabled(), false);
});

test("failure is retryable and never rendered as empty data", () => {
  const h = harness(); h.setAnswer({ status: "failed", message: "Unavailable" });
  const tree = h.render("OperationsCommissions", props);
  assert.equal(find(tree, "EmptyState").length, 0);
  assert.ok(find(tree, "Button").some(node => node.props.children === "Retry"));
});

test("editor keeps exact decimal strings and a failed save retains its draft", async () => {
  const h = harness(); let submitted; let closed = false;
  const editorProps = { row, register: data, currencyCodes: props.currencyCodes, onClose() { closed = true; }, onSave: async value => { submitted = value; throw new h.ApiError("Conflict: reopen entry"); } };
  let tree = h.render("OperationsEditor", editorProps);
  find(tree, "MoneyInput")[0].props.onChange("9007199254740991.01");
  tree = h.render("OperationsEditor", editorProps);
  assert.equal(find(tree, "DraftBoundary")[0].props.dirty, true);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  tree = h.render("OperationsEditor", editorProps);
  assert.equal(submitted.amount, "9007199254740991.01");
  assert.equal(find(tree, "MoneyInput")[0].props.value, submitted.amount);
  assert.equal(find(tree, "Notice")[0].props.children, "Conflict: reopen entry");
  assert.equal(closed, false);
});
