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

test("one Property edit opens identity, features and the complete physical editor", async () => {
  const updates=[];
  const render=mount("components/projects/inventory/unit/UnitProperty.tsx","UnitProperty",{
    "@/lib/api":{inventory:{configuration:async()=>[],updateUnit:async(...args)=>updates.push(args)}},
    "@/components/projects/EditForm":{EditForm:"EditForm",asValue:value=>value},
    "./PhysicalRecord":{PhysicalRecord:"PhysicalRecord"},
  },{projectId:"p",unit:{id:"u",unit_reference:"A101",bedrooms:2},values:[],assets:[],schedules:[],areaTypes:[],canWrite:true,canApprove:true,onChanged:async()=>{}});
  render();await Promise.resolve();
  const edit=nodes(render()).find(n=>n.type==="SectionHeader"&&n.props.title==="Property").props.actions;
  assert.equal(edit.props.disabled,false);edit.props.onClick();
  const form=nodes(render()).find(n=>n.type==="EditForm");
  assert.equal(form.props.closeOnSave,false);
  assert.ok(form.props.fields.some(f=>f.name==="unit_reference"));
  assert.ok(form.props.fields.some(f=>f.name==="view_class_code"));
  assert.equal(nodes(render()).find(n=>n.type==="PhysicalRecord").props.masterEditing,true);
  await form.props.onSave({bedrooms:3,view_class_code:"SEA"});
  assert.equal(JSON.stringify(updates[0]),JSON.stringify(["p","u",{bedrooms:3,view_class_code:"SEA"}]));
  assert.equal(nodes(render()).find(n=>n.type==="PhysicalRecord").props.masterEditing,true);
});

test("read-only Property has no edit actions but retains attachments", () => {
  const render=mount("components/projects/inventory/unit/UnitProperty.tsx","UnitProperty",{
    "@/lib/api":{inventory:{configuration:async()=>[]}},"@/components/projects/EditForm":{EditForm:"EditForm",asValue:value=>value},"./PhysicalRecord":{PhysicalRecord:"PhysicalRecord"},
  },{projectId:"p",unit:{id:"u"},values:[],assets:[{id:"parking"}],schedules:[],areaTypes:[],canWrite:false,canApprove:false,onChanged:async()=>{}});
  assert.ok(nodes(render()).filter(node=>node.type==="SectionHeader").every(node=>node.props.actions===undefined));
  assert.equal(nodes(render()).find(node=>node.type==="PhysicalRecord").props.assets.length,1);
});


test("configured unit fields use project choices and preserve only the current inactive choice", async () => {
  const requests=[];
  const render=mount("components/projects/inventory/unit/UnitProperty.tsx","UnitProperty",{
    "@/lib/api":{inventory:{configuration:async id=>{requests.push(id);return [{category:"view_class",code:"SEA",label:"Sea view",is_active:true},{category:"view_class",code:"OLD",label:"Old garden",is_active:false},{category:"view_class",code:"RETIRED",label:"Retired other",is_active:false},{category:"orientation",code:"N",label:"North",is_active:true}];}}},
    "@/components/projects/EditForm":{EditForm:"EditForm",asValue:value=>value},
    "./PhysicalRecord":{PhysicalRecord:"PhysicalRecord"},
  },{projectId:"project-a",unit:{id:"u",view_class_code:"OLD"},values:[],assets:[],schedules:[],areaTypes:[],canWrite:true,canApprove:true,onChanged:async()=>{}});
  assert.equal(nodes(render()).find(n=>n.type==="SectionHeader" && n.props.title==="Property").props.actions.props.disabled,true);
  await Promise.resolve();
  const edit=nodes(render()).find(n=>n.type==="SectionHeader" && n.props.title==="Property").props.actions;
  assert.equal(edit.props.disabled,false); edit.props.onClick();
  const fields=nodes(render()).find(n=>n.type==="EditForm").props.fields;
  const view=fields.find(f=>f.name==="view_class_code");
  assert.equal(view.kind,"select");
  assert.equal(JSON.stringify(view.options.map(o=>o.value)),JSON.stringify(["","SEA","OLD"]));
  assert.equal(view.options[1].label,"Sea view");
  const orientation=fields.find(f=>f.name==="orientation_code");
  assert.equal(JSON.stringify(orientation.options.map(o=>o.value)),JSON.stringify(["","N"]));
  assert.deepEqual(requests,["project-a"]);
});


test("correcting an existing selling price prefills it and creates a replacement version", async () => {
  const requests=[];
  const render=mount("components/projects/inventory/unit/SellingPriceForm.tsx","SellingPriceForm",{
    "@/lib/api":{ApiError:class extends Error{},pricing:{createPriceVersion:async(...args)=>requests.push(args)}},
  },{projectId:"p",unitId:"u",currencyCode:"EUR",currentAmount:"125000.00",isMasterAdmin:true,onChanged:async()=>{}});
  assert.equal(render().props.children,"Edit selling price");render().props.onClick();
  const amount=nodes(render()).find(n=>n.type==="input"&&n.props.value==="125000.00");
  assert.ok(amount);amount.props.onChange({target:{value:"150000.00"}});
  await render().props.onSubmit({preventDefault(){}});
  assert.equal(JSON.stringify(requests),JSON.stringify([["p","u",{selling_price:"150000.00",valid_from:null}]]));
});

test("unit overview resolves project labels and shows recorded gardens", async () => {
  const render=mount("components/projects/inventory/unit/UnitSummary.tsx","UnitSummary",{
    "@/lib/api":{inventory:{configuration:async()=>[{category:"view_class",code:"S",label:"Sea view"},{category:"sub_asset_subtype",code:"CP",label:"Covered parking"}],subAssets:async()=>[{is_active:true,asset_type:"parking",subtype_code:"CP",asset_reference:"P1"}]}},
    "@/lib/currency":{useCurrencyCode:()=>"EUR"},"@/lib/format":{businessDate:()=>"2026-09-14"},
    "@/components/projects/collections/labels":{},"@/components/projects/sales/labels":{},
  },{projectId:"p",unit:{id:"u",asset_class:"villa",view_class_code:"S",orientation_code:null,garden_class_code:null,parking_count:1,storage_count:0,area_lines:[{physical_component:"roof_garden",raw_area:"20",unit_of_measure:"sqm"}]},pricing:{status:"off"},onOpenTab:()=>{}});
  render();await new Promise(resolve=>setImmediate(resolve));
  const value=label=>nodes(render()).find(n=>n.type==="KeyValue"&&n.props.label===label)?.props.value;
  assert.equal(value("View / orientation"),"Sea view · Not recorded");
  assert.equal(value("Parking types"),"Covered parking · P1");
  assert.equal(value("Roof garden"),"Yes · 20 sqm");
  assert.equal(value("Front garden"),"Not recorded");
});
