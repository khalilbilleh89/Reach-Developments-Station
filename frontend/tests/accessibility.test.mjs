import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { createRequire } from "node:module";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
const exports = {};
const code = ts.transpileModule(readFileSync(new URL("../src/components/ui/Form.tsx", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
runInNewContext(`(function(require, exports) { ${code}\n})`)(name => name === "./Button" ? { Button: "button" } : name === "./Icon" ? { Icon: () => null } : require(name), exports);
const { Field, MoneyInput, RateInput } = exports;
const h = React.createElement;
test("Units remain accessible alongside caller descriptions without rounding", () => {
  for (const [component, code, unit] of [[MoneyInput, "JOD", "Currency: JOD"], [MoneyInput, null, "Currency unavailable"], [RateInput, undefined, "Percent"]]) {
    const html = markup(h(component, { code, value: "0.000001", onChange() {}, "aria-describedby": "external" }));
    const ids = attribute(html, "aria-describedby").split(" ");
    assert.equal(ids[0], "external");
    assert.equal(new Set(ids).size, 4);
    assert.ok(html.includes(`id="${ids.at(-1)}" class="visually-hidden">${unit}</span>`));
    assert.equal(attribute(html, "value"), "0.000001");
  }
  const html = renderToStaticMarkup(h("form", null, ["JOD", "USD"].map(code => h(MoneyInput, { key: code, code, value: "0", onChange() {}, "aria-label": "Amount" }))));
  const ids = [...html.matchAll(/aria-describedby="([^"]+)"/g)].map(match => match[1]);
  assert.equal(new Set(ids).size, 2);
  for (const [i, code] of ["JOD", "USD"].entries()) assert.ok(html.includes(`id="${ids[i]}" class="visually-hidden">Currency: ${code}</span>`));
});
function markup(control, props = {}) {
  return renderToStaticMarkup(h(Field, { label: "Amount", hint: "Use the agreed amount", error: "Amount is required", ...props }, control));
}
function attribute(html, name) { return html.match(new RegExp(`${name}="([^"]+)"`))?.[1]; }

test("Field explicitly labels nested controls and connects both hint and error", () => {
  const html = markup(h("span", null, h("input", { name: "amount" })));
  assert.equal(attribute(html, "aria-invalid"), "true");
  const ids = attribute(html, "aria-describedby").split(" ");
  assert.equal(ids.length, 2);
  for (const id of [...ids, attribute(html, "aria-labelledby")]) assert.ok(html.includes(`id="${id}"`));
  assert.match(html, /Amount is required/);
});

test("Compound money and rate controls receive descriptions without changing exact values", () => {
  for (const component of [MoneyInput, RateInput]) {
    const html = markup(h(component, { code: "JOD", value: "123456789.123456", onChange() {}, "aria-describedby": "currency-basis" }));
    assert.equal(attribute(html, "value"), "123456789.123456");
    assert.ok(attribute(html, "aria-describedby").startsWith("currency-basis "));
    assert.equal(attribute(html, "aria-invalid"), "true");
  }
});

test("Cleared Field validation leaves caller-owned accessibility state intact", () => {
  const html = markup(h("select", { "aria-describedby": "external", "aria-labelledby": "custom-label", "aria-invalid": "grammar", defaultValue: "" }, h("option", { value: "" }, "Choose")), { error: null, hint: undefined });
  assert.equal(attribute(html, "aria-describedby"), "external");
  assert.equal(attribute(html, "aria-labelledby"), "custom-label");
  assert.equal(attribute(html, "aria-invalid"), "grammar");
  assert.ok(!html.includes("field-error"));
});

test("Repeated fields generate distinct label and description identities", () => {
  const html = renderToStaticMarkup(h("form", null, [1, 2].map(key => h(Field, { key, label: "Name", hint: "Buyer name" }, h("textarea")))));
  const ids = [...html.matchAll(/ id="([^"]+)"/g)].map(match => match[1]);
  assert.equal(ids.length, 4);
  assert.equal(new Set(ids).size, ids.length);
});
