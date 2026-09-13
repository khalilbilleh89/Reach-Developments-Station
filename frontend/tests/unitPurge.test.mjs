import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {createRequire} from "node:module";
import {runInNewContext} from "node:vm";
import test from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
const code = ts.transpileModule(readFileSync(new URL("../src/components/projects/inventory/UnitPurgePage.tsx", import.meta.url), "utf8"), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX},
}).outputText;

function harness({blockers = [], fail = false} = {}) {
  const state = [], effects = [], calls = [], exports = {};
  let cursor = 0, completed = 0;
  const hooks = {
    useState(initial) { const i = cursor++; if (!(i in state)) state[i] = initial; return [state[i], value => {state[i] = typeof value === "function" ? value(state[i]) : value;}]; },
    useRef(initial) { const i = cursor++; return state[i] ??= {current: initial}; },
    useCallback(callback) { cursor++; return callback; },
    useEffect(effect, deps) { const i = cursor++; if (!state[i] || deps.some((value, j) => value !== state[i][j])) {state[i] = deps; effects.push(effect);} },
  };
  class ApiError extends Error {}
  runInNewContext(`(function(require, exports) { ${code}\n})`)(name => {
    if (name === "react") return hooks;
    if (name === "@/components/ui") return Object.fromEntries(["Button", "Card", "Field", "Loading", "Notice", "RecordPage", "TableScroll", "UnsavedChangesGuard"].map(key => [key, key]));
    if (name === "@/lib/api") return {ApiError, inventory: {
      unitPurgePreview: async () => ({unit_id: "unit", unit_reference: "1102", fingerprint: "fingerprint", blockers, counts: [{label: "Sale contracts", count: 1}], transactions: [{kind: "Sale", reference: "SALE-1", status: "cancelled"}], total_records: 1}),
      purgeUnitHistory: async (...args) => {calls.push(args); if (fail) throw new ApiError("History changed; refresh preview.");},
    }};
    return require(name);
  }, exports);
  const render = () => {cursor = 0; return exports.UnitPurgePage({projectId: "project", unit: {id: "unit", unit_reference: "1102"}, onClose() {}, onPurged() {completed++;}});};
  return {render, calls, get completed() {return completed;}, async load() {render(); effects.splice(0).forEach(effect => effect()); await new Promise(resolve => setImmediate(resolve)); return render();}};
}

function all(node, predicate) {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap(child => all(child, predicate));
  return [...(predicate(node) ? [node] : []), ...all(node.props?.children, predicate)];
}
const inputs = tree => all(tree, node => node.type === "input");
const submit = tree => all(tree, node => node.type === "form")[0].props.onSubmit({preventDefault() {}});

test("Purge requires exact reference, reason and acknowledgment before sending the preview", async () => {
  const h = harness();
  let tree = await h.load();
  await submit(tree);
  assert.equal(h.calls.length, 0);
  inputs(tree)[0].props.onChange({target: {value: "dummy"}});
  inputs(tree)[1].props.onChange({target: {value: "wrong"}});
  inputs(tree)[2].props.onChange({target: {checked: true}});
  tree = h.render();
  await submit(tree);
  assert.equal(h.calls.length, 0);
  inputs(tree)[1].props.onChange({target: {value: "1102"}});
  await submit(h.render());
  assert.equal(h.completed, 1);
  assert.deepEqual(JSON.parse(JSON.stringify(h.calls)), [["project", "unit", {confirm_reference: "1102", reason: "dummy", fingerprint: "fingerprint", acknowledge_history_deletion: true}]]);
});

test("Failed confirmation clears preview and acknowledgment, preserving the reason", async () => {
  const h = harness({fail: true});
  let tree = await h.load();
  inputs(tree)[0].props.onChange({target: {value: "dummy"}});
  inputs(tree)[1].props.onChange({target: {value: "1102"}});
  inputs(tree)[2].props.onChange({target: {checked: true}});
  await submit(h.render());
  tree = h.render();
  assert.equal(h.completed, 0);
  assert.equal(inputs(tree).length, 0);
  await submit(tree);
  assert.equal(h.calls.length, 1);
  all(tree, node => node.type === "Button" && node.props.children === "Refresh preview")[0].props.onClick();
  tree = await h.load();
  assert.equal(inputs(tree)[0].props.value, "dummy");
  assert.equal(inputs(tree)[1].props.value, "");
  assert.equal(inputs(tree)[2].props.checked, false);
});

test("A server blocker has no destructive confirmation fields", async () => {
  const h = harness({blockers: ["Active sale must be closed."]});
  const tree = await h.load();
  assert.equal(inputs(tree).length, 0);
  await submit(tree);
  assert.equal(h.calls.length, 0);
});
