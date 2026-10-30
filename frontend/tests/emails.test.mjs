import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";

function mount(path, name, dependencies, props, globals = {}) {
  const slots = []; let cursor = 0;
  const react = {useState(initial) {const index = cursor++; if (!(index in slots)) slots[index] = typeof initial === "function" ? initial() : initial; return [slots[index], next => {slots[index] = typeof next === "function" ? next(slots[index]) : next;}];}};
  const jsx = {jsx: (type, props) => ({type, props}), jsxs: (type, props) => ({type, props})};
  const source = readFileSync(new URL(`../src/components/projects/${path}.tsx`, import.meta.url), "utf8");
  const exports = {};
  runInNewContext(ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS, jsx:ts.JsxEmit.ReactJSX}}).outputText, {exports, URLSearchParams, ...globals, require: key => key === "react" ? react : key === "react/jsx-runtime" ? jsx : dependencies[key] ?? new Proxy({}, {get:(_, name) => name})});
  return () => {cursor = 0; return exports[name](props);};
}
const nodes = tree => !tree || typeof tree !== "object" ? [] : Array.isArray(tree) ? tree.flatMap(nodes) : [tree, ...nodes(tree.props?.children)];
const text = tree => tree == null ? "" : Array.isArray(tree) ? tree.map(text).join(" ") : typeof tree === "object" ? text(tree.props?.children) : String(tree);

const row = {id:"email-1", category:"internal", title:"Visit", subject:"Hello [Name]", body:"First line\nSecond line — مرحباً", version:2};

test("compose copies customized Unicode text without changing the saved template", async () => {
  let copied;
  const render = mount("EmailsTab", "EmailComposer", {}, {row, onClose(){}}, {navigator:{clipboard:{writeText:async value => {copied=value;}}}});
  nodes(render()).find(n=>n.type==="textarea").props.onChange({target:{value:"Dear Khalil\nمرحبا"}});
  await nodes(render()).find(n=>text(n)==="Copy body").props.onClick();
  assert.equal(copied,"Dear Khalil\nمرحبا");
  assert.equal(row.body,"First line\nSecond line — مرحباً");
  assert.match(text(render()),/Email body copied/);
  assert.equal(nodes(render()).find(n=>n.type==="DraftBoundary").props.dirty,true);
  await nodes(render()).find(n=>text(n)==="Copy entire email").props.onClick();
  assert.equal(copied,"Subject: Hello [Name]\n\nDear Khalil\nمرحبا");
});

test("clipboard failure provides manual copy and never reports success", async () => {
  const render = mount("EmailsTab", "EmailComposer", {}, {row, onClose(){}}, {navigator:{clipboard:{writeText:async()=>{throw Error("denied");}}}});
  await nodes(render()).find(n=>text(n)==="Copy subject").props.onClick();
  assert.match(text(render()),/copy it manually/);
  assert.doesNotMatch(text(render()),/Subject copied/);
});

test("categories and search narrow the library while readers can compose", () => {
  const rows=[row,{...row,id:"2",category:"clients",title:"Client response"}];
  const render = mount("EmailsTab", "EmailsTab", {"@/lib/answer":{useAnswer:()=>({status:"ready", data:{items:rows, can_edit:false}, retry(){}})}, "@/lib/roles":{hasAnyRole:()=>true}}, {projectId:"p", roles:new Set()});
  assert.equal(nodes(render()).filter(n=>n.type==="Card").length,1);
  assert.equal(nodes(render()).find(n=>n.type==="Card").props.title,"Visit");
  nodes(render()).find(n=>n.type==="Tabs").props.onSelect("clients");
  assert.equal(nodes(render()).find(n=>n.type==="Card").props.title,"Client response");
  nodes(render()).find(n=>n.type==="DataToolbar").props.search.onChange("missing");
  assert.equal(nodes(render()).find(n=>n.type==="EmptyState").props.title,"No matching templates");
  assert.ok(!nodes(render()).some(n=>n.type==="DeleteRecordButton"));
});

test("failed template saves retain draft and expected version", async () => {
  let saved,closed=false;
  class ApiError extends Error {}
  const render=mount("EmailsTab","EmailEditor",{"@/lib/api":{ApiError},"@/lib/api/emails":{emails:{update:async(...args)=>{saved=args;throw new ApiError("Changed. Reload first.");}}}}, {projectId:"p",row,category:"internal",onClose(){},async onSaved(){closed=true;}});
  nodes(render()).find(n=>n.type==="textarea").props.onChange({target:{value:"New\nbody"}});
  await nodes(render()).find(n=>n.type==="form").props.onSubmit({preventDefault(){}});
  assert.equal(saved[1].version,2);
  assert.equal(saved[2].body,"New\nbody");
  assert.equal(saved[2].category,"internal");
  assert.equal(closed,false);
  assert.equal(nodes(render()).find(n=>n.type==="textarea").props.value,"New\nbody");
  assert.match(text(render()),/Changed. Reload first/);
});
