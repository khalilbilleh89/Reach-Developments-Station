import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);
const settle = () => new Promise(resolve => setImmediate(resolve));

function mount(path, component, dependencies, props) {
  const slots = []; let cursor = 0; let effects = [];
  const react = {
    useRef(initial) { const i = cursor++; slots[i] ??= { current: initial }; return slots[i]; },
    useState(initial) { const i = cursor++; slots[i] ??= { value: initial }; return [slots[i].value, value => { slots[i].value = typeof value === "function" ? value(slots[i].value) : value; }]; },
    useEffect(fn, deps) { const i = cursor++; if (!slots[i] || deps.some((value, n) => value !== slots[i].deps[n])) effects.push(() => { slots[i]?.cleanup?.(); slots[i] = { deps, cleanup: fn() }; }); },
  };
  const code = ts.transpileModule(readFileSync(new URL(`../src/${path}`, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const exports = {};
  runInNewContext(`(function(require, exports) { ${code}\n})`, {URLSearchParams})(name => {
    if (name === "react") return react;
    if (name in dependencies) return dependencies[name];
    if (name === "@/components/ui") return new Proxy({}, { get: (_, key) => key });
    return require(name);
  }, exports);
  return () => { cursor = 0; effects = []; const tree = exports[component](props); effects.forEach(fn => fn()); return tree; };
}
function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children)];
}
function field(tree, label) { return nodes(tree).find(node => node.type === "Field" && node.props.label === label).props.children; }

test("Agent/Buyer retains the chosen buyer when connecting a unit and opens Sales", () => {
  const routes = [];
  const render = mount("components/projects/AgentBuyerTab.tsx", "AgentBuyerTab", {
    "next/navigation": {useRouter: () => ({push: route => routes.push(route)})},
    "./sales/ClientsPanel": {ClientsPanel: "ClientsPanel"},
    "./sales/NewReservation": {NewReservation: "NewReservation"},
    "./sales/salesRoutes": {createdSalesHref: (query, project, kind, id) => `${query}&${kind}=${id}`},
  }, {projectId: "project", projectStatus: "active", roles: new Set(["master_admin"])});
  const panel = nodes(render()).find(node => node.type === "ClientsPanel");
  assert.equal(panel.props.canWrite, true);
  panel.props.onConnect({id: "buyer-first", display_name: "Buyer", agent_name: "Agent"});
  const flow = nodes(render()).find(node => node.type === "NewReservation");
  assert.equal(flow.props.clientId, "buyer-first");
  assert.equal(flow.props.allowOwner, true);
  flow.props.onSaleCreated("new-sale");
  assert.match(routes[0], /section=sales/);
  assert.match(routes[0], /sale=new-sale/);
});

test("Sale agent correction preserves all four fields on failure and refreshes after success", async () => {
  const calls = []; let fail = true; let changed = 0;
  const render = mount("components/projects/sales/SaleAgent.tsx", "SaleAgent", {
    "@/lib/api": {ApiError: Error, sales: {updateSaleAgent: async (...args) => {calls.push(args); if (fail) throw new Error("Try again");}}},
    "./AgentFields": {AgentFields: "AgentFields", agentLabels: {agent_country: "Country", agent_branch: "Branch", agent_branch_leader: "Branch Leader", agent_name: "Agent"}, agentPayload: value => value},
  }, {projectId: "project", record: {id: "sale", status: "signature_pending"}, isSale: true, canWrite: true, onChanged: async () => {changed++;}});
  render().props.actions.props.onClick();
  nodes(render()).find(node => node.type === "AgentFields").props.onChange({agent_country: "Jordan", agent_branch: "Amman", agent_branch_leader: "Leader", agent_name: "Agent"});
  field(render(), "Reason for change").props.onChange({target: {value: "Historical attribution"}});
  await nodes(render()).find(node => node.type === "form").props.onSubmit({preventDefault() {}});
  assert.equal(changed, 0);
  assert.equal(nodes(render()).find(node => node.type === "AgentFields").props.value.agent_name, "Agent");
  assert.ok(nodes(render()).some(node => node.type === "Notice" && node.props.children === "Try again"));
  fail = false;
  await nodes(render()).find(node => node.type === "form").props.onSubmit({preventDefault() {}});
  assert.equal(changed, 1);
  assert.equal(calls[1][0], "project");
  assert.equal(calls[1][1], "sale");
  assert.equal(calls[1][2].agent_branch_leader, "Leader");
});

