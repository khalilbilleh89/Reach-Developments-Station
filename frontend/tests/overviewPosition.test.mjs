import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);

/**
 * The overview's commercial band, collections position and standing grid,
 * rendered.
 *
 * The structural guards prove these components are shaped like the rest of the
 * product and name only classes the stylesheet declares. They cannot tell
 * whether a figure is the right figure, whether a bar describes the building
 * it claims to, or whether two currencies quietly become one. That is what
 * these are for.
 */
function mount(file, component, dependencies, props) {
  const slots = [];
  let cursor = 0;
  const react = {
    useState(initial) {
      const i = cursor++;
      slots[i] ??= { value: typeof initial === "function" ? initial() : initial };
      return [slots[i].value, (v) => { slots[i].value = typeof v === "function" ? v(slots[i].value) : v; }];
    },
    useRef(initial) { const i = cursor++; slots[i] ??= { current: initial }; return slots[i]; },
    useEffect() {},
  };
  const source = readFileSync(new URL(`../src/components/dashboard/${file}.tsx`, import.meta.url), "utf8");
  const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const exports = {};
  runInNewContext(`(function(require,exports){${code}\n})`)((key) => {
    if (key === "react") return react;
    if (key in dependencies) return dependencies[key];
    if (key.startsWith("@/components/ui")) return new Proxy({}, { get: (_, name) => name });
    return require(key);
  }, exports);
  cursor = 0;
  return exports[component](props);
}

// A child component of the file under test is rendered in place, so the tree
// reads through it; a primitive from the UI package stays an element named
// after itself, with the figures it was handed still on its props.
const expand = (tree) =>
  tree && typeof tree === "object" && !Array.isArray(tree) && typeof tree.type === "function" ? tree.type(tree.props) : tree;
const nodes = (tree) => {
  tree = expand(tree);
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children)];
};
const textOf = (tree) => {
  tree = expand(tree);
  if (tree == null || typeof tree === "boolean") return "";
  if (typeof tree !== "object") return String(tree);
  if (Array.isArray(tree)) return tree.map(textOf).join(" ");
  return textOf(tree.props?.children);
};
const ofType = (tree, type) => nodes(tree).filter((node) => node.type === type);
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/;
// Every string a primitive was handed: labels, values, amounts, notes.
const handed = (tree) =>
  nodes(tree).flatMap((node) => Object.values(node.props ?? {}).filter((value) => typeof value === "string"));
const withClass = (tree, name) =>
  nodes(tree).filter((node) => typeof node.props?.className === "string" && node.props.className.split(" ").includes(name));

const format = { money: (value, code) => (value === null || value === undefined ? "—" : code ? `${code} ${value}` : String(value)), businessDate: (value) => value };

/**
 * Currency ids are UUIDs, and the fixtures say so.
 *
 * The first version of this suite wrote ``currency_id: "EUR"`` and asserted
 * "EUR 180.00". It passed, and the shipped page rendered
 * "2e654ca7-0122-4323-8ba2-38d58a2f94b8 217,377.30" at an owner, because a
 * fixture shaped like the answer cannot test the step that produces it. Every
 * id below is a UUID, and only the register turns one into a code.
 */
const CYP_ID = "2e654ca7-0122-4323-8ba2-38d58a2f94b8";
const EUR_ID = "7b1d0f26-93aa-4a55-9f0e-2c1b6d84a071";
const UNKNOWN_ID = "00000000-0000-4000-8000-000000000000";
const REGISTER = { [CYP_ID]: "CYP", [EUR_ID]: "EUR" };
const currency = { useCurrencyCode: () => (id) => (id ? (REGISTER[id] ?? null) : null) };

const register = (over = {}) => ({
  units: [], total: 50, sold_count: 0, reserved_count: 0, available_count: 50, held_count: 0, unreleased_count: 0, ...over,
});

function selling(props) {
  return mount("SellingPosition", "SellingPosition", { "@/lib/format": format, "@/lib/currency": currency }, {
    units: null, deals: null, currencyCode: "CYP", onNavigate() {}, ...props,
  });
}

test("the stock bar divides the whole building, and a state with no units takes no width", () => {
  const tree = selling({ units: register({ sold_count: 10, reserved_count: 5, available_count: 30, unreleased_count: 5 }) });
  const parts = withClass(tree, "selling-bar-part");

  assert.deepEqual(parts.map((part) => part.props.style.width), ["20%", "10%", "60%", "10%"], "each band is its own share of 50 units");
  assert.equal(parts.length, 4, "held has no units, so it draws no segment at all");
  assert.equal(parts.reduce((sum, part) => sum + parseFloat(part.props.style.width), 0), 100);
});

test("a development that has sold nothing still draws its stock rather than an empty frame", () => {
  const tree = selling({ units: register() });
  const parts = withClass(tree, "selling-bar-part");

  assert.deepEqual(parts.map((part) => part.props.className), ["selling-bar-part selling-bar-available"]);
  assert.equal(parts[0].props.style.width, "100%");
  assert.match(textOf(tree), /Nothing contracted yet/);
});

