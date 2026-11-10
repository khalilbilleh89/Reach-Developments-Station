import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);

function harness() {
  const slots = []; let cursor = 0;
  const source = readFileSync(new URL("../src/components/projects/reports/ReportDocuments.tsx", import.meta.url), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const exports = {};
  let answer = { status: "loading", retry() {} };
  let enabled;
  class ApiError extends Error {}
  runInNewContext(`(function(require,exports){${code}\n})`, { Error, FormData: class { constructor(form) { this.form = form; } get(key) { return this.form[key]; } } })((key) => {
    if (key === "react") return { useState(initial) {
      const i = cursor++; slots[i] ??= { value: typeof initial === "function" ? initial() : initial };
      return [slots[i].value, value => { slots[i].value = value; }];
    }};
    if (key === "@/lib/api") return { ApiError };
    if (key === "@/lib/format") return { businessDate: value => value };
    if (key === "@/lib/api/siteReports") return { drawings: {}, planCategories: {architecture: "Architectural", electrical: "Electrical", mechanical: "Mechanical", structure: "Structural", shop_drawing: "Shop Drawings"}, drawingCategories: {general: "General"}, drawingStatuses: {reference: "Reference"}, filterDrawings: rows => rows };
    if (key === "@/lib/answer") return { useAnswer(gate) { enabled = gate; return answer; } };
    if (key === "@/lib/roles") return { PROJECT_FINANCIAL_READERS: new Set(["finance"]), hasAnyRole: (roles, allowed) => [...roles].some(role => allowed.has(role)) };
    if (key === "./CompanyDocuments") return { CompanyDocuments: "CompanyDocuments" };
    if (key === "../DeleteRecordButton") return { DeleteRecordButton: "DeleteRecordButton" };
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

test("report requires a title and date; failed PDF uploads retain the draft", async () => {
  const h = harness(); let saved; let closed = false;
  const props = { onSave: async (fields, file) => { saved = { fields, file }; throw new Error("Upload refused"); }, onClose() { closed = true; }, onSaved() {} };
  let tree = h.render("SiteReportForm", props);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  tree = h.render("SiteReportForm", props);
  assert.match(find(tree, "Notice")[0].props.children, /title/);
  find(tree, "input")[0].props.onChange({ target: { value: " Certificate of incorporation " } });
  tree = h.render("SiteReportForm", props);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  tree = h.render("SiteReportForm", props);
  assert.match(find(tree, "Notice")[0].props.children, /date/);
  find(tree, "input").find(node => node.props.type === "date").props.onChange({ target: { value: "2026-11-10" } });
  tree = h.render("SiteReportForm", props);
  const file = { name: "registration.pdf", size: 42 };
  find(tree, "input").find(node => node.props.type === "file").props.onChange({ target: { files: [file] } });
  tree = h.render("SiteReportForm", props);
  assert.equal(find(tree, "DraftBoundary")[0].props.dirty, true);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  tree = h.render("SiteReportForm", props);
  assert.equal(saved.fields.title, "Certificate of incorporation");
  assert.equal(saved.fields.report_date, "2026-11-10");
  assert.equal(saved.file, file);
  assert.equal(closed, false);
  assert.equal(find(tree, "input")[0].props.value, " Certificate of incorporation ");
  assert.equal(find(tree, "Notice")[0].props.children, "Upload refused");
});

test("report metadata edits keep the immutable file and close only after saving", async () => {
  const h = harness(); let saved; let closed = false; let refreshed = false;
  const props = { row: { id: "doc", title: "Old", report_date: "2026-11-10", category: "general", drawing_number: "", location: "", revision: "", status: "reference", notes: "", filename: "original.pdf", version: 2 }, onSave: async (fields, file) => { saved = { fields, file }; }, onClose() { closed = true; }, onSaved() { refreshed = true; } };
  let tree = h.render("SiteReportForm", props);
  assert.equal(find(tree, "input").filter(node => node.props.type === "file").length, 0);
  find(tree, "input")[0].props.onChange({ target: { value: "Trade licence" } });
  tree = h.render("SiteReportForm", props);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  assert.equal(saved.fields.title, "Trade licence");
  assert.equal(saved.file, null);
  assert.equal(closed && refreshed, true);
});




test("report link creation submits the date and URL without a PDF", async () => {
  const h = harness(); let saved;
  const props = { onSave: async (...args) => { saved = args; }, onClose() {}, onSaved() {} };
  let tree = h.render("SiteReportForm", props);
  find(tree, "input")[0].props.onChange({ target: { value: "Site visit" } });
  tree = h.render("SiteReportForm", props);
  find(tree, "input").find(node => node.props.type === "date").props.onChange({ target: { value: "2026-10-31" } });
  find(tree, "ChoiceCards")[0].props.onChange("drive");
  tree = h.render("SiteReportForm", props);
  assert.equal(find(tree, "input").some(node => node.props.type === "file"), false);
  find(tree, "input").find(node => node.props.type === "url").props.onChange({ target: { value: "https://drive.google.com/file/d/demo/view" } });
  tree = h.render("SiteReportForm", props);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  assert.equal(saved[0].report_date, "2026-10-31");
  assert.equal(saved[1], null);
  assert.equal(saved[2], "https://drive.google.com/file/d/demo/view");
});