test("new buyer and sold commitment use one request; failure preserves inputs", async () => {
  class ApiError extends Error {}
  const calls = []; let saved = false; let refuse = true;
  const render = mount("components/projects/sales/RegisterBuyerSaleForm.tsx", "RegisterBuyerSaleForm", {
    "./AgentFields": { AgentFields: "AgentFields", emptyAgent: {agent_country: "", agent_branch: "", agent_branch_leader: "", agent_name: ""}, agentPayload: value => value },
    "./SalesPriceInput": { SalesPriceInput: "SalesPriceInput" },
    "@/components/ui/ValidationSummary": { ValidationSummary: "ValidationSummary" },
    "@/lib/api": { ApiError, sales: {
      clients: async () => [], registerBuyer: async (project, body) => { calls.push({ project, body }); if (refuse) throw new ApiError("Already committed"); return { sale: { id: "sale" } }; },
    }, pricing: { unit: async () => ({ active_price: { reference_price_ex_tax: "250000.00", currency_id: "EUR" }, repricing_required: false }) } },
    "@/lib/currency": { useCurrencyCode: () => id => id },
    "@/lib/format": { money: (amount, code) => `${code} ${amount}` },
  }, { projectId: "project", unitId: "unit", unitOption: {unit_id: "unit", unit_price_version_id: "version", reference_price_ex_tax: "250000.00", currency_id: "EUR"}, onSaved: () => { saved = true; }, onCancel() {} });
  render(); await settle();
  field(render(), "Full buyer name").props.onChange({ target: { value: "Test Buyer" } });
  nodes(render()).find(node => node.type === "AgentFields").props.onChange({agent_country: "Jordan", agent_branch: "Amman", agent_branch_leader: "Leader", agent_name: "Agent"});
  field(render(), "Owner confirmation / reason").props.onChange({ target: { value: "Confirmed sale" } });
  nodes(render()).find(node => node.type === "SalesPriceInput").props.onPreview({sales_price_ex_tax: "250000.00"});
  await nodes(render()).find(node => node.type === "form").props.onSubmit({ preventDefault() {} });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].body.buyer.sole_purchaser_name, "Test Buyer");
  assert.equal(calls[0].body.unit_id, "unit");
  assert.equal(calls[0].body.buyer.agent_name, "Agent");
  assert.equal(saved, false);
  assert.equal(field(render(), "Full buyer name").props.value, "Test Buyer");
  assert.equal(nodes(render()).find(node => node.type === "AgentFields").props.value.agent_branch, "Amman");
  assert.ok(nodes(render()).some(node => node.type === "ValidationSummary" && node.props.error?.message === "Already committed"));
  refuse = false;
  await nodes(render()).find(node => node.type === "form").props.onSubmit({ preventDefault() {} });
  assert.equal(saved, true);
});

test("delete requires confirmation and keeps a failed confirmation open", async () => {
  let deletions = 0; let completed = 0;
  const render = mount("components/projects/DeleteRecordButton.tsx", "DeleteRecordButton", {
    "@/lib/api": { ApiError: Error },
  }, { label: "unit", onDelete: async () => { deletions++; throw new Error("Linked sale exists"); }, onDeleted: async () => { completed++; } });
  nodes(render()).find(node => node.type === "Button").props.onClick();
  assert.equal(deletions, 0);
  await nodes(render()).find(node => node.type === "PromptDialog").props.onSubmit("Duplicate");
  assert.equal(deletions, 1);
  assert.equal(completed, 0);
  assert.equal(nodes(render()).find(node => node.type === "PromptDialog").props.error, "Linked sale exists");
});

test("commercial labels distinguish Available, Reserved and Sold without relabelling legal status", () => {
  const exports = {};
  const code = ts.transpileModule(readFileSync(new URL("../src/components/projects/inventory/statusLabels.ts", import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText;
  runInNewContext(`(function(exports) { ${code}\n})`)(exports);
  assert.equal(exports.statusLabel("available"), "Available");
  assert.equal(exports.statusLabel("reserved"), "Reserved");
  assert.equal(exports.statusLabel("contracted"), "Sold");
  assert.equal(exports.statusLabel("contract_pending"), "Sold · SPA pending");
  assert.equal(exports.statusLabel("no_spa"), "No SPA");
});

test("project choice Delete targets the selected project and refreshes the register", async () => {
  let choices = [{ id: "sea", category: "unit_type", code: "SEA", label: "Sea View", sort_order: 0, is_active: true }];
  const calls = [];
  const render = mount("components/projects/inventory/InventoryConfiguration.tsx", "InventoryConfiguration", {
    "../EditForm": { EditForm: "EditForm" },
    "../DeleteRecordButton": { DeleteRecordButton: "DeleteRecordButton" },
    "@/lib/api": { ApiError: Error, inventory: {
      configuration: async project => { calls.push(["load", project]); return choices; },
      deleteOption: async (...args) => { calls.push(["delete", ...args]); choices = []; },
    } },
  }, { projectId: "pyla", canConfigure: true });
  render(); await settle();
  field(render(), "Configure").props.onChange({ target: { value: "unit_type" } });
  const control = nodes(render()).find(node => node.type === "DeleteRecordButton");
  assert.equal(control.props.label, "Sea View");
  assert.equal(calls.filter(call => call[0] === "delete").length, 0);
  await control.props.onDelete("Entered wrong choice");
  await control.props.onDeleted();
  render(); await settle();
  assert.deepEqual(calls.find(call => call[0] === "delete"), ["delete", "pyla", "sea", "Entered wrong choice"]);
  assert.equal(nodes(render()).filter(node => node.type === "DeleteRecordButton").length, 0);
  assert.ok(nodes(render()).some(node => node.type === "EmptyState"));
});

test("read-only project configuration exposes no deletion control", async () => {
  const render = mount("components/projects/inventory/InventoryConfiguration.tsx", "InventoryConfiguration", {
    "../EditForm": { EditForm: "EditForm" },
    "../DeleteRecordButton": { DeleteRecordButton: "DeleteRecordButton" },
    "@/lib/api": { ApiError: Error, inventory: { configuration: async () => [
      { id: "sea", category: "view_class", code: "SEA", label: "Sea View", sort_order: 0, is_active: true },
    ] } },
  }, { projectId: "pyla", canConfigure: false });
  render(); await settle();
  assert.equal(nodes(render()).filter(node => node.type === "DeleteRecordButton").length, 0);
  assert.equal(nodes(render()).filter(node => node.type === "Button").length, 0);
});
