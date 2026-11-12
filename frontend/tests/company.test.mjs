import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);

function harness() {
  const slots = []; let cursor = 0;
  const source = readFileSync(new URL("../src/components/projects/CompanyTab.tsx", import.meta.url), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const exports = {};
  let answer = { status: "loading", retry() {} };
  let enabled;
  class ApiError extends Error {}
  runInNewContext(`(function(require,exports){${code}\n})`)((key) => {
    if (key === "react") return { useState(initial) {
      const i = cursor++; slots[i] ??= { value: typeof initial === "function" ? initial() : initial };
      return [slots[i].value, value => { slots[i].value = value; }];
    }};
    if (key === "@/lib/format") return { businessDate: value => value };
    if (key === "@/lib/api") return { ApiError, settings: { currencies() {} } };
    if (key === "@/lib/api/companies") return { companies: {} };
    if (key === "@/lib/answer") return { useAnswer(gate) { enabled = gate; return answer; } };
    if (key === "@/lib/roles") return { PROJECT_FINANCIAL_READERS: new Set(["finance"]), hasAnyRole: (roles, allowed) => [...roles].some(role => allowed.has(role)) };
    if (key === "@/components/shell/navigation") return { sectionIcon: () => undefined };
    if (key === "./CompanyLogo") return { CompanyLogoTile: "CompanyLogoTile", CompanyLogoActions: "CompanyLogoActions" };
    if (key === "./CompanyDocuments") return { CompanyDocuments: "CompanyDocuments" };
    if (key === "./DeleteRecordButton") return { DeleteRecordButton: "DeleteRecordButton" };
    if (key === "@/components/ui") return new Proxy({}, { get: (_, name) => name });
    return require(key);
  }, exports);
  return { exports, ApiError, setAnswer(value) { answer = { retry() {}, ...value }; },
    enabled: () => enabled, render(component, props) { cursor = 0; return exports[component](props); } };
}
function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children), ...nodes(tree.props?.actions)];
}
const find = (tree, type) => nodes(tree).filter(node => node.type === type);

test("blank bank fields submit null and retain leading zero account numbers", async () => {
  const h = harness(); let saved; let closed = false;
  const props = { title: "Add bank account", fields: h.exports.BANK_FIELDS, onSave: async values => { saved = values; }, onClose() { closed = true; } };
  let tree = h.render("CompanyEntryForm", props);
  assert.equal(find(tree, "Field").length, 14);
  assert.ok(find(tree, "Field").every(field => field.props.optional));
  assert.ok([...find(tree, "input"), ...find(tree, "textarea")].every(input => !input.props.required));
  const account = find(tree, "Field").find(field => field.props.label === "Account number").props.children;
  account.props.onChange({ target: { value: "00001234" } });
  tree = h.render("CompanyEntryForm", props);
  assert.equal(find(tree, "DraftBoundary")[0].props.dirty, true);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  assert.equal(saved.account_number, "00001234");
  assert.equal(saved.iban, null);
  assert.equal(Object.keys(saved).length, 14);
  assert.equal(closed, true);
});

test("failed save keeps entered values and does not close the editor", async () => {
  const h = harness(); let closed = false;
  const props = { title: "Edit company", fields: h.exports.COMPANY_FIELDS, initial: { legal_name: "Saved" },
    onSave: async () => { throw new h.ApiError("Save refused"); }, onClose() { closed = true; } };
  let tree = h.render("CompanyEntryForm", props);
  find(tree, "input")[0].props.onChange({ target: { value: "Unsaved" } });
  tree = h.render("CompanyEntryForm", props);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  tree = h.render("CompanyEntryForm", props);
  assert.equal(find(tree, "input")[0].props.value, "Unsaved");
  assert.equal(find(tree, "Notice")[0].props.children, "Save refused");
  assert.equal(closed, false);
});

