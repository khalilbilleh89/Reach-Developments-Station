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

const entry = { id: "entry", project_id: "project", effective_date: "2026-10-18", escalation_percent: "5.1256", project_status: "Custom foundation stage", version: 7 };
test("register shows exact saved percentage and custom status; deletion retains version and refreshes", async () => {
  let removed; let retries = 0;
  const render = harness("PriceEscalationTab", {
    "@/lib/api/escalations": { escalations: { remove: async (...args) => { removed = args; } } },
    "@/lib/answer": { useAnswer: () => ({ status: "ready", data: { entries: [entry], can_manage: true }, retry() { retries++; } }) },
  });
  const tree = render("PriceEscalationTab", { projectId: "project" });
  const text = nodes(tree).filter(node => node.type === "dd").map(node => node.props.children).flat().join(" ");
  assert.match(text, /5.1256/); assert.match(text, /Custom foundation stage/);
  const deletion = find(tree, "DeleteRecordButton")[0];
  assert.match(deletion.props.recordName, /2026-10-18/);
  await deletion.props.onDelete("Entered twice"); await deletion.props.onDeleted();
  assert.equal(removed[0], "project"); assert.equal(removed[1].version, 7); assert.equal(removed[2], "Entered twice"); assert.equal(retries, 1);
});
test("failed reads offer retry; readers have no mutations", () => {
  let answer = { status: "failed", message: "Unavailable", retry() {} };
  const render = harness("PriceEscalationTab", { "@/lib/api/escalations": { escalations: {} }, "@/lib/answer": { useAnswer: () => answer } });
  let tree = render("PriceEscalationTab", { projectId: "project" });
  assert.equal(find(tree, "EmptyState").length, 0);
  assert.ok(find(tree, "Notice").some(node => node.props.tone === "error"));
  answer = { ...answer, status: "ready", data: { entries: [entry], can_manage: false } };
  tree = render("PriceEscalationTab", { projectId: "project" });
  assert.equal(find(tree, "PageHeader")[0].props.actions, undefined); assert.equal(find(tree, "DeleteRecordButton").length, 0);
});
test("form accepts arbitrary project status and exact decimal strings, retains failed draft, then saves", async () => {
  let body; let fail = true; let saved = 0;
  const render = harness("PriceEscalationTab", { "@/lib/api/escalations": { escalations: { update: async (project, row, values) => { body = { project, row, values }; if (fail) throw Error("Offline"); } } }, "@/lib/answer": {} });
  const props = { projectId: "project", entry, suggestions: ["Pre-launch"], onClose() {}, onSaved() { saved++; } };
  let tree = render("EscalationForm", props);
  find(tree, "input").find(node => node.props.name === "project_status").props.onChange({ target: { value: "A status of my own" } });
  tree = render("EscalationForm", props);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  tree = render("EscalationForm", props);
  assert.equal(find(tree, "input").find(node => node.props.name === "project_status").props.value, "A status of my own");
  assert.equal(find(tree, "DraftBoundary")[0].props.dirty, true);
  assert.ok(find(tree, "ValidationSummary")[0].props.error);
  assert.equal(body.values.escalation_percent, "5.1256"); assert.equal(body.row.version, 7); assert.equal(saved, 0);
  fail = false; await find(tree, "form")[0].props.onSubmit({ preventDefault() {} }); assert.equal(saved, 1);
});
