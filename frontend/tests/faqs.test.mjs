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

const row = {id:"faq-1", question:"When can I visit?", answer:"First line\nSecond line — مرحباً", version:2};

test("copy sends only the exact saved answer and reports failure honestly", async () => {
  let copied;
  const render = mount("FaqTab", "FaqCard", {}, {row, projectId:"p", canEdit:false, onEdit(){}, onChanged(){}}, {navigator:{clipboard:{writeText:async value => {copied=value;}}}});
  await render().props.actions.props.onClick();
  assert.equal(copied,row.answer);
  assert.match(text(render()),/Answer copied/);
  assert.ok(!nodes(render()).some(n=>n.type==="DeleteRecordButton"));
  const failed = mount("FaqTab", "FaqCard", {}, {row, canEdit:false}, {navigator:{clipboard:{writeText:async()=>{throw Error("denied");}}}});
  await failed().props.actions.props.onClick();
  assert.match(text(failed()),/copy it manually/);
  assert.doesNotMatch(text(failed()),/Answer copied/);
});

test("search finds answer text and editing retains the row version", () => {
  const render = mount("FaqTab", "FaqTab", {"@/lib/answer":{useAnswer:()=>({status:"ready", data:{items:[row], can_edit:true}, retry(){}})}, "@/lib/roles":{hasAnyRole:()=>true}}, {projectId:"p", roles:new Set()});
  nodes(render()).find(n=>n.type==="DataToolbar").props.search.onChange("مرحبا");
  assert.equal(nodes(render()).filter(n=>typeof n.type==="function").length,1);
  nodes(render()).find(n=>n.type==="DataToolbar").props.search.onChange("missing");
  assert.equal(nodes(render()).find(n=>n.type==="EmptyState").props.title,"No matching FAQs");
});

test("save preserves multiline answer and failed saves retain the draft", async () => {
  let saved, closed=false;
  class ApiError extends Error {}
  const render=mount("FaqTab","FaqEditor",{"@/lib/api":{ApiError},"@/lib/api/faqs":{faqs:{update:async(...args)=>{saved=args;throw new ApiError("Changed. Reload first.");}}}}, {projectId:"p",row,onClose(){},async onSaved(){closed=true;}});
  nodes(render()).filter(n=>n.type==="textarea")[1].props.onChange({target:{value:"New\nanswer"}});
  await nodes(render()).find(n=>n.type==="form").props.onSubmit({preventDefault(){}});
  assert.equal(saved[1].version,2);
  assert.equal(saved[2].answer,"New\nanswer");
  assert.equal(closed,false);
  assert.equal(nodes(render()).filter(n=>n.type==="textarea")[1].props.value,"New\nanswer");
  assert.match(text(render()),/Changed. Reload first/);
});

test("failed and denied FAQ loads never pretend the library is empty", () => {
  for(const result of [{status:"failed",message:"Unavailable",retry(){}},{status:"denied"}]) {
    const render=mount("FaqTab","FaqTab",{"@/lib/answer":{useAnswer:()=>result},"@/lib/roles":{hasAnyRole:()=>true}}, {projectId:"p",roles:new Set()});
    assert.ok(!nodes(render()).some(n=>n.type==="EmptyState"));
  }
});
