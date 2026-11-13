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

test("material editor keeps custom category and selected file after a failed upload", async () => {
  const h = harness("MarketingAssets");
  let submitted;
  const props = { placement: "material", categories: [], onClose() {}, onSave: async (values, file) => { submitted = { values, file }; throw new Error("offline"); } };
  let tree = h.render("AssetEditor", props);
  find(tree, "input").find(n => n.props.list).props.onChange({ target: { value: "Research references" } });
  tree = h.render("AssetEditor", props);
  const file = { name: "logo.png", size: 80 };
  find(tree, "input").find(n => n.props.type === "file").props.onChange({ target: { files: [file] } });
  tree = h.render("AssetEditor", props);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  tree = h.render("AssetEditor", props);
  assert.equal(submitted.values.category, "Research references");
  assert.equal(submitted.file, file);
  assert.equal(find(tree, "DraftBoundary")[0].props.dirty, true);
  assert.ok(find(tree, "Notice").some(n => String(n.props.children).includes("kept")));
});

test("logo editor restricts sources and rejects an oversized file before submission", async () => {
  const h = harness("MarketingAssets");
  let calls = 0;
  const props = { placement: "logo", categories: [], onClose() {}, onSave() { calls++; } };
  let tree = h.render("AssetEditor", props);
  assert.equal(find(tree, "select").length, 0);
  const input = find(tree, "input").find(n => n.props.type === "file");
  assert.equal(input.props.accept, ".png,.jpg,.jpeg");
  input.props.onChange({ target: { files: [{ name: "large.png", size: 11 * 1024 * 1024 }] } });
  tree = h.render("AssetEditor", props);
  await find(tree, "form")[0].props.onSubmit({ preventDefault() {} });
  assert.equal(calls, 0);
  assert.ok(find(h.render("AssetEditor", props), "Notice").length);
});

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

test("unit analysis renders server resale, yield and unavailable cap valuation exactly", () => {
  const h = harness("MarketingEconomicsTab", {
    "@/lib/format": { money: (value, code) => value == null ? "Unavailable" : `${code ?? ""} ${value}`, businessDate: value => value },
  });
  const result = {
    currency_id: "00000000-0000-0000-0000-000000000001", scenario_version: 4,
    source_scope: "Unit override", assumptions: null,
    projection: {
      resale_value: "1234567890123.45", net_yield_percent: "-1.25", cap_value: null,
      valuation_basis: "Recorded unit valuation", warnings: ["Synthetic projection"],
      irr_percent: null, irr_reason: "Multiple sign transitions", rental_payback_years: null,
      total_payback_year: null, discounted_payback_year: null, simple_payback_years: null,
      years: [{ year: 1, rental_months: 6, gross_yield_percent: "2.50", net_yield_percent: "-1.25", cumulative_cashflow: "-101250.00" }],
    },
  };
  const tree = h.render("RentalProjection", { result });
  const serialized = JSON.stringify(tree);
  assert.ok(serialized.includes("EUR 1234567890123.45"));
  assert.ok(serialized.includes("-1.25%"));
  assert.ok(serialized.includes("Unavailable: non-positive year-six NOI"));
  assert.ok(serialized.includes("Multiple sign transitions"));
  assert.ok(!serialized.includes(result.currency_id));
});

function amenityFieldModule() {
  const source = readFileSync(new URL('../src/components/projects/marketing/amenityFields.ts', import.meta.url), 'utf8');
  const exports = {};
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  runInNewContext(`(function(exports){${code}\n})`)(exports);
  return exports;
}

test('amenities keep seven ordered names and show recorded zero/false without inventing facts', () => {
  const fields = amenityFieldModule();
  assert.equal(fields.AMENITIES.map(item => item.name).join('|'), "Swimming Pools|Garden View Gym|Tropical Garden View|Energy-Efficient Project|Kid's Play Area|Balconies With Premium View|Dedicated Parking Lots");
  const h = harness('ProjectAmenities', { './amenityFields': fields });
  assert.equal(h.exports.amenityFacts('parking', {}).length, 0);
  assert.ok(h.exports.amenityFacts('parking', { parking: { visitor_spaces: 0 } }).includes('Visitor spaces: 0'));
  assert.ok(h.exports.amenityFacts('garden', { garden: { shared_garden: false } }).includes('Shared garden: No'));
  const facts = h.exports.amenityFacts('gym', { gym: { area_sqm: '120.25', location: 'Garden', equipment: 'Treadmills', access: 'Residents', status: 'available' } });
  assert.equal(facts.length, 3);
  let tree = h.render('ProjectAmenities', { legacyNames: ['Legacy name'] });
  assert.equal(find(tree, 'Button').length, 7);
  find(tree, 'Button')[1].props.onClick();
  tree = h.render('ProjectAmenities', { legacyNames: ['Legacy name'] });
  assert.equal(find(tree, 'RecordPage')[0].props.title, 'Garden View Gym');
});

test('amenity child deletion asks for confirmation and retains other entries and amenities', () => {
  const fields = amenityFieldModule();
  const h = harness('AmenityEditor', { './amenityFields': fields });
  let value = { swimming_pools: { pools: [{ id: 'one', name: 'First pool' }, { id: 'two', name: 'Second pool' }] }, parking: { visitor_spaces: 0 }, balconies: { balconies: [{ id: 'three', unit_type: 'Studio' }] } };
  const props = () => ({ value, onChange: next => { value = next; } });
  let tree = h.render('AmenityEditor', props());
  find(tree, 'Button').find(node => String(node.props.children).replaceAll(',', '') === 'Delete pool 1').props.onClick();
  assert.equal(value.swimming_pools.pools.length, 2);
  tree = h.render('AmenityEditor', props());
  assert.equal(find(tree, 'ConfirmDialog')[0].props.title, 'Delete First pool?');
  find(tree, 'ConfirmDialog')[0].props.onConfirm();
  assert.equal(value.swimming_pools.pools.length, 1);
  assert.equal(value.swimming_pools.pools[0].id, 'two');
  assert.equal(value.parking.visitor_spaces, 0);
  assert.equal(value.balconies.balconies[0].id, 'three');
});

test('bio Save changes forwards optional amenity details and retains draft after save failure', async () => {
  const h = harness('MarketingContentEditor');
  const narrative = { paragraph: '', bullets: [] };
  const initial = { country: narrative, area: narrative, project: narrative, location: narrative, nearby: [], amenities: ['Existing amenity'], source: '', as_of: null, roi_min_percent: null, roi_max_percent: null, roi_basis: '' };
  let submitted;
  const props = { kind: 'bio', initial, onClose() {}, onSave: async data => { submitted = data; throw new Error('offline'); } };
  let tree = h.render('MarketingContentEditor', props);
  find(tree, 'AmenityEditor')[0].props.onChange({ gym: { area_sqm: '42.75' } });
  tree = h.render('MarketingContentEditor', props);
  assert.equal(find(tree, 'StickyActions')[0].props.submitLabel, 'Save changes');
  await find(tree, 'form')[0].props.onSubmit({ preventDefault() {} });
  assert.equal(submitted.amenity_details.gym.area_sqm, '42.75');
  assert.equal(submitted.amenities[0], 'Existing amenity');
  tree = h.render('MarketingContentEditor', props);
  assert.equal(find(tree, 'AmenityEditor')[0].props.value.gym.area_sqm, '42.75');
  assert.equal(find(tree, 'DraftBoundary')[0].props.dirty, true);
});
