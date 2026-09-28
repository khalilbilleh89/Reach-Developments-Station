import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
const settle = () => new Promise(resolve => setImmediate(resolve));

function mount(api, callbacks) {
  const slots = [];
  let cursor = 0;
  let effects = [];
  const react = {
    useState(initial) {
      const index = cursor++;
      slots[index] ??= { value: initial };
      return [
        slots[index].value,
        value => {
          slots[index].value = typeof value === "function" ? value(slots[index].value) : value;
        },
      ];
    },
    useEffect(fn, deps) {
      const index = cursor++;
      if (!slots[index] || deps.some((value, position) => value !== slots[index].deps[position])) {
        effects.push(() => {
          slots[index]?.cleanup?.();
          slots[index] = { deps, cleanup: fn() };
        });
      }
    },
  };
  const source = readFileSync(
    new URL("../src/components/projects/ProjectCurrencyCorrection.tsx", import.meta.url),
    "utf8",
  );
  const code = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX,
    },
  }).outputText;
  const exports = {};
  runInNewContext(`(function(require, exports) { ${code}\n})`)(name => {
    if (name === "react") return react;
    if (name === "@/lib/api") return api;
    if (name === "@/components/ui") return new Proxy({}, { get: (_, key) => key });
    return require(name);
  }, exports);
  const project = {
    id: "project",
    name: "Galini Blu",
    base_currency_id: "jod-id",
    base_currency_code: "JOD",
  };
  return () => {
    cursor = 0;
    effects = [];
    const tree = exports.ProjectCurrencyCorrection({ project, ...callbacks });
    effects.forEach(effect => effect());
    return tree;
  };
}

function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children)];
}

function field(tree, label) {
  return nodes(tree).find(node => node.type === "Field" && node.props.label === label).props.children;
}

function textOf(value) {
  if (Array.isArray(value)) return value.map(textOf).join("");
  if (value && typeof value === "object") return textOf(value.props?.children);
  return value == null ? "" : String(value);
}

test("correction makes no-conversion consequences explicit and sends the guarded command", async () => {
  class ApiError extends Error {}
  const calls = [];
  let saved = 0;
  let closed = 0;
  const render = mount(
    {
      ApiError,
      settings: {
        currencies: async () => [
          { id: "jod-id", code: "JOD", name: "Dinar", is_active: true },
          { id: "usd-id", code: "USD", name: "Dollar", is_active: true },
          { id: "old-id", code: "GBP", name: "Pound", is_active: false },
        ],
      },
      projects: { correctCurrency: async (...args) => calls.push(args) },
    },
    { onSaved: async () => { saved++; }, onClose: () => { closed++; } },
  );

  render();
  await settle();
  let tree = render();
  const warning = textOf(nodes(tree).find(node => node.type === "Notice"));
  assert.match(warning, /does not convert values/i);
  assert.match(warning, /numeric amount remains unchanged/i);
  const options = nodes(field(tree, "New base currency"));
  assert.deepEqual(options.filter(node => node.type === "option").map(node => node.props.value), ["", "usd-id"]);

  field(tree, "New base currency").props.onChange({ target: { value: "usd-id" } });
  field(render(), "Reason").props.onChange({ target: { value: "Source documents confirm USD." } });
  nodes(render()).find(node => node.type === "input" && node.props.type === "checkbox")
    .props.onChange({ target: { checked: true } });
  tree = render();
  nodes(tree).find(node => node.type === "Form").props.onSubmit({ preventDefault() {} });
  await settle();
  await settle();

  assert.equal(
    JSON.stringify(calls),
    JSON.stringify([["project", {
      expected_base_currency_id: "jod-id",
      target_currency_id: "usd-id",
      reason: "Source documents confirm USD.",
      keep_amounts_unchanged: true,
    }]]),
  );
  assert.equal(saved, 1);
  assert.equal(closed, 1);
});

test("a failed correction retains all entered evidence", async () => {
  class ApiError extends Error {}
  const render = mount(
    {
      ApiError,
      settings: { currencies: async () => [{ id: "usd-id", code: "USD", name: "Dollar", is_active: true }] },
      projects: { correctCurrency: async () => { throw new ApiError("The project base currency changed. Refresh before correcting it."); } },
    },
    { onSaved: async () => {}, onClose: () => {} },
  );
  render();
  await settle();
  field(render(), "New base currency").props.onChange({ target: { value: "usd-id" } });
  field(render(), "Reason").props.onChange({ target: { value: "Verified against the signed contract." } });
  nodes(render()).find(node => node.type === "input" && node.props.type === "checkbox")
    .props.onChange({ target: { checked: true } });
  nodes(render()).find(node => node.type === "Form").props.onSubmit({ preventDefault() {} });
  await settle();

  const tree = render();
  assert.equal(field(tree, "New base currency").props.value, "usd-id");
  assert.equal(field(tree, "Reason").props.value, "Verified against the signed contract.");
  assert.equal(
    nodes(tree).find(node => node.type === "input" && node.props.type === "checkbox").props.checked,
    true,
  );
  assert.ok(
    nodes(tree).some(
      node => node.type === "Notice" && textOf(node).includes("Refresh before correcting"),
    ),
  );
});

test("a failed currency read offers retry before showing the correction form", async () => {
  class ApiError extends Error {}
  let attempts = 0;
  const render = mount(
    {
      ApiError,
      settings: { currencies: async () => {
        attempts++;
        if (attempts === 1) throw new ApiError("Currency register unavailable.");
        return [{ id: "usd-id", code: "USD", name: "Dollar", is_active: true }];
      } },
      projects: { correctCurrency: async () => {} },
    },
    { onSaved: async () => {}, onClose: () => {} },
  );

  render();
  await settle();
  let tree = render();
  assert.ok(nodes(tree).some(node => node.type === "Notice" && textOf(node).includes("Currency register unavailable")));
  assert.ok(!nodes(tree).some(node => node.type === "Form"));
  nodes(tree).find(node => node.type === "Button" && node.props.children === "Try again").props.onClick();
  render();
  await settle();
  tree = render();
  assert.equal(attempts, 2);
  assert.ok(nodes(tree).some(node => node.type === "Form"));
});

test("the workspace exposes correction only to administrators outside setup", () => {
  const command = readFileSync(
    new URL("../src/components/dashboard/ProjectCommandCenter.tsx", import.meta.url),
    "utf8",
  );
  const workspace = readFileSync(
    new URL("../src/components/projects/ProjectWorkspace.tsx", import.meta.url),
    "utf8",
  );
  assert.match(command, /canCorrectCurrency/);
  assert.match(command, /Correct base currency/);
  assert.match(workspace, /canCorrectCurrency=\{isAdmin && project\.status !== "setup"\}/);
  assert.match(workspace, /ProjectCurrencyCorrection/);
  const correction = readFileSync(
    new URL("../src/components/projects/ProjectCurrencyCorrection.tsx", import.meta.url),
    "utf8",
  );
  assert.match(correction, /<DraftBoundary/);
  assert.match(correction, /dirty=\{Boolean\(target \|\| reason \|\| acknowledged\)\}/);
});
