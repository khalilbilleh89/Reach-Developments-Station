import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";

// Execute the actual TypeScript routing and navigation modules with the existing
// compiler. No browser globals, Next runtime, new dependencies or navigation mocks.
const sourceRoot = fileURLToPath(new URL("../src/", import.meta.url));
function load(file) {
  const exports = {};
  const source = ts.transpileModule(readFileSync(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const require = name => load(`${name.startsWith("@/") ? resolve(sourceRoot, name.slice(2)) : resolve(dirname(file), name)}.ts`);
  runInNewContext(`(function(require, exports) { ${source}\n})`, { URLSearchParams })(require, exports);
  return exports;
}
const { contextualRecordHref: open, recordReturn: back, recordHref, registerReturn } = load(resolve(sourceRoot, "components/shell/recordRoutes.ts"));
const project = "11111111-1111-4111-8111-111111111111";
const sale = "22222222-2222-4222-8222-222222222222";
const unit = "33333333-3333-4333-8333-333333333333";
const plan = "44444444-4444-4444-8444-444444444444";
const query = href => new URLSearchParams(href.split("?")[1]);
const origin = `/projects/?project=${project}&section=sales&search=Rana&commercial_status=contracted&offset=200`;

test("created Sales transaction returns to the register without reopening preparation", () => {
  const { createdSalesHref } = load(resolve(sourceRoot, "components/projects/sales/salesRoutes.ts"));
  for (const kind of ["sale", "reservation"]) {
    const href = createdSalesHref(query(`${origin}&sales_view=new`), project, kind, sale);
    assert.equal(back(query(href), project, kind).href, origin);
  }
});

test("Sales → Unit → Back keeps cross-module origin, filters, search and page", () => {
  const href = open(query(origin), project, "unit", unit);
  assert.equal(back(query(href), project, "unit").href, origin);
  assert.equal(back(query(href), project, "unit").label, "Sales");
});

test("Sales → Sale → Payment Plan → Back restores the sale tab then the register", () => {
  const saleHref = open(query(origin), project, "sale", sale, "plan");
  const planHref = open(query(saleHref), project, "payment-plan", plan);
  const parent = back(query(planHref), project, "payment-plan");
  assert.equal(parent.label, "Sale");
  assert.equal(parent.href, saleHref);
  assert.equal(parent.origin, origin);
  assert.equal(back(query(parent.href), project, "sale").href, origin);
});

test("nested parents survive serialization and unwind in order without history or storage", () => {
  const saleHref = open(query(origin), project, "sale", sale, "collections");
  const unitHref = open(query(saleHref), project, "unit", unit, "commercial");
  const planHref = open(query(unitHref), project, "payment-plan", plan);
  assert.equal(back(query(planHref), project, "payment-plan").href, unitHref);
  assert.equal(back(query(unitHref), project, "unit").href, saleHref);
});

test("returning to an ancestor through a related-record link does not create a cycle", () => {
  const saleHref = open(query(origin), project, "sale", sale);
  const unitHref = open(query(saleHref), project, "unit", unit);
  const revisited = open(query(unitHref), project, "sale", sale, "contract");
  assert.equal(back(query(revisited), project, "sale").href, origin);
});

test("direct and legacy record links have deterministic module fallbacks", () => {
  const direct = recordHref(project, "sale", sale, "plan");
  const child = open(query(direct), project, "payment-plan", plan);
  const parent = back(query(child), project, "payment-plan");
  assert.equal(query(parent.href).get("sale"), sale);
  assert.equal(query(parent.href).get("tab"), "plan");
  assert.equal(back(query(parent.href), project, "sale").href, `/projects/?project=${project}&section=sales`);
  assert.equal(back(query(recordHref(project, "payment-plan", plan)), project, "payment-plan").label, "Payment Plans");
});

test("external, cross-project, record and unknown-section origins fall back safely", () => {
  for (const unsafe of ["https://evil.example/projects/?project=" + project, "//evil.example", "javascript:alert(1)", origin.replace(project, sale), origin.replace("section=sales", "section=unknown"), recordHref(project, "sale", sale), origin + "#fragment"]) {
    assert.equal(registerReturn(unsafe, project, "inventory"), `/projects/?project=${project}&section=inventory`);
  }
});

test("malformed, cross-project or mismatched-module parents cannot redirect the return", () => {
  for (const trail of ["not-json", "{}", JSON.stringify([origin]), JSON.stringify([recordHref(sale, "unit", unit)]), JSON.stringify([recordHref(project, "unit", unit).replace("section=inventory", "section=sales")]), JSON.stringify([42])]) {
    const params = query(open(query(origin), project, "sale", sale));
    params.set("trail", trail);
    assert.equal(back(params, project, "sale").href, origin);
  }
});

test("opening a different project's record discards the previous project's context", () => {
  const href = open(query(origin), sale, "unit", unit);
  assert.equal(back(query(href), sale, "unit").href, `/projects/?project=${sale}&section=inventory`);
});

test("long journeys bound parent depth while retaining the original register", () => {
  let href = origin;
  for (let index = 0; index < 20; index++) href = open(query(href), project, "unit", `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`);
  assert.equal(JSON.parse(query(href).get("trail")).length, 8);
  assert.equal(back(query(href), project, "unit").origin, origin);
  assert.ok(href.length < 4096);
});

test("post-create reservation and payment-plan navigation keeps the same parent contract", () => {
  const reservation = open(query(origin), project, "reservation", unit);
  const createdSale = open(query(reservation), project, "sale", sale, "contract");
  assert.equal(back(query(createdSale), project, "sale").href, reservation);
  const createdPlan = open(query(createdSale), project, "payment-plan", plan);
  assert.equal(back(query(createdPlan), project, "payment-plan").href, createdSale);
});
