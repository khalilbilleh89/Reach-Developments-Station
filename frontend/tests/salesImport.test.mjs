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
