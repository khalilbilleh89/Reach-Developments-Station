import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);
function harness() {
  const slots = []; let cursor = 0; const calls = []; let saved;
  const code = ts.transpileModule(readFileSync(new URL("../src/components/projects/land/ParcelDocumentForm.tsx", import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const exports = {};
  runInNewContext(`(function(require,exports){${code}\n})`, { Error, URL })((key) => {
    if (key === "react") return { useState(initial) { const i = cursor++; slots[i] ??= { value: initial }; return [slots[i].value, value => { slots[i].value = value; }]; } };
    if (key === "@/lib/api") return { projects: { uploadDocument: async (...args) => { calls.push(["pdf", ...args]); return { id: "saved-pdf" }; }, createDocument: async (...args) => { calls.push(["drive", ...args]); return { id: "saved-drive" }; } } };
    if (key === "@/lib/answer") return { useAnswer: () => ({ status: "ready", data: [{ id: "kind", code: "TITLE_DEED", label: "Title deed", is_active: true }] }) };
    if (key === "@/components/ui") return new Proxy({}, { get: (_, key) => key });
    return require(key);
  }, exports);
  return { calls, saved: () => saved, render() { cursor = 0; return exports.ParcelDocumentForm({projectId: "project", parcelId: "parcel", onClose() {}, onSaved(row) { saved = row; }}); } };
}
function nodes(tree) { if (!tree || typeof tree !== "object") return []; if (Array.isArray(tree)) return tree.flatMap(nodes); return [tree, ...nodes(tree.props?.children)]; }
const find = (tree, type) => nodes(tree).filter(node => node.type === type);
const field = (tree, label) => find(tree, "Field").find(node => node.props.label === label).props.children;
const submit = tree => find(tree, "form")[0].props.onSubmit({preventDefault() {}});
function fill(h) { field(h.render(), "Document name").props.onChange({target:{value:" Survey "}}); field(h.render(), "Document type").props.onChange({target:{value:"TITLE_DEED"}}); }
test("PDF source saves one named file with the current parcel", async () => {
  const h = harness(); fill(h); const file = { name: "survey.pdf", size: 100 };
  assert.equal(find(h.render(), "ChoiceCards")[0].props.value, "pdf");
  field(h.render(), "PDF file").props.onChange({target:{files:[file]}});
  await submit(h.render());
  assert.equal(h.calls[0][2].parcel_id, "parcel"); assert.equal(h.calls[0][2].title, "Survey"); assert.equal(h.calls[0][3], file); assert.equal(h.saved().id, "saved-pdf");
});
test("Drive selection swaps the input and rejects HTTP before saving HTTPS", async () => {
  const h = harness(); fill(h);
  find(h.render(), "ChoiceCards")[0].props.onChange("drive");
  assert.equal(find(h.render(), "input").filter(node => node.props.type === "file").length, 0);
  field(h.render(), "Google Drive link").props.onChange({target:{value:"http://drive.google.com/file/d/synthetic/view"}});
  await submit(h.render()); assert.equal(h.calls.length, 0); assert.match(find(h.render(), "Notice")[0].props.children, /HTTPS/);
  field(h.render(), "Google Drive link").props.onChange({target:{value:"https://drive.google.com/file/d/synthetic/view"}});
  await submit(h.render()); assert.equal(h.calls[0][0], "drive"); assert.equal(h.calls[0][2].parcel_id, "parcel"); assert.equal(h.saved().id, "saved-drive");
});
test("oversized PDF retains the draft without writing a record", async () => {
  const h = harness(); fill(h);
  field(h.render(), "PDF file").props.onChange({target:{files:[{name:"large.pdf",size:10*1024*1024+1}]}});
  await submit(h.render()); assert.equal(h.calls.length, 0); assert.match(find(h.render(), "Notice")[0].props.children, /10 MB/); assert.equal(field(h.render(), "Document name").props.value, " Survey ");
});