test("a currency id never reaches the page as the label of a figure", () => {
  // The fault this suite missed once. ``currency_id`` is a UUID, the figure
  // beside it is money an owner reads at a glance, and the two were printed
  // together: "2e654ca7-0122-4323-8ba2-38d58a2f94b8 217,377.30". The assertion
  // is deliberately about the whole rendered tree, not one element, because the
  // id must not appear anywhere on the band.
  const tree = selling({
    units: register({ sold_count: 1, available_count: 49 }),
    currencyCode: "CYP",
    deals: { units: 63, contracted_value: "217377.30", currency_id: CYP_ID, mixed_currency: false },
  });

  assert.doesNotMatch(textOf(tree), UUID, "a raw currency id is rendered where a currency code belongs");
  assert.equal(textOf(withClass(tree, "selling-figure")[0]), "CYP 217377.30");
});

test("the band carries no collections money: that is the card beneath it", () => {
  const tree = selling({ units: register({ sold_count: 1, available_count: 49 }) });
  assert.equal(withClass(tree, "selling-money-figure").length, 0);
  assert.doesNotMatch(textOf(tree), /Collected|Overdue|Due/);
  assert.match(textOf(tree), /Open sales/);
});

test("a sales register spanning currencies states no contracted total", () => {
  const mixed = selling({ units: register(), deals: { units: 50, contracted_value: "999.00", currency_id: null, mixed_currency: true } });
  assert.match(textOf(withClass(mixed, "selling-figure")[0]), /Several currencies/);
  assert.doesNotMatch(textOf(withClass(mixed, "selling-figure")[0]), /999/);

  const single = selling({ units: register({ sold_count: 3 }), deals: { units: 50, contracted_value: "727431.69", currency_id: EUR_ID, mixed_currency: false } });
  assert.equal(textOf(withClass(single, "selling-figure")[0]), "EUR 727431.69");
  assert.match(textOf(single), /3 of 50 units sold/);
});

test("the band renders nothing at all before the unit register has answered", () => {
  assert.equal(selling({ units: null }), null);
});

function standing(props) {
  return mount("ProjectStanding", "ProjectStanding", { "@/lib/format": format }, {
    project: { planned_completion: null, blocking_permit_count: 0, overdue_permit_count: 0 },
    build: null,
    hasCostBasis: false,
    ...props,
  });
}

test("a fact nobody has recorded reads as an answer rather than a failed load", () => {
  const tree = standing();
  const values = withClass(tree, "project-standing-value");

  assert.deepEqual(values.map(textOf), ["Not scheduled", "No budget in force", "None blocking", "None approved"]);
  assert.equal(values.filter((v) => v.props.className.includes("project-standing-absent")).length, 3);
  assert.doesNotMatch(textOf(tree), /—/, "no dash stands in for a fact the project simply has not set");
});

test("a blocking permit is flagged, and a reader who may not see economics is told so", () => {
  const tree = standing({
    project: { planned_completion: "2027-06-30", blocking_permit_count: 2, overdue_permit_count: 1 },
    build: { budget_version_number: 3 },
    hasCostBasis: null,
  });
  const values = withClass(tree, "project-standing-value");

  assert.deepEqual(values.map(textOf), ["2027-06-30", "Budget v3", "2 blocking", "Not visible to you"]);
  assert.ok(values[2].props.className.includes("project-standing-flagged"));
  // textOf joins sibling children with a space, so the count and its words
  // arrive separated by two. The product renders one.
  assert.match(textOf(tree), /1\s+past their statutory period/);
});

/* ------------------------------------------------------------------------ */
/* The collections position                                                  */
/* ------------------------------------------------------------------------ */

const HEAT = { current: "current", "1_30": "warm", "31_60": "warm", "61_90": "hot", "91_plus": "late" };
const labels = {
  AGING_BUCKETS: ["current", "1_30", "31_60", "61_90", "91_plus", "awaiting_trigger"],
  bucketLabel: (bucket) => bucket,
  bucketHeatForAmount: (bucket, amount) => (Number(amount) > 0 ? (HEAT[bucket] ?? "cool") : "cool"),
};
const collectionsFormat = { ...format, isPositive: (value) => Number(value) > 0 };

const purse = (id, over = {}) => ({
  currency_id: id, accounts: 2, outstanding_total: "200.00", due_total: "20.00", overdue_total: "6.00", unapplied_cash: "0.00",
  confirmed_receipts_total: "180.00",
  buckets: { current: "100.00", "1_30": "0.00", "31_60": "0.00", "61_90": "40.00", "91_plus": "60.00", awaiting_trigger: "0.00" },
  bucket_shares: { current: "50.0", "1_30": "0.0", "31_60": "0.0", "61_90": "20.0", "91_plus": "30.0", awaiting_trigger: "0.0" },
  ...over,
});
const summary = (currencies, over = {}) => ({
  as_of: "2026-09-16", accounts: 4, accounts_overdue: 1, accounts_disputed: 0, accounts_cleared: 0, currencies, ...over,
});

