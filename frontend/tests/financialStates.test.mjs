import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { createRequire } from "node:module";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
const h = React.createElement;
// Render the real conditional components. Presentation primitives are reduced
// to their visible facts so tests assert the decision a reader is offered.
const ui = new Proxy({}, { get: (_, name) => props => h(name === "Button" ? "button" : "section", { "data-tone": props.tone },
  props.title, props.label, props.value, props.note, props.description, props.children) });
function load(path, imports = {}) {
  const exports = {};
  const code = ts.transpileModule(readFileSync(new URL(path, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  runInNewContext(`(function(require, exports) { ${code}\n})`)(name => {
    if (name in imports) return imports[name];
    if (name === "@/components/ui") return ui;
    if (name.startsWith("@/") || name.startsWith("./")) return {};
    return require(name);
  }, exports);
  return exports;
}
const format = load("../src/lib/format.ts");
const imports = { "@/lib/format": format, "./labels": load("../src/components/projects/cashflow/labels.ts") };
const { CashflowOverview } = load("../src/components/projects/cashflow/CashflowOverview.tsx", imports);
const { ProjectCashPosition } = load("../src/components/dashboard/ProjectCommandCenter.tsx", imports);
function summary(active, stale = false) {
  return {
    has_active_forecast: active, staleness: { is_stale: stale },
    basis: { currency_code: "JOD", as_of_date: "2026-09-11", forecast_version_number: active ? 1 : null, forecast_as_of_date: active ? "2026-09-01" : null },
    position: { unrestricted_cash: "10000.00", total_cash: "12000.00", restricted_cash: "2000.00", forecast_collection_coverage: null, coverage_numerator: "0.00", coverage_denominator: "0.00" },
    peak_deficit: { minimum_unrestricted_cash: "10000.00", peak_funding_deficit: "0.00", peak_deficit_month: null },
    funding_windows: [30, 60, 90].map(days => ({ days, funding_requirement: "0.00", opening_unrestricted_cash: "10000.00", usable_inflows: "0.00", outflows: "0.00", minimum_projected_unrestricted_cash: "10000.00", closing_projected_unrestricted_cash: "10000.00", to_date: "2026-12-10" })),
    returns: { net_present_value: "10000.00", net_project_cashflow: "10000.00", discount_rate_per_period: "0", equity_irr_per_period: null, equity_irr_unavailable_reason: null, equity_contributed: "0.00", equity_distributed: "0.00", equity_net: "0.00", npv_basis: "project_operating", equity_irr_basis: "equity_investor" },
  };
}
const render = (component, data) => renderToStaticMarkup(h(component, { summary: data, onOpenForecast() {} }));

test("No forecast keeps actual balances but offers no funding or return assurance", () => {
  const html = render(CashflowOverview, summary(false));
  for (const text of ["JOD 10,000.00", "JOD 12,000.00", "JOD 2,000.00", "Forecast-dependent figures unavailable", "Open Forecast"]) assert.ok(html.includes(text), text);
  for (const text of ["Stays in credit", "No month runs short", "Project NPV", "Net present value", "data-tone=\"success\""]) assert.ok(!html.includes(text), text);
});

test("An active zero-outflow forecast still reports real zero funding requirements", () => {
  const html = render(CashflowOverview, summary(true));
  assert.match(html, /Stays in credit/);
  assert.match(html, /No month runs short/);
  assert.match(html, /JOD 0\.00/);
  assert.match(html, /Project NPV/);
  assert.ok(!html.includes("Forecast-dependent figures unavailable"));
});

test("An active funding deficit retains its amount and warning while stale sources stay explicit", () => {
  const data = summary(true, true);
  data.funding_windows[0].funding_requirement = "321.09";
  data.peak_deficit.peak_funding_deficit = "321.09";
  data.peak_deficit.peak_deficit_month = "2026-10-01";
  const html = render(CashflowOverview, data);
  assert.match(html, /JOD 321\.09/);
  assert.match(html, /Goes below zero/);
  assert.match(html, /sources that have since changed/);
});

test("Project overview also distinguishes missing forecasts from a real zero requirement", () => {
  const missing = render(ProjectCashPosition, summary(false));
  assert.match(missing, /Usable cash/);
  assert.match(missing, /JOD 10,000\.00/);
  assert.match(missing, /Unavailable/);
  assert.ok(!missing.includes("No month runs short"));
  const active = render(ProjectCashPosition, summary(true, true));
  assert.match(active, /No month runs short/);
  assert.match(active, /Sources have changed/);
});
