import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { createRequire } from "node:module";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);
const settle = () => new Promise(resolve => setImmediate(resolve));

test("sales opens only Technical Specifications and never requests construction costs", async () => {
  let costs = 0;
  const render = mount("projects/ConstructionTab", "ConstructionTab", {
    "@/lib/api": { construction: { summary: async () => { costs++; } } },
    "@/lib/roles": { CONSTRUCTION_READERS: new Set(["finance"]), hasAnyRole: (roles, allowed) => [...roles].some(role => allowed.has(role)) },
    "@/components/shell/registerState": { useRegisterFields: () => [{ constructionTab: "budget" }, () => {}] },
    "./construction/TechnicalSpecifications": { TechnicalSpecifications: "TechnicalSpecifications" },
  }, { projectId: "project", roles: new Set(["sales_advisor"]) });
  render(); await settle();
  const tree = nodes(render());
  const tabs = tree.find(node => node.type === "Tabs").props;
  assert.equal(tabs.active, "technical-specifications");
  assert.equal(tabs.tabs.length, 1);
  assert.equal(tabs.tabs[0].label, "Technical Specifications");
  assert.equal(costs, 0);
  assert.ok(tree.some(node => node.type === "TechnicalSpecifications"));
});

test("specification guide searches applicability and saves a complete versioned record", async () => {
  const row = { id: "spec", project_id: "project", category: "water", title: "Hot water", scope: "units", applies_to: "All 2-bedroom units", description: "Synthetic heater", buyer_benefit: "Lower energy use", brand_model: "", inclusion: "included", status: "confirmed", source_reference: "Schedule A", version: 4, updated_at: "2026-09-14T10:00:00Z" };
  let saved;
  const render = mount("projects/construction/TechnicalSpecifications", "TechnicalSpecifications", {
    "@/lib/api/technicalSpecifications": { technicalSpecifications: { list: async () => [row], update: async (...args) => { saved = args; } } },
    "@/lib/roles": { hasAnyRole: () => true }, "@/lib/format": { businessDate: value => value },
    "../EditForm": { EditForm: "EditForm" }, "../DeleteRecordButton": { DeleteRecordButton: "DeleteRecordButton" },
  }, { projectId: "project", roles: new Set(["project_manager"]) });
  render(); await settle();
  nodes(render()).find(node => node.type === "DataToolbar").props.search.onChange("2-bedroom");
  assert.ok(nodes(render()).some(node => node.type === "SectionHeader" && node.props.title === "Hot water"));
  assert.ok(nodes(render()).some(node => node.type === "DeleteRecordButton"));
  nodes(nodes(render()).find(node => node.type === "SectionHeader" && node.props.title === "Hot water").props.actions)[0].props.onClick();
  const form = nodes(render()).find(node => node.type === "EditForm");
  assert.ok(nodes(render()).some(node => node.type === "RecordPage"));
  await form.props.onSave({ description: "Updated heater", brand_model: null });
  assert.equal(saved[0], "project"); assert.equal(saved[1], "spec");
  assert.equal(saved[2].buyer_benefit, "Lower energy use");
  assert.equal(saved[2].version, 4); assert.equal(saved[2].description, "Updated heater");
  assert.equal(saved[2].applies_to, "All 2-bedroom units"); assert.equal(saved[2].brand_model, "");
});

test("Sales guide separates confirmed specification and buyer value without empty checklist cards", async () => {
  const rows = [
    { id: "confirmed", category: "heating_cooling", title: "AC provision", scope: "units", applies_to: "Selected units", description: "Provision only, subject to approved mechanical design.", buyer_benefit: "Comfortable indoor temperatures.", brand_model: "", inclusion: "included", status: "confirmed", source_reference: "Synthetic mechanical schedule", updated_at: "2026-10-20", version: 1 },
    { id: "draft", category: "finishes", title: "Unconfirmed tile", scope: "units", applies_to: "All units", description: "Draft selection", buyer_benefit: "", brand_model: "", inclusion: "undecided", status: "draft", source_reference: "", updated_at: "2026-10-20", version: 1 },
  ];
  const render = mount("projects/construction/TechnicalSpecifications", "TechnicalSpecifications", {
    "@/lib/api/technicalSpecifications": { technicalSpecifications: { list: async () => rows } },
    "@/lib/roles": { hasAnyRole: () => false }, "@/lib/format": { businessDate: value => value },
    "../EditForm": { EditForm: "EditForm" }, "../DeleteRecordButton": { DeleteRecordButton: "DeleteRecordButton" },
  }, { projectId: "project", roles: new Set(["sales_advisor"]) });
  render(); await settle();
  let tree = nodes(render());
  assert.equal(tree.filter(n => n.type === "Card").length, 1);
  assert.ok(tree.some(n => n.type === "Card" && n.props.title === "Comfort, efficiency & clean design"));
  assert.ok(tree.some(n => n.type === "dd" && n.props.children === rows[0].description));
  assert.ok(tree.some(n => n.type === "dd" && n.props.children === rows[0].buyer_benefit));
  assert.ok(!tree.some(n => n.type === "SectionHeader" && n.props.title === "Unconfirmed tile"));
  assert.ok(!tree.some(n => n.type === "DeleteRecordButton"));
  tree.find(n => n.type === "DataToolbar").props.search.onChange("indoor temperatures");
  assert.ok(nodes(render()).some(n => n.type === "SectionHeader" && n.props.title === "AC provision"));
  nodes(render()).find(n => n.type === "DataToolbar").props.search.onChange("unknown feature");
  assert.ok(nodes(render()).some(n => n.type === "EmptyState" && n.props.title === "No matching specifications"));
});

test("Issued permits offer Completed and submit without a mandatory reason", async () => {
  const calls = [];
  const permit = { id: "permit", permit_code: "TEST", status: "issued", prerequisite_satisfied: true };
  const render = mount("projects/PermitsTab", "PermitFile", {
    "@/lib/api": { projects: { permitHistory: async () => [], transitionPermit: async (...args) => { calls.push(args); return { ...permit, status: "completed" }; } } },
    "@/lib/format": { todayISO: () => "2026-09-12", businessDate: value => value },
  }, { projectId: "project", permit, types: [], permits: [], canWrite: true, canDelete: false,
    typeLabel: value => value, onClose() {}, onNotice() {}, onChanged: async () => {} });
  render(); await settle();
  const choice = nodes(render()).find(n => n.type === "Field" && n.props.label === "Move to").props.children;
  assert.ok(nodes(choice).some(n => n.type === "option" && n.props.value === "completed" && n.props.children === "Completed"));
  choice.props.onChange({ target: { value: "completed" } });
  const reason = nodes(render()).find(n => n.type === "Field" && n.props.label === "Reason");
  assert.equal(reason.props.optional, true);
  assert.ok(!reason.props.children.props.required);
  await nodes(render()).find(n => n.type === "form").props.onSubmit({ preventDefault() {} });
  assert.equal(calls[0][2].to_status, "completed");
  assert.ok(!("reason" in calls[0][2]));
});

test("Permit deletion waits for confirmation and keeps server refusal visible", async () => {
  const calls = []; let removed = 0;
  class ApiError extends Error {}
  const render = mount("projects/PermitsTab", "PermitFile", {
    "@/lib/api": { ApiError, projects: { permitHistory: async () => [], removePermit: async (...args) => { calls.push(args); throw new ApiError("Clear dependent first"); } } },
    "@/lib/format": { todayISO: () => "2026-09-12", businessDate: value => value },
  }, { projectId: "project", permit: { id: "permit", permit_code: "TEST", status: "not_started", prerequisite_satisfied: true },
    types: [], permits: [], canWrite: false, canDelete: true, typeLabel: value => value,
    onClose() {}, onNotice() {}, onChanged: async () => {}, onDeleted: async () => { removed++; } });
  render(); await settle();
  const header = nodes(render()).find(n => n.type === "PageHeader");
  nodes(header.props.actions).find(n => n.type === "Button" && n.props.children === "Delete permit").props.onClick();
  assert.equal(calls.length, 0);
  nodes(render()).find(n => n.type === "ConfirmDialog").props.onConfirm();
  await settle();
  assert.equal(calls.length, 1);
  assert.equal(removed, 0);
  assert.equal(nodes(render()).find(n => n.type === "ConfirmDialog").props.body, "Clear dependent first");
});

