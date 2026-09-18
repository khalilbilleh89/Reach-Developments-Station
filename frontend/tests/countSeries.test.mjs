import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);

/**
 * The monthly count series, drawn.
 *
 * The structural guards prove the plot takes counts and nothing else. They
 * cannot tell whether a year of positive months still opens an empty band
 * under the axis, whether a zero is a tick or a bar, or whether a bar shorter
 * than its own rounded cap is drawn inside out. That is what these are for.
 */
function mount(props) {
  const react = { useState: (initial) => [initial, () => {}] };
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
const textOf = (tree) => {
  if (tree == null || typeof tree === "boolean") return "";
  if (typeof tree !== "object") return String(tree);
  if (Array.isArray(tree)) return tree.map(textOf).join(" ");
  return textOf(tree.props?.children);
};

const series = (counts, detail) =>
  mount({ label: "Monthly net sales activity", note: "Units", rows: counts.map((count, index) => ({ label: `M${index + 1}`, count, detail })) });

test("a year of positive months has no empty band beneath the axis", () => {
  const tree = series([0, 0, 0, 4]);
  const svg = svgOf(tree);
  const baseline = withClass(tree, "count-zero")[0].props.y1;

  assert.equal(baseline, 22 + 96, "the baseline sits below the reach of the largest bar");
  assert.equal(svg.props.height, baseline + 32, "and the period labels sit directly beneath it");
  assert.deepEqual(withClass(tree, "count-period").map((label) => label.props.y), [baseline + 24, baseline + 24, baseline + 24, baseline + 24]);
  assert.equal(withClass(tree, "count-grid").length, 1, "one hairline, at the largest count");
  assert.deepEqual(withClass(tree, "count-axis").map(textOf), ["4", "0"]);
});

test("a zero is a tick on the baseline with its count printed quietly, not a bar", () => {
  const tree = series([0, 0, 3]);
  assert.equal(withClass(tree, "count-tick").length, 2);
  assert.equal(withClass(tree, "count-bar").length, 1);
  assert.deepEqual(withClass(tree, "count-value-zero").map(textOf), ["0", "0"]);
  // textOf joins sibling children with a space, so the count and its unit arrive separated by two.
  assert.match(textOf(tree), /3\s+units/, "every count is also printed as text");
});

test("a negative month opens the half below the baseline, and only then", () => {
  const tree = series([2, -1, 0]);
  const baseline = withClass(tree, "count-zero")[0].props.y1;
  const negative = withClass(tree, "count-bar-negative");

  assert.equal(negative.length, 1);
  assert.match(negative[0].props.d, /a4,4 0 0 0/, "the cap is rounded on the way down");
  assert.equal(withClass(tree, "count-grid").length, 2, "a hairline at the extent above and below");
  assert.equal(svgOf(tree).props.height, baseline + 96 + 18 + 32);
});

test("a bar shorter than its cap is drawn square rather than inside out", () => {
  const tree = series([100, 1]);
  const bars = withClass(tree, "count-bar");
  assert.equal(bars[0].type, "path", "the tall bar carries a rounded cap");
  assert.equal(bars[1].type, "rect", "the one-unit bar does not");
  assert.ok(bars[1].props.height > 0 && bars[1].props.height < 4);
});

test("the caption offers the detail behind a period without a tooltip gating it", () => {
  const tree = series([4], "4 activations, 0 cancellations");
  assert.match(textOf(withClass(tree, "count-hover")[0]), /Hover a period/);
  assert.equal(withClass(tree, "count-hit").length, 1, "the whole slot is the hover target, not the bar alone");
});
