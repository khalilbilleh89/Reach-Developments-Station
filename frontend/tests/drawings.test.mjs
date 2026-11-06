import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);

function harness() {
  const slots = []; let cursor = 0;
  const source = readFileSync(new URL("../src/components/projects/design/Drawings.tsx", import.meta.url), "utf8");
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
    if (key === "@/lib/api/drawings") return { drawings: {}, planCategories: {architecture: "Architectural", electrical: "Electrical", mechanical: "Mechanical", structure: "Structural", shop_drawing: "Shop Drawings"}, drawingCategories: {general: "General"}, drawingStatuses: {reference: "Reference"}, filterDrawings: rows => rows };
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

test("drawing upload requires a name and PDF; failures retain the draft", async () => {
  const h = harness(); let saved; let closed = false;
  const props = { onSave: async (fields, file) => { saved = { fields, file }; throw new Error("Upload refused"); }, onClose() { closed = true; }, onSaved() {} };
  let tree = h.render("DrawingForm", props);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  tree = h.render("DrawingForm", props);
  assert.match(find(tree, "Notice")[0].props.children, /title/);
  find(tree, "input")[0].props.onChange({ target: { value: " Certificate of incorporation " } });
  tree = h.render("DrawingForm", props);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  tree = h.render("DrawingForm", props);
  assert.match(find(tree, "Notice")[0].props.children, /PDF/);
  const file = { name: "registration.pdf", size: 42 };
  find(tree, "input").find(node => node.props.type === "file").props.onChange({ target: { files: [file] } });
  tree = h.render("DrawingForm", props);
  assert.equal(find(tree, "DraftBoundary")[0].props.dirty, true);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  tree = h.render("DrawingForm", props);
  assert.equal(saved.fields.name, "Certificate of incorporation");
  assert.equal(saved.file, file);
  assert.equal(closed, false);
  assert.equal(find(tree, "input")[0].props.value, " Certificate of incorporation ");
  assert.equal(find(tree, "Notice")[0].props.children, "Upload refused");
});

test("drawing metadata edits keep the immutable file and close only after saving", async () => {
  const h = harness(); let saved; let closed = false; let refreshed = false;
  const props = { row: { id: "doc", name: "Old", category: "general", drawing_number: "", location: "", revision: "", status: "reference", notes: "", filename: "original.pdf", version: 2 }, onSave: async (fields, file) => { saved = { fields, file }; }, onClose() { closed = true; }, onSaved() { refreshed = true; } };
  let tree = h.render("DrawingForm", props);
  assert.equal(find(tree, "input").filter(node => node.props.type === "file").length, 0);
  find(tree, "input")[0].props.onChange({ target: { value: "Trade licence" } });
  tree = h.render("DrawingForm", props);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  assert.equal(saved.fields.name, "Trade licence");
  assert.equal(saved.file, null);
  assert.equal(closed && refreshed, true);
});



test("drawing viewer keeps page bounds and zoom inside a full record page", () => {
  const h = harness();
  h.setAnswer({ status: "ready", data: {page_count: 2, image: "data:image/png;base64,test"} });
  const props = {projectId: "p", row: {id: "d", name: "Floor plan", category: "general", status: "reference", filename: "plan.pdf"}, onClose() {}};
  let tree = h.render("DrawingViewer", props);
  assert.equal(find(tree, "RecordPage").length, 1);
  const button = label => find(tree, "Button").find(node => node.props.children === label);
  assert.equal(button("Previous page").props.disabled, true);
  assert.equal(button("Next page").props.disabled, false);
  button("Next page").props.onClick();
  tree = h.render("DrawingViewer", props);
  assert.equal(button("Next page").props.disabled, true);
  find(tree, "Segmented").find(node => node.props.label === "Zoom").props.onChange("200");
  tree = h.render("DrawingViewer", props);
  assert.equal(find(tree, "img")[0].props.style.width, "200%");
  h.setAnswer({status:"failed", message:"Encrypted PDF"});
  tree = h.render("DrawingViewer", props);
  assert.equal(find(tree, "img").length, 0);
  assert.equal(find(tree, "Button").some(node => node.props.children === "Retry preview"), true);
});

test("drawing readers see review controls but no edit, upload or deletion", () => {
  const h = harness();
  h.setAnswer({status:"ready", data:[{id:"d", name:"Plan", category:"general", status:"reference", filename:"plan.pdf"}]});
  let tree = h.render("Drawings", {projectId:"p",canWrite:false});
  assert.equal(find(tree,"DeleteRecordButton").length,0);
  assert.equal(find(tree,"Button").some(node => node.props.children === "Add plan"), false);
  assert.equal(find(tree,"Button").some(node => node.props.children === "Open plan"), true);
  tree = h.render("Drawings", {projectId:"p",canWrite:true});
  assert.equal(find(tree,"DeleteRecordButton").length,1);
});

test("drawing search combines human references and filters", () => {
  const source = readFileSync(new URL("../src/lib/api/drawings.ts", import.meta.url), "utf8");
  const code = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  const exports = {};
  runInNewContext(`(function(require,exports){${code}\n})`, {}) (() => ({}), exports);
  const rows = [
    {id:"one", name:"Ground floor", category:"architecture", status:"issued", drawing_number:"A-101", location:"Block A", revision:"R02", filename:"one.pdf", notes:""},
    {id:"two", name:"Service plan", category:"mep", status:"superseded", drawing_number:"M-01", location:"Roof", revision:"R01", filename:"two.pdf", notes:""},
  ];
  assert.equal(exports.filterDrawings(rows," r02 ","architecture","issued")[0].id,"one");
  assert.equal(exports.filterDrawings(rows,"roof","mep","superseded")[0].id,"two");
  assert.equal(exports.filterDrawings(rows,"roof","architecture","").length,0);
});


test("plans expose the five disciplines and keep optional details out of required entry", () => {
  const h = harness();
  let tree = h.render("DrawingForm", { onSave() {}, onClose() {}, onSaved() {} });
  const choices = find(tree, "ChoiceCards")[0];
  assert.deepEqual(Array.from(choices.props.options, row => row.label), ["Architectural", "Electrical", "Mechanical", "Structural", "Shop Drawings"]);
  assert.equal(choices.props.value, "architecture");
  const required = find(tree, "input").filter(node => node.props.required);
  assert.equal(required.length, 2);
  assert.equal(find(tree, "Disclosure")[0].props.title, "More details (optional)");
});


test("plan viewer jumps to a valid page and rejects an out-of-range jump", () => {
  const h = harness();
  h.setAnswer({ status: "ready", data: {page_count: 2, image: "data:image/png;base64,test"} });
  const props = {projectId: "p", row: {id: "d", name: "Plan", category: "architecture", status: "reference", filename: "plan.pdf"}, onClose() {}};
  let tree = h.render("DrawingViewer", props);
  find(tree,"form")[0].props.onSubmit({preventDefault() {}, currentTarget: {page: "2"}});
  tree = h.render("DrawingViewer", props);
  assert.equal(find(tree,"input")[0].props.defaultValue,2);
  find(tree,"form")[0].props.onSubmit({preventDefault() {}, currentTarget: {page: "3"}});
  tree = h.render("DrawingViewer", props);
  assert.equal(find(tree,"input")[0].props.defaultValue,2);
});

test("standalone Plans gates the library before it mounts and grants only Design writers", () => {
  const source = readFileSync(new URL("../src/components/projects/PlansTab.tsx",import.meta.url),"utf8");
  const code = ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  const exports = {};
  runInNewContext(`(function(require,exports){${code}\n})`,{})((key) => {
    if(key === "@/components/ui") return {Notice:"Notice",PageHeader:"PageHeader"};
    if(key === "./design/Drawings") return {Drawings:"Drawings"};
    if(key === "@/lib/roles") return {CONSULTANT_READERS:new Set(["finance","project_manager"]),CONSULTANT_EDITORS:new Set(["project_manager"]),hasAnyRole:(roles,allowed)=>[...roles].some(role=>allowed.has(role))};
    return require(key);
  },exports);
  let tree = exports.PlansTab({projectId:"p",roles:new Set(["sales_advisor"])});
  assert.equal(find(tree,"Drawings").length,0);
  tree = exports.PlansTab({projectId:"p",roles:new Set(["finance"])});
  assert.equal(find(tree,"Drawings")[0].props.canWrite,false);
  tree = exports.PlansTab({projectId:"p",roles:new Set(["project_manager"])});
  assert.equal(find(tree,"Drawings")[0].props.canWrite,true);
});


test("Drive source accepts a link without a file and preserves failed drafts", async () => {
  const h = harness(); let saved;
  const props = {onSave: async (fields, file, sourceUrl) => { saved = {fields, file, sourceUrl}; throw new Error("Link refused"); }, onClose() {}, onSaved() {}};
  let tree = h.render("DrawingForm", props);
  find(tree,"input")[0].props.onChange({target:{value:"Electrical plan"}});
  find(tree,"ChoiceCards").find(node => node.props.name === "plan-source").props.onChange("drive");
  tree = h.render("DrawingForm", props);
  assert.equal(find(tree,"input").some(node => node.props.type === "file"),false);
  await find(tree,"form")[0].props.onSubmit({preventDefault(){}});
  tree = h.render("DrawingForm", props);
  assert.match(find(tree,"Notice")[0].props.children,/Drive/);
  find(tree,"input").find(node => node.props.type === "url").props.onChange({target:{value:"https://drive.google.com/file/d/test/view"}});
  tree = h.render("DrawingForm", props);
  assert.equal(find(tree,"DraftBoundary")[0].props.dirty,true);
  await find(tree,"form")[0].props.onSubmit({preventDefault(){}});
  assert.equal(saved.file,null);
  assert.equal(saved.sourceUrl,"https://drive.google.com/file/d/test/view");
  tree = h.render("DrawingForm", props);
  assert.equal(find(tree,"input").find(node => node.props.type === "url").props.value,saved.sourceUrl);
  assert.equal(find(tree,"Notice")[0].props.children,"Link refused");
});

test("linked plan opens Drive without requesting a PDF preview", () => {
  const h = harness();
  const row = {id:"d",name:"Drive plan",category:"general",status:"reference",filename:null,source_url:"https://drive.google.com/file/d/test/view"};
  const tree = h.render("LinkedDrawingViewer",{row,onClose(){}});
  assert.equal(h.enabled(),undefined);
  assert.equal(find(tree,"ExternalLink")[0].props.href,row.source_url);
  assert.equal(find(tree,"img").length,0);
});

test("PDF client allows 50 MB exactly and refuses one byte over without sending", async () => {
  const source = readFileSync(new URL("../src/lib/api/drawings.ts",import.meta.url),"utf8");
  const code = ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  const exports = {}; let sent = 0;
  runInNewContext(`(function(require,exports){${code}\n})`,{URLSearchParams})(() => ({postBinary:async()=>{sent++;}}),exports);
  await exports.drawings.create("p",{name:"Plan"},{name:"plan.pdf",size:50*1024*1024,arrayBuffer:async()=>new ArrayBuffer(0)});
  assert.equal(sent,1);
  await assert.rejects(exports.drawings.create("p",{name:"Plan"},{name:"plan.pdf",size:50*1024*1024+1}),/50 MB/);
  assert.equal(sent,1);
  assert.equal(exports.filterDrawings([{name:"Drive",category:"architecture",status:"reference",filename:null,source_url:"https://drive.google.com/file/d/test/view",drawing_number:"",location:"",revision:"",notes:""}],"test","","").length,1);
});
