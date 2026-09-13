import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";

const exports = {};
const code = ts.transpileModule(readFileSync(new URL("../src/components/projects/land/presentation.ts", import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
runInNewContext(`(function(exports) { ${code}\n})`)(exports);
test("land measurements preserve exact significant digits and source units", () => {
  assert.equal(exports.measurement("15218.0000", "sqm"), "15,218 sqm");
  assert.equal(exports.measurement("9007199254740993.000001", "sqft"), "9,007,199,254,740,993.000001 sqft");
  assert.equal(exports.measurement("0.0000", "sqm"), "0 sqm");
  assert.equal(exports.measurement(null, "sqm"), "Not recorded");
  assert.equal(exports.measurement("survey pending"), "survey pending");
});
