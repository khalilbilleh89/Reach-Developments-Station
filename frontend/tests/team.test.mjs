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
const member = { id: "person", project_id: "project", team: "engineering", name: "Example Engineer", title: "Architect", scope_of_work: "Coordinate façade drawings", email: "engineer@example.test", version: 7 };

test("directory searches scope and separates teams while retaining search after editing", () => {
  let retries = 0;
  const render = harness("TeamTab", {
    "@/lib/api/team": { team: {} },
    "@/lib/answer": { useAnswer: () => ({ status: "ready", data: { members: [member], can_manage: true }, retry() { retries++; } }) },
  });
  const props = { projectId: "project" };
  let tree = render("TeamTab", props);
  find(tree, "DataToolbar")[0].props.search.onChange("façade");
  tree = render("TeamTab", props);
  assert.equal(find(tree, "TeamSection")[0].props.members.length, 0);
  const engineering = find(tree, "TeamSection")[1];
  assert.equal(engineering.props.members.length, 1);
  engineering.props.onEdit(member);
  tree = render("TeamTab", props);
  assert.equal(find(tree, "TeamMemberForm")[0].props.member.version, 7);
  find(tree, "TeamMemberForm")[0].props.onSaved(member.name);
  tree = render("TeamTab", props);
  assert.equal(find(tree, "DataToolbar")[0].props.search.value, "façade");
  assert.equal(find(tree, "TeamMemberForm").length, 0);
  assert.equal(retries, 1);
});

test("failed reads are not shown as empty teams and readers get no add action", () => {
  let answer = { status: "failed", message: "Unavailable", retry() {} };
  const render = harness("TeamTab", { "@/lib/api/team": { team: {} }, "@/lib/answer": { useAnswer: () => answer } });
  let tree = render("TeamTab", { projectId: "project" });
  assert.equal(find(tree, "TeamSection").length, 0);
  assert.equal(find(tree, "Notice")[0].props.tone, "error");
  answer = { ...answer, status: "ready", data: { members: [member], can_manage: false } };
  tree = render("TeamTab", { projectId: "project" });
  assert.equal(find(tree, "PageHeader")[0].props.actions, undefined);
  assert.ok(find(tree, "TeamSection").every(section => !section.props.canManage));
});

test("all members stay reachable through pagination and deletion uses the saved version", async () => {
  let removed;
  const render = harness("team/TeamSection", { "@/lib/api/team": { team: { remove: async (...args) => { removed = args; } } } });
  const props = { projectId: "project", kind: "engineering", members: Array.from({ length: 29 }, (_, i) => ({ ...member, id: `person-${i}` })), query: "", canManage: true, onDeleted: async () => {} };
  let tree = render("TeamSection", props);
  assert.equal(find(tree, "Card").length, 12);
  find(tree, "RegisterPagination")[0].props.onChange(24);
  tree = render("TeamSection", props);
  assert.equal(find(tree, "Card").length, 5);
  await find(tree, "DeleteRecordButton")[0].props.onDelete("Left project");
  assert.equal(removed[1].id, "person-24");
  assert.equal(removed[1].version, 7);
  assert.equal(removed[2], "Left project");
  tree = render("TeamSection", { ...props, query: "Architect" });
  assert.equal(find(tree, "RegisterPagination")[0].props.offset, 0);
  tree = render("TeamSection", { ...props, canManage: false });
  assert.equal(find(tree, "DeleteRecordButton").length, 0);
});

test("member editor retains failures, submits every field and protects the draft", async () => {
  class ApiError extends Error {}
  let saved; let fail = true; let closed = false;
  const render = harness("team/TeamMemberForm", {
    "@/lib/api": { ApiError },
    "@/lib/api/team": { team: { update: async (...args) => { saved = args; if (fail) throw new ApiError("Conflict"); return member; } } },
  });
  const props = { projectId: "project", initialTeam: "engineering", member, onSaved() { closed = true; }, onClose() {} };
  let tree = render("TeamMemberForm", props);
  const scope = find(tree, "textarea")[0];
  scope.props.onChange({ target: { value: "Updated scope\nSecond line" } });
  tree = render("TeamMemberForm", props);
  assert.equal(find(tree, "DraftBoundary")[0].props.dirty, true);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  tree = render("TeamMemberForm", props);
  assert.equal(find(tree, "ValidationSummary")[0].props.error.message, "Conflict");
  assert.equal(find(tree, "textarea")[0].props.value, "Updated scope\nSecond line");
  assert.equal(closed, false);
  fail = false;
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  assert.equal(saved[1].version, 7);
  assert.equal(saved[2].scope_of_work, "Updated scope\nSecond line");
  assert.equal(saved[2].email, member.email);
  assert.equal(closed, true);
});
