import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);

/**
 * The overview's commercial band and standing grid, rendered.
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

const nodes = (tree) => {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children)];
};
const textOf = (tree) => {
  if (tree == null || typeof tree === "boolean") return "";
  if (typeof tree !== "object") return String(tree);
  if (Array.isArray(tree)) return tree.map(textOf).join(" ");
  return textOf(tree.props?.children);
};
const withClass = (tree, name) =>
  nodes(tree).filter((node) => typeof node.props?.className === "string" && node.props.className.split(" ").includes(name));

const format = { money: (value, code) => (value === null || value === undefined ? "—" : code ? `${code} ${value}` : String(value)), businessDate: (value) => value };

const register = (over = {}) => ({
  units: [], total: 50, sold_count: 0, reserved_count: 0, available_count: 50, held_count: 0, unreleased_count: 0, ...over,
});

function selling(props) {
  return mount("SellingPosition", "SellingPosition", { "@/lib/format": format }, {
    units: null, deals: null, cash: null, currencyCode: "CYP", onNavigate() {}, ...props,
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

test("two collection currencies are never added together", () => {
  // Adding CYP to EUR would be the first lie on the page. The band says so and
  // sends the reader to the module that shows each currency on its own.
  const tree = selling({
    units: register(),
    cash: { as_of: "2026-09-16", accounts: 4, accounts_overdue: 1, accounts_disputed: 0, accounts_cleared: 0, currencies: [
      { currency_id: "CYP", accounts: 2, outstanding_total: "100.00", due_total: "10.00", overdue_total: "5.00", unapplied_cash: "0", confirmed_receipts_total: "90.00", buckets: {} },
      { currency_id: "EUR", accounts: 2, outstanding_total: "200.00", due_total: "20.00", overdue_total: "6.00", unapplied_cash: "0", confirmed_receipts_total: "180.00", buckets: {} },
    ] },
  });

  const figures = withClass(tree, "selling-money-figure").map(textOf);
  assert.deepEqual(figures, ["Several currencies", "Several currencies", "Several currencies"]);
  assert.doesNotMatch(textOf(tree), /270|30\.00|11\.00/, "no total is invented across the two purses");
});

test("one collection currency is shown with its own code, not the project's base", () => {
  const tree = selling({
    units: register(),
    currencyCode: "CYP",
    cash: { as_of: "2026-09-16", accounts: 2, accounts_overdue: 1, accounts_disputed: 0, accounts_cleared: 0, currencies: [
      { currency_id: "EUR", accounts: 2, outstanding_total: "200.00", due_total: "20.00", overdue_total: "6.00", unapplied_cash: "0", confirmed_receipts_total: "180.00", buckets: {} },
    ] },
  });

  assert.deepEqual(withClass(tree, "selling-money-figure").map(textOf), ["EUR 180.00", "EUR 20.00", "EUR 6.00"]);
});

test("a sales register spanning currencies states no contracted total", () => {
  const mixed = selling({ units: register(), deals: { units: 50, contracted_value: "999.00", currency_id: null, mixed_currency: true } });
  assert.match(textOf(withClass(mixed, "selling-figure")[0]), /Several currencies/);
  assert.doesNotMatch(textOf(withClass(mixed, "selling-figure")[0]), /999/);

  const single = selling({ units: register({ sold_count: 3 }), deals: { units: 50, contracted_value: "727431.69", currency_id: "c", mixed_currency: false } });
  assert.equal(textOf(withClass(single, "selling-figure")[0]), "CYP 727431.69");
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