test("two accounts appear independently and denied readers do not request company details", () => {
  const h = harness();
  h.setAnswer({ status: "ready", data: [{ id: "company", legal_name: "Example", bank_accounts: [
    { id: "first", beneficiary_bank: "First Bank", account_number: "0001" },
    { id: "second", beneficiary_bank: "Second Bank", account_number: "0002" },
  ] }] });
  const tree = h.render("CompanyTab", { projectId: "project", roles: new Set(["finance"]) });
  assert.equal(h.enabled(), true);
  assert.deepEqual(find(tree, "SectionHeader").map(node => node.props.title), ["Identity & registration", "Address & contacts", "Bank accounts"]);
  assert.deepEqual(find(tree, "SubPanel").map(node => node.props.title), ["First Bank", "Second Bank"]);
  assert.equal(find(tree, "DeleteRecordButton").length, 3);
  // Every delete sits behind its record's menu; Edit stays visible beside it.
  assert.ok(find(tree, "RowMenu").every(menu => find(menu.props.children, "DeleteRecordButton").length >= 1));
  assert.equal(find(tree, "RowMenu").length, 3);
  h.setAnswer({ status: "off" });
  h.render("CompanyTab", { projectId: "project", roles: new Set(["sales_advisor"]) });
  assert.equal(h.enabled(), false);
});


test("company role and relationship are dropdowns and percentage stays a decimal string", async () => {
  const h = harness(); let saved;
  const props = { title: "Add company", fields: h.exports.COMPANY_FIELDS, onSave: async values => { saved = values; }, onClose() {} };
  let tree = h.render("CompanyEntryForm", props);
  const fields = find(tree, "Field");
  const role = fields.find(node => node.props.label === "Company role in the project").props.children;
  assert.equal(role.type, "select");
  assert.equal(find(role, "option").length, 7);
  role.props.onChange({ target: { value: "other" } });
  tree = h.render("CompanyEntryForm", props);
  assert.ok(find(tree, "Field").some(node => node.props.label === "Other role"));
  const percentage = find(tree, "Field").find(node => node.props.label === "Ownership share in project (%)").props.children;
  percentage.props.onChange({ target: { value: "0.1250" } });
  tree = h.render("CompanyEntryForm", props);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  assert.equal(saved.ownership_percentage, "0.1250");
  assert.equal(saved.project_role, "other");
});

test("non-finance readers never render bank details even if a response contains them", () => {
  const h = harness();
  h.setAnswer({ status: "ready", data: [{ id: "company", legal_name: "Example", bank_accounts: [{ id: "bank", account_number: "secret" }] }] });
  const tree = h.render("CompanyTab", { projectId: "project", roles: new Set(["project_manager"]) });
  assert.ok(!find(tree, "SectionHeader").some(node => node.props.title === "Bank Details"));
});

test("adding a parent selects the saved record and preserves the company draft", async () => {
  const h = harness(); let saved; let parentValues;
  const parent = { id: "parent-1", legal_name: "Parent Ltd", registration_number: "0012", bank_accounts: [] };
  const props = { title: "Edit company", fields: h.exports.COMPANY_FIELDS, initial: { legal_name: "Original" }, relatedCompanies: [],
    onSaveRelated: async values => { parentValues = values; return parent; }, onSave: async values => { saved = values; }, onClose() {} };
  let tree = h.render("CompanyEntryForm", props);
  find(tree, "Field").find(node => node.props.label === "Legal company name").props.children.props.onChange({ target: { value: "Draft company" } });
  tree = h.render("CompanyEntryForm", props);
  find(tree, "Button").find(node => node.props.children === "Add parent company").props.onClick();
  tree = h.render("CompanyEntryForm", props);
  assert.equal(find(tree, "StickyActions")[0].props.disabled, true);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  assert.equal(saved, undefined);
  const editor = find(tree, h.exports.RelatedCompanyEditor)[0];
  await editor.props.onSave({ legal_name: "Parent Ltd", registration_number: "0012" });
  editor.props.onClose();
  tree = h.render("CompanyEntryForm", props);
  assert.equal(parentValues.registration_number, "0012");
  const relation = find(tree, "Field").find(node => node.props.label === "Parent or related company").props.children;
  assert.equal(relation.props.value, parent.id);
  assert.ok(find(relation, "option").some(node => node.props.children === "Parent Ltd"));
  find(tree, "Button").find(node => node.props.children === "Edit parent company details").props.onClick();
  tree = h.render("CompanyEntryForm", props);
  const edit = find(tree, h.exports.RelatedCompanyEditor)[0];
  assert.equal(edit.props.row.id, parent.id);
  edit.props.onClose();
  tree = h.render("CompanyEntryForm", props);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  assert.equal(saved.legal_name, "Draft company");
  assert.equal(saved.related_company_id, parent.id);
});

