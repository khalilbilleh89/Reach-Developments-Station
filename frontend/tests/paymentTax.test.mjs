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

const deps = {
 "@/lib/currency": {useCurrencyCode: () => id => id},
 "@/lib/format": {money: (value, code) => code + " " + value, percentInput: value => String(Number(value)*100), percent: value => String(Number(value)*100) + "%", businessDate: value => value},
 "@/components/projects/payments/labels": {DATE_BASED_TRIGGERS: new Set(["fixed_date"]), REFERENCE_TRIGGERS: new Set(), TRIGGER_TYPES: ["fixed_date"], triggerLabel: value => value, triggerStatusLabel: value => value, triggerStatusTone: () => "neutral"},
};
const source = "components/projects/payments/ScheduleEditor.tsx";
function textOf(tree) { if (tree == null || typeof tree === "boolean") return ""; if (typeof tree !== "object") return String(tree); if (Array.isArray(tree)) return tree.map(textOf).join(" "); return textOf(tree.props?.children); }

test("each installment has its own editable VAT percentage and saved amounts", () => {
 const changes=[]; const removed=[];
 const rows = [{key:"a",sequence:1,label:"First",trigger_type:"fixed_date",grace_days:"0",tax_rate_fraction:"19",tax_amount:"190.00",total_scheduled_amount:"1190.00"},{key:"b",sequence:2,label:"Second",trigger_type:"fixed_date",grace_days:"0",tax_rate_fraction:"0",tax_amount:"0.00",total_scheduled_amount:"1000.00"}];
 const tree=mount(source,"ScheduleEditor",deps,{rows,allocationMode:"percentage",chargeMode:"per_installment",currencyId:"EUR",milestones:[],onChange:(...args)=>changes.push(args),onRemove:key=>removed.push(key)})();
 const rates=nodes(tree).filter(n=>n.type==="RateInput" && n.props["aria-label"].startsWith("VAT"));
 assert.equal(rates.length,2); assert.equal(rates[0].props.value,"19"); assert.equal(rates[1].props.value,"0");
 rates[1].props.onChange("5"); assert.deepEqual(changes,[["b","tax_rate_fraction","5"]]);
 const content=textOf(tree); assert.ok(content.includes("EUR 190.00")); assert.ok(content.includes("EUR 0.00")); assert.ok(content.includes("EUR 1190.00"));
 nodes(tree).find(n=>n.type==="Button" && n.props["aria-label"]==="Remove instalment 2").props.onClick();
 assert.deepEqual(removed,["b"]);
});
test("settled rows distinguish an explicit zero rate from a legacy allocation", () => {
 const rows=[{id:"a",sequence:1,tax_rate_fraction:"0",tax_amount:"0.00",principal_amount:"1000.00",total_scheduled_amount:"1000.00"},{id:"b",sequence:2,tax_rate_fraction:null,tax_amount:"190.00",principal_amount:"1000.00",total_scheduled_amount:"1190.00"}];
 const tree=mount(source,"ScheduleTable",deps,{installments:rows,currencyId:"EUR"})();
 const cells=nodes(tree).filter(n=>n.type==="td").map(textOf);
 assert.ok(cells.includes("0%")); assert.ok(cells.includes("Legacy allocation")); assert.ok(cells.includes("EUR 1190.00"));
});
