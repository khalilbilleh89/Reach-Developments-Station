import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);

function harness() {
  const slots = []; let cursor = 0;
  const source = readFileSync(new URL("../src/components/projects/AgreementsTab.tsx", import.meta.url), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const exports = {};
  let answer = { status: "loading", retry() {} };
  let enabled;
  class ApiError extends Error {}
  runInNewContext(`(function(require,exports){${code}\n})`)((key) => {
    if (key === "react") return { useState(initial) {
      const i = cursor++; slots[i] ??= { value: typeof initial === "function" ? initial() : initial };
      return [slots[i].value, value => { slots[i].value = value; }];
    }};
    if (key === "@/lib/api") return { ApiError };
    if (key === "@/lib/api/agreements") return { agreements: {} };
    if (key === "@/lib/answer") return { useAnswer(gate) { enabled = gate; return answer; } };
    if (key === "@/lib/format") return { businessDate: value => value };
    if (key === "@/lib/roles") return { AGREEMENT_READERS: new Set(["finance", "legal"]), AGREEMENT_WRITERS: new Set(["legal"]), hasAnyRole: (roles, allowed) => [...roles].some(role => allowed.has(role)) };
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


const row = { id: "cbf9322e-a76a-43ee-8f57-8aba0fa39011", name: "Purchase agreement", signing_company: "Example Ltd", draft_created_on: "2026-09-27", filename: "Final.pdf", version: 1 };

test("final draft register displays all four fields and writer edit/delete", () => {
 const h=harness();h.setAnswer({status:"ready",data:[row]});
 const tree=h.render("AgreementsTab",{projectId:"p",roles:new Set(["legal"])});
 assert.equal(h.enabled(),true);
 assert.deepEqual(find(tree,"th").map(n=>n.props.children),["Agreement name","Signing company","Draft creation date","Document","Actions",row.name]);
 assert.equal(find(tree,"time")[0].props.dateTime,row.draft_created_on);
 assert.equal(find(tree,"DeleteRecordButton")[0].props.recordName,row.name);
});

test("reader has download but no mutation controls; denied request is gated", () => {
 const h=harness();h.setAnswer({status:"ready",data:[row]});
 let tree=h.render("AgreementsTab",{projectId:"p",roles:new Set(["finance"])});
 assert.equal(find(tree,"DeleteRecordButton").length,0);
 assert.equal(find(tree,"Button").length,1);
 h.setAnswer({status:"off"});tree=h.render("AgreementsTab",{projectId:"p",roles:new Set(["design_engineering"])});
 assert.equal(h.enabled(),false);assert.equal(find(tree,"table").length,0);
});

test("failed and loading reads cannot appear as an empty register", () => {
 const h=harness();
 for (const status of ["failed","loading","denied"]) {
  h.setAnswer({status,message:"Network failure"});const tree=h.render("AgreementsTab",{projectId:"p",roles:new Set(["legal"])});
  assert.equal(find(tree,"EmptyState").length,0);
  assert.equal(find(tree,"PageHeader")[0].props.actions,undefined);
 }
});

test("new form requires a file and preserves typed values on failed save", async () => {
 const h=harness();let calls=0;let closed=false;
 const props={onSave:async()=>{calls++;throw new Error("Upload failed");},onSaved(){},onClose:()=>{closed=true;}};
 let tree=h.render("AgreementForm",props);
 await find(tree,"form")[0].props.onSubmit({preventDefault(){}});
 assert.equal(calls,0);
 find(tree,"input")[0].props.onChange({target:{value:"SPA"}});
 tree=h.render("AgreementForm",props);
 find(tree,"input").find(n=>n.props.type==="file").props.onChange({target:{files:[{name:"draft.pdf",size:10}]}});
 tree=h.render("AgreementForm",props);
 assert.equal(find(tree,"DraftBoundary")[0].props.dirty,true);
 await find(tree,"form")[0].props.onSubmit({preventDefault(){}});
 tree=h.render("AgreementForm",props);
 assert.equal(calls,1);assert.equal(closed,false);assert.equal(find(tree,"input")[0].props.value,"SPA");assert.equal(find(tree,"Notice").length,1);
});

test("editing submits date-only metadata, closes, then refreshes", async () => {
 const h=harness();let saved;const order=[];
 const props={row,onSave:async fields=>{saved=fields;},onClose:()=>{order.push("close");},onSaved:()=>{order.push("refresh");}};
 const tree=h.render("AgreementForm",props);
 assert.equal(find(tree,"input").filter(n=>n.props.type==="file").length,0);
 await find(tree,"form")[0].props.onSubmit({preventDefault(){}});
 assert.equal(saved.draft_created_on,"2026-09-27");assert.equal(saved.signing_company,"Example Ltd");assert.deepEqual(order,["close","refresh"]);
});
