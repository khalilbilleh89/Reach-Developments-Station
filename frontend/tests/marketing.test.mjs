import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);

function harness(file, dependencies = {}) {
  const slots = []; let cursor = 0;
  const source = readFileSync(new URL(`../src/components/projects/marketing/${file}.tsx`, import.meta.url), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const exports = {};
  class ApiError extends Error {}
  runInNewContext(`(function(require,exports){${code}\n})`)((key) => {
    if (key === "react") return { useState(initial) { const i = cursor++; slots[i] ??= { value: typeof initial === "function" ? initial() : initial }; return [slots[i].value, value => { slots[i].value = value; }]; } };
    if (key === "@/lib/api") return { ApiError };
    if (key === "@/components/ui") return new Proxy({}, { get: (_, name) => name });
    if (key in dependencies) return dependencies[key];
    if (key === "@/lib/currency") return { useCurrencyCode: () => id => id === "00000000-0000-0000-0000-000000000001" ? "EUR" : null };
    if (key.startsWith("@/") || key.startsWith("./") || key.startsWith("../")) return new Proxy({}, { get: (_, name) => name });
    return require(key);
  }, exports);
  return { exports, render(name, props) { cursor = 0; return exports[name](props); } };
}
function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children), ...nodes(tree.props?.actions)];
}
const find = (tree, type) => nodes(tree).filter(node => node.type === type);

test("rental editor submits exact decimal strings and preserves failed drafts", async () => {
  const h = harness("RentalEditor");
  const initial = h.exports.blankScenario("00000000-0000-0000-0000-000000000001", "short_term");
  let submitted;
  const props = { initial, scopeLabel: "Unit 101", onClose() {}, onSave: async value => { submitted = value; throw new Error("offline"); } };
  let tree = h.render("RentalEditor", props);
  find(tree, "MoneyInput")[0].props.onChange("1234567890123.45");
  tree = h.render("RentalEditor", props);
  assert.equal(find(tree, "DraftBoundary")[0].props.dirty, true);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  assert.equal(submitted.annual_rent_per_sqm, "1234567890123.45");
  tree = h.render("RentalEditor", props);
  assert.equal(find(tree, "MoneyInput")[0].props.value, "1234567890123.45");
  assert.ok(find(tree, "Notice").some(node => String(node.props.children).includes("kept")));
  assert.equal(find(tree, "MoneyInput")[0].props.code, "EUR");
});

test("branding has working draft colour and font deletion", () => {
  const h = harness("MarketingContentEditor");
  const props = { kind: "branding", initial: { project_name: "Test", name_definition: "Story", colors: [{ name: "Blue", hex: "#123456", usage: "Primary" }], fonts: [{ family: "Arial", usage: "Body" }], source: "Guide", as_of: null }, onSave() {}, onClose() {} };
  let tree = h.render("MarketingContentEditor", props);
  find(tree, "Button").find(node => String(node.props.children).includes("Delete colour")).props.onClick();
  tree = h.render("MarketingContentEditor", props);
  assert.equal(find(tree, "Field").some(node => node.props.label === "Hex colour (#RRGGBB)"), false);
  assert.equal(find(tree, "DraftBoundary")[0].props.dirty, true);
  find(tree, "Button").find(node => String(node.props.children).includes("Delete font")).props.onClick();
  tree = h.render("MarketingContentEditor", props);
  assert.equal(find(tree, "Field").some(node => node.props.label === "Font family"), false);
});

test("missing projection is an explicit unavailable state", () => {
  const h = harness("MarketingEconomicsTab");
  const tree = h.render("RentalProjection", { result: { currency_id: "00000000-0000-0000-0000-000000000001", projection: null, unavailable: "No approved area" } });
  assert.equal(tree.props.children, "No approved area");
  assert.equal(find(tree, "KeyValue").length, 0);
});
