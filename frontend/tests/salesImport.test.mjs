import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);
function harness(file, mocks = {}) {
  const slots = []; let cursor = 0;
  const source = readFileSync(new URL(`../src/components/projects/${file}.tsx`, import.meta.url), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const exports = {};
  runInNewContext(`(function(require,exports){${code}\n})`)((key) => {
    if (key in mocks) return mocks[key];
    if (key === "react") return { useState(initial) {
      const i = cursor++; slots[i] ??= { value: typeof initial === "function" ? initial() : initial };
      return [slots[i].value, value => { slots[i].value = typeof value === "function" ? value(slots[i].value) : value; }];
    }};
    if (key === "@/components/ui") return new Proxy({}, { get: (_, name) => name });
    if (key.includes("DeleteRecordButton")) return { DeleteRecordButton: "DeleteRecordButton" };
    if (key.includes("TeamJobDescription")) return { TeamJobDescription: "TeamJobDescription" };
    if (key === "@/lib/api") return { ApiError: class ApiError extends Error {} };
    if (key.includes("TeamMemberForm")) return { TeamMemberForm: "TeamMemberForm" };
    if (key.includes("TeamSection")) return { TeamSection: "TeamSection" };
    return require(key);
  }, exports);
  return (name, props) => { cursor = 0; return exports[name](props); };
}
function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children), ...nodes(tree.props?.actions)];
}
const find = (tree, type) => nodes(tree).filter(node => node.type === type);

class ImportApiError extends Error {}
function setup(run) {
  return harness("sales/SalesImport", {
    "@/lib/api/salesImport": { salesImport: { run, template: async () => {} } },
    "@/lib/api": { ApiError: ImportApiError },
  });
}
const props = {projectId: "project", kind: "buyers", onClose() {}, onImported() {}};
const report = {total_rows: 2, created_count: 0, applied: false, error_count: 0, issues: [], issues_truncated: false};
const button = (tree, text) => find(tree, "Button").find(x => String(x.props.children).includes(text));
const choose = async (tree, bytes = new ArrayBuffer(10)) => find(tree, "input")[0].props.onChange({target: {files: [{name: "buyers.xlsx", size: 10, arrayBuffer: async () => bytes}]}});

test("import requires validation and invalidates it after changing files", async () => {
  const calls = [];
  const render = setup(async (...args) => { calls.push(args); return report; });
  let tree = render("SalesImport", props);
  assert.equal(button(tree, "Import").props.disabled, true);
  const bytes = new ArrayBuffer(10);
  await choose(tree, bytes);
  tree = render("SalesImport", props);
  assert.equal(find(tree, "DraftBoundary")[0].props.dirty, true);
  await button(tree, "Validate").props.onClick();
  tree = render("SalesImport", props);
  assert.equal(button(tree, "Import").props.disabled, false);
  assert.equal(calls[0][0], "project");
  assert.equal(calls[0][1], "buyers");
  assert.equal(calls[0][2], "validate");
  assert.equal(calls[0][3], bytes);
  await choose(tree);
  tree = render("SalesImport", props);
  assert.equal(button(tree, "Import").props.disabled, true);
});

test("row errors block import, API failures retain selection and require revalidation", async () => {
  let result = {...report, error_count: 1, issues: [{row: 3, column: "display_name", message: "Required"}]};
  const render = setup(async () => { if (result instanceof Error) throw result; return result; });
  let tree = render("SalesImport", props);
  await choose(tree);
  tree = render("SalesImport", props);
  await button(tree, "Validate").props.onClick();
  tree = render("SalesImport", props);
  assert.equal(button(tree, "Import").props.disabled, true);
  assert.equal(find(tree, "td")[0].props.children, 3);
  result = report;
  await button(tree, "Validate").props.onClick();
  tree = render("SalesImport", props);
  result = new ImportApiError("Service unavailable");
  await button(tree, "Import").props.onClick();
  tree = render("SalesImport", props);
  assert.equal(button(tree, "Import").props.disabled, true);
  assert.equal(find(tree, "DraftBoundary")[0].props.dirty, true);
  assert.equal(find(tree, "Notice")[0].props.children, "Service unavailable");
});

