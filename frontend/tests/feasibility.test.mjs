import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

const require=createRequire(import.meta.url);
const code=ts.transpileModule(readFileSync(new URL("../src/components/dashboard/FeasibilityView.tsx",import.meta.url),"utf8"),{
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX},
}).outputText;
const exports={};
runInNewContext(`(function(require,exports){${code}\n})`)(name=>{
  if(name==="@/lib/format") return {businessDate:value=>value};
  if(name==="@/components/ui") return new Proxy({}, {get:()=>props=>React.createElement("div",null,props.title,props.label,props.value,props.description,props.note,props.children)});
  return require(name);
},exports);
const measurement=value=>({value,measured_count:value===null?0:1,expected_count:1,reason:value===null?"Record measurement":null,formula:"Server source formula"});
function data(value){
  const keys=["covered","internal","balcony","terrace","common","total","garage","building","community","roads_pavements","grand","buildable"];
  const values=Object.fromEntries(keys.map(key=>[key,measurement(value)]));
  return {context:{snapshot_as_of:"2026-09-12"},apartments:1,other_units:0,totals:values,averages:values,
    groups:[{unit_type:"Studio",bedrooms:0,apartments:1,areas:values}],
    efficiencies:[{label:"Internal / buildable efficiency",percentage:null,numerator:null,denominator:null,formula:"Internal / buildable",reason:"Missing denominator"}],notes:["Current snapshot"]};
}
test("Feasibility renders every requested area family and studio grouping using server values",()=>{
  const html=renderToStaticMarkup(React.createElement(exports.FeasibilityView,{data:data("123.4500")}));
  for(const label of ["Number of Apartments","Total Buildable Area","Total Garage Area","Grand Total Area","Total Roads &amp; Pavements Area","Average Apartment Common Area","Average Apartment Total Area","Studio (0)","123.4500 m²"]) assert.ok(html.includes(label),label);
});
test("missing area and undefined efficiency are not rendered as zero",()=>{
  const missing=renderToStaticMarkup(React.createElement(exports.FeasibilityView,{data:data(null)}));
  assert.ok(missing.includes("Not recorded / incomplete"));assert.ok(missing.includes("Unavailable"));
  assert.ok(missing.includes("Record measurement"));assert.ok(!missing.includes("NaN"));assert.ok(!missing.includes("0.0000 m²"));
  const zero=renderToStaticMarkup(React.createElement(exports.FeasibilityView,{data:data("0.0000")}));
  assert.ok(zero.includes("0.0000 m²"));
});
