import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);

function mount(path, component, dependencies, props) {
  const slots = []; let cursor = 0; let effects = [];
  const react = {
    useRef(initial) { const i = cursor++; slots[i] ??= { current: initial }; return slots[i]; },
    useState(initial) { const i = cursor++; slots[i] ??= { value: initial }; return [slots[i].value, value => { slots[i].value = typeof value === "function" ? value(slots[i].value) : value; }]; },
    useEffect(fn, deps) { const i = cursor++; if (!slots[i] || deps.some((value, n) => value !== slots[i].deps[n])) effects.push(() => { slots[i]?.cleanup?.(); slots[i] = { deps, cleanup: fn() }; }); },
  };
  const code = ts.transpileModule(readFileSync(new URL(`../src/${path}`, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const exports = {};
  runInNewContext(`(function(require, exports) { ${code}\n})`)(name => {
    if (name === "react") return react;
    if (name in dependencies) return dependencies[name];
    if (name === "@/components/ui") return new Proxy({}, { get: (_, key) => key });
    return require(name);
  }, exports);
  return () => { cursor = 0; effects = []; const tree = exports[component](props); effects.forEach(fn => fn()); return tree; };
}
function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children)];
}
function field(tree, label) { return nodes(tree).find(node => node.type === "Field" && node.props.label === label).props.children; }

test("launch price entry omits Reason and keeps amount after a refused save", async () => {
  const calls=[];
  const render=mount("components/projects/inventory/unit/SellingPriceForm.tsx","SellingPriceForm",{
    "@/lib/api":{ApiError:Error,pricing:{createPriceVersion:async (...args)=>{calls.push(args);throw new Error("Approval measurement required");}}},
  },{projectId:"p",unitId:"u",currencyCode:"EUR",onChanged:async()=>{}});
  nodes(render()).find(node=>node.type==="Button").props.onClick();
  field(render(),"Selling price (EUR, ex tax)").props.onChange({target:{value:"125000.25"}});
  assert.ok(!nodes(render()).some(node=>node.type==="Field" && node.props.label==="Reason"));
  await nodes(render()).find(node=>node.type==="form").props.onSubmit({preventDefault(){}});
  assert.equal(calls[0][2].selling_price,"125000.25");
  assert.ok(!("change_reason" in calls[0][2]));
  assert.equal(field(render(),"Selling price (EUR, ex tax)").props.value,"125000.25");
});

test("Inventory release offers only Available and preserves server eligibility", () => {
  const moves=[];
  const unit={commercial_status:"unreleased",release_eligible:true,is_active:true,release_blockers:[]};
  const props={unit,roles:new Set(["master_admin"]),busy:false,onSaveControls:async()=>{},onTransition:move=>moves.push(move)};
  const render=mount("components/projects/inventory/unit/UnitRelease.tsx","UnitRelease",{
    "@/components/projects/EditForm":{EditForm:"EditForm",asValue:value=>value},
    "@/lib/format":{todayISO:()=>"2026-09-12",businessDate:value=>value},
  },props);
  const release=()=>nodes(render()).find(node=>node.type==="Button" && node.props.type==="submit");
  assert.equal(release().props.disabled,false);
  nodes(render()).find(node=>node.type==="form").props.onSubmit({preventDefault(){}});
  assert.equal(moves[0].to_status,"available");
  unit.release_eligible=false;
  assert.equal(release().props.disabled,true);
  unit.commercial_status="contracted";
  assert.equal(release(),undefined);
  assert.ok(!nodes(render()).some(node=>node.type==="select"));
});
