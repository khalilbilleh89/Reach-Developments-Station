import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../src/components/projects/CommissionsTab.tsx", import.meta.url), "utf8");
const slots = [];
let cursor = 0;
const react = {
  useState(initial) {
    const index = cursor++;
    if (!slots[index]) slots[index] = { value: initial };
    return [slots[index].value, value => { slots[index].value = value; }];
  },
};
const exports = {};
const code = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
runInNewContext(`(function(require, exports) { ${code}\nexports.AllocationDialog = AllocationDialog; })`, {
  URLSearchParams,
})(name => {
  if (name === "react") return react;
  if (name === "react/jsx-runtime") return { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) };
  if (name === "@/lib/format") return { percentInput: value => value ?? "", fractionFromPercent: value => value };
  if (name === "@/components/ui") return new Proxy({}, { get: (_, key) => key });
  return {};
}, exports);

function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children)];
}

const agent = { id: "agent-uuid", display_name: "Receiving Agent", branch: "East", is_active: true };
const sale = { sale_agent_id: "sale-agent-uuid", sale_agent_branch: "Amman" };
function dialog(overrides = {}) {
  slots.length = 0;
  const submitted = [];
  const props = {
    allocation: null, sale, agents: [agent], agentError: null, busy: false,
    error: null, onCancel() {}, onSubmit: value => submitted.push(value), ...overrides,
  };
  const render = () => { cursor = 0; return exports.AllocationDialog(props); };
  return { render, submitted };
}

test("Agent uses a selected UUID and no editable beneficiary name", () => {
  const view = dialog();
  let tree = view.render();
  assert.equal(nodes(tree).find(node => node.props?.label === "Beneficiary type").props.children.props.value, "agent");
  const selector = nodes(tree).find(node => node.props?.label === "Agent").props.children;
  assert.equal(nodes(selector).find(node => node.props?.value === agent.id).props.children[0], agent.display_name);
  assert.equal(nodes(tree).some(node => node.props?.label === "Beneficiary name"), false);
  selector.props.onChange({ target: { value: agent.id } });
  tree = view.render();
  tree.props.onSubmit();
  assert.equal(view.submitted[0].sales_agent_id, agent.id);
  assert.equal("beneficiary_name" in view.submitted[0], false);
});

test("Branch is read-only Sale attribution, while Other submits null when unnamed", () => {
  const view = dialog();
  let tree = view.render();
  nodes(tree).find(node => node.props?.label === "Beneficiary type").props.children.props.onChange({ target: { value: "branch" } });
  tree = view.render();
  assert.equal(nodes(tree).some(node => node.props?.children?.includes?.("Sale branch: ")), true);
  assert.equal(nodes(tree).some(node => node.props?.label === "Beneficiary name"), false);
  tree.props.onSubmit();
  assert.equal(view.submitted[0].beneficiary_type, "branch");
  assert.equal("beneficiary_name" in view.submitted[0], false);
  nodes(tree).find(node => node.props?.label === "Beneficiary type").props.children.props.onChange({ target: { value: "other" } });
  tree = view.render();
  assert.equal(nodes(tree).find(node => node.props?.label === "Beneficiary name").props.optional, true);
  tree.props.onSubmit();
  assert.equal(view.submitted[1].beneficiary_name, null);
});

test("Sale context and legacy type are explicit in the Commission file", () => {
  assert.match(source, /Sale information/);
  assert.match(source, /Sale agent/);
  assert.match(source, /Sale branch/);
  assert.match(source, /beneficiary_type === "legacy" \? "Legacy"/);
  assert.match(source, /selected\.status === "draft"/);
  assert.doesNotMatch(source, /calculated_amount\s*[:=]\s*[^,]*\*/);
});
