import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);
const source = readFileSync(new URL("../src/components/projects/ProjectEdit.tsx", import.meta.url), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
const exports = {};
runInNewContext(`(function(require,exports){${code}\n})`)(name => {
  if (name === "./projectStatus") return { PROJECT_STATUSES: ["setup", "active", "completed"], projectStatusLabel: value => value };
  if (name.startsWith("@/") || name === "./EditForm") return {};
  return require(name);
}, exports);
const project = { status: "setup", country_pack_id: "existing", base_currency_id: "existing", reporting_currency_id: "existing" };
const packs = [{ id: "existing", name: "Original", country_code: "JO", is_active: false }, { id: "new", name: "New", country_code: "CY", is_active: true }];
const currencies = [{ id: "existing", code: "JOD", name: "Dinar", is_active: false }, { id: "new", code: "EUR", name: "Euro", is_active: true }];
test("setup editor exposes all creation inputs and preserves existing inactive selections", () => {
  const fields = exports.projectFields(project, packs, currencies);
  const names = fields.filter(f => f.visible !== false).map(f => f.name);
  for (const name of ["code", "name", "developer_entity", "status", "project_type_code", "country_pack_id", "base_currency_id", "reporting_currency_id", "fiscal_year_start_month", "city", "location", "latitude", "longitude", "planned_start", "planned_completion"]) assert.ok(names.includes(name), name);
  for (const name of ["country_pack_id", "base_currency_id", "reporting_currency_id"]) assert.equal(fields.find(f => f.name === name).options[0].value, "existing");
});
test("operational editor keeps editable identity and excludes locked basis and setup transition", () => {
  const fields = exports.projectFields({ ...project, status: "active" }, packs, currencies);
  assert.ok(fields.find(f => f.name === "code"));
  for (const name of ["country_pack_id", "base_currency_id", "reporting_currency_id"]) assert.equal(fields.find(f => f.name === name).visible, false);
  assert.ok(!fields.find(f => f.name === "status").options.some(o => o.value === "setup"));
});