test("Permit creation is a full-page single save, retaining all fields after failure", async () => {
  const calls = []; let fail = true; let completed = 0;
  class ApiError extends Error {}
  const render = mount("projects/PermitCreatePage", "PermitCreatePage", {
    "@/lib/api": { ApiError, projects: {
      permitAssignees: async () => [],
      createPermit: async (...args) => { calls.push(args); if (fail) throw new ApiError("Save refused"); return { id: "permit" }; },
    } },
    "@/lib/format": { todayISO: () => "2026-09-12" },
  }, { projectId: "project", types: [], parcels: [], permits: [], statuses: { issued: "Issued" }, canSeeCost: true,
    currencyCode: "EUR", onCancel() {}, onCreated: async () => { completed++; } });
  render(); await settle();
  const change = (label, value) => nodes(render()).find(n => n.type === "Field" && n.props.label === label).props.children.props.onChange({ target: { value } });
  nodes(render()).find(n => n.type === "input" && n.props.type === "checkbox").props.onChange({ target: { checked: true } });
  for (const [label, value] of [["Permit code", "TEST"], ["Authority", "Council"], ["New type code", "new"], ["New type name", "New consent"], ["Fee", "1234.56"], ["Conditions", "Keep this condition"], ["Issued", "2026-09-10"]]) change(label, value);
  assert.ok(nodes(render()).some(n => n.type === "article"));
  assert.ok(!nodes(render()).some(n => ["RecordPage", "FormDialog"].includes(n.type)));
  await nodes(render()).find(n => n.type === "form").props.onSubmit({ preventDefault() {} });
  assert.equal(calls.length, 1);
  assert.equal(calls[0][1].new_permit_type.label, "New consent");
  assert.equal(calls[0][1].fee_amount, "1234.56");
  assert.equal(calls[0][1].initial_status, undefined);
  assert.equal(calls[0][1].status_effective_date, undefined);
  assert.equal(calls[0][1].issue_date, "2026-09-10");
  assert.equal(nodes(render()).find(n => n.type === "Field" && n.props.label === "Conditions").props.children.props.value, "Keep this condition");
  assert.equal(completed, 0);
  fail = false;
  await nodes(render()).find(n => n.type === "form").props.onSubmit({ preventDefault() {} });
  assert.equal(completed, 1);
});

