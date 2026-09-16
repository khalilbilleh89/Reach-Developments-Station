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
const textOf = tree => {
  if (tree == null || typeof tree === "boolean") return "";
  if (typeof tree !== "object") return String(tree);
  if (Array.isArray(tree)) return tree.map(textOf).join(" ");
  return textOf(tree.props?.children);
};

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

test("Inventory release states the date and never asks for a second confirmation", () => {
  const unit={commercial_status:"unreleased",release_eligible:false,is_active:true,
    release_blockers:["Pricing not approved"],pricing_approved:false,drawings_approved:false,legal_sale_eligible:false};
  const props={unit,roles:new Set(["master_admin"]),onSaveControls:async()=>{}};
  const render=mount("components/projects/inventory/unit/UnitRelease.tsx","UnitRelease",{
    "@/components/projects/EditForm":{EditForm:"EditForm",asValue:value=>value},
    "@/lib/format":{businessDate:value=>value},
  },props);
  // No release button and no release form: setting the date is the whole action.
  assert.equal(nodes(render()).find(node=>node.type==="form"),undefined);
  assert.equal(nodes(render()).find(node=>node.type==="Button" && node.props.type==="submit"),undefined);
  // While it is off the market the outstanding gates are named.
  assert.match(textOf(render()),/Pricing not approved/);
  // Once it is on sale the unit says so instead.
  unit.commercial_status="available"; unit.release_blockers=[];
  assert.match(textOf(render()),/on sale/);
  assert.ok(!nodes(render()).some(node=>node.type==="select"));
});
