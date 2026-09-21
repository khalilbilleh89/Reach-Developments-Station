import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";

function mount(path, name, dependencies, props) {
  const slots = []; let cursor = 0;
  const react = {useState(initial) {const index = cursor++; if (!(index in slots)) slots[index] = typeof initial === "function" ? initial() : initial; return [slots[index], next => {slots[index] = typeof next === "function" ? next(slots[index]) : next;}];}};
  const jsx = {jsx: (type, props) => ({type, props}), jsxs: (type, props) => ({type, props})};
  const source = readFileSync(new URL(`../src/components/projects/${path}.tsx`, import.meta.url), "utf8");
  const exports = {};
  runInNewContext(ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS, jsx:ts.JsxEmit.ReactJSX}}).outputText, {exports, URLSearchParams, require: key => key === "react" ? react : key === "react/jsx-runtime" ? jsx : dependencies[key] ?? new Proxy({}, {get:(_, name) => name})});
  return () => {cursor = 0; return exports[name](props);};
}
const nodes = tree => !tree || typeof tree !== "object" ? [] : Array.isArray(tree) ? tree.flatMap(nodes) : [tree, ...nodes(tree.props?.children)];
const text = tree => tree == null ? "" : Array.isArray(tree) ? tree.map(text).join(" ") : typeof tree === "object" ? text(tree.props?.children) : String(tree);
const stage = (id, section="property_purchase") => ({id, label:id, section, position:0, source:"manual", is_active:true});
const data = {pipeline_version:2, stages:[stage("EOI"), stage("Visa", "golden_visa")], buyers:[], summaries:[], buyer_count:0, golden_visa_count:0, investment_count:0, purpose_unknown_count:0, can_configure:true, can_edit:true};
const buyer = {id:"buyer", number:"B001", name:"Synthetic Buyer", version:1, purpose:null, milestones:data.stages.map(s => ({stage_id:s.id, completed:null, completed_date:null, applicable:s.section === "property_purchase" ? true : null, source:"Operations", editable:true, total_sales:0, signed_sales:0}))};

test("reordering and renaming stages preserve the stable stage identities", async () => {
  let saved;
  const render = mount("operations/PipelineConfiguration", "PipelineConfiguration", {"@/lib/api/operations":{operations:{savePipeline:async (...args) => {saved=args;}}}}, {projectId:"p", data, onClose(){}, async onChanged(){}});
  nodes(render()).find(n => n.props?.["aria-label"] === "Move Visa up").props.onClick();
  nodes(render()).find(n => n.type === "input").props.onChange({target:{value:"Visa submitted"}});
  await nodes(render()).find(n => n.type === "form").props.onSubmit({preventDefault(){}});
  assert.equal(saved[2][0].id, "Visa");
  assert.equal(saved[2][0].label, "Visa submitted");
  assert.equal(saved[2][1].id, "EOI");
});

test("failed buyer save retains entered status, calendar date, purpose and reason", async () => {
  let submitted;
  const render = mount("operations/BuyerOperations", "BuyerOperations", {"@/lib/api":{ApiError:class extends Error {}}, "@/lib/api/operations":{operations:{saveBuyer:async (...args) => {submitted=args; throw Error("offline");}}}}, {projectId:"p", buyer, data, onClose(){}, async onChanged(){throw Error("Should not close");}});
  nodes(render()).filter(n => n.type === "select")[0].props.onChange({target:{value:"golden_visa"}});
  nodes(render()).filter(n => n.type === "select")[1].props.onChange({target:{value:"yes"}});
  nodes(render()).find(n => n.type === "input" && n.props.type === "date").props.onChange({target:{value:"2026-09-21"}});
  nodes(render()).find(n => n.type === "input" && n.props.maxLength === 1000).props.onChange({target:{value:"Verified original"}});
  await nodes(render()).find(n => n.type === "form").props.onSubmit({preventDefault(){}});
  assert.equal(submitted[4], "golden_visa");
  assert.equal(submitted[5][0].completed_date, "2026-09-21");
  assert.equal(nodes(render()).find(n => n.type === "input" && n.props.type === "date").props.value, "2026-09-21");
  assert.match(text(render()), /Could not save buyer progress/);
});

test("Sales signatures are read-only and investment-only visa controls are disabled", () => {
  const linked = {...buyer, purpose:"investment_only", milestones:[{...buyer.milestones[0], completed:true, completed_date:"2026-09-21", total_sales:2, signed_sales:2}, buyer.milestones[1]]};
  const render = mount("operations/BuyerOperations", "BuyerOperations", {"@/lib/format":{businessDate:value=>value}}, {projectId:"p", buyer:linked, data, onClose(){}, onChanged(){}});
  const selects = nodes(render()).filter(n => n.type === "select");
  assert.equal(selects[1].props.disabled, true);
  assert.equal(selects[2].props.disabled, true);
  assert.match(text(render()), /2\s+of\s+2\s+current purchases/);
  assert.match(text(render()), /Not applicable to Investment Only/);
});

test("denied and failed reads do not display zero-buyer analysis", () => {
  for (const answer of [{status:"denied"}, {status:"failed", message:"Unavailable", retry(){}}]) {
    const render = mount("OperationsTab", "OperationsTab", {"@/lib/answer":{useAnswer:()=>answer}, "@/lib/roles":{hasAnyRole:()=>true}}, {projectId:"p", roles:new Set()});
    assert.doesNotMatch(text(render()), /0 buyers/);
    assert.match(text(render()), /not available|Unavailable/);
  }
});