const landFormat = {};
runInNewContext(ts.transpileModule(readFileSync(new URL("../src/lib/format.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, { exports: landFormat });

function landFixture(canWrite = true) {
  let rejectWrite = true;
  const calls = [];
  const analytics = {
    land_area_sqm: "100", max_buildable_area_sqm: "200", purchase_cost_per_sqm: "1000.00",
    purchase_cost_per_buildable_sqm: "500.00", acquisition_cost_per_sqm: "1100.00",
    acquisition_cost_per_buildable_sqm: "550.00", purchase_cost_to_gdv_fraction: null,
    acquisition_cost_to_gdv_fraction: null, market_years: [],
  };
  const props = { projectId: "project", parcel: { id: "parcel", expected_gdv_amount: null, base_currency_code: "EUR", purchase_price: "100000.00", total_acquisition_cost: "110000.00" }, canWrite,
    onChanged: async () => { props.parcel = { ...props.parcel, expected_gdv_amount: "200000.00" }; } };
  class ApiError extends Error {}
  const projects = {
    landAnalytics: async () => analytics,
    writeLandMarketYear: async (...args) => { calls.push(args); if (rejectWrite) throw new ApiError("Write refused"); return analytics; },
    updateParcel: async (...args) => { calls.push(args); return { ...props.parcel, expected_gdv_amount: "200000.00" }; },
  };
  const render = mount("projects/land/LandAnalytics", "LandAnalytics", {
    "@/lib/api": { ApiError, projects }, "@/lib/format": landFormat,
  }, props);
  return { render, calls, recover() { rejectWrite = false; } };
}

test("Land analytics preserves a failed annual draft and sends the exact signed percentage", async () => {
  const f = landFixture(); f.render(); await settle();
  let tree = nodes(f.render());
  tree.find(n => n.type === "Field" && n.props.label === "Year").props.children.props.onChange({ target: { value: "2027" } });
  tree.find(n => n.type === "Field" && n.props.label === "Expected increase / decrease (%)").props.children.props.onChange({ target: { value: "-5.25" } });
  await nodes(f.render()).filter(n => n.type === "form")[1].props.onSubmit({ preventDefault() {} });
  tree = nodes(f.render());
  assert.equal(f.calls[0][3], "-0.0525");
  assert.equal(tree.find(n => n.type === "Field" && n.props.label === "Year").props.children.props.value, "2027");
  assert.ok(JSON.stringify(tree).includes("Write refused"));
  f.recover();
  await tree.filter(n => n.type === "form")[1].props.onSubmit({ preventDefault() {} });
  assert.equal(nodes(f.render()).find(n => n.type === "Field" && n.props.label === "Year").props.children.props.value, "");
});

test("Land analytics canonicalizes saved GDV so a successful save leaves no false dirty draft", async () => {
  const f = landFixture(); f.render(); await settle();
  nodes(f.render()).find(n => n.type === "Field" && n.props.label === "Expected GDV for this parcel").props.children.props.onChange({ target: { value: "200000" } });
  await nodes(f.render()).find(n => n.type === "form").props.onSubmit({ preventDefault() {} });
  assert.equal(f.calls[0][2].expected_gdv_amount, "200000");
  assert.equal(f.render().props.dirty, false);
});

test("Land analytics read-only permission exposes metrics but no write controls", async () => {
  const f = landFixture(false); f.render(); await settle();
  const tree = nodes(f.render());
  assert.ok(tree.some(n => n.type === "KeyValue" && n.props.value === "EUR 1,000.00"));
  assert.ok(!tree.some(n => n.type === "form"));
  assert.equal(f.calls.length, 0);
});

// Execute the real reader callbacks and render branches with a small hook
// lifecycle. No requests are made and no component implementation is copied.
function mount(file, name, dependencies, props) {
  const slots = []; let cursor = 0; let effects = [];
  const same = (a, b) => a?.length === b.length && b.every((v, i) => Object.is(v, a[i]));
  const react = {
    useRef(initial) { const i = cursor++; slots[i] ??= { current: initial }; return slots[i]; },
    useState(initial) { const i = cursor++; slots[i] ??= { value: typeof initial === "function" ? initial() : initial }; return [slots[i].value, v => { slots[i].value = typeof v === "function" ? v(slots[i].value) : v; }]; },
    useMemo(fn, deps) { const i = cursor++; if (!same(slots[i]?.deps, deps)) slots[i] = { deps, value: fn() }; return slots[i].value; },
    useCallback(fn, deps) { return react.useMemo(() => fn, deps); },
    useEffect(fn, deps) { const i = cursor++; if (!same(slots[i]?.deps, deps)) effects.push(() => { slots[i]?.cleanup?.(); slots[i] = { deps, cleanup: fn() }; }); },
  };
  const exports = {};
  const source = readFileSync(new URL(`../src/components/${file}.tsx`, import.meta.url), "utf8") + `\nexport { ${name} as TestedComponent };`;
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const ui = new Proxy({}, { get: (_, key) => key });
  runInNewContext(`(function(require, exports) { ${code}\n})`, { setTimeout, clearTimeout, crypto: globalThis.crypto })(key => {
    if (key === "react") return react;
    if (key in dependencies) return dependencies[key];
    if (key === "@/lib/api") return { ApiError: class extends Error { fieldErrors = []; } };
    if (key === "@/components/ui") return ui;
    if (key === "@/components/shell/navigation") return { sectionDescription: () => "", projectHref: () => "/projects/" };
    if (key === "@/lib/roles") return { hasAnyRole: () => false };
    if (key === "./presentation" || key === "@/components/projects/land/presentation" || key === "./permits/presentation") {
      const helper = {};
      const helperPath = key === "./permits/presentation" ? "permits" : "land";
      const compiled = ts.transpileModule(readFileSync(new URL(`../src/components/projects/${helperPath}/presentation.ts`, import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
      runInNewContext(`(function(exports) { ${compiled}\n})`)(helper);
      return helper;
    }
    if (key.startsWith("@/") || key.startsWith("./")) return {};
    return require(key);
  }, exports);
  return () => { cursor = 0; effects = []; const tree = exports.TestedComponent(props); effects.forEach(fn => fn()); return tree; };
}
test("Design payment retries a failed optional PDF without recording the payment twice", async () => {
  const records = [], uploads = []; let fail = true, done = 0;
  const currencyId = "74e15285-fd35-46dc-a3d1-d377459f8bbc";
  const saved = { id: "payment", expense: {} };
  const render = mount("projects/design/DesignPayments", "PaymentForm", {
    "@/lib/api": { ApiError: class extends Error {}, consultantEngineering: {
      recordPayment: async (...args) => { records.push(args); return saved; },
      uploadPaymentProof: async (...args) => { uploads.push(args); if (fail) throw new Error("Connection lost"); },
    } },
    "@/lib/answer": { useAnswer: () => ({ status: "ready", data: { amount: "105.00", vat_amount: "5.00" } }) },
    "@/lib/format": { todayISO: () => "2026-10-26", businessDate: value => value, money: value => value },
  }, { projectId: "0fdbd0e1-90fc-4a24-b535-561b0bd67d77", stage: { id: "023e4172-7c6c-49dd-be1f-78bf4e5ea1ba", name: "Lighting", actual_completion_date: "2026-10-01", updated_at: "2026-10-01T10:00:00Z" }, agreement: { consultant_name: "Lighting Ltd" }, currencyId, currencyCode: "EUR", onDone() { done++; }, onCancel() {} });
  const field = label => nodes(render()).find(n => n.type === "Field" && n.props.label === label).props.children;
  field("Amount excluding VAT").props.onChange("100.00");
  field("VAT (%)").props.onChange({ target: { value: "5" } });
  const file = { name: "proof.pdf", size: 40 };
  field("PDF proof of payment").props.onChange({ target: { files: [file] } });
  nodes(render()).find(n => n.type === "form").props.onSubmit({ preventDefault() {} }); await settle();
  assert.equal(records.length, 1); assert.equal(done, 0);
  assert.equal(records[0][2].currency_id, currencyId);
  assert.equal(records[0][2].expected_stage_updated_at, "2026-10-01T10:00:00Z");
  assert.equal(records[0][2].amount_ex_vat, "100.00");
  assert.ok(nodes(render()).some(n => n.type === "Notice" && n.props.children.includes("Payment saved")));
  assert.equal(field("Amount excluding VAT").props.disabled, true);
  fail = false;
  nodes(render()).find(n => n.type === "form").props.onSubmit({ preventDefault() {} }); await settle();
  assert.equal(records.length, 1); assert.equal(uploads.length, 2);
  assert.equal(uploads[1][2], file); assert.equal(done, 1);
});

test("Design actual payment reads are gated before loading for engineering-only users", () => {
  let allowed;
  const render = mount("projects/design/DesignPayments", "DesignPayments", {
    "@/lib/answer": { useAnswer: gate => { allowed = gate; return { status: "off" }; } },
    "@/lib/roles": { hasAnyRole: () => false },
  }, { projectId: "project", roles: new Set(["engineer"]), stages: [], agreement: { id: "agreement" } });
  render(); assert.equal(allowed, false);
});

function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children), ...nodes(tree.props?.actions)];
}

test("active consultant agreement edits the same record and keeps a refused save open", async () => {
  const row = { id: "agreement", consultant_name: "Original", agreement_reference: "CE-1", status: "active", updated_at: "version-1" };
  const calls = []; let fail = true;
  class ApiError extends Error {}
  const render = mount("projects/ConsultantEngineerTab", "ConsultantEngineerTab", {
    "@/lib/api": { ApiError, consultantEngineering: {
      workspace: async () => ({ active_engagement: row, engagements: [row], disciplines: [], stages: [], deliverables: [] }),
      updateEngagement: async (...args) => { calls.push(args); if (fail) throw new ApiError("Agreement changed. Reload before saving."); },
    } },
    "@/lib/roles": { hasAnyRole: () => true },
    "@/lib/format": { businessDate: value => value ?? "—" },
  }, { projectId: "project", roles: new Set(["master_admin"]) });
  render(); await settle();
  nodes(render()).find(n => n.type === "Button" && n.props.children === "Edit agreement").props.onClick();
  let dialog = nodes(render()).find(n => n.props?.editor);
  assert.equal(dialog.props.editor.row.id, "agreement");
  await dialog.props.onSubmit({ consultant_name: "Corrected", agreement_reference: "CE-2" }); await settle();
  assert.equal(calls[0][0], "project"); assert.equal(calls[0][1], "agreement");
  assert.equal(calls[0][2].expected_updated_at, "version-1");
  dialog = nodes(render()).find(n => n.props?.editor);
  assert.ok(dialog.props.error.includes("Reload"));
  fail = false; await dialog.props.onSubmit({ consultant_name: "Corrected", agreement_reference: "CE-2" }); await settle();
  assert.ok(!nodes(render()).some(n => n.props?.editor));
});

test("Pre-Launch renders server category amounts after the register and honors confirmation eligibility", async () => {
  const calls = [];
  const row = { id: "expense", invoice_reference: "INV-17", evidence_reference: "EVID-29", movement_reference: "MOV-08", category: "design", amount: "1.01", movement_date: "2026-09-12", status: "recorded", can_confirm: true };
  const render = mount("projects/PreLaunchTab", "PreLaunchTab", {
    "@/lib/api": { ApiError: Error, prelaunch: {
      register: async () => ({ expenses: [row], recorded_amount: "1.01", confirmed_paid_amount: "2.02", categories: [{ category: "design", recorded_amount: "1.01", confirmed_paid_amount: "2.02", total_amount: "3.03", confirmed_share_percent: "100.00" }] }),
      confirm: async (...args) => { calls.push(args); row.can_confirm = false; row.status = "confirmed"; },
    } },
    "@/lib/roles": { hasAnyRole: () => true }, "@/lib/format": landFormat,
  }, { projectId: "project", roles: new Set(["master_admin"]), currencyCode: "USD" });
  render(); await settle();
  const tree = nodes(render());
  assert.ok(tree.findIndex(n => n.props?.className === "expense-category-list") > tree.findIndex(n => n.props?.className === "expense-entry-list"));
  assert.ok(tree.some(n => n.type === "dd" && n.props.children === landFormat.money("3.03", "USD")));
  for (const reference of ["INV-17", "EVID-29", "MOV-08"]) assert.ok(tree.some(n => n.type === "dd" && n.props.children === reference));
  const confirm = tree.find(n => n.type === "Button" && n.props.children === "Confirm");
  assert.equal(confirm.props.disabled, false);
  await confirm.props.onClick(); await settle();
  assert.equal(calls[0][1], "expense"); assert.equal(calls[0][2].amount, "1.01");
  assert.ok(!nodes(render()).some(n => n.type === "Button" && n.props.children === "Confirm"));
});
function apiFixture() {
  let failed = true; const calls = [];
  class ApiError extends Error {}
  const api = new Proxy({}, { get: (_, name) => async () => { calls.push(name); if (failed) throw new ApiError("Temporary read failure"); return []; } });
  return { ApiError, api, calls, recover() { failed = false; } };
}

test("Pre-Launch keeps a failed removal open, refreshes eligibility and blocks duplicate submits", async () => {
  const row = { id: "expense", category: "utilities", amount: "1250.25", movement_date: "2026-01-01",
    notes: "Water fee", counterparty_reference: null, invoice_reference: null, evidence_reference: null,
    status: "recorded", can_edit: true, can_remove: true, currency_code: "USD" };
  const calls = []; let reject; let reads = 0;
  class ApiError extends Error { constructor(status, message) { super(message); this.status = status; } }
  const prelaunch = {
    register: async () => { reads++; return { expenses: [row], categories: [], recorded_amount: "1250.25", confirmed_paid_amount: "0" }; },
    remove: (...args) => { calls.push(args); return new Promise((_, no) => { reject = no; }); },
  };
  const render = mount("projects/PreLaunchTab", "PreLaunchTab", {
    "@/lib/api": { ApiError, prelaunch }, "@/lib/format": landFormat,
  }, { projectId: "project", currencyId: "currency", currencyCode: "USD", roles: [] });
  render(); await settle();
  nodes(render()).find(n => n.type === "Button" && n.props.children === "Remove").props.onClick();
  const dialog = nodes(render()).find(n => n.type === "PromptDialog");
  dialog.props.onSubmit("Duplicate"); dialog.props.onSubmit("Duplicate");
  assert.equal(calls.length, 1);
  assert.equal(calls[0][2].expected.amount, "1250.25");
  reject(new ApiError(409, "Expense changed")); await settle();
  const failed = nodes(render()).find(n => n.type === "PromptDialog");
  assert.equal(failed.props.error, "Expense changed");
  assert.equal(failed.props.busy, false);
  assert.equal(reads, 2);
});

test("Pre-Launch editor sends only editable fields and retains corrected values after an error", async () => {
  const initial = { id: "expense", category: "utilities", amount: "1250.25", movement_date: "2026-01-01",
    notes: "Water fee", counterparty_reference: "Authority", invoice_reference: "INV", evidence_reference: "proof" };
  let submitted;
  const props = { projectId: "project", initial, currencyId: "currency", currencyCode: "USD", busy: false, error: null,
    onCancel() {}, onSubmit(body) { submitted = body; } };
  const render = mount("projects/PreLaunchTab", "ExpenseDialog", {
    "@/lib/api": { prelaunch: { preview: async body => ({ amount: "99.99", vat_amount: null }) } },
    "@/lib/format": landFormat,
  }, props);
  nodes(render()).find(n => n.type === "MoneyInput").props.onChange("99.99");
  assert.equal(nodes(render()).find(n => n.type === "DraftBoundary").props.dirty, true);
  await new Promise(resolve => setTimeout(resolve, 300));
  nodes(render()).find(n => n.type === "form").props.onSubmit({ preventDefault() {} });
  assert.equal(submitted.amount, "99.99");
  assert.equal(submitted.invoice_reference, "INV");
  assert.ok(!("currency_id" in submitted));
  props.error = "Validation refused";
  assert.equal(nodes(render()).find(n => n.type === "MoneyInput").props.value, "99.99");
  assert.ok(nodes(render()).some(n => n.type === "Notice" && n.props.children === "Validation refused"));
});

test("Pre-Launch VAT input sends net and percentage strings and waits for the matching server total", async () => {
  const requests = []; let submitted;
  const render = mount("projects/PreLaunchTab", "ExpenseDialog", {
    "@/lib/api": { ApiError: Error, prelaunch: { preview: (...args) => new Promise(resolve => requests.push({ args, resolve })) } },
    "@/lib/format": landFormat,
  }, { projectId: "project", currencyId: "currency", currencyCode: "USD", busy: false, error: null,
    onCancel() {}, onSubmit(body) { submitted = body; } });
  const change = (label, value) => nodes(render()).find(n => n.type === "Field" && n.props.label === label).props.children.props.onChange({ target: { value } });
  change("Notes", "Design expense"); change("Payment / movement date", "2026-10-18");
  nodes(render()).find(n => n.type === "MoneyInput").props.onChange("1000.00");
  change("VAT (%)", "5"); render();
  await new Promise(resolve => setTimeout(resolve, 300));
  assert.equal(requests[0].args[1].amount_ex_vat, "1000.00");
  assert.equal(requests[0].args[1].vat_rate_percent, "5");
  assert.equal(nodes(render()).find(n => n.type === "Button" && n.props.type === "submit").props.disabled, true);
  change("VAT (%)", "10"); render();
  requests[0].resolve({ amount: "1050.00", vat_amount: "50.00" }); await settle();
  assert.ok(!nodes(render()).some(n => n.type === "PositionFigure"));
  await new Promise(resolve => setTimeout(resolve, 300));
  requests[1].resolve({ amount: "1100.00", vat_amount: "100.00" }); await settle();
  assert.equal(nodes(render()).find(n => n.type === "PositionFigure" && n.props.label === "Total including VAT").props.value, landFormat.money("1100.00", "USD"));
  nodes(render()).find(n => n.type === "form").props.onSubmit({ preventDefault() {} });
  assert.equal(submitted.amount_ex_vat, "1000.00"); assert.equal(submitted.vat_rate_percent, "10");
  assert.ok(!("amount" in submitted)); assert.equal(submitted.currency_id, "currency");
});

test("Authorities expense Notes are optional, retained after failure and clearable", async () => {
  const submissions = [];
  const props = { projectId: "fa058b5d-5300-473c-80ca-e4fd340d635d", currencyId: "0bea5f65-7f36-4473-bca7-351a226fda15", currencyCode: "USD", busy: false, error: null,
    onCancel() {}, onSubmit(body) { submissions.push(body); } };
  const render = mount("projects/PreLaunchTab", "ExpenseDialog", {
    "@/lib/api": { prelaunch: { preview: async () => ({ amount: "100.00", vat_amount: "0.00" }) } },
    "@/lib/format": landFormat,
  }, props);
  const notes = () => nodes(render()).find(n => n.type === "Field" && n.props.label === "Notes");
  assert.equal(notes().props.optional, true);
  assert.equal(notes().props.children.type, "textarea");
  assert.ok(!notes().props.children.props.required);
  assert.equal(nodes(render()).find(n => n.type === "RecordPage").props.title, "Add Authorities expense");
  nodes(render()).find(n => n.type === "Field" && n.props.label === "Payment / movement date").props.children.props.onChange({ target: { value: "2026-10-29" } });
  nodes(render()).find(n => n.type === "MoneyInput").props.onChange("100.00");
  render(); await new Promise(resolve => setTimeout(resolve, 300));
  const save = () => nodes(render()).find(n => n.type === "form").props.onSubmit({ preventDefault() {} });
  assert.equal(nodes(render()).find(n => n.type === "Button" && n.props.type === "submit").props.disabled, false);
  save(); assert.equal(submissions[0].notes, null);
  notes().props.children.props.onChange({ target: { value: "Utility connection\nReceipt to follow" } });
  save(); assert.equal(submissions[1].notes, "Utility connection\nReceipt to follow");
  props.error = "Save refused";
  assert.equal(notes().props.children.props.value, "Utility connection\nReceipt to follow");
  assert.ok(nodes(render()).some(n => n.type === "Notice" && n.props.children === "Save refused"));
  notes().props.children.props.onChange({ target: { value: "   " } });
  save(); assert.equal(submissions[2].notes, null);
});

test("legacy VAT conversion clears the unknown total and failed previews retain the entered rate", async () => {
  const initial = { id: "legacy", amount: "1050.00", amount_ex_vat: null, vat_rate_percent: null, notes: "Legacy fee", category: "design", movement_date: "2026-10-18" };
  const render = mount("projects/PreLaunchTab", "ExpenseDialog", {
    "@/lib/api": { ApiError: Error, prelaunch: { preview: async () => { throw new Error("Preview unavailable"); } } },
    "@/lib/format": landFormat,
  }, { projectId: "project", initial, currencyCode: "USD", busy: false, error: null, onCancel() {}, onSubmit() {} });
  nodes(render()).find(n => n.type === "Button" && n.props.children === "Enter VAT breakdown").props.onClick();
  assert.equal(nodes(render()).find(n => n.type === "MoneyInput").props.value, "");
  nodes(render()).find(n => n.type === "MoneyInput").props.onChange("1000.00");
  nodes(render()).find(n => n.type === "Field" && n.props.label === "VAT (%)").props.children.props.onChange({ target: { value: "5" } });
  render(); await new Promise(resolve => setTimeout(resolve, 300));
  assert.ok(nodes(render()).some(n => n.type === "Button" && n.props.children === "Retry total"));
  assert.equal(nodes(render()).find(n => n.type === "Field" && n.props.label === "VAT (%)").props.children.props.value, "5");
  assert.equal(nodes(render()).find(n => n.type === "Button" && n.props.type === "submit").props.disabled, true);
});
for (const component of ["ContractsSection", "VariationsSection", "CertificatesSection", "CashSection", "MilestonesSection", "ForecastSection"]) {
  test(`${component}: failed read retries GETs and accepts a recovered empty response`, async () => {
    const f = apiFixture();
    const render = mount("projects/ConstructionTab", component, { "@/lib/api": { ApiError: f.ApiError, construction: f.api }, "@/components/shell/registerState": { useRegisterFields: () => [{ contractSearch: "", contractStatus: "", constructionContract: "" }, () => {}] } }, { projectId: "synthetic" });
    render(); await settle();
    const failed = nodes(render());
    assert.ok(failed.some(node => node.type === "Notice" && node.props.children === "Temporary read failure"));
    assert.ok(!failed.some(node => node.type === "EmptyState"));
    const retry = failed.find(node => node.type === "Button" && node.props.children === "Retry");
    assert.ok(retry);
    f.recover(); const before = f.calls.length; await retry.props.onClick(); await settle();
    const ready = nodes(render());
    assert.ok(f.calls.length > before);
    assert.ok(!ready.some(node => node.type === "Notice"));
    assert.ok(!ready.some(node => node.type === "Loading"));
    assert.ok(!ready.some(node => node.type === "Button" && node.props.children === "Retry"));
    assert.ok(f.calls.every(name => ["budgets", "contracts", "variations", "certificates", "invoices", "payments", "milestones", "forecasts"].includes(name)));
  });
}

for (const [component, dependency, readyData, label] of [
  ["DocumentsTab", "projects", [], "Retry documents"],
  ["PreLaunchTab", "prelaunch", { expenses: [], categories: [], recorded_amount: "0", confirmed_paid_amount: "0" }, "Retry Authorities expenses"],
  ["ConsultantEngineerTab", "consultantEngineering", { engagements: [], disciplines: [], stages: [], deliverables: [] }, "Retry Design"],
]) {
  test(`${component}: retry clears the read error without calling a write`, async () => {
    let failed = true; const calls = [];
    class ApiError extends Error {}
    const api = new Proxy({}, { get: (_, method) => async () => {
      calls.push(method);
      if (failed) throw new ApiError("Temporary read failure");
      return readyData;
    } });
    const render = mount(`projects/${component}`, component, {
      "@/lib/api": { ApiError, [dependency]: api, settings: { referenceValues: async () => [] } },
      "@/lib/format": { money: () => "JOD 0.00" },
    }, { projectId: "synthetic", roles: new Set(), canWrite: false, currencyId: "synthetic", currencyCode: "JOD" });
    render(); await settle();
    const errorTree = nodes(render());
    const retry = errorTree.find(node => node.type === "Button" && node.props.children === label);
    assert.ok(retry);
    failed = false; const before = calls.length; await retry.props.onClick(); await settle();
    const recovered = nodes(render());
    assert.ok(calls.length > before);
    assert.ok(!recovered.some(node => node.type === "Notice" && node.props.children === "Temporary read failure"));
    assert.ok(calls.every(method => ["documents", "documentTypes", "parcels", "permits", "register", "workspace"].includes(method)));
  });
}

test("Payment Plans retries its register without submitting a new plan", async () => {
  let failed = true; let reads = 0;
  class ApiError extends Error {}
  const render = mount("projects/PaymentPlansTab", "PaymentPlansTab", {
    "@/lib/api": { ApiError, paymentPlans: { register: async () => { reads++; if (failed) throw new ApiError("Temporary read failure"); return { rows: [] }; } } },
    "@/lib/currency": { useCurrencyCode: () => () => "JOD" },
    "@/lib/format": { todayISO: () => "2026-09-11" },
    "@/components/projects/payments/labels": { versionLabel: value => value },
    "next/navigation": { useRouter: () => ({}) },
    "@/components/ui": new Proxy({ useRecordHref: () => () => "" }, { get: (target, key) => target[key] ?? key }),
    "@/components/shell/registerState": { useRegisterRestore() {}, useRegisterFields: () => [{ search: "", status: "" }, () => {}] },
    "@/components/shell/navigation": { sectionDescription: () => "", projectHref: () => "/projects/" },
  }, { projectId: "synthetic", projectStatus: "active", roles: new Set() });
  render(); await settle();
  const retry = nodes(render()).find(node => node.type === "Button" && node.props.children === "Retry payment plans");
  assert.ok(retry); failed = false; await retry.props.onClick(); await settle();
  assert.equal(reads, 2);
  assert.ok(!nodes(render()).some(node => node.type === "Notice"));
});

test("Portfolio offers the existing retry on failure, never on denied access", () => {
  let calls = 0;
  const retry = () => calls++;
  const render = mount("portfolio/Portfolio", "Pending", {}, { answer: { status: "failed", message: "Temporary read failure", retry } });
  const button = nodes(render()).find(node => node.type === "Button");
  button.props.onClick(); assert.equal(calls, 1);
  const denied = mount("portfolio/Portfolio", "Pending", {}, { answer: { status: "denied", retry } });
  assert.ok(!nodes(denied()).some(node => node.type === "Button"));
});


test("Budget workspace retains failed-read recovery after adding the version register", () => {
  let failed = true; let retries = 0;
  const render = mount("projects/construction/BudgetWorkspace", "BudgetWorkspace", {
    "@/lib/answer": { useAnswer: () => failed ? { status: "failed", message: "Temporary read failure", retry() { retries++; failed = false; } } : { status: "ready", data: [], retry() {} } },
    "@/components/shell/registerState": { useRegisterFields: () => [{ budgetVersion: "" }, () => {}] },
    "@/components/shell/navigation": { projectHref: () => "/projects/" },
  }, { projectId: "synthetic", roles: new Set(), onChanged: async () => {} });
  const button = nodes(render()).find(node => node.type === "Button" && node.props.children === "Retry budget versions");
  assert.ok(button); button.props.onClick(); assert.equal(retries, 1);
  const recovered = nodes(render());
  assert.ok(recovered.some(node => node.type === "EmptyState" && node.props.title === "No budget versions"));
  assert.ok(!recovered.some(node => node.type === "Notice" && node.props.children === "Temporary read failure"));
});

test("Budget line editor submits exact decimal strings and never rewrites a copied baseline", () => {
  let payload;
  const render = mount("projects/construction/BudgetWorkspace", "BudgetEditor", {
    "@/lib/format": { todayISO: () => "2026-09-11" },
  }, { editor: { kind: "line", code: { id: "code", code: "HARD", name: "Works" }, line: { approved_budget_amount: "1.00", contingency_amount: "0.00", baseline_amount: "900.00" } }, detail: { source_version_id: "source", currency_code: "JOD" }, versions: [], busy: false, failure: null, onSubmit: body => { payload = body; }, onCancel() {} });
  const amount = nodes(render()).find(node => node.type === "Field" && node.props.label === "Budget authorization");
  amount.props.children.props.onChange("123456789.12");
  render().props.onSubmit();
  assert.equal(payload.approved_budget_amount, "123456789.12");
  assert.equal(payload.contingency_amount, "0.00");
  assert.ok(!("baseline_amount" in payload));
});

test("Budget rejection keeps the typed reason when the server refuses the write", () => {
  let payload;
  const props = { editor: { kind: "reject" }, detail: { status: "approved" }, versions: [], busy: false, failure: null, onSubmit: body => { payload = body; }, onCancel() {} };
  const render = mount("projects/construction/BudgetWorkspace", "BudgetEditor", { "@/lib/format": { todayISO: () => "2026-09-11" } }, props);
  const reason = nodes(render()).find(node => node.type === "Field" && node.props.label === "Rejection reason");
  reason.props.children.props.onChange({ target: { value: "Recheck commitment coverage" } });
  render().props.onSubmit();
  assert.equal(payload.reason, "Recheck commitment coverage");
  props.failure = new Error("Conflict: version changed");
  const failed = render();
  assert.equal(failed.props.title, "Return budget for correction");
  assert.equal(nodes(failed).find(node => node.type === "Field" && node.props.label === "Rejection reason").props.children.props.value, "Recheck commitment coverage");
  assert.ok(nodes(failed).some(node => node.type === "Notice" && node.props.children === props.failure.message));
});

test("Budget workspace offers correction when activation is blocked, without opening a second candidate", () => {
  let count = 0;
  const detail = { id: "candidate", version_number: 2, status: "approved", lines: [], workflow: { editing_blocker: "Frozen", activation_blocker: "Existing commitments exceed authorization", rejection_blocker: null } };
  const render = mount("projects/construction/BudgetWorkspace", "BudgetWorkspace", {
    "@/lib/answer": { useAnswer: () => ({ status: "ready", data: [[{ id: "candidate", status: "approved", version_number: 2 }], [], detail][count++ % 3], retry() {} }) },
    "@/components/shell/registerState": { useRegisterFields: () => [{ budgetVersion: "candidate" }, () => {}] },
    "@/components/shell/navigation": { projectHref: () => "/projects/" },
    "@/lib/roles": { hasAnyRole: () => true },
    "@/lib/format": { businessDate: () => "Date" },
  }, { projectId: "synthetic", roles: new Set(["approver_cfo"]), onChanged: async () => {} });
  const tree = nodes(render());
  assert.equal(tree.find(node => node.type === "Button" && node.props.children === "Activate budget").props.disabled, true);
  assert.equal(tree.find(node => node.type === "Button" && node.props.children === "Return for correction").props.disabled, false);
  assert.ok(!tree.some(node => node.type === "Button" && node.props.children === "Create budget revision"));
});


test("Budget revision waits for its selected source instead of silently copying the active version", () => {
  let count = 0;
  const render = mount("projects/construction/BudgetWorkspace", "BudgetWorkspace", {
    "@/lib/answer": { useAnswer: () => [
      { status: "ready", data: [{ id: "active", status: "active", version_number: 1 }] },
      { status: "ready", data: [] },
      { status: "failed", message: "Selected version unavailable", retry() {} },
    ][count++ % 3] },
    "@/components/shell/registerState": { useRegisterFields: () => [{ budgetVersion: "rejected-source" }, () => {}] },
    "@/components/shell/navigation": { projectHref: () => "/projects/" },
    "@/lib/roles": { hasAnyRole: () => true },
  }, { projectId: "synthetic", roles: new Set(["finance"]), onChanged: async () => {} });
  const tree = nodes(render());
  assert.equal(tree.find(node => node.type === "Button" && node.props.children === "Create budget revision").props.disabled, true);
  assert.ok(tree.some(node => node.type === "Button" && node.props.children === "Retry selected budget"));
});

const contractFormat = {};
runInNewContext(ts.transpileModule(readFileSync(new URL('../src/lib/format.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, { exports: contractFormat });

test("Signed contract entry preserves exact amounts, percentage conversion and unstated tax", () => {
  let payload;
  const render = mount("projects/construction/ContractWorkflow", "ContractHeaderEditor", { "@/lib/format": contractFormat }, { currencyId: "f63c733c-bfaa-4236-8ab4-ea103f265854", currencyCode: "JOD", busy: false, failure: null, onSubmit: body => { payload = body; }, onCancel() {} });
  const set = (label, value, custom = false) => {
    const field = nodes(render()).find(node => node.type === "Field" && node.props.label === label);
    field.props.children.props.onChange(custom ? value : { target: { value } });
  };
  set("Contract reference", "CT-EXACT"); set("Main contractor / subcontractor name", "Vendor"); set("Signed contract document reference", "Signed agreement");
  set("Contract value excluding tax", "123456789.12", true); set("Retention percentage", "5.5", true);
  nodes(render()).find(node => node.type === "form").props.onSubmit({ preventDefault() {} });
  assert.equal(payload.original_contract_value_ex_tax, "123456789.12");
  assert.equal(payload.retention_rate_fraction, "0.055");
  assert.equal(payload.tax_rate_fraction, null);
  assert.equal(payload.currency_id, "f63c733c-bfaa-4236-8ab4-ea103f265854");
  assert.equal(payload.signed_contract, true);
  assert.equal(payload.signed_reference, "Signed agreement");
  set("Tax percentage", "0", true); nodes(render()).find(node => node.type === "form").props.onSubmit({ preventDefault() {} });
  assert.equal(payload.tax_rate_fraction, "0");
});

test("Contract workflow uses the total and exposes no line entry", () => {
  const render = mount("projects/construction/ContractWorkflow", "ContractWorkflow", { "@/lib/format": contractFormat }, { projectId: "p", detail: {status: "draft", workflow: {editing_blocker: null, signed_registration_blocker: null}, lines: []}, reading: false, unavailable: false });
  const tree = nodes(render());
  assert.ok(tree.some(n => n.type === "Button" && n.props.children === "Activate signed contract"));
  assert.ok(!tree.some(n => n.type === "Button" && n.props.children === "Add contract line"));
});

test("Contract cancellation keeps the reason after a failed request and remains cancelable on failed refresh", () => {
  const props = { action: "cancel", busy: false, failure: null, onSubmit() {}, onCancel() {} };
  const render = mount("projects/construction/ContractWorkflow", "ContractDecision", {}, props);
  nodes(render()).find(node => node.type === "Field").props.children.props.onChange({ target: { value: "Wrong scope; prepare replacement" } });
  props.failure = new Error("Conflict"); props.unavailable = true;
  const tree = render();
  assert.equal(tree.props.disabled, true); assert.equal(tree.props.busy, false);
  assert.equal(nodes(tree).find(node => node.type === "Field").props.children.props.value, "Wrong scope; prepare replacement");
});

test("Contract workspace renders server activation blockers and offers no draft edits after submission", () => {
  const render = mount("projects/construction/ContractWorkflow", "ContractWorkflow", { "@/lib/format": contractFormat }, { projectId: "project", detail: { status: "submitted", original_contract_value_ex_tax: "100.00", line_total: "100.00", currency_code: "JOD", lines: [], workflow: { editing_blocker: "Frozen", signed_registration_blocker: "Currency must match project", cancellation_blocker: null } }, codes: [], codesReady: true, reading: false, unavailable: false, onChanged: async () => {}, onRefresh: async () => {} });
  const tree = nodes(render());
  assert.equal(tree.find(node => node.type === "Button" && node.props.children === "Activate signed contract").props.disabled, true);
  assert.ok(!tree.some(node => node.type === "Button" && node.props.children === "Edit draft terms"));
  assert.ok(tree.some(node => node.props.children === "Currency must match project"));
});

test("Contract confirmation disables itself when refreshed eligibility changes", () => {
  const props = { projectId: "project", detail: { status: "submitted", original_contract_value_ex_tax: "100.00", line_total: "100.00", currency_code: "JOD", lines: [], workflow: { editing_blocker: "Frozen", signed_registration_blocker: null, cancellation_blocker: null } }, codes: [], codesReady: true, reading: false, unavailable: false, onChanged: async () => {}, onRefresh: async () => {} };
  const render = mount("projects/construction/ContractWorkflow", "ContractWorkflow", { "@/lib/format": contractFormat }, props);
  nodes(render()).find(node => node.type === "Button" && node.props.children === "Activate signed contract").props.onClick();
  props.detail.workflow.signed_registration_blocker = "Already activated by another operator";
  const dialog = nodes(render()).find(node => typeof node.type === "function" && node.type.name === "ContractDecision");
  assert.equal(dialog.props.unavailable, true);
  assert.equal(dialog.props.failure.message, "Already activated by another operator");
});

test("Consultant tabs separate programme from agreement and do not treat missing deliverables as complete", async () => {
 const row={id:"agreement",consultant_name:"Sample",agreement_reference:"CE-1",status:"active"};
 const render=mount("projects/ConsultantEngineerTab","ConsultantEngineerTab",{
  "@/lib/api":{ApiError:Error,consultantEngineering:{workspace:async()=>({active_engagement:row,engagements:[row],disciplines:[],stages:[{id:"stage",engagement_id:row.id,name:"Concept",sequence:1,status:"not_started",planned_date:null}],deliverables:[],outstanding_deliverables:0})}},
  "@/lib/roles":{hasAnyRole:()=>true},"@/lib/format":{businessDate:v=>v??"—"},
 },{projectId:"project",roles:new Set(["master_admin"])});
 render();await settle();
 let tree=nodes(render());
 assert.equal(tree.find(n=>n.type==="PositionFigure"&&n.props.label==="Outstanding deliverables").props.value,"Not registered");
 assert.ok(tree.some(n=>n.type==="Button"&&n.props.children==="Edit agreement"));
 tree.find(n=>n.type==="Tabs").props.onSelect("programme");tree=nodes(render());
 assert.ok(!tree.some(n=>n.type==="Button"&&n.props.children==="Edit agreement"));
 assert.ok(tree.some(n=>n.type==="KeyValue"&&n.props.value==="Not scheduled"));
 assert.ok(!tree.some(n=>n.type==="Button"&&n.props.children==="Move up"));
 const programme=tree.find(n=>n.type==="SubPanel"&&n.props.title==="Design programme");
 assert.ok(nodes(programme.props.actions).some(n=>n.type==="Button"&&n.props.children==="Reorder stages"&&n.props.disabled));
});
test("programme deliverables stay with their stage and open the existing editable record", async()=>{
 const agreement={id:"a",status:"active",consultant_name:"Sample",agreement_reference:"CE"};
 const item={id:"d",engagement_id:"a",stage_id:"s",name:"Drawings",status:"submitted",revision_reference:"R2"};
 const render=mount("projects/ConsultantEngineerTab","ConsultantEngineerTab",{
  "@/lib/api":{ApiError:Error,consultantEngineering:{workspace:async()=>({active_engagement:agreement,engagements:[agreement],disciplines:[],stages:[{id:"s",engagement_id:"a",name:"Concept",sequence:1,status:"in_progress"}],deliverables:[item,{...item,id:"accepted",status:"accepted"},{...item,id:"other",stage_id:"other",name:"Other stage"}],outstanding_deliverables:2})}},
  "@/lib/roles":{hasAnyRole:()=>true},"@/lib/format":{businessDate:v=>v??"—"},
 },{projectId:"p",roles:new Set(["master_admin"])});
 render();await settle();nodes(render()).find(n=>n.type==="Tabs").props.onSelect("programme");
 const tree=nodes(render());const updates=tree.filter(n=>n.type==="Button"&&n.props.children==="Update deliverable");
 assert.equal(updates.length,1);assert.ok(!tree.some(n=>n.type==="strong"&&n.props.children==="Other stage"));
 updates[0].props.onClick();assert.equal(nodes(render()).find(n=>n.props?.editor).props.editor.row.id,"d");
});
test("Construction navigation starts from contracts and has no Budget section", async () => {
  const render = mount("projects/ConstructionTab", "ConstructionTab", {
    "@/lib/api": { construction: { summary: async () => ({ controls: {} }) } },
    "@/lib/roles": { hasAnyRole: () => true },
    "@/components/shell/registerState": { useRegisterFields: defaults => [defaults, () => {}] },
  }, { projectId: "project", roles: new Set(["finance"]) });
  render(); await settle();
  const tabs = nodes(render()).find(node => node.type === "Tabs").props;
  assert.equal(tabs.active, "contracts");
  assert.ok(!tabs.tabs.some(tab => tab.key === "budget"));
});
for (const kind of ["payment", "reduction"]) test(`${kind} entry sends exact values and keeps a failed save open`, async () => {
  let payload; let closed = 0; let fail = true;
  const save = async (_project, _contract, body) => { payload = body; if (fail) throw new Error("Conflict: refresh and retry"); };
  const render = mount("projects/construction/ContractTransactions", "ContractTransactionEditor", {
    "@/lib/api": { construction: { recordPayment: save, createVariation: save } },
    "../DeleteRecordButton": {},
  }, { kind, projectId: "project", contract: { id: "contract", contract_number: "CT-1", vendor_name: "Vendor", currency_id: "f63c733c-bfaa-4236-8ab4-ea103f265854", currency_code: "EUR", lines: [{ cost_code_id: "scope" }], cost_code_position: [{ cost_code_id: "scope", cost_code_name: "Main works" }] }, unavailable: false, onClose() { closed++; }, onChanged: async () => {} });
  const set = (label, value, custom = false) => nodes(render()).find(node => node.type === "Field" && node.props.label === label).props.children.props.onChange(custom ? value : { target: { value } });
  set("Reference", "REF-1"); set(kind === "payment" ? "Payment date" : "Change date", "2026-09-20");
  set(kind === "payment" ? "Amount paid including tax" : "Change amount excluding tax", "123456789.12", true);
  set(kind === "payment" ? "Payment proof reference" : "Agreement / instruction reference", "Receipt 1");
  set(kind === "payment" ? "Notes" : "Description of added or removed items", "Client tiles");
  const submit = () => nodes(render()).find(node => node.type === "form").props.onSubmit({ preventDefault() {} });
  submit(); await settle();
  assert.equal(closed, 0);
  assert.ok(nodes(render()).some(node => node.type === "Notice" && node.props.children.includes("Could not save")));
  assert.equal(payload[kind === "payment" ? "amount" : "adjustment_amount"], "123456789.12");
  if (kind === "payment") { assert.equal(payload.direct_contract_payment, true); assert.equal(payload.proof_reference, "Receipt 1"); assert.equal(payload.invoice_id, null); }
  else { assert.equal(payload.adjustment_kind, "reduction"); assert.equal(payload.cost_code_id, "scope"); }
  fail = false; submit(); await settle(); assert.equal(closed, 1);
});

test("current unit costs show server totals, separate forecasts and a full-page breakdown", () => {
  const figures = { gross_area_sqm: "120.0000", hard_cost_per_sqm: "500.00", hard_cost: "60000.00", land_cost: "40000.00", soft_cost: "10000.00", additional_cost: "0.00", finance_cost: "0.00", direct_cost: "0.00", seller_cost: "0.00", commission_cost: "2000.00", total_cost: "112000.00", total_cost_per_sqm: "933.33", revenue: "165000.00", profit_before_tax: "53000.00", tax_amount: null, net_profit: null };
  const unit = { ...figures, unit_id: "u", unit_reference: "B1-101", building_id: "b", building_name: "Building 1", floor_name: "First floor", revenue_basis: "sold", commission_basis: "released grant", issues: [] };
  const group = { ...figures, id: "b", building_id: "b", label: "Building 1", unit_count: 1, sold_count: 1, cost_complete_count: 1, net_profit_complete_count: 0, sold_revenue: "165000.00", forecast_revenue: "0.00" };
  const report = { as_of_date: "2026-09-20", currency_id: "f63c733c-bfaa-4236-8ab4-ea103f265854", currency_code: "EUR", settings: { revision: 2 }, project: group, buildings: [group], floors: [group], units: [unit], sources: [], issues: ["Profit tax rate not entered"] };
  const render = mount("projects/economics/CurrentCostAnalysis", "AnalysisView", { "@/lib/format": contractFormat, "../DeleteRecordButton": { DeleteRecordButton: "DeleteRecordButton" } }, { report, projectId: "project", canWrite: true, onRefresh() {} });
  let tree = nodes(render());
  assert.equal(tree.find(n => n.type === "KeyValue" && n.props.label === "Total project cost").props.value, "EUR 112,000.00");
  assert.ok(tree.some(n => n.type === "KeyValue" && n.props.label === "Unsold asking-price forecast"));
  assert.ok(tree.some(n => n.type === "DeleteRecordButton"));
  assert.ok(!JSON.stringify(tree).includes(report.currency_id));
  tree.find(n => n.type === "Button" && n.props.children === "B1-101").props.onClick();
  tree = nodes(render());
  assert.ok(tree.some(n => n.type === "RecordPage"));
  assert.equal(tree.find(n => n.type === "KeyValue" && n.props.label === "Estimated net profit").props.value, "—");
});

test("current cost read failures offer retry and forbidden readers never fetch", () => {
  let enabled; let retries = 0;
  const dependencies = { "../DeleteRecordButton": {}, "@/lib/answer": { useAnswer: (flag) => { enabled = flag; return { status: flag ? "failed" : "off", message: "Connection lost", retry: () => retries++ }; } }, "@/lib/roles": { ECONOMICS_READERS: new Set(["finance"]), hasAnyRole: (roles, allowed) => [...roles].some(r => allowed.has(r)) } };
  const props = { projectId: "project", roles: new Set(["sales_advisor"]) };
  const render = mount("projects/economics/CurrentCostAnalysis", "CurrentCostAnalysis", dependencies, props);
  assert.ok(nodes(render()).some(n => n.type === "EmptyState"));
  assert.equal(enabled, false);
  props.roles = new Set(["finance"]);
  nodes(render()).find(n => n.type === "Button").props.onClick();
  assert.equal(enabled, true); assert.equal(retries, 1);
});

test("current cost inputs preserve exact amounts, explicit zero tax and failed drafts", async () => {
  let sent; let saved = 0; let fail = true;
  const area = { id: "area", label: "Gross built", area_role: "gross", is_active: true, unit_of_measure: "sqm" };
  const render = mount("projects/economics/CurrentCostAnalysis", "SettingsEditor", {
    "../DeleteRecordButton": {}, "@/lib/format": contractFormat,
    "@/lib/answer": { useAnswer: () => ({ status: "ready", data: [area] }) },
    "@/lib/api": { unitEconomics: { writeCurrentCostSettings: async (_id, body) => { sent = body; if (fail) throw new Error("Inputs changed; refresh before saving"); } } },
  }, { projectId: "project", settings: null, code: "EUR", onClose() {}, onSaved() { saved++; } });
  const field = label => nodes(render()).find(n => n.type === "Field" && n.props.label === label).props.children;
  field("Approved gross-built area").props.onChange({ target: { value: "area" } });
  field("Supplemental soft costs").props.onChange("123456789.12");
  field("Profit tax %").props.onChange("0");
  field("Reason for saving").props.onChange({ target: { value: "Recorded signed costs" } });
  const submit = () => nodes(render()).find(n => n.type === "form").props.onSubmit({ preventDefault() {} });
  submit(); await settle();
  assert.equal(sent.supplemental_soft_cost, "123456789.12");
  assert.equal(sent.additional_cost, null);
  assert.equal(sent.profit_tax_rate_fraction, "0");
  assert.equal(sent.expected_revision, 0);
  assert.equal(saved, 0);
  assert.equal(field("Supplemental soft costs").props.value, "123456789.12");
  assert.ok(nodes(render()).find(n => n.type === "DraftBoundary").props.dirty);
  assert.ok(nodes(render()).some(n => n.type === "Notice" && n.props.children.includes("Could not save cost inputs")));
  fail = false; submit(); await settle(); assert.equal(saved, 1);
});


test("Documents: project types work without Settings and a new type is selected", async () => {
  const calls = []; let types = [];
  const projects = {
    documents: async () => [], parcels: async () => [], permits: async () => ({ permits: [] }),
    documentTypes: async () => types,
    createDocumentType: async (id, label) => { calls.push([id, label]); const row = { id: "type", code: "DOC_NEW", label, is_active: true, removable: true }; types = [row]; return row; },
  };
  const render = mount("projects/DocumentsTab", "DocumentsTab", {
    "@/lib/api": { projects, ApiError: class extends Error {} },
    "@/components/ui/UnsavedChangesGuard": { DraftBoundary: "DraftBoundary" },
  }, { projectId: "project", canWrite: true });
  render(); await settle();
  nodes(render()).find(n => n.type === "Button" && n.props.children === "New document").props.onClick();
  assert.ok(nodes(render()).some(n => n.type === "RecordPage" && n.props.title === "New document"));
  const field = nodes(render()).find(n => n.type === "Field" && n.props.label === "New document type");
  nodes(field).find(n => n.type === "input").props.onChange({ target: { value: "Survey" } });
  const form = nodes(render()).filter(n => n.type === "form")[1];
  await form.props.onSubmit({ preventDefault() {} });
  assert.deepEqual(calls, [["project", "Survey"]]);
  const select = nodes(nodes(render()).find(n => n.type === "Field" && n.props.label === "Document type")).find(n => n.type === "select");
  assert.equal(select.props.value, "DOC_NEW");
  assert.ok(nodes(select).some(n => n.type === "option" && n.props.children === "Survey"));
});

test("Documents: failed PDF upload retains file and typed metadata", async () => {
  class ApiError extends Error {}
  const calls = [];
  const projects = {
    documents: async () => [], parcels: async () => [], permits: async () => ({ permits: [] }),
    documentTypes: async () => [{ id: "type", code: "DEED", label: "Deed", is_active: true }],
    uploadDocument: async (...args) => { calls.push(args); throw new ApiError("Upload failed"); },
  };
  const render = mount("projects/DocumentsTab", "DocumentsTab", {
    "@/lib/api": { projects, ApiError },
    "@/components/ui/UnsavedChangesGuard": { DraftBoundary: "DraftBoundary" },
  }, { projectId: "project", canWrite: true });
  render(); await settle();
  nodes(render()).find(n => n.type === "Button" && n.props.children === "New document").props.onClick();
  const control = label => nodes(nodes(render()).find(n => n.type === "Field" && n.props.label === label)).find(n => ["input", "select"].includes(n.type));
  control("Title").props.onChange({ target: { value: "Site deed" } });
  control("Document type").props.onChange({ target: { value: "DEED" } });
  control("Document source").props.onChange({ target: { value: "pdf" } });
  const file = { name: "deed.pdf", size: 100 };
  control("PDF file").props.onChange({ target: { files: [file] } });
  await nodes(render()).find(n => n.type === "form").props.onSubmit({ preventDefault() {} });
  assert.equal(calls[0][0], "project"); assert.equal(calls[0][1].title, "Site deed");
  assert.equal(calls[0][1].document_type_code, "DEED"); assert.equal(calls[0][2], file);
  assert.equal(control("Title").props.value, "Site deed");
  assert.ok(nodes(render()).some(n => n.type === "Notice" && n.props.children === "Upload failed"));
  await nodes(render()).find(n => n.type === "form").props.onSubmit({ preventDefault() {} });
  assert.equal(calls[1][2], file);
});

test("Documents: readers download PDFs without mutation controls", async () => {
  const calls = [];
  const row = { id: "doc", title: "Deed", document_type_code: "DEED", filename: "deed.pdf", external_url: null, is_active: true };
  const projects = { documents: async () => [row], parcels: async () => [], permits: async () => ({ permits: [] }), documentTypes: async () => [], downloadDocument: async (...args) => { calls.push(args); } };
  const render = mount("projects/DocumentsTab", "DocumentsTab", { "@/lib/api": { projects, ApiError: class extends Error {} } }, { projectId: "project", canWrite: false });
  render(); await settle();
  const tree = nodes(render());
  assert.ok(!tree.some(n => n.type === "Button" && ["New document", "Document types", "Edit"].includes(n.props.children)));
  tree.find(n => n.type === "Button" && n.props.children === "Download PDF").props.onClick(); await settle();
  assert.equal(calls[0][0], "project"); assert.equal(calls[0][1], row);
});

test("certificate entry sends a single period amount and exact deductions atomically", async () => {
  let payload;
  const render = mount("projects/construction/ContractDocuments", "DocumentEditor", {
    "../DeleteRecordButton": {},
    "@/lib/api": {construction: {createCertificate: async (_p, _c, body) => {payload=body;}}},
    "@/lib/format": contractFormat,
  }, {projectId:"p", mode:"certificates", contract:{id:"c", contract_number:"CT", vendor_name:"Vendor", currency_code:"EUR", certified_to_date:"100.00", advance_outstanding:"20.00", retention_outstanding:"10.00", cost_code_position:[{cost_code_id:"scope"}]}, certificates:[], onClose(){}, async onChanged(){}});
  const set=(label,value,custom=false)=>nodes(render()).find(n=>n.type==="Field"&&n.props.label===label).props.children.props.onChange(custom?value:{target:{value}});
  set("Reference","IPC-2"); set("Document date","2026-10-18"); set("Period start","2026-10-01"); set("Period end","2026-10-18");
  set("Work completed this period, excluding tax","123456.78",true); set("Advance recovery this period","10.01",true); set("Certificate / completion evidence reference","Engineer certificate");
  nodes(render()).find(n=>n.type==="form").props.onSubmit({preventDefault(){}}); await settle();
  assert.equal(payload.current_work_value_ex_tax,"123456.78"); assert.equal(payload.advance_recovery_amount,"10.01"); assert.equal(payload.cost_code_id,null);
  assert.ok(!("lines" in payload));
});

test("paid invoice selection is sent without recomputing its balance", async () => {
  let payload;
  const render=mount("projects/construction/ContractTransactions","ContractTransactionEditor", {
    "../DeleteRecordButton": {},
    "@/lib/api":{construction:{recordPayment:async(_p,_c,body)=>{payload=body;}}},
    "@/lib/format":contractFormat,
  }, {kind:"payment",projectId:"p",contract:{id:"c",contract_number:"CT",lines:[],cost_code_position:[],currency_code:"EUR",currency_id:"f63c733c-bfaa-4236-8ab4-ea103f265854"}, invoices:[{id:"invoice",status:"approved",invoice_number:"ADV-1",invoice_type:"advance",outstanding:"100.00"}], onClose(){},async onChanged(){}});
  nodes(render()).find(n=>n.type==="select").props.onChange({target:{value:"invoice"}});
  nodes(render()).find(n=>n.type==="MoneyInput").props.onChange("25.01");
  nodes(render()).find(n=>n.type==="form").props.onSubmit({preventDefault(){}}); await settle();
  assert.equal(payload.invoice_id,"invoice"); assert.equal(payload.amount,"25.01"); assert.equal(payload.direct_contract_payment,true);
});