test("successful import refreshes register and prevents repeat submission", async () => {
  let imported = 0;
  const render = setup(async (_project, _kind, operation) => operation === "apply" ? {...report, applied: true, created_count: 2} : report);
  const p = {...props, onImported() { imported++; }};
  let tree = render("SalesImport", p);
  await choose(tree);
  tree = render("SalesImport", p);
  await button(tree, "Validate").props.onClick();
  tree = render("SalesImport", p);
  await button(tree, "Import").props.onClick();
  tree = render("SalesImport", p);
  assert.equal(imported, 1);
  assert.equal(button(tree, "Import").props.disabled, true);
  assert.equal(find(tree, "DraftBoundary")[0].props.dirty, false);
});


test("duplicates do not block new imports and both totals are shown", async () => {
  let imported = 0;
  const duplicateReport = {...report, total_rows: 57, new_count: 56, duplicate_count: 1,
    duplicates: [{row: 2, source: "existing"}], duplicates_truncated: false};
  const render = setup(async (_project, _kind, operation) => operation === "apply"
    ? {...duplicateReport, applied: true, created_count: 56} : duplicateReport);
  const p = {...props, kind: "agents", onImported() { imported++; }};
  let tree = render("SalesImport", p);
  await choose(tree);
  tree = render("SalesImport", p);
  await button(tree, "Validate").props.onClick();
  tree = render("SalesImport", p);
  assert.equal(button(tree, "Import").props.children, "Import 56 new agents");
  assert.equal(button(tree, "Import").props.disabled, false);
  assert.match(find(tree, "Notice")[0].props.children, /56 new agents.*1 duplicate/);
  assert.equal(find(tree, "td")[0].props.children, 2);
  assert.equal(find(tree, "td")[1].props.children, "Already in this project");
  await button(tree, "Import").props.onClick();
  tree = render("SalesImport", p);
  assert.match(find(tree, "Notice")[0].props.children, /Imported 56 new agents.*Skipped 1 duplicate/);
  assert.equal(imported, 1);
});

test("an all-duplicate file completes with zero new records", async () => {
  const duplicateReport = {...report, total_rows: 57, new_count: 0, duplicate_count: 57};
  const render = setup(async (_project, _kind, operation) => ({...duplicateReport, applied: operation === "apply"}));
  let tree = render("SalesImport", props);
  await choose(tree);
  tree = render("SalesImport", props);
  await button(tree, "Validate").props.onClick();
  tree = render("SalesImport", props);
  assert.equal(button(tree, "Finish import").props.disabled, false);
  assert.match(find(tree, "Notice")[0].props.children, /0 new buyers.*57 duplicate/);
  await button(tree, "Finish import").props.onClick();
  tree = render("SalesImport", props);
  assert.match(find(tree, "Notice")[0].props.children, /Imported 0 new buyers.*Skipped 57 duplicate/);
  assert.equal(find(tree, "DraftBoundary")[0].props.dirty, false);
  assert.equal(button(tree, "Import").props.disabled, true);
});

test("FAQ upload validates the same bytes before importing and uses FAQ guidance", async () => {
  const calls = [];
  const render = setup(async (...args) => { calls.push(args); return {...report, applied: args[2]==="apply", created_count: args[2]==="apply" ? 2 : 0}; });
  const p = {...props, kind:"faqs"};
  let tree = render("SalesImport", p);
  assert.equal(tree.props.title,"Import FAQs from Excel");
  assert.match(find(tree,"Field")[0].props.hint,/plain text/);
  const bytes = new ArrayBuffer(10);
  await choose(tree,bytes);
  await button(render("SalesImport",p),"Validate").props.onClick();
  await button(render("SalesImport",p),"Import").props.onClick();
  assert.deepEqual(calls.map(args => args.slice(1,3)),[["faqs","validate"],["faqs","apply"]]);
  assert.ok(calls.every(args => args[3] === bytes));
  tree = render("SalesImport", p);
  assert.equal(find(tree,"Notice")[0].props.children,"Imported 2 FAQs.");
});
