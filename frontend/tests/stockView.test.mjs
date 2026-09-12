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
const deps = {"@/lib/currency": {useCurrencyCode: () => id => id}, "@/lib/format": {money: (amount, currency) => `${currency} ${amount}`}};
const source = "components/projects/inventory/StockView.tsx";
function textOf(tree) { if (tree == null || typeof tree === "boolean") return ""; if (typeof tree !== "object") return String(tree); if (Array.isArray(tree)) return tree.map(textOf).join(" "); return textOf(tree.props?.children); }
const unit = {id:"u1",unit_reference:"A-101",phase_code:"P1",building_code:"A",floor_code:"01",is_active:true,bedrooms:2,bathrooms:1,asset_class:"residential",parking_count:0,storage_count:0,physical_components:{internal:{area:"90.1000",unit:"sqm"},balcony:{area:"0.0000",unit:"sqm"}},net_area:"90.1000",net_area_unit:"sqm",gross_area:null,gross_area_unit:null};
const register = {total:121,units:[unit]};
const prices = {priced_count:100,unpriced_count:21,repricing_count:2,totals:[{currency_id:"JOD",amount:"1000000.00"},{currency_id:"EUR",amount:"500000.00"}],rows:[{unit_id:"u1",price:"100000.00",currency_id:"JOD",repricing_required:false}]};
test("stock distinguishes zero and unknown measurements and uses the current launch price", () => {
 const tree=mount(source,"StockTable",deps,{projectId:"p",register,prices,seesPrice:true,priceError:null,expanded:false,onExpanded:()=>{}})();
 const cells=nodes(tree).filter(n=>n.type==="td").map(textOf);
 assert.ok(cells.includes("90.1 sqm")); assert.ok(cells.includes("0 sqm")); assert.ok(cells.includes("—")); assert.ok(cells.includes("JOD 100000.00"));
 const headings=nodes(tree).filter(n=>n.type==="th").map(textOf); assert.ok(!headings.includes("Roof garden")); assert.ok(!headings.includes("Status"));
});
test("stock expands optional areas and omits price cells for roles without pricing access", () => {
 const tree=mount(source,"StockTable",deps,{projectId:"p",register,prices:null,seesPrice:false,priceError:null,expanded:true,onExpanded:()=>{}})();
 const headings=nodes(tree).filter(n=>n.type==="th").map(textOf); assert.ok(headings.includes("Roof garden")); assert.ok(headings.includes("Front garden")); assert.ok(!headings.some(s=>s.includes("Launch price")));
});
test("stock totals use the entire selection and keep currencies separate", () => {
 const text=textOf(mount(source,"StockSummary",deps,{register,prices})());
 for(const value of ["121","100","21","JOD 1000000.00","EUR 500000.00"]) assert.ok(text.includes(value));
});
test("a stale launch price is labelled for review instead of displayed", () => {
 const tree=mount(source,"StockTable",deps,{projectId:"p",register,prices:{...prices,rows:[{...prices.rows[0],repricing_required:true}]},seesPrice:true,priceError:null,expanded:false,onExpanded:()=>{}})();
 assert.ok(textOf(tree).includes("Review price")); assert.ok(!textOf(tree).includes("JOD 100000.00"));
});