function collections(data) {
  return mount("CollectionsPosition", "CollectionsPosition", {
    "@/lib/format": collectionsFormat,
    "@/components/projects/collections/labels": labels,
  }, { summary: data, currencyCodeOf: (id) => (id ? (REGISTER[id] ?? null) : null) });
}

test("two collection currencies each get their own stage and are never added", () => {
  const tree = collections(summary([purse(CYP_ID, { outstanding_total: "100.00" }), purse(EUR_ID)]));

  assert.equal(withClass(tree, "position-stage").length, 2, "one stage per denomination");
  assert.deepEqual(ofType(tree, "PositionFigure").map((figure) => figure.props.value), ["CYP 100.00", "EUR 200.00"]);
  assert.equal(withClass(tree, "currency-block-title").length, 2, "each block is named when there is more than one");
  assert.ok(!handed(tree).some((value) => /300/.test(value)), "no total is invented across the two purses");
});

test("one currency is resolved to its own code, named once, and never by its id", () => {
  const tree = collections(summary([purse(EUR_ID)]));

  assert.equal(withClass(tree, "currency-block-title").length, 0, "a single denomination is not labelled twice");
  assert.equal(ofType(tree, "PositionFigure")[0].props.value, "EUR 200.00");
  assert.deepEqual(ofType(tree, "BreakdownRow").map((row) => row.props.amount), ["EUR 20.00", "EUR 6.00", "EUR 0.00", "EUR 180.00"]);
  assert.ok(!handed(tree).some((value) => UUID.test(value)), "a raw currency id is rendered where a code belongs");
});

test("an unresolvable currency shows its figures undenominated rather than guessing", () => {
  const tree = collections(summary([purse(UNKNOWN_ID)]));
  assert.equal(ofType(tree, "PositionFigure")[0].props.value, "200.00");
  assert.ok(!handed(tree).some((value) => /CYP|EUR/.test(value)), "no other purse's code is borrowed");
});

test("the ledger marks overdue and unapplied only when there is money in them", () => {
  const rows = (data) => Object.fromEntries(ofType(collections(data), "BreakdownRow").map((row) => [row.props.label, row.props]));

  const live = rows(summary([purse(CYP_ID, { unapplied_cash: "0.90" })]));
  assert.equal(live.Overdue.tone, "danger");
  assert.equal(live.Overdue.mark, "danger");
  assert.equal(live["Unapplied cash"].mark, "warning");
  assert.equal(live["Unapplied cash"].tone, undefined, "ninety cents is a mark beside a label, never an amber amount");

  const quiet = rows(summary([purse(CYP_ID, { overdue_total: "0.00" })]));
  assert.equal(quiet.Overdue.tone, "neutral");
  assert.equal(quiet.Overdue.mark, undefined);
  assert.equal(quiet["Unapplied cash"].mark, undefined);
});

test("the ageing track is drawn from the server's shares and the bands print every amount", () => {
  const tree = collections(summary([purse(CYP_ID)]));

  const track = ofType(tree, "DistributionTrack")[0];
  assert.deepEqual(track.props.segments.map((segment) => [segment.key, segment.share, segment.heat]), [
    ["current", "50.0", "current"], ["1_30", "0.0", "cool"], ["31_60", "0.0", "cool"],
    ["61_90", "20.0", "hot"], ["91_plus", "30.0", "late"], ["awaiting_trigger", "0.0", "cool"],
  ]);
  const bands = ofType(tree, "DistributionBand");
  assert.deepEqual(bands.map((band) => band.props.value), ["CYP 100.00", "CYP 0.00", "CYP 0.00", "CYP 40.00", "CYP 60.00", "CYP 0.00"]);
  assert.deepEqual(bands.filter((band) => band.props.empty).map((band) => band.props.label), ["1_30", "31_60", "awaiting_trigger"]);
});

test("a balance the server gave no shares for is still aged in bands", () => {
  const tree = collections(summary([purse(CYP_ID, { bucket_shares: {} })]));
  const track = ofType(tree, "DistributionTrack")[0];
  assert.ok(track.props.segments.every((segment) => segment.share === undefined), "no share is invented from the amounts");
  assert.equal(ofType(tree, "DistributionBand").length, 6);
});

test("the account counts are project-wide and dated once", () => {
  const tree = collections(summary([purse(CYP_ID), purse(EUR_ID)], { accounts: 4, accounts_overdue: 3, accounts_disputed: 1, accounts_cleared: 0 }));
  const items = Object.fromEntries(ofType(tree, "StatStripItem").map((item) => [item.props.label, item.props]));
  assert.equal(items.Accounts.value, 4);
  assert.equal(items.Overdue.value, 3);
  assert.equal(items.Overdue.tone, "danger");
  assert.equal(items.Disputed.tone, "warning");
  assert.equal(items.Cleared.value, 0);
  assert.equal(ofType(tree, "StatStripNote").length, 1);
  assert.match(textOf(ofType(tree, "StatStripNote")[0]), /As at\s+2026-09-16/);
});
