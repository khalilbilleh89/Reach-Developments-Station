import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);

/**
 * The monthly count series, drawn (design system A1).
 *
 * The structural guards prove the plot takes counts and nothing else. They
 * cannot tell whether a year of positive months still opens an empty band
 * under the axis, whether a zero is a tick or a bar, whether a one-unit bar
 * keeps a positive height, or whether the detail behind a period is reachable
 * from the whole slot rather than the bar alone. That is what these are for.
 *
 * `hovered` stands in for the pointer: the component keeps the hovered index
 * in state, so the test seeds that state instead of dispatching events.
 */
function mount(props, hovered = null) {
  const react = { useState: (initial) => [hovered ?? initial, () => {}] };
  const source = readFileSync(new URL("../src/components/ui/CountVisuals.tsx", import.meta.url), "utf8");
  const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const exports = {};
  runInNewContext(`(function(require,exports){${code}\n})`)((key) => (key === "react" ? react : require(key)), exports);
  return exports.CountSeries(props);
}

const nodes = (tree) => {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children)];
};
const withClass = (tree, name) =>
  nodes(tree).filter((node) => typeof node.props?.className === "string" && node.props.className.split(" ").includes(name));
const svgOf = (tree) => nodes(tree).find((node) => node.type === "svg");
const viewBoxHeight = (tree) => Number(svgOf(tree).props.viewBox.split(" ")[3]);
const textOf = (tree) => {
  if (tree == null || typeof tree === "boolean") return "";
  if (typeof tree !== "object") return String(tree);
  if (Array.isArray(tree)) return tree.map(textOf).join(" ");
  return textOf(tree.props?.children);
};

/** The plot's fixed geometry, as the component declares it. */
const REACH = 120;
const TOP = 10;
const FOOT = 22;

const series = (counts, detail, hovered = null) =>
  mount({ label: "Monthly net sales activity", note: "Units", rows: counts.map((count, index) => ({ label: `M${index + 1}`, count, detail })) }, hovered);

test("a year of positive months has no empty band beneath the axis", () => {
  const tree = series([0, 0, 0, 4]);
  const baseline = withClass(tree, "count-zero")[0].props.y1;

  assert.equal(baseline, TOP + REACH, "the baseline sits exactly one reach below the top");
  assert.equal(viewBoxHeight(tree), baseline + FOOT, "and the period labels sit directly beneath it");
  assert.deepEqual(withClass(tree, "count-period").map((label) => label.props.y), Array(4).fill(baseline + 16));
  assert.equal(withClass(tree, "count-grid").length, 2, "hairlines at the largest count and its half, none below");
  assert.deepEqual(withClass(tree, "count-axis").map(textOf), ["4", "2", "0"]);
});

test("a zero is a faint tick on the baseline, not a bar and not a printed figure", () => {
  const tree = series([0, 0, 3]);
  assert.equal(withClass(tree, "count-tick").length, 2);
  assert.equal(withClass(tree, "count-bar").length, 1);
  assert.deepEqual(withClass(tree, "count-value").map(textOf), ["3"], "only the non-zero count is labelled on the plot");
  // textOf joins sibling children with a space, so the count and its unit arrive separated by two.
  assert.match(textOf(tree), /0\s+units.*0\s+units.*3\s+units/, "every count, zeros included, is still printed as text");
});

test("a negative month opens the half below the baseline, and only then", () => {
  const tree = series([2, -1, 0]);
  const baseline = withClass(tree, "count-zero")[0].props.y1;
  const negative = withClass(tree, "count-bar-negative");

  assert.equal(negative.length, 1);
  assert.equal(negative[0].type, "rect");
  assert.equal(negative[0].props.y, baseline, "it hangs from the baseline");
  assert.equal(negative[0].props.height, REACH / 2);
  assert.equal(withClass(tree, "count-grid").length, 3, "hairlines at the extent and half above, and the extent below");
  assert.deepEqual(withClass(tree, "count-axis").map(textOf), ["2", "1", "-2", "0"]);
  assert.equal(viewBoxHeight(tree), baseline + REACH + FOOT);
});

test("a bar shorter than its corner radius keeps a positive height and ends on the baseline", () => {
  const tree = series([100, 1]);
  const baseline = withClass(tree, "count-zero")[0].props.y1;
  const bars = withClass(tree, "count-bar");
  assert.equal(bars.length, 2);
  assert.ok(bars[1].props.height > 0 && bars[1].props.height < bars[1].props.rx, "the one-unit bar is thinner than its rounding");
  assert.equal(bars[1].props.y + bars[1].props.height, baseline, "and still rises from the baseline, never below it");
  assert.equal(bars[0].props.y, baseline - REACH);
});

test("the latest active period is the one drawn in gold", () => {
  const tree = series([3, 5, 0, 0]);
  const latest = withClass(tree, "count-bar-latest");
  assert.equal(latest.length, 1);
  assert.equal(withClass(tree, "count-bar")[1], latest[0], "the trailing zeros do not take the highlight");
});

test("the detail behind a period is reached from the whole slot, and named in the tip", () => {
  const detail = "4 activations, 0 cancellations";
  const quiet = series([4, 2], detail);
  assert.equal(withClass(quiet, "count-hit").length, 2, "each slot is a hover target, not the bar alone");
  assert.equal(withClass(quiet, "count-hit")[0].props.height, viewBoxHeight(quiet), "the target spans the plot's full height");
  assert.equal(textOf(withClass(quiet, "count-tip")[0]).trim(), "", "nothing is shown until a period is pointed at");

  const pointed = series([4, 2], detail, 0);
  const tip = withClass(pointed, "count-tip-shown");
  assert.equal(tip.length, 1);
  assert.match(textOf(tip[0]), /4\s+units/);
  assert.match(textOf(tip[0]), /M1/);
  assert.match(textOf(tip[0]), new RegExp(detail));
  assert.equal(withClass(pointed, "count-bar-hover").length, 1, "and the pointed bar answers in the accent");
});
