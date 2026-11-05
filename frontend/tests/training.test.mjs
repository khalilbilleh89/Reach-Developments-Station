import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);

function harness(file, dependencies = {}) {
  const slots = []; let cursor = 0;
  const source = readFileSync(new URL(`../src/components/projects/${file}.tsx`, import.meta.url), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const exports = {};
  class ApiError extends Error {}
  runInNewContext(`(function(require,exports){${code}\n})`)((key) => {
    if (key === "react") return { useState(initial) { const i = cursor++; slots[i] ??= { value: typeof initial === "function" ? initial() : initial }; return [slots[i].value, value => { slots[i].value = value; }]; } };
    if (key === "@/lib/api") return { ApiError };
    if (key === "@/components/ui") return new Proxy({}, { get: (_, name) => name });
    if (key in dependencies) return dependencies[key];
    if (key === "@/lib/currency") return { useCurrencyCode: () => id => id === "00000000-0000-0000-0000-000000000001" ? "EUR" : null };
    if (key.startsWith("@/") || key.startsWith("./") || key.startsWith("../")) return new Proxy({}, { get: (_, name) => name });
    return require(key);
  }, exports);
  return { exports, render(name, props) { cursor = 0; return exports[name](props); } };
}
function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children), ...nodes(tree.props?.actions)];
}
const find = (tree, type) => nodes(tree).filter(node => node.type === type);


test("training preserves metadata and upload after save failure", async () => {
 const h=harness("TrainingTab"); let sent;
 const props={categories:[],onClose(){},onSave:async(values,file)=>{sent={values,file};throw new Error("offline");}};
 let tree=h.render("AssetEditor",props);
 const field=(tree,label)=>find(tree,"Field").find(n=>n.props.label===label);
 field(tree,"Title").props.children.props.onChange({target:{value:"Safety induction"}});
 tree=h.render("AssetEditor",props);
 find(tree,"input").find(n=>n.props.list).props.onChange({target:{value:"Site safety"}});
 tree=h.render("AssetEditor",props);
 field(tree,"Execution date").props.children.props.onChange({target:{value:"2026-11-05"}});
 tree=h.render("AssetEditor",props);
 field(tree,"Training description").props.children.props.onChange({target:{value:"Emergency procedures"}});
 tree=h.render("AssetEditor",props);
 const file={name:"training.pdf",size:80};
 find(tree,"input").find(n=>n.props.type==="file").props.onChange({target:{files:[file]}});
 tree=h.render("AssetEditor",props);
 await find(tree,"form")[0].props.onSubmit({preventDefault(){}});
 assert.equal(sent.values.execution_date,"2026-11-05"); assert.equal(sent.values.category,"Site safety"); assert.equal(sent.values.description,"Emergency procedures"); assert.equal(sent.file,file);
 tree=h.render("AssetEditor",props); assert.equal(find(tree,"DraftBoundary")[0].props.dirty,true); assert.ok(find(tree,"Notice").length);
});
test("training link submission carries all fields without upload", async()=>{
 const h=harness("TrainingTab"); let sent;
 const props={categories:[],onClose(){},onSave:async(values,file)=>{sent={values,file};}};
 let tree=h.render("AssetEditor",props);
 find(tree,"select").find(n=>n.props.value==="upload").props.onChange({target:{value:"link"}});
 tree=h.render("AssetEditor",props);
 find(tree,"input").find(n=>n.props.type==="url").props.onChange({target:{value:"https://drive.google.com/file/d/example/view"}});
 tree=h.render("AssetEditor",props);
 await find(tree,"form")[0].props.onSubmit({preventDefault(){}});
 assert.equal(sent.file,null); assert.equal(sent.values.external_url,"https://drive.google.com/file/d/example/view");
});
test("training rejects oversized PDFs before saving",async()=>{
 const h=harness("TrainingTab");let calls=0;
 const props={categories:[],onClose(){},onSave:async()=>{calls++;}};
 let tree=h.render("AssetEditor",props);
 const input=find(tree,"input").find(n=>n.props.type==="file"); assert.equal(input.props.accept,".pdf");
 input.props.onChange({target:{files:[{name:"big.pdf",size:11*1024*1024}]}});
 tree=h.render("AssetEditor",props); await find(tree,"form")[0].props.onSubmit({preventDefault(){}});
 assert.equal(calls,0);assert.ok(find(h.render("AssetEditor",props),"Notice").length);
});
