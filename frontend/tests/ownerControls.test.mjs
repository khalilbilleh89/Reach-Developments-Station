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
    useCallback(fn) { return fn; },
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

function buyerAgentTab(props, routes = []) {
  return mount("components/projects/AgentBuyerTab.tsx", "AgentBuyerTab", {
    "next/navigation": {useRouter: () => ({push: route => routes.push(route)})},
    "./sales/ClientsPanel": {ClientsPanel: "ClientsPanel"},
    "./sales/AgentsPanel": {AgentsPanel: "AgentsPanel"},
    "./sales/NewReservation": {NewReservation: "NewReservation"},
    "./sales/salesRoutes": {createdSalesHref: (query, project, kind, id) => `${query}&${kind}=${id}`},
  }, props);
}

test("Buyers retains the chosen buyer when connecting a unit and opens Sales", () => {
  const routes = [];
  const render = buyerAgentTab({projectId: "project", projectStatus: "active", roles: new Set(["master_admin"])}, routes);
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

test("Buyers and Agents are two screens, and connecting a unit belongs to Buyers", () => {
  const buyers = nodes(buyerAgentTab({mode: "buyers", projectId: "project", projectStatus: "active", roles: new Set(["sales_operations"])})());
  const agents = nodes(buyerAgentTab({mode: "agents", projectId: "project", projectStatus: "active", roles: new Set(["sales_operations"])})());

  // Each screen answers its own question and offers only its own register.
  assert.equal(buyers.find(node => node.type === "PageHeader").props.title, "Buyers");
  assert.equal(agents.find(node => node.type === "PageHeader").props.title, "Agents");
  assert.ok(buyers.find(node => node.type === "ClientsPanel"));
  assert.equal(buyers.find(node => node.type === "AgentsPanel"), undefined);
  assert.ok(agents.find(node => node.type === "AgentsPanel"));
  assert.equal(agents.find(node => node.type === "ClientsPanel"), undefined);

  // Reservation creation is a buyer workflow. The agent is attribution, and
  // Agents must never become a second place to commit a unit.
  const render = buyerAgentTab({mode: "agents", projectId: "project", projectStatus: "active", roles: new Set(["master_admin"])});
  assert.equal(nodes(render()).find(node => node.type === "NewReservation"), undefined);
});

test("Buyers no longer prints the selling team under the purchaser's name", () => {
  const source = readFileSync(new URL("../src/components/projects/sales/ClientsPanel.tsx", import.meta.url), "utf8");
  const identity = source.split('className="buyer-identity"')[1].split("</td>")[0];
  // The four agent_* fields describe the salesperson. Under a buyer's name
  // they read as the purchaser's nationality and address.
  for (const field of ["agent_country", "agent_branch", "agent_branch_leader", "agent_name"]) {
    assert.ok(!identity.includes(field), `${field} is still rendered as buyer identity`);
  }
});

test("Agents reads and creates independent roster records", () => {
  const source = readFileSync(new URL("../src/components/projects/sales/AgentsPanel.tsx", import.meta.url), "utf8");
  for (const call of ["sales.agents", "sales.createAgent", "sales.updateAgent", "sales.deleteAgent"]) assert.ok(source.includes(call), call);
  assert.ok(!source.includes("sales.clients"));
  assert.ok(source.includes("Add agent"));
  assert.ok(source.includes("Agent can exist before any buyer or sale"));
});

test("Buyer Agent dropdown uses UUIDs, keeps No agent, and excludes unrelated inactive Agents", async () => {
  const selected = [];
  const rows = [
    {id: "agent-a", display_name: "Ahmad Saleh", branch: "Amman", is_active: true},
    {id: "agent-b", display_name: "Ahmad Saleh", branch: "Aqaba", is_active: true},
    {id: "agent-old", display_name: "Retired", branch: "Dubai", is_active: false},
  ];
  const render = mount("components/projects/sales/AgentSelect.tsx", "AgentSelect", {
    "@/lib/api": {ApiError: Error, sales: {agents: async () => rows}},
  }, {projectId: "project", value: "", currentId: null, onChange: id => selected.push(id)});
  render(); await settle();
  const select = nodes(render()).find(node => node.type === "select");
  const options = nodes(select).filter(node => node.type === "option");
  assert.deepEqual(options.map(option => option.props.value), ["", "agent-a", "agent-b"]);
  assert.equal(options[0].props.children, "No agent");
  assert.match(options[1].props.children, /Amman/);
  assert.match(options[2].props.children, /Aqaba/);
  select.props.onChange({target: {value: "agent-b"}});
  assert.deepEqual(selected, ["agent-b"]);
});

test("Sale Agent correction selects a stable ID, retains draft on failure and refreshes", async () => {
  const calls = []; let fail = true; let changed = 0;
  const render = mount("components/projects/sales/SaleAgent.tsx", "SaleAgent", {
    "@/lib/api": {ApiError: Error, sales: {updateSaleAgent: async (...args) => {calls.push(args); if (fail) throw new Error("Try again");}}},
    "./AgentSelect": {AgentSelect: "AgentSelect"},
  }, {projectId: "project", record: {id: "sale", status: "signature_pending"}, isSale: true, canWrite: true, onChanged: async () => {changed++;}});
  render().props.actions.props.onClick();
  nodes(render()).find(node => node.type === "AgentSelect").props.onChange("agent-uuid");
  field(render(), "Reason for change").props.onChange({target: {value: "Historical attribution"}});
  await nodes(render()).find(node => node.type === "form").props.onSubmit({preventDefault() {}});
  assert.equal(changed, 0);
  assert.equal(nodes(render()).find(node => node.type === "AgentSelect").props.value, "agent-uuid");
  assert.ok(nodes(render()).some(node => node.type === "Notice" && node.props.children === "Try again"));
  fail = false;
  await nodes(render()).find(node => node.type === "form").props.onSubmit({preventDefault() {}});
  assert.equal(changed, 1);
  assert.equal(calls[1][0], "project");
  assert.equal(calls[1][1], "sale");
  assert.equal(calls[1][2].agent_id, "agent-uuid");
  assert.equal(calls[1][2].reason, "Historical attribution");
});

test("new buyer and sold commitment use one request; failure preserves inputs", async () => {
  class ApiError extends Error {}
  const calls = []; let saved = false; let refuse = true;
  const render = mount("components/projects/sales/RegisterBuyerSaleForm.tsx", "RegisterBuyerSaleForm", {
    "./AgentSelect": { AgentSelect: "AgentSelect" },
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
  nodes(render()).find(node => node.type === "AgentSelect").props.onChange("agent-uuid");
  field(render(), "Owner confirmation / reason").props.onChange({ target: { value: "Confirmed sale" } });
  nodes(render()).find(node => node.type === "SalesPriceInput").props.onPreview({sales_price_ex_tax: "250000.00"});
  await nodes(render()).find(node => node.type === "form").props.onSubmit({ preventDefault() {} });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].body.buyer.sole_purchaser_name, "Test Buyer");
  assert.equal(calls[0].body.unit_id, "unit");
  assert.equal(calls[0].body.buyer.agent_id, "agent-uuid");
  assert.equal(calls[0].body.buyer.agent_name, undefined);
  assert.equal(saved, false);
  assert.equal(field(render(), "Full buyer name").props.value, "Test Buyer");
  assert.equal(nodes(render()).find(node => node.type === "AgentSelect").props.value, "agent-uuid");
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
