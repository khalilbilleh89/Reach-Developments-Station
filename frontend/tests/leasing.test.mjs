import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);
const owner = { id: "00000000-0000-0000-0000-000000000001", display_name: "Synthetic owner", client_number: "C-1", is_active: true };
const source = { unit: { id: "00000000-0000-0000-0000-000000000002", unit_reference: "A-101", building: "A", floor: "1", is_active: true }, project_name: "Example development", currency_code: "EUR", sale_client: owner, sale_reference: "S-1" };
function harness(file, dependencies = {}) {
  const slots = []; let cursor = 0;
  const code = ts.transpileModule(readFileSync(new URL(`../src/components/leasing/${file}.tsx`, import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const exports = {};
  runInNewContext(`(function(require,exports){${code}\n})`)((key) => {
    if (key === "react") return { useState(initial) { const i=cursor++; slots[i] ??= { value: typeof initial === "function" ? initial() : initial }; return [slots[i].value, value => { slots[i].value=value; }]; } };
    if (key === "@/lib/api") return { ApiError: Error };
    if (key === "@/components/ui") return new Proxy({}, { get: (_, name) => name });
    if (key in dependencies) return dependencies[key];
    if (key === "@/lib/answer") return { useAnswer: () => ({status:"ready",data:[owner],retry(){}}) };
    if (key === "@/lib/api/leasing") return { LEASING_STAGES: [{key:"draft",label:"Instruction"}], leasing: {} };
    if (key.startsWith("@/") || key.startsWith("./")) return new Proxy({}, { get: (_, name) => name });
    return require(key);
  },exports);
  return { exports, render(name,props){cursor=0;return exports[name](props);} };
}
function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree,...nodes(tree.props?.children),...nodes(tree.props?.actions)];
}
const find=(tree,type)=>nodes(tree).filter(n=>n.type===type);

test("new leasing instruction prefills the sale buyer and preserves missing sources",()=>{
  const h=harness("LeasingEditor");
  assert.equal(h.exports.initialTerms(source).owner_client_id,owner.id);
  assert.equal(h.exports.initialTerms({...source,sale_client:null}).owner_client_id,null);
  assert.equal(h.exports.initialTerms(source).asking_rent_monthly,null);
  assert.equal(h.exports.initialTerms(source,{owner_client_id:null,status:"draft",asking_rent_monthly:"1000.01"}).owner_client_id,null);
});

test("failed save retains exact monetary input, owner and dirty form",async()=>{
  let sent;
  const h=harness("LeasingEditor",{"@/lib/api/leasing":{LEASING_STAGES:[{key:"draft",label:"Instruction"}],leasing:{create:async(project,unit,values)=>{sent={project,unit,values};throw Error("Save unavailable");}}}});
  const props={project:"project-id",source,onClose(){},onSaved(){throw Error("Must not close");}};
  let tree=h.render("TermsEditor",props);
  find(tree,"MoneyInput")[0].props.onChange("123456789.12");
  tree=h.render("TermsEditor",props);
  assert.equal(find(tree,"DraftBoundary")[0].props.dirty,true);
  await find(tree,"form")[0].props.onSubmit({preventDefault(){}});
  tree=h.render("TermsEditor",props);
  assert.equal(sent.values.asking_rent_monthly,"123456789.12");
  assert.equal(sent.values.owner_client_id,owner.id);
  assert.equal(find(tree,"MoneyInput")[0].props.value,"123456789.12");
  assert.equal(find(tree,"MoneyInput")[0].props.code,"EUR");
  assert.equal(find(tree,"Notice")[0].props.children,"Save unavailable");
});

test("register read failure remains an explicit retryable error",()=>{
  const h=harness("LeasingWorkspace");
  let retried=false;
  const tree=h.render("AnswerState",{answer:{status:"failed",message:"Unable to load",retry(){retried=true;}}});
  assert.equal(tree.type,"Notice");assert.equal(tree.props.tone,"error");
  find(tree,"Button")[0].props.onClick();assert.equal(retried,true);
  assert.equal(find(tree,"EmptyState").length,0);
});