test("parent save failure retains entries and never submits a nested form", async () => {
  const h = harness(); let closed = false; const busyStates = [];
  const props = { onSave: async () => { throw new h.ApiError("Parent save refused"); }, onClose() { closed = true; }, onBusy(value) { busyStates.push(value); } };
  let tree = h.render("RelatedCompanyEditor", props);
  assert.equal(find(tree, "form").length, 0);
  assert.ok(find(tree, "Field").every(field => field.props.optional));
  find(tree, "input")[0].props.onChange({ target: { value: "Unsaved parent" } });
  tree = h.render("RelatedCompanyEditor", props);
  await find(tree, "Button").find(node => node.props.children === "Save parent company").props.onClick();
  tree = h.render("RelatedCompanyEditor", props);
  assert.equal(find(tree, "input")[0].props.value, "Unsaved parent");
  assert.equal(find(tree, "DraftBoundary")[0].props.dirty, true);
  assert.ok(find(tree, "Notice")[0].props.children.includes("Parent save refused"));
  assert.deepEqual(busyStates, [true, false]);
  assert.equal(closed, false);
  assert.equal(find(tree, "Button").find(node => node.props.children === "Cancel parent details").props["data-leaves-editor"], true);
});


test("profile shows entered details at full weight and names missing ones once", () => {
  const h = harness();
  h.setAnswer({ status: "ready", data: [{ id: "company", legal_name: "Example", registration_number: "0042", ownership_percentage: "12.5000", project_role: "investor", status: "active", bank_accounts: [] }] });
  const page = h.render("CompanyTab", { projectId: "project", roles: new Set(["project_manager"]) });
  // Expand the profile's detail groups, which the harness leaves as component nodes.
  const tree = [page, ...find(page, h.exports.RecordedDetails).map(node => node.type(node.props))];
  const values = find(tree, "KeyValue");
  assert.deepEqual([...values.map(node => node.props.label)], ["Registration number"]);
  assert.equal(values[0].props.value, "0042");
  assert.equal(values[0].props.mono, true);
  assert.ok(!values.some(node => node.props.value === "Not entered"));
  const missing = nodes(tree).filter(node => node.type === "p" && String(node.props.className).includes("company-missing"));
  assert.equal(missing.length, 2);
  assert.match(missing.map(node => [].concat(node.props.children).join("")).join(" "), /Tax \/ VAT number/);
  const strip = find(page, "RecordStrip")[0].props;
  assert.equal(strip.lead.value, "12.5000%");
  assert.equal(strip.items[0].value, "Investor");
  assert.equal(strip.items[1].tone, "muted");
});

test("long company form gets section links and a sticky save bar; short bank form does not", () => {
  const h = harness();
  let tree = h.render("CompanyEntryForm", { title: "Add company", fields: h.exports.COMPANY_FIELDS, onSave: async () => {}, onClose() {} });
  assert.deepEqual([...find(tree, "FormOutline")[0].props.sections], ["Identity & registration", "Project & ownership", "Address & contacts", "Notes"]);
  assert.equal(find(tree, "StickyActions").length, 1);
  const status = find(tree, "Field").find(node => node.props.label === "Company status").props.children;
  assert.equal(status.type, "Segmented");
  assert.deepEqual([...status.props.options.map(option => option.value)], ["", "active", "inactive", "under_review"]);
  tree = h.render("CompanyEntryForm", { title: "Add bank account", fields: h.exports.BANK_FIELDS, onSave: async () => {}, onClose() {} });
  assert.equal(find(tree, "FormOutline").length, 0);
  assert.equal(find(tree, "StickyActions").length, 0);
});
