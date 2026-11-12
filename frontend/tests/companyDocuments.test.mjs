import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);

function harness() {
  const slots = []; let cursor = 0;
  const source = readFileSync(new URL("../src/components/projects/CompanyDocuments.tsx", import.meta.url), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const exports = {};
  let answer = { status: "loading", retry() {} };
  let enabled;
  class ApiError extends Error {}
  runInNewContext(`(function(require,exports){${code}\n})`, { Error })((key) => {
    if (key === "react") return { useState(initial) {
      const i = cursor++; slots[i] ??= { value: typeof initial === "function" ? initial() : initial };
      return [slots[i].value, value => { slots[i].value = value; }];
    }};
    if (key === "@/lib/format") return { businessDate: value => value };
    if (key === "@/lib/api") return { ApiError };
    if (key === "@/lib/api/companies") return { companyDocuments: {} };
    if (key === "@/lib/answer") return { useAnswer(gate) { enabled = gate; return answer; } };
    if (key === "@/lib/roles") return { PROJECT_FINANCIAL_READERS: new Set(["finance"]), hasAnyRole: (roles, allowed) => [...roles].some(role => allowed.has(role)) };
    if (key === "./CompanyDocuments") return { CompanyDocuments: "CompanyDocuments" };
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

test("document upload requires a label and file; failures retain the draft", async () => {
  const h = harness(); let saved; let closed = false;
  const props = { onSave: async (label, file) => { saved = { label, file }; throw new Error("Upload refused"); }, onClose() { closed = true; }, onSaved() {} };
  let tree = h.render("CompanyDocumentForm", props);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  tree = h.render("CompanyDocumentForm", props);
  assert.match(find(tree, "Notice")[0].props.children, /label/);
  find(tree, "input")[0].props.onChange({ target: { value: " Certificate of incorporation " } });
  tree = h.render("CompanyDocumentForm", props);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  tree = h.render("CompanyDocumentForm", props);
  assert.match(find(tree, "Notice")[0].props.children, /PDF/);
  const file = { name: "registration.pdf", size: 42 };
  find(tree, "input").find(node => node.props.type === "file").props.onChange({ target: { files: [file] } });
  tree = h.render("CompanyDocumentForm", props);
  assert.equal(find(tree, "DraftBoundary")[0].props.dirty, true);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  tree = h.render("CompanyDocumentForm", props);
  assert.equal(saved.label, "Certificate of incorporation");
  assert.equal(saved.file, file);
  assert.equal(closed, false);
  assert.equal(find(tree, "input")[0].props.value, " Certificate of incorporation ");
  assert.equal(find(tree, "Notice")[0].props.children, "Upload refused");
});

test("label edits keep the immutable file and close only after saving", async () => {
  const h = harness(); let saved; let closed = false; let refreshed = false;
  const props = { row: { id: "doc", label: "Old", filename: "original.pdf", version: 2 }, onSave: async (label, file) => { saved = { label, file }; }, onClose() { closed = true; }, onSaved() { refreshed = true; } };
  let tree = h.render("CompanyDocumentForm", props);
  assert.equal(find(tree, "input").filter(node => node.props.type === "file").length, 0);
  find(tree, "input")[0].props.onChange({ target: { value: "Trade licence" } });
  tree = h.render("CompanyDocumentForm", props);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  assert.equal(saved.label, "Trade licence");
  assert.equal(saved.file, null);
  assert.equal(closed && refreshed, true);
});

test("multiple labeled PDFs have independent edit and delete actions; readers can download", () => {
  const h = harness();
  h.setAnswer({ status: "ready", data: [{ id: "a", label: "Incorporation", filename: "one.pdf", version: 1 }, { id: "b", label: "Tax registration", filename: "two.pdf", version: 1 }] });
  let tree = h.render("CompanyDocuments", { projectId: "project", companyId: "company", canWrite: true });
  assert.equal(find(tree, "DeleteRecordButton").length, 2);
  assert.deepEqual(find(tree, "SectionHeader").map(node => node.props.title), ["Registration documents"]);
  assert.ok(find(tree, "CardRow").every(row => row.props.facts.length <= 3));
  assert.deepEqual(find(tree, "CardRow").map(node => node.props.title), ["Incorporation", "Tax registration"]);
  tree = h.render("CompanyDocuments", { projectId: "project", companyId: "company", canWrite: false });
  assert.equal(find(tree, "DeleteRecordButton").length, 0);
  assert.equal(find(tree, "Button").filter(node => node.props.children === "Download PDF").length, 2);
});



test("Drive source submits a link with optional metadata and no PDF", async () => {
  const h = harness(); let saved;
  const props = { onSave: async (...args) => { saved = args; }, onClose() {}, onSaved() {} };
  let tree = h.render("CompanyDocumentForm", props);
  find(tree, "input")[0].props.onChange({ target: { value: "Registration" } });
  tree = h.render("CompanyDocumentForm", props);
  find(tree, "ChoiceCards")[0].props.onChange("drive");
  tree = h.render("CompanyDocumentForm", props);
  assert.ok(!find(tree, "input").some(node => node.props.type === "file"));
  find(tree, "input").find(node => node.props.type === "url").props.onChange({ target: { value: "https://drive.google.com/file/d/example/view" } });
  tree = h.render("CompanyDocumentForm", props);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  assert.equal(saved[0], "Registration");
  assert.equal(saved[1], null);
  assert.equal(saved[2].expiry_date, null);
  assert.equal(saved[3], "https://drive.google.com/file/d/example/view");
});

test("Drive document renders an external link and renewal state without a download action", () => {
  const h = harness();
  h.setAnswer({ status: "ready", data: [{ id: "link", label: "Licence", filename: null, source_url: "https://drive.google.com/file/d/example/view", version: 1, reminder_status: "expired" }] });
  const tree = h.render("CompanyDocuments", { projectId: "project", companyId: "company", canWrite: true });
  assert.equal(find(tree, "ExternalLink")[0].props.href, "https://drive.google.com/file/d/example/view");
  assert.ok(!find(tree, "Button").some(node => String(node.props["aria-label"]).startsWith("Download PDF")));
  const row = find(tree, "CardRow")[0].props;
  assert.equal(row.flagged, true);
  const pill = h.exports.renewalState({ reminder_status: "expired" });
  assert.equal(pill.type, "Badge");
  assert.equal(pill.props.tone, "danger");
  assert.equal(pill.props.children, "Expired");
  assert.equal(h.exports.renewalState({ reminder_status: "renewal_due" }).props.children, "Renewal due");
  assert.equal(h.exports.renewalState({ reminder_status: null }), null);
});
