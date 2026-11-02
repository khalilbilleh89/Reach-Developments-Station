import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);
const settle = () => new Promise(resolve => setImmediate(resolve));

function mount(path, component, dependencies, props) {
  const slots = []; let cursor = 0;
  const react = {
    useState(initial) { const i = cursor++; slots[i] ??= { value: initial }; return [slots[i].value, value => { slots[i].value = typeof value === "function" ? value(slots[i].value) : value; }]; },
  };
  const code = ts.transpileModule(readFileSync(new URL(`../src/${path}`, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const exports = {};
  runInNewContext(`(function(require, exports) { ${code}\n})`)(name => {
    if (name === "react") return react;
    if (name in dependencies) return dependencies[name];
    if (name === "@/components/ui") return new Proxy({}, { get: (_, key) => key });
    return require(name);
  }, exports);
  return () => { cursor = 0; return exports[component](props); };
}
function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children)];
}
const text = tree => JSON.stringify(tree);

class ApiError extends Error {}

function bar(run, events) {
  return mount("components/projects/sales/BulkRemoval.tsx", "BulkRemovalBar", { "@/lib/api": { ApiError } }, {
    count: 3, noun: "buyer", verb: "Delete", description: "Buyers with history are kept.",
    names: { a: "Alpha", b: "Bravo", c: "Charlie" }, run,
    onClear: () => events.push("clear"), onDone: () => events.push("done"),
  });
}

test("bulk removal asks for a reason, names what was kept, and refreshes the register", async () => {
  const events = []; const reasons = [];
  const render = bar(async reason => { reasons.push(reason); return { removed: ["a", "b"], skipped: [{ id: "c", message: "This buyer has transaction history." }] }; }, events);
  let tree = render();
  const open = nodes(tree).find(node => node.type === "Button" && node.props.children.join("") === "Delete selected");
  assert.equal(open.props.variant, "danger");
  open.props.onClick(); tree = render();
  const dialog = nodes(tree).find(node => node.type === "PromptDialog");
  assert.equal(dialog.props.title, "Delete 3 buyers?");
  assert.equal(dialog.props.destructive, true);
  dialog.props.onSubmit("Clear test buyers"); await settle(); tree = render();
  assert.deepEqual(reasons, ["Clear test buyers"]);
  assert.deepEqual(events, ["clear", "done"]);
  assert.equal(nodes(tree).find(node => node.type === "PromptDialog"), undefined);
  const notice = nodes(tree).find(node => node.type === "Notice");
  assert.equal(notice.props.tone, "warning");
  assert.match(text(notice), /Deleted 2 buyers\./);
  assert.match(text(notice), /1 buyer kept/);
  assert.match(text(notice), /Charlie/);
  assert.match(text(notice), /transaction history/);
  assert.equal(nodes(notice).filter(node => node.type === "li").length, 1);
});

test("a failed bulk request keeps the dialog open with the server's message", async () => {
  const events = [];
  const render = bar(async () => { throw new ApiError("Only an administrator may delete buyers."); }, events);
  let tree = render();
  nodes(tree).find(node => node.type === "Button" && node.props.children.join("") === "Delete selected").props.onClick();
  tree = render();
  nodes(tree).find(node => node.type === "PromptDialog").props.onSubmit("No"); await settle(); tree = render();
  const dialog = nodes(tree).find(node => node.type === "PromptDialog");
  assert.equal(dialog.props.error, "Only an administrator may delete buyers.");
  assert.deepEqual(events, []);
  assert.equal(nodes(tree).find(node => node.type === "Notice"), undefined);
});

test("the three registers send ticked rows to their bulk routes behind the right roles", () => {
  const read = file => readFileSync(new URL(`../src/components/projects/${file}`, import.meta.url), "utf8");
  const buyers = read("sales/ClientsPanel.tsx");
  assert.match(buyers, /canAdmin \? <BulkRemovalBar[^]*sales\.bulkDeleteClients\(projectId, ticked\.selected/);
  assert.match(buyers, /canAdmin \? <SelectAllCell/);
  const agents = read("sales/AgentsPanel.tsx");
  assert.match(agents, /canWrite \? <BulkRemovalBar[^]*sales\.bulkDeleteAgents\(projectId, ticked\.selected/);
  const salesTab = read("SalesTab.tsx");
  assert.match(salesTab, /const canRemove = roles\.has\("master_admin"\) && !history;/);
  assert.match(salesTab, /canRemove \? <BulkRemovalBar[^]*sales\.bulkRemoveTransactions\(/);
  const api = readFileSync(new URL("../src/lib/api/index.ts", import.meta.url), "utf8");
  for (const route of ["sales/clients/bulk-delete", "sales/agents/bulk-delete", "sales/transactions/bulk-remove"]) assert.ok(api.includes(route), route);
});
