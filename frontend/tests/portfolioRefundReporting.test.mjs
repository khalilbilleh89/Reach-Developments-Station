import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
const source = path => readFileSync(new URL(path, import.meta.url), "utf8");
const labels = {};
const code = ts.transpileModule(source("../src/components/portfolio/metricLabels.ts"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
runInNewContext(`(function(require,exports){${code}\n})`)(require, labels);

test("live and legacy monetary facts retain distinct, honest labels", () => {
  for (const [code, expected] of Object.entries({
    contracted_value: "Active contracted value",
    confirmed_receipts: "Confirmed receipts",
    refund_due: "Refund due",
    refund_confirmed: "Refund paid",
    refund_outstanding: "Refund still to pay",
    refunds: "Confirmed refunds (legacy)",
  })) assert.equal(labels.metricLabel(code), expected);
  const live = source("../src/components/portfolio/Portfolio.tsx");
  const frozen = source("../src/components/portfolio/ReportingDocument.tsx");
  assert.match(live, /Cancelled sales/);
  assert.match(live, /title="Refund position"/);
  assert.match(frozen, /metricLabel\(m\.metric_code\)/);
  assert.match(frozen, /\["Refunds",\["refunds","refund_due","refund_confirmed","refund_outstanding"\]\]/);
  assert.match(frozen, /m\.prior_availability === "absent" \? "Not captured"/);
  assert.match(frozen, /p\.cancelled_sales !== null && p\.cancelled_sales !== undefined/);
  assert.doesNotMatch(live + frozen, /parseFloat|Number\(.*refund|refund_due\s*-/);
});
