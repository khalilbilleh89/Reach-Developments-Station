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

test("Identity and Features edit in their own sections and save only that section", async () => {
  const updates=[];let refreshed=0;
  const render=mount("components/projects/inventory/unit/UnitProperty.tsx","UnitProperty",{
    "@/lib/api":{inventory:{updateUnit:async (...args)=>updates.push(args)}},
    "@/components/projects/EditForm":{EditForm:"EditForm",asValue:value=>value},
    "./PhysicalRecord":{PhysicalRecord:"PhysicalRecord"},
  },{projectId:"p",unit:{id:"u",unit_reference:"A101",bedrooms:2,view_class_code:"Garden"},values:[],assets:[],schedules:[],areaTypes:[],canWrite:true,canApprove:true,onChanged:async()=>{refreshed++;}});
  function edit(title){nodes(render()).find(node=>node.type==="SectionHeader" && node.props.title===title).props.actions.props.onClick();}
  edit("Identity");
  let form=nodes(render()).find(node=>node.type==="EditForm");
  assert.ok(form.props.fields.some(field=>field.name==="bedrooms"));
  assert.ok(!form.props.fields.some(field=>field.name==="view_class_code"));
  assert.equal(nodes(render()).filter(node=>node.type==="EditForm").length,1);
  form.props.onCancel();
  assert.equal(updates.length,0);
  edit("Features");
  form=nodes(render()).find(node=>node.type==="EditForm");
  assert.ok(form.props.fields.some(field=>field.name==="view_class_code"));
  assert.ok(!form.props.fields.some(field=>field.name==="unit_reference"));
  await form.props.onSave({view_class_code:"Pool"});
  assert.equal(JSON.stringify(updates[0]),JSON.stringify(["p","u",{view_class_code:"Pool"}]));
  assert.equal(refreshed,1);
  assert.equal(nodes(render()).filter(node=>node.type==="EditForm").length,0);
});

test("read-only Property has no edit actions but retains attachments", () => {
  const render=mount("components/projects/inventory/unit/UnitProperty.tsx","UnitProperty",{
    "@/lib/api":{inventory:{}},"@/components/projects/EditForm":{EditForm:"EditForm",asValue:value=>value},"./PhysicalRecord":{PhysicalRecord:"PhysicalRecord"},
  },{projectId:"p",unit:{id:"u"},values:[],assets:[{id:"parking"}],schedules:[],areaTypes:[],canWrite:false,canApprove:false,onChanged:async()=>{}});
  assert.ok(nodes(render()).filter(node=>node.type==="SectionHeader").every(node=>node.props.actions===undefined));
  assert.equal(nodes(render()).find(node=>node.type==="PhysicalRecord").props.assets.length,1);
});

