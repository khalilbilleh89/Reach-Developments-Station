import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
function harness() {
  const slots = [];
  let cursor = 0;
  const ui = new Proxy({}, { get: (_, name) => name });
  const exports = {};
  const code = ts.transpileModule(readFileSync(new URL("../src/components/projects/cashflow/CashflowMovements.tsx", import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  runInNewContext(`(function(require, exports) { ${code}\n})`)(name => {
    if (name === "react") return { useState(initial) { const i = cursor++; slots[i] ??= { value: initial }; return [slots[i].value, value => { slots[i].value = value; }]; } };
    if (name === "@/components/ui") return ui;
    if (name === "@/lib/format") return { money: value => value, businessDate: value => value };
    if (name === "./labels") return { categoryLabel: value => value, movementLabel: value => value, movementTone: () => "neutral" };
    return require(name);
  }, exports);
  const nodes = node => {
    if (node == null || typeof node !== "object") return [];
    if (Array.isArray(node)) return node.flatMap(nodes);
    if (typeof node.type === "function") return nodes(node.type(node.props));
    return [node, ...nodes(node.props?.children)];
  };
  return props => { cursor = 0; return nodes(exports.CashflowMovements(props)); };
}
const movement = (status, id = status) => ({ id, status, movement_reference: `REF-${id}`, movement_date: "2026-09-12", amount: "100.00", category: "other", movement_type: "equity_contribution", counts_as_cash: status === "confirmed" });
const ready = data => ({ status: "ready", data });
const props = () => ({ development: ready([movement("recorded"), movement("confirmed"), movement("reversed")]), financing: ready([]), currency: "JOD", currencyId: "currency", canRecord: false, canConfirm: true, busy: false, error: null });

test("only authorized recorded movements offer Delete; confirmed movements keep Reverse", () => {
  const render = harness();
  const buttons = render(props()).filter(n => n.type === "Button");
  assert.deepEqual(buttons.map(n => n.props.children), ["Confirm", "Delete", "Reverse"]);
  assert.equal(render({ ...props(), canConfirm: false }).filter(n => n.type === "Button").length, 0);
  assert.ok(render({ ...props(), busy: true }).filter(n => n.type === "Button").every(n => n.props.disabled));
});

test("confirmed reversal explains its effect on current cash and keeps history", async () => {
  const render = harness();
  const input = { ...props(), onReverseDevelopment: async () => true };
  render(input).find(n => n.type === "Button" && n.props.children === "Reverse").props.onClick();
  const dialog = render(input).find(n => n.type === "PromptDialog");
  assert.equal(dialog.props.title, "Reverse REF-confirmed");
  assert.equal(dialog.props.confirmLabel, "Reverse");
  assert.match(dialog.props.hint, /withdrawn from the current cash position/);
  assert.match(dialog.props.hint, /historical cash evidence/);
  await dialog.props.onSubmit("Wrong posting");
  assert.equal(render(input).find(n => n.type === "PromptDialog"), undefined);
});

for (const kind of ["development", "financing"]) {
  test(`${kind} removal identifies the record and keeps the dialog through pending and failed writes`, async () => {
    const render = harness();
    const calls = [];
    let finish;
    const input = { ...props(), development: ready([]), financing: ready([]), [kind]: ready([movement("recorded", kind)]),
      [kind === "development" ? "onReverseDevelopment" : "onReverseFinancing"]: (id, reason) => { calls.push([id, reason]); return new Promise(resolve => { finish = resolve; }); } };
    render(input).find(n => n.type === "Button" && n.props.children === "Delete").props.onClick();
    const dialog = () => render(input).find(n => n.type === "PromptDialog");
    assert.equal(dialog().props.title, `Delete REF-${kind}`);
    assert.match(dialog().props.hint, /never counted as cash/);
    assert.match(dialog().props.hint, /retained for audit/);
    const request = dialog().props.onSubmit("Duplicate entry");
    assert.ok(dialog());
    finish(false); await request;
    input.error = "Already changed";
    assert.equal(dialog().props.error, "Already changed");
    assert.equal(dialog().props.title, `Delete REF-${kind}`);
    const retry = dialog().props.onSubmit("Duplicate entry");
    finish(true); await retry;
    assert.equal(dialog(), undefined);
    assert.deepEqual(calls, [[kind, "Duplicate entry"], [kind, "Duplicate entry"]]);
  });
}
