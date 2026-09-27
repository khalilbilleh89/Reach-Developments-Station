import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
const settle = () => new Promise(resolve => setImmediate(resolve));
const currency = { id: "currency", code: "JOD", name: "Jordanian Dinar", symbol: null, minor_units: 3, is_active: true };

function harness() {
  const slots = [];
  let cursor = 0;
  let retries = 0;
  let deleteFailure = false;
  const calls = [];
  class ApiError extends Error {}
  const settings = {
    currencies: async () => [currency],
    createCurrency: async body => calls.push(["create", body]),
    updateCurrency: async (...args) => calls.push(["update", ...args]),
    deleteCurrency: async (...args) => {
      calls.push(["delete", ...args]);
      if (deleteFailure) throw new ApiError("Currency is in use");
    },
  };
  const source = readFileSync(new URL("../src/components/settings/CurrencySection.tsx", import.meta.url), "utf8");
  const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const exports = {};
  runInNewContext(`(function(require, exports) { ${code}\n})`)(name => {
    if (name === "react") return { useState(initial) {
      const index = cursor++;
      slots[index] ??= { value: typeof initial === "function" ? initial() : initial };
      return [slots[index].value, value => {
        slots[index].value = typeof value === "function" ? value(slots[index].value) : value;
      }];
    }};
    if (name === "@/components/ui") return new Proxy({}, { get: (_, key) => key });
    if (name === "@/lib/answer") return { useAnswer: () => ({ status: "ready", data: [currency], retry: () => { retries += 1; } }) };
    if (name === "@/lib/api") return { ApiError, settings };
    return require(name);
  }, exports);
  return {
    calls,
    retries: () => retries,
    failDelete() { deleteFailure = true; },
    render() { cursor = 0; return exports.CurrencySection(); },
  };
}

function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children), ...nodes(tree.props?.actions)];
}

function textOf(tree) {
  if (tree == null || typeof tree === "boolean") return "";
  if (typeof tree !== "object") return String(tree);
  if (Array.isArray(tree)) return tree.map(textOf).join(" ");
  return textOf(tree.props?.children);
}

function field(view, label) {
  return view.find(node => node.type === "Field" && node.props.label === label);
}

test("currency administration explains shared symbol impact and creates then refreshes", async () => {
  const h = harness();
  let tree = h.render();
  assert.match(textOf(tree), /changes how that currency is displayed on every screen/);
  nodes(tree).find(node => node.type === "Button" && node.props.children === "Add currency").props.onClick();
  let view = nodes(h.render());
  field(view, "Currency code").props.children.props.onChange({ target: { value: "usd" } });
  view = nodes(h.render());
  field(view, "Name").props.children.props.onChange({ target: { value: "US Dollar" } });
  view = nodes(h.render());
  field(view, "Symbol").props.children.props.onChange({ target: { value: "$" } });
  view = nodes(h.render());
  field(view, "Minor units").props.children.props.onChange({ target: { value: "2" } });
  view = nodes(h.render());
  assert.equal(view.find(node => node.type === "FormDialog").props.disabled, false);
  view.find(node => node.type === "FormDialog").props.onSubmit();
  await settle();
  assert.equal(
    JSON.stringify(h.calls[0]),
    JSON.stringify(["create", { code: "USD", name: "US Dollar", symbol: "$", minor_units: 2 }]),
  );
  assert.equal(h.retries(), 1);
});

test("symbol editing updates shared configuration and refreshes the registry", async () => {
  const h = harness();
  let view = nodes(h.render());
  view.find(node => node.type === "Button" && node.props.children === "Edit symbol").props.onClick();
  view = nodes(h.render());
  const dialog = view.find(node => node.type === "FormDialog");
  assert.match(dialog.props.description, /Numeric amounts remain unchanged/);
  field(view, "Symbol").props.children.props.onChange({ target: { value: "JD" } });
  nodes(h.render()).find(node => node.type === "FormDialog").props.onSubmit();
  await settle();
  assert.equal(JSON.stringify(h.calls[0]), JSON.stringify(["update", "currency", { symbol: "JD" }]));
  assert.equal(h.retries(), 1);
});

test("delete requires a reason, refreshes on success and retains a failed confirmation", async () => {
  const success = harness();
  let view = nodes(success.render());
  view.find(node => node.type === "Button" && node.props.children === "Delete").props.onClick();
  view = nodes(success.render());
  let dialog = view.find(node => node.type === "PromptDialog");
  assert.equal(dialog.props.title, "Delete JOD?");
  assert.match(dialog.props.description, /business record that still references it will block deletion/);
  dialog.props.onSubmit("Duplicate entered in error");
  await settle();
  assert.equal(
    JSON.stringify(success.calls[0]),
    JSON.stringify(["delete", "currency", "Duplicate entered in error"]),
  );
  assert.equal(success.retries(), 1);

  const failure = harness();
  failure.failDelete();
  view = nodes(failure.render());
  view.find(node => node.type === "Button" && node.props.children === "Delete").props.onClick();
  nodes(failure.render()).find(node => node.type === "PromptDialog").props.onSubmit("Still referenced by project");
  await settle();
  dialog = nodes(failure.render()).find(node => node.type === "PromptDialog");
  assert.equal(dialog.props.error, "Currency is in use");
  assert.equal(failure.retries(), 0);
});

test("currency navigation is visible only to System Administrators", () => {
  const source = readFileSync(new URL("../src/components/shell/navigation.ts", import.meta.url), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const exports = {};
  const roles = {
    ROLE_SYSTEM_ADMIN: "system_admin",
    hasAnyRole: (held, allowed) => [...held].some(role => allowed.has(role)),
  };
  for (const name of ["AUDIT_READERS", "CASHFLOW_READERS", "COLLECTION_READERS", "SPECIFICATION_READERS", "CONSULTANT_READERS", "COMMISSION_READERS", "ECONOMICS_READERS", "PLAN_READERS", "PROJECT_FINANCIAL_READERS", "SALES_READERS"]) roles[name] = new Set();
  runInNewContext(`(function(require, exports) { ${code}\n})`, { URLSearchParams })(name => {
    if (name === "@/lib/roles") return roles;
    return require(name);
  }, exports);
  const keys = held => exports.visibleNavigation(exports.SETTINGS_NAVIGATION, new Set(held)).flatMap(group => group.items.map(item => item.key));
  assert.ok(keys(["system_admin"]).includes("currencies"));
  assert.ok(!keys(["project_manager"]).includes("currencies"));
});
