import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
const require = createRequire(import.meta.url);
function load(path, dependencies = {}) {
  const exports = {};
  const code = ts.transpileModule(readFileSync(new URL(`../src/${path}`, import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  runInNewContext(`(function(require,exports){${code}\n})`)(key => key in dependencies ? dependencies[key] : require(key), exports);
  return exports;
}
const format = load("lib/format.ts");
const { ReportChart, reportValue } = load("components/projects/reports/ReportChart.tsx", { "@/lib/format": format });
const chart = { key:"cost",title:"Cost control",category:"Cash & cost",kind:"bars",unit:"EUR",points:[{label:"Budget",value:null,scale_percentage:"0",share_percentage:null},{label:"Outflow",value:"-123456789.01",scale_percentage:"100",share_percentage:null}],insight:"Separate measures.",source:"Construction register",note:"No budget recorded." };
test("report preserves exact money, negative values and unavailable inputs",()=>{
 assert.equal(reportValue("123456789012.99","EUR"),"EUR 123,456,789,012.99");
 const html=renderToStaticMarkup(React.createElement(ReportChart,{chart}));
 assert.ok(html.includes("Unavailable")); assert.ok(html.includes("EUR -123,456,789.01"));
 assert.ok(html.includes("No budget recorded.")); assert.ok(html.includes("Construction register"));
});
test("print chart includes every monthly amount without a collapsed disclosure",()=>{
 const html=renderToStaticMarkup(React.createElement(ReportChart,{chart:{...chart,kind:"columns"},print:true}));
 assert.ok(html.includes("report-print-values")); assert.ok(!html.includes("<details"));
 assert.ok(html.includes("EUR -123,456,789.01"));
});
test("empty report chart does not invent data",()=>{
 const html=renderToStaticMarkup(React.createElement(ReportChart,{chart:{...chart,points:[]}}));
 assert.ok(html.includes("No matching records")); assert.ok(!html.includes("<svg"));
});
