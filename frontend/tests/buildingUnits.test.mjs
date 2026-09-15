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

test("unit placement follows the selected building and never invents a floor", async () => {
  const requests=[];
  const render=mount("components/projects/inventory/StructureViews.tsx","UnitForm",{
    "@/lib/format":{businessDate:()=>"2026-09-14"},
    "@/lib/api":{inventory:{createUnit:async(...args)=>requests.push(args)}},
    "@/components/projects/DeleteRecordButton":{DeleteRecordButton:"DeleteRecordButton"},
  },{projectId:"p",buildings:[{id:"villa",code:"V",name:"Villa",phase_id:"phase"},{id:"tower",code:"T",name:"Tower",phase_id:"phase"}],phases:[{id:"phase",code:"P"}],floors:[{id:"f",building_id:"tower",code:"1",label:"First"}],allFloors:[{id:"f",building_id:"tower",code:"1",label:"First"}],defaultFloorId:"",defaultBuildingId:"villa",onCancel:()=>{},onSaved:async()=>{}});
  const field=(label)=>nodes(render()).find(n=>n.type==="Field"&&n.props.label===label);
  const change=(label,value)=>nodes(field(label)).find(n=>n.type==="input"||n.type==="select").props.onChange({target:{value}});
  assert.equal(field("Floor"),undefined);
  change("Unit number","V1");change("Unit reference","VILLA-1");
  assert.equal(render().props.disabled,false);
  render().props.onSubmit();await new Promise(resolve=>setImmediate(resolve));
  assert.equal(requests[0][1].building_id,"villa");assert.ok(!("floor_id" in requests[0][1]));
  change("Building","tower");assert.ok(field("Floor"));assert.equal(render().props.disabled,true);
  change("Floor","f");assert.equal(render().props.disabled,false);
  render().props.onSubmit();await new Promise(resolve=>setImmediate(resolve));
  assert.equal(requests[1][1].floor_id,"f");assert.ok(!("building_id" in requests[1][1]));
});
